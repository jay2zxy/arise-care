"""Speaker clustering for streaming sessions.

Per-utterance ECAPA-TDNN embedding (pyannote/embedding, 192-dim). During
streaming we only store embeddings; clustering is deferred to the end of the
session, where one-shot agglomerative clustering yields cleaner groupings than
greedy online merging on short natural-speech segments.
"""
import os
import threading

import numpy as np
import torch
from pyannote.audio import Inference, Model

MIN_DURATION = 0.5
EMBEDDING_SR = 16000
# Cosine distance threshold for offline agglomerative reclustering on stop.
# distance = 1 - cos_sim; 0.7 means clusters merge while avg pairwise cos > 0.3.
# Tuned from 0.6 -> 0.7 because typical therapy session has 2-3 acoustically distinct
# speakers; over-splitting one person is the common failure mode, under-merging is rare.
FINAL_DISTANCE_THRESHOLD = 0.7

_embedder: Inference | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Inference:
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                token = os.getenv("HF_TOKEN")
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                try:
                    model = Model.from_pretrained("pyannote/embedding", token=token)
                except TypeError:
                    # pyannote < 4.0 used use_auth_token
                    model = Model.from_pretrained("pyannote/embedding", use_auth_token=token)
                _embedder = Inference(model, window="whole", device=device)
    return _embedder


def embed(waveform: np.ndarray, sample_rate: int = EMBEDDING_SR) -> np.ndarray:
    """waveform: 1D float32 in [-1, 1]. Returns L2-normalized 192-d embedding."""
    inf = get_embedder()
    wf = waveform[np.newaxis, :] if waveform.ndim == 1 else waveform
    tensor = torch.from_numpy(wf.astype(np.float32))
    out = inf({"waveform": tensor, "sample_rate": sample_rate})
    arr = np.asarray(out.data if hasattr(out, "data") else out).flatten()
    return arr / (np.linalg.norm(arr) + 1e-8)


class SpeakerClusterer:
    """Collects per-utterance embeddings; one-shot agglomerative cluster on stop."""

    def __init__(self):
        self.utterances: list[tuple[int, np.ndarray, float, str]] = []

    def record(self, uid: int, embedding: np.ndarray, duration: float, text: str) -> None:
        self.utterances.append((uid, embedding.copy(), duration, text))

    def final_cluster(
        self, distance_threshold: float = FINAL_DISTANCE_THRESHOLD
    ) -> tuple[dict[int, str], list[dict]]:
        """Run agglomerative clustering on all stored embeddings.

        Returns (relabel: {uid -> 'S1'/'S2'/...}, summary: [...]).
        Cluster ids are renumbered by first-appearance order in time.
        """
        if not self.utterances:
            return {}, []

        embs = np.stack([u[1] for u in self.utterances])
        if len(embs) == 1:
            labels = np.array([0])
        else:
            from sklearn.cluster import AgglomerativeClustering
            try:
                model = AgglomerativeClustering(
                    n_clusters=None,
                    distance_threshold=distance_threshold,
                    metric="cosine",
                    linkage="average",
                )
            except TypeError:
                # sklearn < 1.2 used `affinity`
                model = AgglomerativeClustering(
                    n_clusters=None,
                    distance_threshold=distance_threshold,
                    affinity="cosine",
                    linkage="average",
                )
            labels = model.fit_predict(embs)

        seen: list[int] = []
        for lbl in labels:
            ilbl = int(lbl)
            if ilbl not in seen:
                seen.append(ilbl)
        label_to_sid = {lbl: f"S{i + 1}" for i, lbl in enumerate(seen)}

        relabel: dict[int, str] = {}
        bucket: dict[str, dict] = {}
        for (uid, _emb, dur, text), lbl in zip(self.utterances, labels):
            sid = label_to_sid[int(lbl)]
            relabel[uid] = sid
            b = bucket.setdefault(sid, {"count": 0, "total_seconds": 0.0, "samples": []})
            b["count"] += 1
            b["total_seconds"] += dur
            if text and len(b["samples"]) < 3:
                b["samples"].append(text)

        summary = [
            {
                "id": sid,
                "count": b["count"],
                "total_seconds": round(b["total_seconds"], 2),
                "samples": b["samples"],
            }
            for sid, b in bucket.items()
        ]
        print(f"[cluster] offline recluster: {len(self.utterances)} utterances -> {len(summary)} clusters")
        return relabel, summary
