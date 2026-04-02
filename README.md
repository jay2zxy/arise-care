# Arise Care

Automated fidelity assessment system for strategy training in rehabilitation.

Analyzes rehabilitation session recordings to evaluate how therapists deliver verbal cues — classifying each utterance as **DIRECTED**, **GUIDED**, or **NONE**.

## Pipeline

```
Audio Upload → Whisper (ASR) → pyannote (Speaker Diarization)
    → Identify Therapist Speech → Classify Each Utterance
    → Generate Fidelity Report
```

1. **Transcription** — Upload session audio, transcribed locally via faster-whisper
2. **Speaker Diarization** — Separate therapist vs patient speech (pyannote)
3. **Classification** — Classify each therapist utterance:
   - **DIRECTED**: Explicit commands or demonstrations ("Raise your left arm")
   - **GUIDED**: Questions or prompts encouraging patient problem-solving ("What do you think you should do next?")
   - **NONE**: Casual conversation, observations, explanations ("Your session went well today")
4. **Fidelity Report** — Counts, percentages, and timeline of cue types per session

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python + FastAPI |
| ASR | faster-whisper (Whisper small, CPU) |
| Diarization | pyannote.audio + PyAV |
| Classification | Ollama API (fine-tuned Qwen2.5-7B) |
| Frontend | HTML / CSS / JS |

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up .env (for speaker diarization)
echo "HF_TOKEN=your_huggingface_token" > .env

# 4. Start Ollama with classification model
ollama serve
# (in another terminal) ollama run qwen-bala

# 5. Start the app
uvicorn app.main:app --reload
# http://localhost:8000
```

## API

```
POST /api/classify
Body: { "text": "therapist utterance" }
Response: { "input": "...", "classification": "DIRECTED|GUIDED|NONE" }

POST /api/transcribe?diarize=false
Body: multipart/form-data, file=audio
Response: { "segments": [...], "speakers": [...] }
```

## License

Proprietary. All rights reserved.
