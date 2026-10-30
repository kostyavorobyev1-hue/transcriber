"""Автообработка записей Телемоста.

Раз в минуту смотрит в папку записей. Новый файл берётся в работу, когда перестал расти
(Телемост дописывает запись, пока идёт звонок). Результат — расшифровка и протокол
в <папка>/Протоколы, плюс расшифровка в истории приложения и уведомление macOS.

Файлы, которые лежали в папке при первом запуске, не обрабатываются: они сразу
помечаются как просмотренные (state-файл в storage/).
"""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path

from ..core.config import settings
from .file_manager import get_unique_stem, save_transcription
from .summarizer import SummaryError, write_protocol
from .transcriber import transcribe_file

logger = logging.getLogger(__name__)

MEDIA_SUFFIXES = {".webm", ".mp4", ".m4v", ".mkv", ".mp3", ".m4a", ".wav", ".ogg"}
POLL_SECONDS = 60
# Сколько файл должен не меняться, чтобы считать запись законченной
STABLE_SECONDS = 120
OUTPUT_SUBDIR = "Протоколы"


def _state_path() -> Path:
    return settings.storage_transcriptions.parent / "telemost_state.json"


def _load_state() -> dict | None:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _save_state(state: dict) -> None:
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _media_files(folder: Path) -> list[Path]:
    return sorted(
        (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_SUFFIXES),
        key=lambda p: p.stat().st_mtime,
    )


def _notify(title: str, message: str) -> None:
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
    except Exception as e:
        logger.warning(f"telemost: уведомление не показано: {e}")


def _meeting_name(media: Path) -> str:
    """«Встреча в Телемосте 30.10.26 12-59-01 — запись.webm» → «Встреча в Телемосте 30.10.26 12-59-01»."""
    return media.stem.removesuffix(" — запись").strip()


def process_recording(media: Path) -> str:
    """Расшифровка + протокол для одной записи. Возвращает статус для state-файла."""
    name = _meeting_name(media)
    out_dir = settings.telemost_dir / OUTPUT_SUBDIR
    out_dir.mkdir(exist_ok=True)

    logger.info(f"telemost: расшифровываю {media.name}")
    text = transcribe_file(media)
    transcript = save_transcription(text, get_unique_stem(media.name), ".txt")
    (out_dir / f"{name} — расшифровка.txt").write_text(text + "\n", encoding="utf-8")

    try:
        protocol = write_protocol(transcript)
    except SummaryError as e:
        logger.warning(f"telemost: протокол не составлен для {media.name}: {e}")
        _notify("Транскрибатор", f"{name}: расшифровка готова, протокол не составлен")
        return "transcribed"

    (out_dir / f"{name} — протокол.txt").write_text(protocol.read_text(encoding="utf-8"), encoding="utf-8")
    logger.info(f"telemost: готово {media.name}")
    _notify("Транскрибатор", f"{name}: протокол готов (Телемост/{OUTPUT_SUBDIR})")
    return "done"


async def scan_once(state: dict, sizes: dict[str, int]) -> None:
    """Один проход: новые файлы, которые перестали расти, обрабатываются по одному."""
    seen = state["seen"]
    now = time.time()
    for media in _media_files(settings.telemost_dir):
        if media.name in seen:
            continue
        st = media.stat()
        previous = sizes.get(media.name)
        sizes[media.name] = st.st_size
        if previous != st.st_size or now - st.st_mtime < STABLE_SECONDS:
            continue

        try:
            seen[media.name] = await asyncio.to_thread(process_recording, media)
        except Exception as e:
            logger.exception(f"telemost: не удалось обработать {media.name}")
            seen[media.name] = f"failed: {e}"
            _notify("Транскрибатор", f"{_meeting_name(media)}: ошибка расшифровки")
        sizes.pop(media.name, None)
        _save_state(state)


async def watch_forever() -> None:
    state = _load_state()
    if state is None:
        state = {"seen": {p.name: "baseline" for p in _media_files(settings.telemost_dir)}}
        _save_state(state)
        logger.info(f"telemost: первый запуск, старых записей пропущено: {len(state['seen'])}")
    logger.info(f"telemost: слежу за {settings.telemost_dir}")

    sizes: dict[str, int] = {}
    while True:
        try:
            await scan_once(state, sizes)
        except Exception:
            logger.exception("telemost: ошибка прохода")
        await asyncio.sleep(POLL_SECONDS)
