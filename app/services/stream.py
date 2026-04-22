import asyncio
import os
import tempfile
import traceback

import av
from fastapi import WebSocket

from app.services.asr import transcribe
from app.services.classifier import classify


def _audio_duration(path: str) -> float:
    try:
        container = av.open(path)
        duration = float(container.duration) / av.time_base if container.duration else 0.0
        container.close()
        return duration
    except Exception:
        return 0.0


class StreamSession:
    """
    Per-connection streaming state.
    Client sends audio chunks (complete WebM/Opus blobs).
    Server transcribes sync, enqueues utterances, classifier worker
    pushes labels back asynchronously — decoupled from ASR latency.
    """

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.uid = 0
        self.elapsed = 0.0  # running audio-time offset across chunks
        self.queue: asyncio.Queue = asyncio.Queue()
        self.worker: asyncio.Task | None = None
        self.closed = False

    def start(self) -> None:
        self.worker = asyncio.create_task(self._classify_worker())

    async def handle_chunk(self, audio_bytes: bytes) -> None:
        if not audio_bytes:
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        try:
            duration = _audio_duration(tmp.name)
            segments = await asyncio.to_thread(transcribe, tmp.name)

            chunk_start = self.elapsed
            for seg in segments:
                text = (seg.get("text") or "").strip()
                if not text:
                    continue
                self.uid += 1
                uid = self.uid
                await self._send({
                    "type": "utterance",
                    "id": uid,
                    "start": round(chunk_start + seg["start"], 2),
                    "end": round(chunk_start + seg["end"], 2),
                    "text": text,
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

    async def _classify_worker(self) -> None:
        while not self.closed:
            uid, text = await self.queue.get()
            try:
                cls = await asyncio.to_thread(classify, text)
                await self._send({"type": "classification", "id": uid, "cls": cls})
            except Exception as e:
                traceback.print_exc()
                await self._send({"type": "classification", "id": uid, "cls": "ERROR", "error": str(e)})

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
