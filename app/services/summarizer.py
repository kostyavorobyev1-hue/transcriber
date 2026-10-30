from __future__ import annotations
import logging
from pathlib import Path

import requests

from ..core.config import settings
from ..core.templates import protocol_prompt

logger = logging.getLogger(__name__)

INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
# Перегрузка или временный сбой модели — пробуем следующую из списка
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
TIMEOUT_SECONDS = 300


class SummaryError(RuntimeError):
    pass


def build_input(transcript: str) -> str:
    return (
        f"{protocol_prompt()}\n\n"
        "Ответ — только протокол по структуре выше, без вступления и заключения. "
        "Он сохраняется в .txt, поэтому пиши простым текстом без Markdown: без #, ** и таблиц; "
        "заголовки разделов — строкой «1. Карточка встречи», пункты списков — через «- ».\n\n"
        "## ТРАНСКРИПТ\n"
        "Каждая строка начинается с тайм-кода [чч:мм:сс] от начала записи.\n\n"
        f"{transcript}"
    )


def _extract_text(data: dict) -> str:
    parts = [
        c.get("text", "")
        for step in data.get("steps", [])
        if step.get("type") == "model_output"
        for c in step.get("content", [])
    ]
    return "".join(parts).strip()


def summarize(transcript: str) -> str:
    """Протокол встречи по шаблону через Gemini Interactions API. Возвращает Markdown."""
    if not settings.gemini_api_key:
        raise SummaryError("Не задан GEMINI_API_KEY (файл .env.local в корне проекта).")

    payload_input = build_input(transcript)
    errors = []
    for model in settings.gemini_models:
        try:
            resp = requests.post(
                INTERACTIONS_URL,
                headers={"x-goog-api-key": settings.gemini_api_key},
                json={"model": model, "input": payload_input},
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            logger.warning(f"Gemini {model}: сетевая ошибка {e}")
            errors.append(f"{model}: {type(e).__name__}")
            continue

        if resp.status_code in RETRYABLE_STATUS:
            logger.warning(f"Gemini {model}: HTTP {resp.status_code}, пробую следующую модель")
            errors.append(f"{model}: HTTP {resp.status_code}")
            continue
        if resp.status_code != 200:
            try:
                message = resp.json().get("error", {}).get("message", "")
            except ValueError:
                message = resp.text[:200]
            raise SummaryError(f"Gemini {model}: HTTP {resp.status_code} {message}".strip())

        text = _extract_text(resp.json())
        if not text:
            errors.append(f"{model}: пустой ответ")
            continue
        logger.info(f"protocol: model={model} chars={len(text)}")
        return text

    raise SummaryError("Gemini сейчас недоступен, попробуйте позже. " + "; ".join(errors))


def write_protocol(transcript_path: Path) -> Path:
    """Протокол по расшифровке → protocols/<имя>_protocol.txt.

    Отдельная папка — чтобы протокол не попадал в историю и библиотеку как ещё одна расшифровка (.txt).
    """
    text = summarize(transcript_path.read_text(encoding="utf-8"))
    out_dir = settings.storage_transcriptions / "protocols"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{transcript_path.stem}_protocol.txt"
    out_path.write_text(text + "\n", encoding="utf-8")
    return out_path
