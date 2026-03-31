# Arise Care

Automated fidelity assessment system for strategy training in rehabilitation.

Automatically identifies **guided**, **directed**, and **none** verbal cues from rehabilitation session recordings using NLP.

## Features

- **Audio Transcription** — Upload audio files, transcribed locally via Whisper
- **Speaker Diarization** — Distinguish therapist vs patient speech
- **Utterance Classification** — Classify each therapist utterance as DIRECTED / GUIDED / NONE
- **Fidelity Report** — Statistics and timeline of cue types

## Tech Stack

- **Backend**: Python + FastAPI
- **Classification**: llama-cpp-python (fine-tuned Qwen2.5-7B, GGUF)
- **ASR**: faster-whisper
- **Diarization**: whisperX + pyannote
- **Frontend**: HTML / CSS / JS

## Quick Start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# http://localhost:8000
```

## License

Proprietary. All rights reserved.
