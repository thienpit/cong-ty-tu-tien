"""watch.py — Theo dõi hoạt động 4 đệ tử theo thời gian thực.

Xem 3 lớp:
1. Log crew (output/crew.log) — đệ tử nào đang nghĩ gì, làm task nào
2. Call log OmniRoute — đệ tử nào đang gọi model nào, kết quả ra sao
3. Ollama ps — model local có đang chạy không

Cách dùng:
    ./.venv/Scripts/python scripts/watch.py            # theo dõi liên tục
    ./.venv/Scripts/python scripts/watch.py --once     # xem 1 lần rồi thoát
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CREW_LOG = BASE / "output" / "crew.log"
OMNI_LOGS = Path(os.path.expanduser("~/.omniroute/call_logs"))


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def tail_crew_log(n: int = 5) -> list[str]:
    if not CREW_LOG.exists():
        return []
    lines = CREW_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()
    return lines[-n:]


def latest_omni_calls(n: int = 6) -> list[str]:
    """Đọc các call log OmniRoute mới nhất."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_dir = OMNI_LOGS / today
    if not day_dir.exists():
        return []
    files = sorted(day_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for f in files[:n]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            rb = d.get("requestBody", {})
            s = d.get("summary", {})
            status = s.get("status") or d.get("error", {}).get("type", "?")
            route = rb.get("model", "?")
            ms = s.get("durationMs")
            out.append(f"{_now()}  ☁️  {route:<40} {status:<4} {ms and str(ms)+'ms' or ''}")
        except Exception:
            pass
    return out


def ollama_status() -> list[str]:
    """Ollama có model nào đang nạp không."""
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=3) as r:
            d = json.loads(r.read())
        if d.get("models"):
            return [
                f"{_now()}  🖥️  local: {m['name']} | VRAM {m.get('size_vram', 0)//1024//1024}MB"
                for m in d["models"]
            ]
        return [f"{_now()}  🖥️  local: (không có model đang nạp)"]
    except Exception:
        return [f"{_now()}  🖥️  local: không kết nối được Ollama"]


def render_once(show_crew: bool = True) -> None:
    print("=" * 70)
    print("🏯 CÔNG TY TU TIÊN — BẢNG GIÁM SÁT", _now())
    print("=" * 70)
    if show_crew:
        crew_lines = tail_crew_log()
        if crew_lines:
            print("\n📜 LOG DÂY CHUYỀN (5 dòng cuối):")
            for l in crew_lines:
                print("  ", l[-160:])
        else:
            print("\n📜 LOG DÂY CHUYỀN: (chưa có — chạy lần đầu mới ghi)")
    print("\n☁️  CALL CLOUD GẦN NHẤT (OmniRoute):")
    for l in latest_omni_calls():
        print("  ", l)
    print("\n🖥️  LOCAL (Ollama):")
    for l in ollama_status():
        print("  ", l)
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="xem 1 lần rồi thoát")
    ap.add_argument("--interval", type=int, default=5)
    args = ap.parse_args()

    if args.once:
        render_once()
        return
    print("Theo dõi liên tục (Ctrl+C để thoát)...")
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            render_once()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nHết theo dõi.")


if __name__ == "__main__":
    main()
