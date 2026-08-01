"""Entrypoint: chạy cả dây chuyền công ty tu tiên.

Cách dùng:
    python -m src.main "Viết kế hoạch marketing cho game Nghịch Hỏa Tinh Đồ"

Mọi output (verbose của agent) được ghi đồng thời ra console + output/crew.log
để xem bằng: python scripts/watch.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.crew import build_crew, build_llms  # noqa: E402


class _Tee:
    """Ghi output ra cả console lẫn file log (flush ngay, để watch.py đọc live)."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._f = open(log_path, "a", encoding="utf-8")

    def write(self, data: str) -> int:
        sys.__stdout__.write(data)
        self._f.write(data)
        self._f.flush()
        return len(data)

    def flush(self) -> None:
        sys.__stdout__.flush()
        self._f.flush()


def main() -> None:
    mission = " ".join(sys.argv[1:]) or "Mở rộng kênh bán hàng online cho shop thời trang"
    print(f"🏯 Giao nhiệm vụ: {mission}\n")

    out_dir = Path(__file__).resolve().parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    sys.stdout = _Tee(out_dir / "crew.log")  # noqa: P103

    llms = build_llms()
    crew = build_crew(mission, llms=llms)
    result = crew.kickoff()
    print("\n" + "=" * 60)
    print("📜 KẾT QUẢ DÂY CHUYỀN:")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
