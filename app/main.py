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


@api.get("/health")
def health():
    """Report whether the currently selected classification backend is ready.

    BERT runs in-process (always ready). For an Ollama model we probe the daemon
    and check the model is actually installed, so the UI can show a truthful
    status dot instead of assuming 'online'.
    """
    model = state.current_model
    if model == state.BERT_MODEL:
        return {"backend": "bert", "model": model, "ollama_up": None, "model_available": True, "ready": True}

    up = False
    present = False
    try:
        res = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if res.status_code == 200:
            up = True
            names = [m["name"] for m in res.json().get("models", [])]
            present = any(n == model or n.split(":")[0] == model for n in names)
    except Exception:
        up = False
    return {"backend": "ollama", "model": model, "ollama_up": up, "model_available": present, "ready": up and present}


app.include_router(api)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")
