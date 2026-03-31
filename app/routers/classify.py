from fastapi import APIRouter
from app.models.schemas import ClassifyRequest, ClassifyResponse
from app.services.classifier import classify

router = APIRouter()


@router.post("/api/classify", response_model=ClassifyResponse)
def classify_utterance(req: ClassifyRequest):
    result = classify(req.text)
    return ClassifyResponse(input=req.text, classification=result)
