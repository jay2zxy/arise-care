# Arise Care

Automated fidelity assessment for strategy training in inpatient rehabilitation. Analyzes rehabilitation session recordings and classifies each therapist utterance as **DIRECTED**, **GUIDED**, or **NONE**.

## Prerequisites

- **Python 3.10** (developed and tested on 3.10.11; newer minors are untested against the pinned torch/pyannote versions)
- **Ollama** — [install](https://ollama.com/download)
- **Classification model** — `qwen_bala_Q5_K_M.gguf` (~5.2 GB) + its `Modelfile`. Not in the repo; get both from the project owner.
- **HuggingFace token** — speaker diarization downloads gated models on first run. Do this once:
  1. Register / log in at [huggingface.co](https://huggingface.co).
  2. While logged in, open each model page and click **Agree** to accept its terms:
     [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) and [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1).
  3. Create a **read** token at [hf.co/settings/tokens](https://huggingface.co/settings/tokens) — you'll paste it into `.env` in the Run step below.

## Run

```bash
git clone https://github.com/PittNAIL/arise-care.git
cd arise-care
python -m venv venv
venv\Scripts\activate                 # macOS/Linux: source venv/bin/activate
python -m pip install --upgrade pip   # pip < 24 OOMs while resolving pyannote deps
pip install -r requirements.txt

echo HF_TOKEN=hf_your_token_here > .env   # replace with your real token from the step above

# Import the classification model (qwen_bala_Q5_K_M.gguf must sit next to the Modelfile)
ollama serve                          # in a separate terminal
ollama create qwen-bala -f Modelfile

uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Usage

- **Text Classify** — type a therapist utterance, press Enter → DIRECTED / GUIDED / NONE.
- **Session Analysis** — upload audio (.m4a/.mp3/.wav/.ogg/.flac), click **Analyze** → transcription + speaker diarization + per-utterance classification + stats. Export as JSON/CSV.
- **History** — past sessions are saved in browser localStorage.
