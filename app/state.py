from config import OLLAMA_MODEL

# Sentinel "model name" that routes classify() to the local BERT instead of
# Ollama. Selectable in the same model picker as the Ollama models.
BERT_MODEL = "bert"

current_model: str = OLLAMA_MODEL
