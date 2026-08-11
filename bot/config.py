import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Copy .env.example to .env and fill it in.")

_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {int(x) for x in _admin_ids_raw.replace(" ", "").split(",") if x}

DB_PATH = os.getenv("DB_PATH", "bot.db")
DEFAULT_RATE_LIMIT_SECONDS = float(os.getenv("DEFAULT_RATE_LIMIT_SECONDS", "1.0"))
