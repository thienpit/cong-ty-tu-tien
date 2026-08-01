"""Test nhanh Ollama local — không cần crew, không tốn token cloud."""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
MODEL = os.getenv("LOCAL_MODEL", "qwen3:8b")

if __name__ == "__main__":
    from openai import OpenAI

    client = OpenAI(base_url=BASE_URL, api_key="ollama")
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Chào ngươi, giới thiệu ngươi là ai trong 2 câu."
    print(f"🔌 {BASE_URL} | model: {MODEL}")
    print(f"🗣️  Prompt: {prompt}\n")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
    )
    print("💬", resp.choices[0].message.content)
