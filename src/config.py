import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
SESSIONS_DIR = PROJECT_ROOT / "sessions"
DATA_DIR = PROJECT_ROOT / "data"

_REQUIRED_KEYS = (
    "instagram_accounts",
    "tiktok_ms_token",
    "google_sheets_credentials",
    "google_sheets_id",
)

_REQUIRED_ACCOUNT_KEYS = ("label", "username", "password")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json mangler. Forventet sti: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    missing = [k for k in _REQUIRED_KEYS if cfg.get(k) in (None, "", [])]
    if missing:
        raise ValueError(f"config.json mangler verdier: {', '.join(missing)}")

    accounts = cfg["instagram_accounts"]
    if not isinstance(accounts, list) or not accounts:
        raise ValueError("instagram_accounts må være en ikke-tom liste")
    for i, acc in enumerate(accounts):
        for k in _REQUIRED_ACCOUNT_KEYS:
            if not acc.get(k):
                raise ValueError(
                    f"instagram_accounts[{i}] mangler '{k}'"
                )
        acc.setdefault("warmup_mode", False)
        acc.setdefault("proxy", "")

    creds_path = Path(cfg["google_sheets_credentials"])
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Service account JSON ikke funnet: {creds_path}"
        )

    cfg.setdefault("seed_profiles", {})
    cfg.setdefault("seed_max_per_niche", 15)
    cfg.setdefault("proxy", "")
    cfg.setdefault("tiktok_proxy", "")

    SESSIONS_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    return cfg


def active_accounts(cfg: dict) -> list[dict]:
    """Returner kontoer som ikke er i warmup_mode."""
    return [a for a in cfg["instagram_accounts"] if not a.get("warmup_mode", False)]
