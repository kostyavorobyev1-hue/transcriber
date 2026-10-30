from unittest.mock import MagicMock, patch

import pytest

from app.services import summarizer
from app.services.summarizer import SummaryError, summarize


def _resp(status, payload=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload or {}
    return r


OK_PAYLOAD = {"steps": [
    {"type": "thought", "content": [{"text": "..."}]},
    {"type": "model_output", "content": [{"text": "### 1. Карточка встречи\n"}, {"text": "- Тема: тест"}]},
]}


@patch.object(summarizer, "settings")
def test_requires_api_key(mock_settings):
    mock_settings.gemini_api_key = ""
    with pytest.raises(SummaryError, match="GEMINI_API_KEY"):
        summarize("[00:00:00] текст")


@patch.object(summarizer.requests, "post")
@patch.object(summarizer, "settings")
def test_falls_back_to_next_model_when_overloaded(mock_settings, mock_post):
    mock_settings.gemini_api_key = "key"
    mock_settings.gemini_models = ["busy-model", "spare-model"]
    mock_post.side_effect = [_resp(503), _resp(200, OK_PAYLOAD)]

    result = summarize("[00:00:00] текст")

    assert result == "### 1. Карточка встречи\n- Тема: тест"
    assert [c.kwargs["json"]["model"] for c in mock_post.call_args_list] == ["busy-model", "spare-model"]
    sent_input = mock_post.call_args.kwargs["json"]["input"]
    assert "## ТРАНСКРИПТ" in sent_input and sent_input.endswith("[00:00:00] текст")


@patch.object(summarizer.requests, "post")
@patch.object(summarizer, "settings")
def test_all_models_unavailable(mock_settings, mock_post):
    mock_settings.gemini_api_key = "key"
    mock_settings.gemini_models = ["a", "b"]
    mock_post.side_effect = [_resp(503), _resp(429)]

    with pytest.raises(SummaryError, match="недоступен"):
        summarize("текст")
