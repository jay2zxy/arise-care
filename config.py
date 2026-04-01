OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen-bala"

TEMPERATURE = 0.1
MAX_TOKENS = 10

SYSTEM_PROMPT = (
    "You are a rehabilitation therapy classifier. "
    "Classify the following therapist utterance as exactly one of: DIRECTED, GUIDED, or NONE. "
    "Reply with only the label, nothing else."
)

# ASR settings
WHISPER_MODEL = "small"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
