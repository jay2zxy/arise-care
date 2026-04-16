import os

try:
    import nvidia.cublas
    _cublas_bin = os.path.join(nvidia.cublas.__path__[0], "bin")
    if os.path.isdir(_cublas_bin):
        os.environ["PATH"] = _cublas_bin + os.pathsep + os.environ.get("PATH", "")
except ImportError:
    pass

import av
import torch
import numpy as np
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
from config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from dotenv import load_dotenv

load_dotenv()

_whisper_model: WhisperModel | None = None
_diarize_pipeline: Pipeline | None = None


def get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
    return _whisper_model


def get_diarize_pipeline() -> Pipeline:
    global _diarize_pipeline
    if _diarize_pipeline is None:
        token = os.getenv("HF_TOKEN")
        _diarize_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", token=token
        )
    return _diarize_pipeline


def load_audio_pyav(audio_path: str) -> tuple[torch.Tensor, int]:
    """Load audio file using PyAV (no system FFmpeg needed)."""
    container = av.open(audio_path)
    stream = container.streams.audio[0]
    frames = []
    for frame in container.decode(audio=0):
        frames.append(frame.to_ndarray())
    container.close()
    audio = np.concatenate(frames, axis=1)
    waveform = torch.from_numpy(audio).float()
    sample_rate = stream.rate
    return waveform, sample_rate


def transcribe(audio_path: str) -> list[dict]:
    model = get_whisper_model()
    segments, info = model.transcribe(audio_path, beam_size=5)

    result = []
    for seg in segments:
        result.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })

    return result


def diarize(audio_path: str) -> list[dict]:
    """Run speaker diarization on audio file."""
    pipeline = get_diarize_pipeline()
    waveform, sample_rate = load_audio_pyav(audio_path)
    result = pipeline({"waveform": waveform, "sample_rate": sample_rate})
    annotation = result.speaker_diarization

    speakers = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        speakers.append({
            "start": round(turn.start, 2),
            "end": round(turn.end, 2),
            "speaker": speaker,
        })

    return speakers


def transcribe_with_diarization(audio_path: str) -> dict:
    """Transcribe audio and assign speakers to each segment."""
    segments = transcribe(audio_path)
    speakers = diarize(audio_path)

    # Assign speaker to each transcription segment by overlap
    for seg in segments:
        seg_mid = (seg["start"] + seg["end"]) / 2
        best_speaker = "UNKNOWN"
        for sp in speakers:
            if sp["start"] <= seg_mid <= sp["end"]:
                best_speaker = sp["speaker"]
                break
        seg["speaker"] = best_speaker

    return {"segments": segments, "speakers": speakers}
