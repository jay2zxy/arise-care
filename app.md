# Arise Care — Application Architecture

## System Overview

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
│  FastAPI Backend                                             │
│                                                              │
│  Routers:                                                    │
│    POST /api/classify      Text → classification label       │
│    POST /api/transcribe    Audio → transcript + speakers     │
│    POST /api/analyze       Audio → full fidelity report      │
│                                                              │
│  Services:                                                   │
│    classifier.py    httpx → Ollama API                       │
│    asr.py           faster-whisper + pyannote.audio          │
│    pipeline.py      ASR → diarize → classify → stats         │
└─────────┬────────────────────────────┬───────────────────────┘
          │                            │
          ▼                            ▼
┌─────────────────────┐  ┌─────────────────────────────────────┐
│  Ollama              │  │  Local Models                       │
│  localhost:11434     │  │  - Whisper small (faster-whisper)   │
│  qwen-bala           │  │  - pyannote segmentation-3.0       │
│  (Qwen2.5-7B Q5_K_M)│  │  - pyannote speaker-diarization    │
└─────────────────────┘  └─────────────────────────────────────┘
```

## Pipeline Flow

```
Audio file (.m4a / .mp3 / .wav)
  │
  ├──► faster-whisper ──► Timestamped transcript
  │                        [{start, end, text}, ...]
  │
  ├──► pyannote.audio ──► Speaker timeline
  │                        [{start, end, speaker}, ...]
  │
  ├──► Midpoint alignment
  │     Assign speaker to each transcript segment
  │
  ├──► Therapist detection
  │     Most frequent speaker = therapist (or manual override)
  │
  ├──► Classify therapist utterances (Ollama → qwen-bala)
  │     Each utterance → DIRECTED | GUIDED | NONE
  │
  └──► Report generation
        Counts, percentages, durations, annotated transcript
```

## Module Responsibilities

```
app/
├── main.py                 App entry point
│                           - Mounts API router (/api prefix)
│                           - Serves static files
│                           - Returns index.html at /
│
├── routers/
│   ├── classify.py         POST /api/classify
│   │                       - Accepts JSON {text}
│   │                       - Returns {classification}
│   │
│   ├── transcribe.py       POST /api/transcribe
│   │                       - Accepts audio file upload
│   │                       - Optional ?diarize=true for speaker labels
│   │                       - Returns {segments, speakers}
│   │
│   └── pipeline.py         POST /api/analyze
│                           - Accepts audio file upload
│                           - Optional ?therapist_speaker=SPEAKER_00
│                           - Runs full pipeline, returns {segments, stats}
│
├── services/
│   ├── classifier.py       Sends utterance to Ollama API
│   │                       - Uses httpx POST to localhost:11434
│   │                       - System prompt constrains output to label only
│   │                       - temperature=0.1, max_tokens=10
│   │
│   ├── asr.py              Audio processing
│   │                       - Whisper: transcribe() → segments with timestamps
│   │                       - pyannote: diarize() → speaker turns
│   │                       - PyAV for audio decoding (no system FFmpeg)
│   │                       - Midpoint matching to assign speakers to segments
│   │
│   └── pipeline.py         Orchestration
│                           - Calls transcribe_with_diarization()
│                           - Detects therapist (most utterances)
│                           - Classifies each therapist segment
│                           - Computes stats (counts, percentages, durations)
│
├── models/
│   └── schemas.py          Pydantic models for request/response validation
│
└── static/
    └── index.html          Single-page frontend
                            - Three-column layout (nav / content / settings)
                            - Three pages: Classify, Analyze, History
                            - localStorage for session and classify history
                            - JSON/CSV export
                            - Responsive with collapsible sidebars
```

## Data Flow

```
                    ┌─────────────┐
                    │ index.html  │
                    └──────┬──────┘
                           │ fetch('/api/analyze', formData)
                           ▼
                    ┌─────────────┐
                    │ pipeline    │ router receives uploaded audio
                    │ router      │ saves to temp file
                    └──────┬──────┘
                           │ run_pipeline(tmp_path)
                           ▼
                    ┌─────────────┐
                    │ pipeline    │ service orchestrates steps
                    │ service     │
                    └──┬─────┬───┘
                       │     │
            ┌──────────┘     └──────────┐
            ▼                           ▼
     ┌─────────────┐            ┌─────────────┐
     │ transcribe  │            │  diarize    │
     │ (whisper)   │            │ (pyannote)  │
     └──────┬──────┘            └──────┬──────┘
            │                          │
            └────────┬─────────────────┘
                     │ merge by midpoint
                     ▼
              ┌─────────────┐
              │  classify   │ for each therapist utterance
              │  (ollama)   │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │   stats     │ counts, percentages, durations
              └──────┬──────┘
                     │
                     ▼
              JSON response → browser renders report
```

## External Dependencies

| Dependency | Role | Size | Required |
|-----------|------|------|----------|
| Ollama | Hosts qwen-bala classification model | ~200 MB installer + 5.2 GB model | Yes |
| HuggingFace Token | Downloads pyannote models on first run | ~20 MB models | Yes (first run only) |
| CUDA 12 | GPU acceleration for faster-whisper | — | Optional (falls back to CPU) |

## Configuration

All tuneable parameters live in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen-bala` | Classification model name |
| `TEMPERATURE` | `0.1` | Low temperature for deterministic classification |
| `MAX_TOKENS` | `10` | Only need a single label |
| `WHISPER_MODEL` | `small` | Whisper model size |
| `WHISPER_DEVICE` | `cpu` | Device for Whisper inference |
| `WHISPER_COMPUTE_TYPE` | `int8` | Quantization for CPU mode |
