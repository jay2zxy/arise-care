import tempfile
import traceback
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from app.models.schemas import TranscribeResponse
from app.services.asr import transcribe

router = APIRouter()


@router.post("/api/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{file.filename.split('.')[-1]}", delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        segments = transcribe(tmp_path)
        return TranscribeResponse(segments=segments)
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
