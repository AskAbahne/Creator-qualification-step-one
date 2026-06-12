"""
Google Sheets-eksport av godkjente creators (spec seksjon 6).

Kolonner:
  Handle | Engagement % | Hovedplattform | Nisje | Land | Dato sjekket

Implementasjon: append til samme ark hver kjøring. Datokolonnen lar deg
filtrere per sesjon. Header-rad opprettes automatisk hvis arket er tomt.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

import gspread
from google.oauth2.service_account import Credentials

from .config import load_config
from .filters import FilterResult

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADER = ["Handle", "Engagement %", "Hovedplattform", "Nisje", "Land", "Dato sjekket"]

LANG_TO_COUNTRY = {
    "no": "Norge",
    "sv": "Sverige",
    "da": "Danmark",
    "en": "Engelsk-talende marked",
}


def _client() -> gspread.Client:
    cfg = load_config()
    creds = Credentials.from_service_account_file(
        cfg["google_sheets_credentials"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def _open_worksheet():
    cfg = load_config()
    gc = _client()
    sh = gc.open_by_key(cfg["google_sheets_id"])
    ws = sh.sheet1
    return ws


def _ensure_header(ws) -> None:
    first_row = ws.row_values(1)
    if first_row != HEADER:
        if not first_row:
            ws.append_row(HEADER, value_input_option="USER_ENTERED")
        elif first_row[: len(HEADER)] != HEADER:
            ws.update("A1", [HEADER])


def _build_row(result: FilterResult) -> list:
    handle_link = f"https://www.instagram.com/{result.handle}/" if result.platform == "instagram" \
        else f"https://www.tiktok.com/@{result.handle}"
    return [
        f'=HYPERLINK("{handle_link}", "@{result.handle}")',
        f"{result.engagement_rate:.2f}%" if result.engagement_rate is not None else "",
        "Instagram" if result.platform == "instagram" else "TikTok",
        result.niche or "",
        LANG_TO_COUNTRY.get(result.language or "", result.language or ""),
        datetime.now(timezone.utc).strftime("%d.%m.%Y"),
    ]


def append_approved(results: Iterable[FilterResult]) -> int:
    """Skriv godkjente creators som nye rader. Returner antall skrevet."""
    rows = [_build_row(r) for r in results if r.passed]
    if not rows:
        return 0
    ws = _open_worksheet()
    _ensure_header(ws)
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return len(rows)


def verify_connection() -> dict:
    """Live-sjekk at vi kan koble til, lese tittel, og at headeren er på plass."""
    ws = _open_worksheet()
    _ensure_header(ws)
    return {
        "spreadsheet_title": ws.spreadsheet.title,
        "worksheet_title": ws.title,
        "row_count": ws.row_count,
        "current_data_rows": len(ws.get_all_values()),
    }
