from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    telegram_token: str
    db_path: str
    timezone: str
    allowed_user_id: Optional[int]
    webapp_url: str
    export_dir: str
    sync_http_host: str
    sync_http_port: int
    sync_http_token: str


def load_config() -> Config:
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    db_path = os.getenv("DB_PATH", "data/lifeos.db").strip()
    timezone = os.getenv("TIMEZONE", "Europe/Moscow").strip()
    allowed_user_id_raw = os.getenv("ALLOWED_USER_ID", "").strip()
    allowed_user_id = int(allowed_user_id_raw) if allowed_user_id_raw else None
    webapp_url = os.getenv("WEBAPP_URL", "").strip()
    export_dir = os.getenv("EXPORT_DIR", "exports").strip()
    sync_http_host = os.getenv("SYNC_HTTP_HOST", "0.0.0.0").strip() or "0.0.0.0"
    sync_http_port_raw = os.getenv("SYNC_HTTP_PORT", "8088").strip()
    sync_http_port = int(sync_http_port_raw) if sync_http_port_raw else 8088
    sync_http_token = os.getenv("SYNC_HTTP_TOKEN", "").strip()

    missing = [name for name, value in {"TELEGRAM_BOT_TOKEN": telegram_token}.items() if not value]
    if missing:
        raise ValueError(f"Missing env vars: {', '.join(missing)}")

    return Config(
        telegram_token=telegram_token,
        db_path=db_path,
        timezone=timezone,
        allowed_user_id=allowed_user_id,
        webapp_url=webapp_url,
        export_dir=export_dir,
        sync_http_host=sync_http_host,
        sync_http_port=sync_http_port,
        sync_http_token=sync_http_token,
    )
