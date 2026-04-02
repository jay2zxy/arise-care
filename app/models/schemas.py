from pydantic import BaseModel


class ClassifyRequest(BaseModel):
    text: str


class ClassifyResponse(BaseModel):
    input: str
    classification: str


class TranscribeSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str | None = None


class SpeakerTurn(BaseModel):
    start: float
    end: float
    speaker: str


class TranscribeResponse(BaseModel):
    segments: list[TranscribeSegment]
    speakers: list[SpeakerTurn] | None = None
