import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel

from app.routers import classify, transcribe, pipeline, stream
from app import state

app = FastAPI(title="Arise Care")

api = APIRouter(prefix="/api")
api.include_router(classify.router)
api.include_router(transcribe.router)
api.include_router(pipeline.router)
api.include_router(stream.router)


class ModelChoice(BaseModel):
    model: str


@api.get("/config")
def get_config():
    return {"model": state.current_model}


def _is_cloud_model(name: str) -> bool:
    return name.endswith(":cloud") or name.endswith("-cloud")


@api.post("/config")
def set_config(choice: ModelChoice):
    if _is_cloud_model(choice.model):
        raise HTTPException(
            status_code=400,
            detail="Cloud models are disabled: medical data must not leave this machine",
        )
    state.current_model = choice.model
    return {"model": state.current_model}


@api.get("/models")
def list_models():
    # BERT runs in-process, so it's always available — list it first, even if
    # Ollama is down. Append Ollama models when reachable.
    names = [state.BERT_MODEL]
    try:
        res = httpx.get("http://localhost:11434/api/tags", timeout=5)
        names += [m["name"] for m in res.json().get("models", [])]
    except Exception:
        pass
    return {"models": names}


app.include_router(api)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")
