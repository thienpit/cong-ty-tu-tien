#!/usr/bin/env python3
"""Dashboard server for Công Ty Tu Tiên — multi-agent monitoring."""

import http.server
import socketserver
import json
import os
import sys
import datetime
import base64
import traceback

# ── Config ──────────────────────────────────────────────────────────────────
PORT = 8080
AUTH_USER = "tongchu"
AUTH_PASS = "thienlun1603"
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

AGENTS = ["hermes", "agent1", "agent2", "ollama"]
OLLAMA_URL = "http://localhost:11434"
OLLAMA_LOG_DIR = os.path.join(os.path.expanduser("~"), ".hermes", "logs", "ollama_calls")

# OmniRoute connectionId → agent mapping (populated from logs)
# "noauth" = Hermes (default connection, uses free models)
# Gemini connections = Agent1, NVIDIA/OpenCode connections = Agent2
CONNECTION_MAP = {
    "noauth": "hermes",
    "2a8d00b0-a471-4b1a-ab06-4c0e78d7eb87": "agent1",
    "dd5812fd-0e14-44a1-89b7-22309819fbc6": "agent2",
}

def agent_for(log_data):
    """Map an OmniRoute log entry to an agent key."""
    summary = log_data.get("summary") or {}
    model = (log_data.get("requestBody") or {}).get("model", "").lower()

    # 1. Direct Ollama calls (not through OmniRoute)
    if any(x in model for x in ("qwen", "ollama")):
        return "ollama"

    # 2. Use connectionId for OmniRoute-routed calls
    cid = summary.get("connectionId", "")
    if cid in CONNECTION_MAP:
        return CONNECTION_MAP[cid]

    # 3. Fallback: model name pattern
    if "auto" in model:
        return "hermes"
    if "gemini" in model:
        return "agent1"
    if any(x in model for x in ("opencode", "deepseek", "nvidia", "mistral", "groq")):
        return "agent2"

    return "hermes"  # Default to hermes for auto-routed calls


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def handle_error(self, request, client_address):
        import traceback, sys
        exc = sys.exc_info()[1]
        # Silently ignore client disconnect errors
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError)):
            return
        # Log other errors
        print(f"[ERROR] {client_address}: {exc}")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    # ── Auth ────────────────────────────────────────────────────────────────
    def check_auth(self):
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
            return decoded == f"{AUTH_USER}:{AUTH_PASS}"
        except Exception:
            return False

    def require_auth(self):
        # Skip auth for localhost (Electron app, local browser)
        client = self.client_address[0] if self.client_address else ""
        if client in ("127.0.0.1", "::1", "localhost"):
            return True
        if not self.check_auth():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Dashboard"')
            self.send_header("Content-Type", "text/plain")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(b"401 Unauthorized")
            return False
        return True

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    # ── Ollama proxy ─────────────────────────────────────────────────────────
    def today_ollama_logs(self):
        today = datetime.date.today().isoformat()
        d = os.path.join(OLLAMA_LOG_DIR, today)
        os.makedirs(d, exist_ok=True)
        return d

    def log_ollama_call(self, model, prompt_tokens, completion_tokens, duration_ms):
        """Log an Ollama call for dashboard display."""
        import uuid
        log = {
            "id": str(uuid.uuid4()),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "duration_ms": duration_ms,
            "timestamp": datetime.datetime.now().isoformat(),
            "source": "ollama_local",
        }
        log_path = self.today_ollama_logs()
        fn = os.path.join(log_path, f"{uuid.uuid4().hex[:8]}.json")
        with open(fn, "w") as f:
            json.dump(log, f)

    def proxy_ollama(self, ollama_path):
        """Proxy request to Ollama and log token usage."""
        import urllib.request as ur
        import time

        body = None
        if self.command == "POST":
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                body = self.rfile.read(length)

        url = f"{OLLAMA_URL}{ollama_path}"
        req = ur.Request(url, data=body, method=self.command)
        req.add_header("Content-Type", "application/json")

        start = time.time()
        try:
            resp = ur.urlopen(req, timeout=300)
            resp_body = resp.read()
            duration_ms = int((time.time() - start) * 1000)

            # Try to extract token info from response
            try:
                data = json.loads(resp_body)
                model = data.get("model", "unknown")
                prompt_n = data.get("prompt_eval_count", 0)
                compl_n = data.get("eval_count", 0)
                if prompt_n > 0 or compl_n > 0:
                    self.log_ollama_call(model, prompt_n, compl_n, duration_ms)
            except Exception:
                pass

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp_body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp_body)
        except Exception as e:
            error_body = json.dumps({"error": str(e)}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(error_body)))
            self.end_headers()
            self.wfile.write(error_body)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path.startswith("/ollama/"):
            ollama_path = path[len("/ollama"):]  # /api/chat -> /api/chat
            self.proxy_ollama(ollama_path)
        else:
            self.send_error(404)

    # ── Routing ─────────────────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if not self.require_auth():
            return
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            self.handle_api(path)
        else:
            if path == "/":
                path = "/index.html"
            self.path = path
            filepath = os.path.join(DIRECTORY, path.lstrip("/"))
            if os.path.isfile(filepath):
                super().do_GET()
            else:
                self.send_error(404)

    def handle_api(self, path):
        try:
            if path == "/api/agents":
                self.send_json(self.api_agents())
            elif path == "/api/system":
                self.send_json(self.api_system())
            elif path == "/api/tokens":
                self.send_json(self.api_tokens())
            elif path == "/api/crew":
                self.send_json(self.api_crew())
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            traceback.print_exc()
            self.send_json({"error": str(e)}, 500)

    def send_json(self, data, status=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            pass

    # ── API: /api/agents ────────────────────────────────────────────────────
    def api_agents(self):
        log_path = self.today_logs()
        stats = {a: {"calls": 0, "tokens": 0, "errors": 0} for a in AGENTS}

        if os.path.isdir(log_path):
            for fn in os.listdir(log_path):
                if not fn.endswith(".json"):
                    continue
                try:
                    data = self._load_log(log_path, fn)
                    if not data:
                        continue
                    a = agent_for(data)
                    stats[a]["calls"] += 1
                    tk = (data.get("summary") or {}).get("tokens") or {}
                    stats[a]["tokens"] += tk.get("in", 0) + tk.get("out", 0)
                    st = str((data.get("summary") or {}).get("status", ""))
                    if st.startswith("5") or st == "error":
                        stats[a]["errors"] += 1
                except Exception:
                    pass

        # Crew status from OmniRoute logs (use last call time per agent)
        crew_status = {a: {"status": "idle", "last_active": None} for a in AGENTS}
        if os.path.isdir(log_path):
            files = sorted(
                [f for f in os.listdir(log_path) if f.endswith(".json")],
                reverse=True,
            )[:50]
            for fn in files:
                try:
                    data = self._load_log(log_path, fn)
                    if not data:
                        continue
                    a = agent_for(data)
                    ts = (data.get("summary") or {}).get("timestamp", "")
                    if ts:
                        # Parse ISO timestamp to epoch
                        try:
                            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            epoch = dt.timestamp()
                            if crew_status[a]["last_active"] is None or epoch > crew_status[a]["last_active"]:
                                crew_status[a]["last_active"] = epoch
                                crew_status[a]["status"] = "active"
                        except Exception:
                            pass
                except Exception:
                    pass

        # Add Ollama local tokens to stats
        ollama_log_path = os.path.join(OLLAMA_LOG_DIR, datetime.date.today().isoformat())
        if os.path.isdir(ollama_log_path):
            for fn in os.listdir(ollama_log_path):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(ollama_log_path, fn)) as f:
                        odata = json.load(f)
                    stats["ollama"]["tokens"] += odata.get("total_tokens", 0)
                    stats["ollama"]["calls"] += 1
                except Exception:
                    pass

        return {
            "agents": stats,
            "crew": crew_status,
            "models": self.model_breakdown(log_path),
        }

    # ── API: /api/system ────────────────────────────────────────────────────
    def api_system(self):
        try:
            import psutil
        except ImportError:
            psutil = None

        cpu = mem = disk = 0
        if psutil:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage(os.path.expanduser("~")).percent

        # VRAM via nvidia-smi
        vram = None
        try:
            import subprocess
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                vram = float(r.stdout.strip().split("\n")[0])
        except Exception:
            pass

        ollama_models = []
        try:
            import urllib.request as ur
            resp = ur.urlopen("http://localhost:11434/api/tags", timeout=3)
            data = json.loads(resp.read())
            ollama_models = [m.get("name", "") for m in data.get("models", [])]
        except Exception:
            pass

        return {
            "cpu": round(cpu, 1),
            "memory": round(mem, 1),
            "disk": round(disk, 1),
            "vram": round(vram, 1) if vram is not None else None,
            "ollama_models": ollama_models,
        }

    # ── API: /api/tokens ────────────────────────────────────────────────────
    def api_tokens(self):
        log_path = self.today_logs()
        by_agent = {a: 0 for a in AGENTS}
        by_model = {}
        total = 0

        if os.path.isdir(log_path):
            for fn in os.listdir(log_path):
                if not fn.endswith(".json"):
                    continue
                try:
                    data = self._load_log(log_path, fn)
                    if not data:
                        continue
                    tk = (data.get("summary") or {}).get("tokens") or {}
                    t = tk.get("in", 0) + tk.get("out", 0)
                    if t <= 0:
                        continue
                    model = (data.get("requestBody") or {}).get("model", "unknown")
                    a = agent_for(data)
                    by_agent[a] += t
                    by_model[model] = by_model.get(model, 0) + t
                    total += t
                except Exception:
                    pass

        # Count Ollama local tokens
        ollama_path = os.path.join(OLLAMA_LOG_DIR, datetime.date.today().isoformat())
        ollama_tokens = 0
        if os.path.isdir(ollama_path):
            for fn in os.listdir(ollama_path):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(ollama_path, fn)) as f:
                        data = json.load(f)
                    ollama_tokens += data.get("total_tokens", 0)
                except Exception:
                    pass
        by_agent["ollama"] = ollama_tokens
        total += ollama_tokens

        return {
            "total_tokens": total,
            "by_agent": by_agent,
            "by_model": by_model,
        }

    # ── API: /api/crew ──────────────────────────────────────────────────────
    def api_crew(self):
        log_path = self.today_logs()
        agents = {a: {"status": "idle", "last_active": None, "task": None} for a in AGENTS}
        tasks_completed = 0

        # Build agent activity from OmniRoute logs
        if os.path.isdir(log_path):
            files = sorted(
                [f for f in os.listdir(log_path) if f.endswith(".json")],
                reverse=True,
            )[:50]
            for fn in files:
                try:
                    data = self._load_log(log_path, fn)
                    if not data:
                        continue
                    a = agent_for(data)
                    summary = data.get("summary") or {}
                    ts = summary.get("timestamp", "")
                    status = str(summary.get("status", ""))
                    if ts:
                        try:
                            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            epoch = dt.timestamp()
                            if agents[a]["last_active"] is None or epoch > agents[a]["last_active"]:
                                agents[a]["last_active"] = epoch
                        except Exception:
                            pass
                    if status.startswith("5") or status == "error":
                        agents[a]["status"] = "error"
                    elif status == "200":
                        agents[a]["status"] = "active"
                except Exception:
                    pass

        # Recent calls
        recent = []
        if os.path.isdir(log_path):
            files = sorted(
                [f for f in os.listdir(log_path) if f.endswith(".json")],
                reverse=True,
            )[:20]
            for fn in files:
                try:
                    data = self._load_log(log_path, fn)
                    if not data:
                        continue
                    summary = data.get("summary") or {}
                    recent.append({
                        "model": (data.get("requestBody") or {}).get("model", "?"),
                        "status": summary.get("status", "?"),
                        "duration": summary.get("duration", 0),
                        "timestamp": summary.get("timestamp", ""),
                        "agent": agent_for(data),
                    })
                except Exception:
                    pass

        return {
            "agents": agents,
            "tasks_completed": tasks_completed,
            "recent_calls": recent,
        }

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _load_log(self, log_path, fn):
        try:
            with open(os.path.join(log_path, fn), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def today_logs(self):
        today = datetime.date.today().strftime("%Y-%m-%d")
        return os.path.expanduser(f"~/.omniroute/call_logs/{today}/")

    def model_breakdown(self, log_path):
        models = {}
        if os.path.isdir(log_path):
            for fn in os.listdir(log_path):
                if not fn.endswith(".json"):
                    continue
                data = self._load_log(log_path, fn)
                if not data:
                    continue
                model = (data.get("requestBody") or {}).get("model", "unknown")
                tk = (data.get("summary") or {}).get("tokens") or {}
                t = tk.get("in", 0) + tk.get("out", 0)
                if model not in models:
                    models[model] = {"calls": 0, "tokens": 0}
                models[model]["calls"] += 1
                models[model]["tokens"] += t
        return models


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.chdir(DIRECTORY)
    with ThreadedHTTPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
        httpd.allow_reuse_address = True
        print(f"🏯 Dashboard running at http://0.0.0.0:{PORT}")
        httpd.serve_forever()
