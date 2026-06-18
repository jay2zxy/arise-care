from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx

from app.models.schemas import ClassifyRequest
from app.services.classifier import classify

router = APIRouter()


@router.post("/classify")
def classify_utterance(req: ClassifyRequest):
    try:
        result = classify(req.text)
        return {"input": req.text, "classification": result}
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
        # Ollama backend is down / unreachable — give the UI an actionable message.
        return JSONResponse(
            status_code=503,
            content={"error": "Ollama not reachable — start it with `ollama serve`, or switch to the BERT model."},
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
