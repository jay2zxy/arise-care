from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.routers import classify, transcribe, pipeline

app = FastAPI(title="Arise Care")

api = APIRouter(prefix="/api")
api.include_router(classify.router)
api.include_router(transcribe.router)
api.include_router(pipeline.router)
app.include_router(api)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index():
    return FileResponse(static_dir / "index.html")
