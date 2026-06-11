import asyncio
import os
import tempfile
import traceback
import wave

import av
import numpy as np
from fastapi import WebSocket

from app.services.asr import transcribe
from app.services.pipeline import run_pipeline

# Mono PCM accumulation rate. 16 kHz is Whisper-native; pyannote resamples
# internally, so one rate serves both the live ASR preview and the final pipeline.
SR = 16000


def _decode_audio(path: str, target_sr: int = SR) -> tuple[np.ndarray, float]:
    """Decode a WebM/Opus chunk to mono float32 [-1, 1] at target_sr.

    Returns (audio, duration_seconds). Empty array on decode failure.
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


def _write_wav(samples: np.ndarray, sr: int, path: str) -> None:
    """Write mono float32 [-1, 1] samples to a 16-bit PCM WAV."""
    pcm16 = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())


class StreamSession:
    """
    Per-connection streaming state.

    During recording each chunk is transcribed for a live text preview and its
    decoded PCM is accumulated. On 'stop' finalize() stitches the full waveform
    into a WAV and runs the offline pipeline (pyannote diarization + classify) —
    the same proven path as /api/analyze — then pushes the final result.

    No online speaker clustering or classification: those are weak on short
    chunk-boundary clips, so all real analysis happens once at the end on the
    complete recording.
    """

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.uid = 0
        self.elapsed = 0.0
        self.closed = False
        self.pcm: list[np.ndarray] = []  # accumulated waveform for the final pipeline

    async def handle_chunk(self, audio_bytes: bytes) -> None:
        if not audio_bytes:
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        tmp.write(audio_bytes)
        tmp.close()

        try:
            audio, duration = await asyncio.to_thread(_decode_audio, tmp.name)
            if audio.size:
                self.pcm.append(audio)
            segments = await asyncio.to_thread(transcribe, tmp.name, vad_filter=True)

            chunk_start = self.elapsed
            for seg in segments:
                text = (seg.get("text") or "").strip()
                if not text:
                    continue
                self.uid += 1
                await self._send({
                    "type": "utterance",
                    "id": self.uid,
                    "start": round(chunk_start + seg["start"], 2),
                    "end": round(chunk_start + seg["end"], 2),
                    "text": text,
                })

            self.elapsed += duration
        except Exception as e:
            traceback.print_exc()
            await self._send({"type": "error", "message": str(e)})
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    async def finalize(self) -> None:
        """Stop: write the full session to WAV, run the offline pipeline, push result."""
        if not self.pcm:
            await self._send({"type": "result", "segments": [], "stats": None})
            return

        loop = asyncio.get_running_loop()

        def progress(msg: str) -> None:
            # Called from the pipeline worker thread; hop back to the event loop.
            asyncio.run_coroutine_threadsafe(
                self._send({"type": "status", "message": msg}), loop
            )

        wav_path = None
        try:
            samples = np.concatenate(self.pcm)
            fd, wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            await asyncio.to_thread(_write_wav, samples, SR, wav_path)
            result = await asyncio.to_thread(run_pipeline, wav_path, None, progress)
            await self._send({
                "type": "result",
                "segments": result["segments"],
                "stats": result["stats"],
            })
        except Exception as e:
            traceback.print_exc()
            await self._send({"type": "error", "message": str(e)})
        finally:
            if wav_path:
                try:
                    os.unlink(wav_path)
                except OSError:
                    pass

    async def _send(self, payload: dict) -> None:
        if self.closed:
            return
        try:
            await self.ws.send_json(payload)
        except Exception:
            self.closed = True

    async def close(self) -> None:
        self.closed = True
