import re
import httpx
from config import OLLAMA_URL, OLLAMA_MODEL, TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT


def classify(text: str) -> str:
    response = httpx.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": MAX_TOKENS,
            },
        },
        timeout=60,
    )
    raw = response.json()["message"]["content"].strip()
    match = re.search(r"DIRECTED|GUIDED|NONE", raw, re.IGNORECASE)
    return match.group(0).upper() if match else raw
