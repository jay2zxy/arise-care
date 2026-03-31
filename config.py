from pathlib import Path

MODEL_PATH = Path(r"C:\Users\del\.ollama\custom\qwen_bala_Q5_K_M.gguf")

# llama-cpp-python settings
N_CTX = 2048
N_GPU_LAYERS = 0  # CPU only; set >0 if GPU available
TEMPERATURE = 0.1
MAX_TOKENS = 10

SYSTEM_PROMPT = (
    "You are a rehabilitation therapy classifier. "
    "Classify the following therapist utterance as exactly one of: DIRECTED, GUIDED, or NONE. "
    "Reply with only the label, nothing else."
)
