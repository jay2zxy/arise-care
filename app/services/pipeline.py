from collections import Counter
from app.services.asr import transcribe_with_diarization
from app.services.classifier import classify


def _detect_therapist(segments: list[dict]) -> str:
    """Pick the speaker with the most utterances as therapist."""
    counts = Counter(
        seg["speaker"] for seg in segments if seg.get("speaker") not in (None, "UNKNOWN")
    )
    if not counts:
        return "SPEAKER_00"
    return counts.most_common(1)[0][0]


def run_pipeline(audio_path: str, therapist_speaker: str | None = None) -> dict:
    """
    Full pipeline: audio → transcribe+diarize → classify therapist utterances → report.
    """
    # Step 1: transcribe + diarize
    asr_result = transcribe_with_diarization(audio_path)
    segments = asr_result["segments"]
    speakers = asr_result["speakers"]

    # Step 2: identify therapist
    if therapist_speaker is None:
        therapist_speaker = _detect_therapist(segments)

    # Step 3: classify therapist utterances
    for seg in segments:
        if seg.get("speaker") == therapist_speaker and seg["text"].strip():
            seg["classification"] = classify(seg["text"])
        else:
            seg["classification"] = None

    # Step 4: compute stats
    therapist_segs = [s for s in segments if s.get("speaker") == therapist_speaker]
    classified = [s for s in therapist_segs if s["classification"] is not None]
    total = len(classified)

    counts = Counter(s["classification"] for s in classified)

    def pct(n):
        return round(n / total * 100, 1) if total > 0 else 0.0

    # speaker durations from diarization timeline
    durations: dict[str, float] = {}
    for sp in speakers:
        spk = sp["speaker"]
        durations[spk] = round(durations.get(spk, 0.0) + (sp["end"] - sp["start"]), 2)

    stats = {
        "therapist_speaker": therapist_speaker,
        "total_therapist_utterances": total,
        "directed": {"count": counts.get("DIRECTED", 0), "percentage": pct(counts.get("DIRECTED", 0))},
        "guided":   {"count": counts.get("GUIDED",   0), "percentage": pct(counts.get("GUIDED",   0))},
        "none":     {"count": counts.get("NONE",     0), "percentage": pct(counts.get("NONE",     0))},
        "speaker_durations": durations,
    }

    return {"segments": segments, "stats": stats}
