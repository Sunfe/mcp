from pathlib import Path

from pydantic import BaseModel
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def resolve_project_path(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path.resolve())


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "MCP Knowledge Server")
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    api_token: str = os.getenv("API_TOKEN", "replace_me")
    raw_dir: str = resolve_project_path(os.getenv("RAW_DIR", "raw"))
    db_path: str = resolve_project_path(os.getenv("DB_PATH", "data/knowledge.db"))
    log_level: str = os.getenv("LOG_LEVEL", "info")
    default_search_limit: int = int(os.getenv("DEFAULT_SEARCH_LIMIT", "5"))
    max_search_limit: int = int(os.getenv("MAX_SEARCH_LIMIT", "20"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "800"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "100"))


settings = Settings()
