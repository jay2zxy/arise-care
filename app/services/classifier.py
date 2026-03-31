import re
from llama_cpp import Llama
from config import MODEL_PATH, N_CTX, N_GPU_LAYERS, TEMPERATURE, MAX_TOKENS, SYSTEM_PROMPT

_llm: Llama | None = None


def get_llm() -> Llama:
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=N_CTX,
            n_gpu_layers=N_GPU_LAYERS,
            verbose=False,
        )
    return _llm


def classify(text: str) -> str:
    llm = get_llm()
    response = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    raw = response["choices"][0]["message"]["content"].strip()
    match = re.search(r"DIRECTED|GUIDED|NONE", raw, re.IGNORECASE)
    return match.group(0).upper() if match else raw
