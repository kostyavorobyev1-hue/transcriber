import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .core.config import settings
from .core.templates import templates  # Importa templates configurados

# Без этого INFO-сообщения приложения (не uvicorn) не попадают в лог
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

import asyncio  # noqa: E402
from pathlib import Path  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from .services.summarizer import write_protocol, SummaryError  # noqa: E402
from .services.telemost_watcher import watch_forever  # noqa: E402


@app.on_event("startup")
async def start_telemost_watcher():
    if not settings.telemost_watch:
        return
    try:
        next(settings.telemost_dir.iterdir(), None)
    except OSError as e:
        # Папка не найдена или macOS не даёт доступ к ~/Documents (нужен «Полный доступ к диску» для python)
        logging.getLogger(__name__).warning(f"telemost: папка недоступна, автообработка выключена: {e}")
        return
    app.state.telemost_watcher = asyncio.create_task(watch_forever())


@app.get("/download/{filename}")
async def download(filename: str):
    file_path = settings.storage_transcriptions / filename
    return FileResponse(path=str(file_path), filename=filename, media_type="text/plain")


@app.post("/protocol/{filename}")
async def protocol(filename: str):
    """Протокол встречи по шаблону (Gemini) для готовой расшифровки."""
    source = settings.storage_transcriptions / filename
    if Path(filename).name != filename or source.suffix != ".txt" or not source.is_file():
        raise HTTPException(status_code=404, detail="Расшифровка не найдена")

    try:
        out_path = await asyncio.to_thread(write_protocol, source)
    except SummaryError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return FileResponse(path=str(out_path), filename=out_path.name, media_type="text/plain; charset=utf-8")

# Include routers (to be implemented)
from .routers import home, upload, history, websocket, library  # noqa: E402

app.include_router(home.router)
app.include_router(upload.router)
app.include_router(history.router)
app.include_router(websocket.router)
app.include_router(library.router)


@app.get("/health")
async def health():
    return {"status": "ok"}