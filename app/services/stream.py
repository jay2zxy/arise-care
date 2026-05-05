import asyncio
import os
import tempfile
import traceback

import av
import numpy as np
from fastapi import WebSocket

from app.services.asr import transcribe
from app.services.classifier import classify
from app.services.speaker import EMBEDDING_SR, MIN_DURATION, SpeakerClusterer, embed


def _decode_audio(path: str, target_sr: int = EMBEDDING_SR) -> tuple[np.ndarray, float]:
    """Decode WebM/Opus chunk to mono float32 [-1, 1] at target_sr.

    Returns (audio, duration_seconds). Empty array on decode failure — caller
    treats that as no-speaker-info and emits the utterance with speaker='?'.
    """
    try:
        container = av.open(path)
    except Exception:
        return np.zeros(0, dtype=np.float32), 0.0
    try:
        resampler = av.audio.resampler.AudioResampler(
            format="s16", layout="mono", rate=target_sr
        )
        chunks: list[np.ndarray] = []
        for frame in container.decode(audio=0):
            for r in resampler.resample(frame):
                chunks.append(r.to_ndarray())
    finally:
        container.close()
    if not chunks:
        return np.zeros(0, dtype=np.float32), 0.0
    audio = np.concatenate(chunks, axis=1).flatten().astype(np.float32) / 32768.0
    duration = len(audio) / target_sr
    return audio, duration


class StreamSession:
    """
    Per-connection streaming state.
    Client sends audio chunks (complete WebM/Opus blobs).
    Each chunk: ASR -> per-segment speaker clustering -> enqueue to classifier.
    On 'stop' the route calls finalize() to drain classifications + push summary.
    """

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.uid = 0
        self.elapsed = 0.0
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker: asyncio.Task | None = None
        self.closed = False
        self.clusterer = SpeakerClusterer()

    def start(self) -> None:
        self.worker = asyncio.create_task(self._classify_worker())

    async def handle_chunk(self, audio_bytes: bytes) -> None:
        if not audio_bytes:
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        try:
            audio, duration = await asyncio.to_thread(_decode_audio, tmp.name)
            segments = await asyncio.to_thread(transcribe, tmp.name, vad_filter=True)

            chunk_start = self.elapsed
            for seg in segments:
                text = (seg.get("text") or "").strip()
                if not text:
                    continue
                self.uid += 1
                uid = self.uid

                speaker = await asyncio.to_thread(
                    self._assign_speaker, audio, seg["start"], seg["end"], text, uid
                )

                await self._send({
                    "type": "utterance",
                    "id": uid,
                    "start": round(chunk_start + seg["start"], 2),
                    "end": round(chunk_start + seg["end"], 2),
                    "text": text,
                    "speaker": speaker,
                })
                await self.queue.put((uid, text))

            self.elapsed += duration
        except Exception as e:
            traceback.print_exc()
            await self._send({"type": "error", "message": str(e)})
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def _assign_speaker(self, audio: np.ndarray, start: float, end: float, text: str, uid: int) -> str:
        """Embed and store for offline reclustering. Always returns '?' during streaming.

        The real S1/S2/... labels are assigned in finalize() once the full set of
        embeddings is available — agglomerative clustering on the whole session is
        much cleaner than greedy online merging on short noisy clips.
        """
        duration = end - start
        if duration < MIN_DURATION or audio.size == 0:
            return "?"
        s = max(0, int(start * EMBEDDING_SR))
        e = min(len(audio), int(end * EMBEDDING_SR))
        slice_wf = audio[s:e]
        if slice_wf.size < int(MIN_DURATION * EMBEDDING_SR):
            return "?"
        try:
            emb = embed(slice_wf, EMBEDDING_SR)
            self.clusterer.record(uid, emb, duration, text)
        except Exception:
            traceback.print_exc()
        return "?"

    async def _classify_worker(self) -> None:
        while not self.closed:
            uid, text = await self.queue.get()
            try:
                cls = await asyncio.to_thread(classify, text)
                await self._send({"type": "classification", "id": uid, "cls": cls})
            except Exception as e:
                traceback.print_exc()
                await self._send({"type": "classification", "id": uid, "cls": "ERROR", "error": str(e)})
            finally:
                self.queue.task_done()

    async def finalize(self) -> None:
        """Wait for queue drain, run offline reclustering, push speakers_summary."""
        try:
            await asyncio.wait_for(self.queue.join(), timeout=30.0)
        except asyncio.TimeoutError:
            pass
        try:
            relabel, summary = await asyncio.to_thread(self.clusterer.final_cluster)
        except Exception:
            traceback.print_exc()
            relabel, summary = {}, []
        await self._send({
            "type": "speakers_summary",
            "clusters": summary,
            "relabel": relabel,
        })

    async def _send(self, payload: dict) -> None:
        if self.closed:
            return
        try:
            await self.ws.send_json(payload)
        except Exception:
            self.closed = True

    async def close(self) -> None:
        self.closed = True
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except (asyncio.CancelledError, Exception):
                pass
