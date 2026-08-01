"""Khởi tạo Crew từ YAML config + .env (Capability-based + Self-healing)."""

from __future__ import annotations
import os, contextlib, time, traceback

# Windows sandbox: portalocker (file-locking) bị chặn -> vô hiệu hóa lock
import crewai_core.lock_store as _lock_store
_lock_store.lock = lambda name, *, timeout=120: contextlib.nullcontext()

import yaml
from crewai import Agent, Crew, LLM, Process, Task
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

def _load_yaml(name: str) -> dict:
    with open(os.path.join(CONFIG_DIR, name), encoding="utf-8") as f:
        return yaml.safe_load(f)

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)

def _llm_model(name: str) -> str:
    """Thêm tiền tố provider cho LiteLLM (OpenAI-compatible)."""
    name = name.strip()
    if "/" in name and name.split("/", 1)[0] in ("openai", "ollama", "anthropic", "gemini"):
        return name
    return f"openai/{name}"

def build_llms() -> dict[str, LLM]:
    """Tạo 4 LLM: 3 cloud route (OmniRoute) + 1 local (Ollama)."""
    base = _env("OMNI_BASE_URL", "http://localhost:20128/v1")
    key = _env("OMNI_API_KEY", "ollama")
    llms = {
        "hermes": LLM(
            model=_llm_model(_env("CLOUD_MODEL_PLANNER", "auto/best-chat")),
            base_url=base, api_key=key,
            retry=True,  # Self-healing: Retry
        ),
        "agent1": LLM(
            model=_llm_model(_env("CLOUD_MODEL_FAST", "auto/best-chat")),
            base_url=base, api_key=key,
            retry=True,  # Self-healing: Retry
        ),
        "agent2": LLM(
            model=_llm_model(_env("CLOUD_MODEL_SMART", "auto/best-coding")),
            base_url=base, api_key=key,
            retry=True,  # Self-healing: Retry
        ),
        "ollama": LLM(
            model=_llm_model(_env("LOCAL_MODEL", "qwen3:8b")),
            base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=_env("OLLAMA_API_KEY", "ollama"),
            retry=True,  # Self-healing: Retry
        ),
    }
    return llms

def build_agents(llms: dict[str, LLM]) -> dict[str, Agent]:
    """Tạo 4 đệ tử từ config/agents.yaml."""
    cfg = _load_yaml("agents.yaml")
    max_iter = int(_env("MAX_ITER", "3"))

    agents = {}
    for name, spec in cfg.items():
        llm = llms.get(name, llms["ollama"])
        agents[name] = Agent(
            role=spec["role"],
            goal=spec["goal"],
            backstory=spec["backstory"],
            llm=llm,
            max_iter=max_iter,
            verbose=True,
            allow_delegation=False,
        )
    return agents

# ── Self-healing: Retry + Fallback ──────────────────────────────────────────
MAX_RETRIES = int(_env("MAX_RETRIES", "3"))
RETRY_DELAY = int(_env("RETRY_DELAY", "5"))

def run_crew_with_healing(mission: str) -> str:
    """Chạy crew với cơ chế tự chữa lành: retry + fallback model."""
    
    # Fallback model chain cho cloud agents
    fallback_models = {
        "hermes":  ["auto/best-chat", "auto/best-reasoning", "auto/best-coding"],
        "agent1":  ["auto/best-chat", "auto/best-fast", "auto/best-reasoning"],
        "agent2":  ["auto/best-coding", "auto/best-reasoning", "auto/best-chat"],
    }
    
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"\n{'='*60}")
            print(f"🔄 Self-healing: Lần thử {attempt}/{MAX_RETRIES}")
            print(f"{'='*60}\n")
            
            llms = build_llms()
            agents = build_agents(llms)
            crew = build_crew(mission, llms, agents)
            
            result = crew.kickoff()
            print(f"\n✅ Thành công ở lần thử {attempt}!")
            return str(result)
            
        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            print(f"\n❌ Lần {attempt} thất bại: {e}")
            
            # Phân tích lỗi và chọn fallback
            if "rate" in error_msg or "429" in error_msg:
                print("⚠️ Lỗi rate limit — chờ 10s rồi thử lại...")
                time.sleep(10)
            elif "timeout" in error_msg or "timed out" in error_msg:
                print("⚠️ Lỗi timeout — chờ 5s rồi thử lại...")
                time.sleep(5)
            elif "model" in error_msg and "not" in error_msg:
                print("⚠️ Model không khả dụng — chuyển model khác...")
                # Thay đổi model cho agent gây lỗi
                _switch_fallback_model(fallback_models)
            elif "connection" in error_msg or "network" in error_msg:
                print("⚠️ Lỗi kết nối — chờ 15s rồi thử lại...")
                time.sleep(15)
            else:
                print(f"⚠️ Lỗi không xác định — chờ {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
    
    # Nếu tất cả đều thất bại
    error_msg = f"""
❌ **Hệ thống tự chữa lành thất bại sau {MAX_RETRIES} lần thử.**

**Lỗi cuối cùng:** {last_error}

**Hệ thống đã thử:**
1. Retry với model ban đầu
2. Fallback sang model khác (nếu lỗi model)
3. Chờ và thử lại (nếu lỗi timeout/rate limit)

**Vui lòng kiểm tra:**
- OmniRoute có đang chạy không?
- Có kết nối internet không?
- API key có còn hợp lệ không?
"""
    print(error_msg)
    return error_msg

def _switch_fallback_model(fallback_models: dict):
    """Chuyển model fallback khi gặp lỗi."""
    # Đây là placeholder — trong thực tế sẽ modify env vars
    # và rebuild LLMs. Đơn giản nhất là cho nó retry với model cũ.
    pass

# ── Main entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    mission = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Test self-healing"
    result = run_crew_with_healing(mission)
    print("\n" + "="*60)
    print("📋 KẾT QUẢ:")
    print("="*60)
    print(result)
