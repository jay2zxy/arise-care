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
    try:
        res = httpx.get("http://localhost:11434/api/tags", timeout=5)
        tags = res.json().get("models", [])
        names = [m["name"] for m in tags]
        return {"models": names}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}")


app.include_router(api)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")
