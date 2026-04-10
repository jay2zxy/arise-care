import tempfile
import traceback
from fastapi import APIRouter, UploadFile, File, Query
from fastapi.responses import JSONResponse
from app.services.pipeline import run_pipeline

router = APIRouter()


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    therapist_speaker: str | None = Query(None, description="Force therapist speaker label, e.g. SPEAKER_00"),
):
    try:
        suffix = f".{file.filename.rsplit('.', 1)[-1]}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        result = run_pipeline(tmp_path, therapist_speaker=therapist_speaker)
        return result
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
