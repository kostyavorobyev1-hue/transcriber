import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

local = TestClient(app, base_url="http://127.0.0.1:8770")


@pytest.mark.parametrize("base_url", ["http://127.0.0.1:8770", "http://localhost:8770"])
def test_local_hosts_allowed(base_url):
    assert TestClient(app, base_url=base_url).get("/health").status_code == 200


def test_foreign_host_rejected():
    # DNS rebinding: чужой домен указывает на 127.0.0.1, браузер шлёт его в Host
    resp = TestClient(app, base_url="http://evil.example.com:8770").get("/history/")
    assert resp.status_code == 403


def test_cross_site_post_rejected():
    resp = local.post("/library/delete", data={"transcription_path": "x"},
                      headers={"Origin": "https://evil.example.com"}, follow_redirects=False)
    assert resp.status_code == 403


def test_opaque_origin_post_rejected():
    resp = local.post("/library/delete", headers={"Origin": "null"}, follow_redirects=False)
    assert resp.status_code == 403


def test_same_origin_post_allowed():
    resp = local.post("/library/delete", data={},
                      headers={"Origin": "http://127.0.0.1:8770"}, follow_redirects=False)
    assert resp.status_code == 303


def test_cross_site_websocket_rejected():
    with pytest.raises(WebSocketDisconnect):
        with local.websocket_connect("/ws/progress/some-task", headers={"Origin": "https://evil.example.com"}):
            pass
