"""Configuration: env vars + multi-account JSON."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---- Required ----
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "").strip()

# ---- VFS ----
VFS_URL = os.getenv("VFS_URL", "https://visa.vfsglobal.com/aze/en/ita/login").strip()
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "10"))
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# ---- Dashboard ----
DASHBOARD_ENABLED = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8000"))
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "change-me-please")
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "insecure-default-change-me")

# ---- Captcha ----
TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY", "").strip()

# ---- Logging ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "logs/bot.log")

# ---- Paths ----
DB_PATH = os.getenv("DB_PATH", "data/subscribers.db")
ACCOUNTS_FILE = os.getenv("ACCOUNTS_FILE", "accounts.json")
SESSIONS_DIR = "sessions"


@dataclass
class Account:
    name: str
    email: str
    session_path: str
    enabled: bool = True
    notes: str = ""


def load_accounts() -> list[Account]:
    """Load accounts from accounts.json, fall back to a single anonymous account."""
    path = Path(ACCOUNTS_FILE)
    if not path.exists():
        # Allow running with no accounts configured — the checker will warn.
        return []
    try:
        data = json.loads(path.read_text())
        return [Account(**item) for item in data if item.get("enabled", True)]
    except (json.JSONDecodeError, TypeError) as e:
        logging.warning("Failed to parse %s: %s", ACCOUNTS_FILE, e)
        return []


def ensure_dirs() -> None:
    for d in ("data", "logs", SESSIONS_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)


def configure_logging() -> None:
    ensure_dirs()
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        handlers.append(logging.FileHandler(LOG_FILE))
    except OSError:
        pass  # read-only filesystem etc.; stderr is enough
    logging.basicConfig(level=LOG_LEVEL, format=log_format, handlers=handlers)


def validate() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Copy .env.example to .env and fill it in."
        )
    if DASHBOARD_ENABLED and DASHBOARD_SECRET == "insecure-default-change-me":
        logging.warning(
            "DASHBOARD_SECRET is set to the default. Generate one with "
            "`python -c \"import secrets; print(secrets.token_hex(32))\"`."
        )
