from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv
import os

# Define o caminho base do projeto para a raiz subindo dois níveis
BASE_DIR = Path(__file__).resolve().parents[2]

# .env.local — локальные секреты (ключи API), не хранится в git; загружается первым, поэтому важнее .env
load_dotenv(BASE_DIR / ".env.local")
load_dotenv()


class Settings(BaseModel):
    app_name: str = "Transcriber"
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    
    storage_uploads: Path = Path(os.getenv("STORAGE_UPLOADS", str(BASE_DIR / "storage" / "uploads")))
    storage_transcriptions: Path = Path(os.getenv("STORAGE_TRANSCRIPTIONS", str(BASE_DIR / "storage" / "transcriptions")))
    templates_dir: Path = Path(os.getenv("TEMPLATES_DIR", str(BASE_DIR / "app" / "templates")))
    static_dir: Path = Path(os.getenv("STATIC_DIR", str(BASE_DIR / "app" / "static")))
    
    # Whisper Settings
    whisper_model_default: str = os.getenv("WHISPER_MODEL", "base")
    # Transcription Device: 'auto' (prefer GPU), 'cuda' (force GPU), 'cpu' (force CPU)
    transcription_device: str = os.getenv("TRANSCRIPTION_DEVICE", "auto").lower()

    # Gemini (протокол встречи по шаблону): модели пробуются по порядку, следующая — если предыдущая перегружена
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_models: list[str] = [
        m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-3.6-flash,gemini-3.1-flash-lite").split(",") if m.strip()
    ]

    # Автообработка записей Телемоста: новые файлы в папке → расшифровка + протокол в <папка>/Протоколы
    telemost_watch: bool = os.getenv("TELEMOST_WATCH", "true").lower() == "true"
    telemost_dir: Path = Path(os.getenv("TELEMOST_DIR", str(Path.home() / "Documents" / "Телемост")))


settings = Settings()

# Ensure directories exist (apenas se forem locais, se for um storage remoto montado, pode não precisar, mas o código assume local)
# Evitar criar se for um device, por exemplo
if not str(settings.storage_uploads).startswith("/dev"): 
    settings.storage_uploads.mkdir(parents=True, exist_ok=True)
if not str(settings.storage_transcriptions).startswith("/dev"):
    settings.storage_transcriptions.mkdir(parents=True, exist_ok=True)
