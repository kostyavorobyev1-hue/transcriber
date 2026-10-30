"""Защита локального сервиса от чужих сайтов, открытых в том же браузере.

- Host: только 127.0.0.1 / localhost — закрывает DNS rebinding (чужой домен,
  перенаправленный на 127.0.0.1, не прочитает историю и расшифровки).
- Origin: изменяющие запросы (POST и т. п.) и WebSocket — только со своей страницы,
  иначе чужой сайт может отправить форму (удалить файл, потратить лимит Gemini).
"""
from __future__ import annotations

from urllib.parse import urlsplit

from starlette.responses import PlainTextResponse

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _hostname(value: str) -> str:
    return (urlsplit(f"//{value}").hostname or "").lower()


class LocalOnlyMiddleware:
    def __init__(self, app, allowed_hosts: set[str] = ALLOWED_HOSTS):
        self.app = app
        self.allowed_hosts = allowed_hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        if _hostname(headers.get("host", "")) not in self.allowed_hosts:
            return await self._reject(scope, receive, send, "Недопустимый Host")

        needs_origin = scope["type"] == "websocket" or scope["method"] not in SAFE_METHODS
        origin = headers.get("origin")
        # Браузер всегда шлёт Origin для POST с другого сайта и для WebSocket; curl и тесты — нет
        if needs_origin and origin is not None:
            if origin == "null" or _hostname(urlsplit(origin).netloc) not in self.allowed_hosts:
                return await self._reject(scope, receive, send, "Запрос с чужого сайта")

        return await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope, receive, send, reason: str):
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        return await PlainTextResponse(reason, status_code=403)(scope, receive, send)
