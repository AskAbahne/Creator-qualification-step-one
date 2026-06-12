import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
SESSIONS_DIR = PROJECT_ROOT / "sessions"
DATA_DIR = PROJECT_ROOT / "data"

_REQUIRED_KEYS = (
    "instagram_username",
    "instagram_password",
    "tiktok_ms_token",
    "google_sheets_credentials",
    "google_sheets_id",
)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json mangler. Forventet sti: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    missing = [k for k in _REQUIRED_KEYS if not cfg.get(k)]
    if missing:
        raise ValueError(f"config.json mangler verdier: {', '.join(missing)}")

    creds_path = Path(cfg["google_sheets_credentials"])
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Service account JSON ikke funnet: {creds_path}"
        )

    SESSIONS_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    return cfg
