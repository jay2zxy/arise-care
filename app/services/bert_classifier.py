"""BERT cue classifier — in-process inference, no Ollama/HTTP.

⚠️ The team's saved config.json only has generic LABEL_0/1/2, and the mapping
in their training script (Bert2026.py: {'NONE':0,'GUIDED':1,'DIRECTED':2}) does
NOT match this checkpoint. The real mapping was recovered empirically from the
human annotations in test/3001_PT_(a)_transcript.txt_court.xml (see
test/bert_verify.py): DIRECTED cues land on idx1 (24/28), GUIDED on idx0 (9/9,
zero leakage) — clean separation, so:
    idx0 = GUIDED, idx1 = DIRECTED, idx2 = NONE
idx2=NONE is inferred (that gold file has no NONE cues) — CONFIRM with the team.
"""
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_DIR = "BERT_finetuned_final"
ID2LABEL = {0: "GUIDED", 1: "DIRECTED", 2: "NONE"}

_device = "cuda" if torch.cuda.is_available() else "cpu"
_tok = None
_model = None


def load(model_dir: str = MODEL_DIR):
    """Lazy singleton load; model + tokenizer stay resident after first call."""
    global _tok, _model
    if _model is None:
        _tok = AutoTokenizer.from_pretrained(model_dir)
        _model = (
            AutoModelForSequenceClassification.from_pretrained(model_dir)
            .to(_device)
            .eval()
        )
    return _tok, _model


@torch.inference_mode()
def classify(text: str) -> str:
    tok, model = load()
    enc = tok(text, truncation=True, max_length=512, return_tensors="pt").to(_device)
    idx = int(model(**enc).logits.argmax(-1))
    return ID2LABEL[idx]
