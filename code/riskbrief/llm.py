"""Small Ollama client: one chat call with fixed settings, returns the text and run statistics."""
import json
import os
import re
import time
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("RISKBRIEF_MODEL", "qwen2.5:7b")
SETTINGS = {"temperature": 0, "seed": 42, "num_ctx": 8192}


def chat(system: str, user: str, fmt=None, options=None) -> dict:
    body = {"model": MODEL, "stream": False, "options": {**SETTINGS, **(options or {})},
            "messages": ([{"role": "system", "content": system}] if system else []) +
                        [{"role": "user", "content": user}]}
    if fmt is not None:
        body["format"] = fmt
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        out = json.loads(r.read())
    return {"text": out["message"]["content"], "seconds": round(time.time() - t0, 2),
            "prompt_tokens": out.get("prompt_eval_count"), "output_tokens": out.get("eval_count"),
            "model": out.get("model"), "options": body["options"], "format": "schema" if isinstance(fmt, dict)
            else fmt}


def model_digest() -> str:
    with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=10) as r:
        for m in json.loads(r.read())["models"]:
            if m["name"] == MODEL:
                return m["digest"][:12]
    return "unknown"


def parse_json(text: str):
    """Parse model output as JSON. Code fences are removed first (and reported)."""
    t = text.strip()
    fenced = False
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if m:
        t, fenced = m.group(1), True
    try:
        return json.loads(t), fenced, None
    except json.JSONDecodeError as e:
        return None, fenced, str(e)
