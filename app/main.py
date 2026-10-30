from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .core.config import settings
from .core.templates import templates  # Importa templates configurados

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

import asyncio  # noqa: E402
from pathlib import Path  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from .services.summarizer import summarize, SummaryError  # noqa: E402


@app.get("/download/{filename}")
async def download(filename: str):
    file_path = settings.storage_transcriptions / filename
    return FileResponse(path=str(file_path), filename=filename, media_type="text/plain")


@app.post("/protocol/{filename}")
async def protocol(filename: str):
    """Протокол встречи по шаблону (Gemini) для готовой расшифровки; сохраняется в protocols/<имя>_protocol.txt.

    Отдельная папка — чтобы протокол не попадал в историю и библиотеку как ещё одна расшифровка (.txt).
    """
    source = settings.storage_transcriptions / filename
    if Path(filename).name != filename or source.suffix != ".txt" or not source.is_file():
        raise HTTPException(status_code=404, detail="Расшифровка не найдена")

    try:
        text = await asyncio.to_thread(summarize, source.read_text(encoding="utf-8"))
    except SummaryError as e:
        raise HTTPException(status_code=502, detail=str(e))

    out_dir = settings.storage_transcriptions / "protocols"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{source.stem}_protocol.txt"
    out_path.write_text(text + "\n", encoding="utf-8")
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