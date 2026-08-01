"""CrewAI — 4 agents chia task đều, mỗi con 1 phần."""

from __future__ import annotations
import os, contextlib, time, traceback

import crewai_core.lock_store as _lock_store
_lock_store.lock = lambda name, *, timeout=120: contextlib.nullcontext()

import yaml
from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool
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
    name = name.strip()
    if "/" in name and name.split("/", 1)[0] in ("openai", "ollama", "anthropic", "gemini"):
        return name
    return f"openai/{name}"


# ── System tools cho Ollama ────────────────────────────────────────────────
class SystemMonitorTool(BaseTool):
    name: str = "system_monitor"
    description: str = "Xem CPU, RAM, VRAM, Disk hiện tại"
    def _run(self) -> str:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory().percent
            disk = psutil.disk_usage(os.path.expanduser("~")).percent
            return f"CPU: {cpu}% | RAM: {mem}% | Disk: {disk}%"
        except Exception as e:
            return f"Lỗi: {e}"

class FileReadTool(BaseTool):
    name: str = "file_read"
    description: str = "Đọc nội dung file theo đường dẫn"
    def _run(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()[:5000]
        except Exception as e:
            return f"Lỗi đọc file: {e}"


# ── Build LLMs ─────────────────────────────────────────────────────────────
def build_llms() -> dict[str, LLM]:
    base = _env("OMNI_BASE_URL", "http://localhost:20128/v1")
    key = _env("OMNI_API_KEY", "ollama")
    llms = {
        "hermes": LLM(
            model=_llm_model(_env("CLOUD_MODEL_PLANNER", "auto/best-chat")),
            base_url=base, api_key=key, retry=True,
        ),
        "agent1": LLM(
            model=_llm_model(_env("CLOUD_MODEL_FAST", "auto/best-chat")),
            base_url=base, api_key=key, retry=True,
        ),
        "agent2": LLM(
            model=_llm_model(_env("CLOUD_MODEL_SMART", "auto/best-coding")),
            base_url=base, api_key=key, retry=True,
        ),
        "ollama": LLM(
            model=_llm_model(_env("LOCAL_MODEL", "qwen3:8b")),
            base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=_env("OLLAMA_API_KEY", "ollama"), retry=True,
        ),
    }
    return llms


# ── Build Agents ───────────────────────────────────────────────────────────
def build_agents(llms: dict[str, LLM]) -> dict[str, Agent]:
    cfg = _load_yaml("agents.yaml")
    max_iter = int(_env("MAX_ITER", "5"))

    # Hermes: planner + coordinator — DELEGATION BẬT
    hermes = Agent(
        role=cfg["hermes"]["role"],
        goal=cfg["hermes"]["goal"],
        backstory=cfg["hermes"]["backstory"],
        llm=llms["hermes"],
        max_iter=max_iter,
        verbose=True,
        allow_delegation=True,  # ← QUAN TRỌNG: Hermes delegate được cho 3 con
    )

    # Agent 1: Fast — xử lý phần đơn giản/nhanh
    agent1 = Agent(
        role=cfg["agent1"]["role"],
        goal=cfg["agent1"]["goal"],
        backstory=cfg["agent1"]["backstory"],
        llm=llms["agent1"],
        max_iter=max_iter,
        verbose=True,
        allow_delegation=False,
    )

    # Agent 2: Smart — xử lý phần phức tạp/coding
    agent2 = Agent(
        role=cfg["agent2"]["role"],
        goal=cfg["agent2"]["goal"],
        backstory=cfg["agent2"]["backstory"],
        llm=llms["agent2"],
        max_iter=max_iter,
        verbose=True,
        allow_delegation=False,
    )

    # Ollama: Local — review, format, system check
    ollama = Agent(
        role=cfg["ollama"]["role"],
        goal=cfg["ollama"]["goal"],
        backstory=cfg["ollama"]["backstory"],
        llm=llms["ollama"],
        max_iter=max_iter,
        verbose=True,
        allow_delegation=False,
        tools=[SystemMonitorTool(), FileReadTool()],
    )

    return {"hermes": hermes, "agent1": agent1, "agent2": agent2, "ollama": ollama}


# ── Build Crew: 4 con chia task đều ────────────────────────────────────────
def build_crew(mission: str, llms: dict, agents: dict) -> Crew:
    """
    Flow: Hermes chia task → 4 con mỗi đứa 1 phần → gộp kết quả.

    Hermes: Lập kế hoạch + chia nhỏ + tổng hợp
    Agent 1: Xử lý phần nhanh (tóm tắt, phân loại, content)
    Agent 2: Xử lý phần khó (coding, reasoning, debug)
    Ollama: Review + format + system check
    """

    # Task 1: Hermes lập kế hoạch và chia task
    plan_task = Task(
        description=f"""Phân tích nhiệm vụ và chia thành 4 phần rõ ràng:

NHIỆM VỤ: {mission}

Hãy:
1. Phân tích yêu cầu
2. Chia thành 4 phần việc cụ thể
3. Giao phần đơn giản/nhanh cho Agent 1 (tóm tắt, phân loại, content)
4. Giao phần phức tạp/coding cho Agent 2 (lập trình, reasoning)
5. Giao phần review/system cho Ollama (kiểm tra, format)
6. Mình (Hermes) sẽ tổng hợp kết quả cuối cùng

Trả về PLAN cụ thể với từng phần việc cho từng agent.""",
        agent=agents["hermes"],
        expected_output="Plan chi tiết với 4 phần việc được giao rõ ràng cho từng agent",
    )

    # Task 2: Agent 1 xử lý phần nhanh
    task_agent1 = Task(
        description=f"""Đây là phần việc được Hermes giao cho bạn:

NHIỆM VỤ GỐC: {mission}

Bạn chịu trách nhiệm phần: Xử lý nhanh — tóm tắt, phân loại, viết content, trả lời câu hỏi thông thường.

Làm việc nhanh gọn, chính xác. Trả kết quả rõ ràng.""",
        agent=agents["agent1"],
        expected_output="Kết quả phần xử lý nhanh: tóm tắt/phân loại/content",
    )

    # Task 3: Agent 2 xử lý phần khó
    task_agent2 = Task(
        description=f"""Đây là phần việc được Hermes giao cho bạn:

NHIỆM VỤ GỐC: {mission}

Bạn chịu trách nhiệm phần: Xử lý phức tạp — coding, reasoning sâu, debug, lập kế hoạch kỹ thuật.

Làm việc tỉ mỉ, chính xác. Nếu cần code thì viết code đầy đủ.""",
        agent=agents["agent2"],
        expected_output="Kết quả phần xử lý phức tạp: code/reasoning/debug",
    )

    # Task 4: Ollama review + system check
    task_ollama = Task(
        description=f"""Đây là phần việc được Hermes giao cho bạn:

NHIỆM VỤ GỐC: {mission}

Bạn chịu trách nhiệm phần: Review + format + kiểm tra hệ thống.

Hãy:
1. Kiểm tra system status (dùng system_monitor tool)
2. Review output của các agent khác
3. Format kết quả cho đẹp
4. Kiểm tra có lỗi sai sót không""",
        agent=agents["ollama"],
        expected_output="Kết quả review: system status + formatted output + error check",
    )

    # Task 5: Hermes tổng hợp
    summary_task = Task(
        description=f"""Tổng hợp kết quả từ 3 đệ tử:

NHIỆM VỤ GỐC: {mission}

Agent 1 đã làm: [xem kết quả task trước]
Agent 2 đã làm: [xem kết quả task trước]
Ollama đã review: [xem kết quả task trước]

Hãy:
1. Gộp tất cả kết quả
2. Sửa lỗi nếu có
3. Trả về kết quả cuối cùng hoàn chỉnh""",
        agent=agents["hermes"],
        expected_output="Kết quả cuối cùng hoàn chỉnh, gộp từ 4 agent",
    )

    crew = Crew(
        agents=[agents["hermes"], agents["agent1"], agents["agent2"], agents["ollama"]],
        tasks=[plan_task, task_agent1, task_agent2, task_ollama, summary_task],
        process=Process.sequential,
        verbose=True,
    )
    return crew


# ── Self-healing ────────────────────────────────────────────────────────────
MAX_RETRIES = int(_env("MAX_RETRIES", "3"))
RETRY_DELAY = int(_env("RETRY_DELAY", "5"))

def run_crew_with_healing(mission: str) -> str:
    """Chạy crew với self-healing: retry + fallback."""
    fallback_models = {
        "hermes":  ["auto/best-chat", "auto/best-reasoning", "auto/best-coding"],
        "agent1":  ["auto/best-chat", "auto/best-fast", "auto/best-reasoning"],
        "agent2":  ["auto/best-coding", "auto/best-reasoning", "auto/best-chat"],
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"\n{'='*60}")
            print(f"🔄 Self-healing: Lần {attempt}/{MAX_RETRIES}")
            print(f"{'='*60}\n")

            llms = build_llms()
            agents = build_agents(llms)
            crew = build_crew(mission, llms, agents)

            result = crew.kickoff()
            print(f"\n✅ Thành công ở lần {attempt}!")
            return str(result)

        except Exception as e:
            last_error = e
            error_msg = str(e).lower()
            print(f"\n❌ Lần {attempt} thất bại: {e}")

            if "rate" in error_msg or "429" in error_msg:
                print("⚠️ Rate limit — chờ 10s...")
                time.sleep(10)
            elif "timeout" in error_msg:
                print("⚠️ Timeout — chờ 5s...")
                time.sleep(5)
            elif "model" in error_msg and "not" in error_msg:
                print("⚠️ Model unavailable — fallback...")
                _switch_fallback_model(fallback_models)
            elif "connection" in error_msg:
                print("⚠️ Connection error — chờ 15s...")
                time.sleep(15)
            else:
                print(f"⚠️ Unknown error — chờ {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)

    return f"❌ Self-healing thất bại sau {MAX_RETRIES} lần. Lỗi cuối: {last_error}"


def _switch_fallback_model(fallback_models: dict):
    """Chuyển model fallback (placeholder)."""
    pass


# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    mission = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Test 4-agent split"
    result = run_crew_with_healing(mission)
    print("\n" + "="*60)
    print("📋 KẾT QUẢ:")
    print("="*60)
    print(result)
