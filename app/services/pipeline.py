import time
from collections import Counter
from app.services.asr import transcribe, diarize
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
    total_start = time.perf_counter()

    # Step 1a: ASR
    t0 = time.perf_counter()
    segments = transcribe(audio_path)
    t_asr = time.perf_counter() - t0
    print(f"[pipeline] ASR: {t_asr:.1f}s ({len(segments)} segments)")

    # Step 1b: diarization
    t0 = time.perf_counter()
    speakers = diarize(audio_path)
    t_diar = time.perf_counter() - t0
    print(f"[pipeline] Diarization: {t_diar:.1f}s ({len(speakers)} speaker turns)")

    # Assign speakers to each segment by max overlap
    for seg in segments:
        overlap: dict[str, float] = {}
        for sp in speakers:
            o = max(0.0, min(seg["end"], sp["end"]) - max(seg["start"], sp["start"]))
            if o > 0:
                overlap[sp["speaker"]] = overlap.get(sp["speaker"], 0.0) + o
        seg["speaker"] = max(overlap, key=overlap.get) if overlap else "UNKNOWN"

    # Step 2: identify therapist
    if therapist_speaker is None:
        therapist_speaker = _detect_therapist(segments)

    # Step 3: classify therapist utterances
    t0 = time.perf_counter()
    classified_count = 0
    for seg in segments:
        if seg.get("speaker") == therapist_speaker and seg["text"].strip():
            seg["classification"] = classify(seg["text"])
            classified_count += 1
        else:
            seg["classification"] = None
    t_clf = time.perf_counter() - t0
    print(f"[pipeline] Classify: {t_clf:.1f}s ({classified_count} utterances)")

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

    t_total = time.perf_counter() - total_start
    print(f"[pipeline] Total: {t_total:.1f}s")

    stats = {
        "therapist_speaker": therapist_speaker,
        "total_therapist_utterances": total,
        "directed": {"count": counts.get("DIRECTED", 0), "percentage": pct(counts.get("DIRECTED", 0))},
        "guided":   {"count": counts.get("GUIDED",   0), "percentage": pct(counts.get("GUIDED",   0))},
        "none":     {"count": counts.get("NONE",     0), "percentage": pct(counts.get("NONE",     0))},
        "speaker_durations": durations,
        "timings": {
            "asr": round(t_asr, 1),
            "diarization": round(t_diar, 1),
            "classify": round(t_clf, 1),
            "total": round(t_total, 1),
        },
    }

    return {"segments": segments, "stats": stats}
