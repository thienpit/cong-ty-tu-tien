import json, os, datetime
def log_ollama_call(model, prompt_n, compl_n, duration_ms):
    log_path = os.path.join(os.path.dirname(__file__), "logs", "ollama")
    os.makedirs(log_path, exist_ok=True)
    log_file = os.path.join(log_path, f"{datetime.datetime.now().strftime('%Y-%m-%d')}.jsonl")
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "model": model,
        "prompt_tokens": prompt_n,
        "completion_tokens": compl_n,
        "total_tokens": prompt_n + compl_n,
        "duration_ms": duration_ms,
        "source": "ollama_local"
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
