from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    telegram_token: str
    spreadsheet_id: str
    service_account_file: str
    timezone: str
    allowed_user_id: Optional[int]
    daily_max_rows: int = 400
    foodlog_max_rows: int = 2000


def load_config() -> Config:
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip()
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    timezone = os.getenv("TIMEZONE", "Europe/Moscow").strip()
    allowed_user_id_raw = os.getenv("ALLOWED_USER_ID", "").strip()
    allowed_user_id = int(allowed_user_id_raw) if allowed_user_id_raw else None

    missing = [
        name
        for name, value in {
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "GOOGLE_SHEETS_ID": spreadsheet_id,
            "GOOGLE_SERVICE_ACCOUNT_FILE": service_account_file,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing env vars: {', '.join(missing)}")

    return Config(
        telegram_token=telegram_token,
        spreadsheet_id=spreadsheet_id,
        service_account_file=service_account_file,
        timezone=timezone,
        allowed_user_id=allowed_user_id,
    )
