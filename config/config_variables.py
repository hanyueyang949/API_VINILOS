from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

config = dotenv_values(ENV_FILE)

APP_TITLE = config.get("APP_TITLE", "Vinilo API")
APP_VERSION = config.get("APP_VERSION", "1.0.0")
APP_DESCRIPTION = config.get("APP_DESCRIPTION", "REST API for managing Vinilos")
DATABASE_URL = config.get("DATABASE_URL", "sqlite:///./vinilos.db")

CORS_ORIGINS = [
    origin.strip()
    for origin in config.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
