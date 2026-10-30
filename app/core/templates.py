from fastapi.templating import Jinja2Templates
from datetime import datetime
from pathlib import Path
from .config import settings
from .theme import default_theme

PROTOCOL_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "meeting_protocol.md"

# Create a single Jinja2Templates instance
templates = Jinja2Templates(directory=str(settings.templates_dir))

# Register Filters
def timestamp_to_date(timestamp: float) -> str:
    try:
        return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M')
    except Exception:
        return ""

templates.env.filters["timestamp_to_date"] = timestamp_to_date

def protocol_prompt() -> str:
    """Шаблон протокола встречи; читается при каждом рендере, чтобы правки файла подхватывались без перезапуска."""
    try:
        return PROTOCOL_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return ""

# Register Globals
templates.env.globals["theme"] = default_theme()
templates.env.globals["protocol_prompt"] = protocol_prompt
