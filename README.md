# Arise Care

Automated fidelity assessment for strategy training in inpatient rehabilitation. Based on research from the University of Pittsburgh, this tool analyzes rehabilitation session recordings to evaluate therapist verbal cueing patterns — classifying each utterance as **DIRECTED**, **GUIDED**, or **NONE**.

Strategy training emphasizes guided cueing (open-ended questions and prompts) over directed cueing (explicit commands). This tool automates the manual fidelity assessment process, which traditionally requires trained evaluators reviewing session recordings at 1-2 minutes per minute of video.

## Classification Categories

| Category | Description | Example |
|----------|-------------|---------|
| **DIRECTED** | Explicit instructions, commands, or demonstrations telling the patient what to do | "Raise your left arm slowly." |
| **GUIDED** | Open-ended questions or prompts encouraging the patient to think and problem-solve | "What do you think you should do next?" |
| **NONE** | General conversation, observations, or explanations with no instructional intent | "Your session went well today." |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Browser (localhost:8000)                                    │
│  ┌────────────┬──────────────────────┬────────────────────┐  │
│  │  Left Nav   │    Main Content      │   Right Panel      │  │
│  │  - Classify │    - Upload audio    │   - Model info     │  │
│  │  - Analyze  │    - View report     │   - Settings       │  │
│  │  - History  │    - Classify text   │   - Stats summary  │  │
│  └────────────┴──────────────────────┴────────────────────┘  │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼───────────────────────────────────────┐
│  FastAPI Backend (Python)                                    │
│                                                              │
│  Routers:                                                    │
│    POST /api/classify      Text classification               │
│    POST /api/transcribe    Audio transcription                │
│    POST /api/analyze       Full pipeline                     │
│                                                              │
│  Services:                                                   │
│    classifier.py    httpx → Ollama API                       │
│    asr.py           faster-whisper + pyannote.audio          │
│    pipeline.py      Orchestrates: ASR → diarize → classify   │
└─────────┬────────────────────────────┬───────────────────────┘
          │                            │
          ▼                            ▼
┌─────────────────────┐  ┌─────────────────────────────────────┐
│  Ollama              │  │  Local Models                       │
│  localhost:11434     │  │  - Whisper small (faster-whisper)   │
│  qwen-bala model     │  │  - pyannote segmentation-3.0       │
│  (Qwen2.5-7B fine-  │  │  - pyannote speaker-diarization    │
│   tuned, Q5_K_M)    │  │                                     │
└─────────────────────┘  └─────────────────────────────────────┘
```

## Pipeline

```
Audio file (.m4a/.mp3/.wav)
  │
  ├──► faster-whisper ──► Timestamped transcript
  │                        [{start, end, text}, ...]
  │
  ├──► pyannote.audio ──► Speaker timeline
  │                        [{start, end, speaker}, ...]
  │
  ├──► Merge (midpoint alignment)
  │     Assign speaker label to each transcript segment
  │
  ├──► Identify therapist (most frequent speaker, or manual override)
  │
  ├──► Classify therapist utterances via Ollama (qwen-bala)
  │     Each utterance → DIRECTED | GUIDED | NONE
  │
  └──► Generate report
        Counts, percentages, speaker durations, full annotated transcript
```

## Project Structure

```
arise-care/
├── app/
│   ├── main.py                 FastAPI entry point, static file serving
│   ├── routers/
│   │   ├── classify.py         POST /api/classify
│   │   ├── transcribe.py       POST /api/transcribe
│   │   └── pipeline.py         POST /api/analyze
│   ├── services/
│   │   ├── classifier.py       Ollama API client (httpx)
│   │   ├── asr.py              Whisper transcription + pyannote diarization
│   │   └── pipeline.py         Pipeline orchestration + stats
│   ├── models/
│   │   └── schemas.py          Pydantic request/response models
│   └── static/
│       └── index.html          Single-page frontend
├── config.py                   Model names, API URLs, inference parameters
├── requirements.txt            Python dependencies
├── legacy/                     Original Node.js prototype (reference only)
└── paper/                      Research papers (not tracked in git)
```

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python 3.11+ / FastAPI / Uvicorn | Async HTTP server |
| Classification | Ollama API → qwen-bala | Fine-tuned Qwen2.5-7B, Q5_K_M quantized (5.2 GB) |
| ASR | faster-whisper (small model) | Local Whisper inference, CPU mode |
| Speaker Diarization | pyannote.audio 4.0 + PyAV | Requires HuggingFace token for model download |
| Frontend | Vanilla HTML / CSS / JS | Three-column layout, localStorage persistence |

## Prerequisites

- **Python 3.11+**
- **Ollama** — [Install Ollama](https://ollama.com/download)
- **HuggingFace account** — Accept model agreements for [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) and [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
- **GPU (optional)** — Ollama uses GPU by default; Whisper and pyannote run on CPU

## Setup

```bash
# Clone the repository
git clone https://github.com/jay2zxy/arise-care.git
cd arise-care

# Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate    # Windows (Git Bash)
# source venv/bin/activate      # macOS / Linux

# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your HuggingFace token:
#   HF_TOKEN=hf_your_token_here

# Import the classification model into Ollama
ollama serve                            # Start Ollama (if not running)
ollama create qwen-bala -f Modelfile    # Import fine-tuned model

# Start the application
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

## Usage

### Text Classification

Navigate to **Text Classify**, type or paste a therapist utterance, and press Enter. The model returns DIRECTED, GUIDED, or NONE. Click the example cards for quick testing.

### Session Analysis

1. Navigate to **Session Analysis**
2. Upload an audio file (supports .m4a, .mp3, .wav, .ogg, .flac)
3. Optionally set the therapist speaker label in the right panel
4. Click **Analyze** — the pipeline runs transcription, diarization, and classification
5. View the annotated transcript with classification badges and speaker durations
6. Export results as JSON or CSV

### History

Analyzed sessions are saved in browser localStorage (up to 20 sessions). Access past reports from the **History** page or the left sidebar.

## API Reference

### Classify Text

```
POST /api/classify
Content-Type: application/json

{ "text": "Please raise your left arm slowly." }

→ { "input": "...", "classification": "DIRECTED" }
```

### Transcribe Audio

```
POST /api/transcribe?diarize=true
Content-Type: multipart/form-data

file: <audio file>

→ {
    "segments": [
      { "start": 0.0, "end": 2.5, "text": "...", "speaker": "SPEAKER_00" }
    ],
    "speakers": [
      { "start": 0.0, "end": 2.5, "speaker": "SPEAKER_00" }
    ]
  }
```

### Full Pipeline

```
POST /api/analyze?therapist_speaker=SPEAKER_00
Content-Type: multipart/form-data

file: <audio file>

→ {
    "segments": [...],
    "stats": {
      "therapist_speaker": "SPEAKER_00",
      "total_therapist_utterances": 15,
      "directed": { "count": 5, "percentage": 33.3 },
      "guided": { "count": 8, "percentage": 53.3 },
      "none": { "count": 2, "percentage": 13.3 },
      "speaker_durations": { "SPEAKER_00": 120.5, "SPEAKER_01": 45.2 }
    }
  }
```

## Known Limitations

- **GPU memory**: Ollama (qwen-bala) uses ~5.2 GB VRAM. Whisper and pyannote run on CPU to avoid contention on 8 GB GPUs.
- **CUDA 12 required** for faster-whisper GPU mode (cublas64_12.dll). Falls back to CPU if unavailable.
- **NONE classification accuracy**: Rehabilitation-related observations may be misclassified as GUIDED due to limited NONE examples in training data.
- **Speaker alignment**: Uses midpoint matching between Whisper segments and pyannote speaker turns. Edge cases with overlapping speech may result in UNKNOWN labels.
- **PyTorch dependency**: pyannote.audio requires PyTorch (~800 MB), which increases the environment size significantly.

## References

- Osterhoudt, H., et al. "Automated Fidelity Assessment for Strategy Training in Inpatient Rehabilitation using Natural Language Processing." AMIA 2023.
- Skidmore, E.R., et al. "Strategy training shows promise for addressing disability in the first 6 months after stroke." Neurorehabilitation and Neural Repair, 2015.

## License

Proprietary. All rights reserved.
