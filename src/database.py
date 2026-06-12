"""
SQLite-database for deduplisering og prosesseringslogg (spec seksjon 9.1).

Tabell: processed_handles
  handle        TEXT     — @handle uten foran-snabel
  platform      TEXT     — 'instagram' eller 'tiktok'
  checked_at    TEXT     — ISO 8601 timestamp
  result        TEXT     — 'approved' | 'rejected'
  failed_at     TEXT     — Steg-navn (f.eks. '1_follower_count') eller NULL
  reason        TEXT     — Menneskelig forklaring eller NULL
  niche         TEXT     — Matchet nisje eller NULL
  engagement    REAL     — ER % eller NULL
  follower_count INTEGER — eller NULL

  PRIMARY KEY (handle, platform)  -- samme handle kan finnes på begge plattformer
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import DATA_DIR
from .filters import FilterResult

DB_PATH: Path = DATA_DIR / "discovery.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_handles (
    handle         TEXT    NOT NULL,
    platform       TEXT    NOT NULL,
    checked_at     TEXT    NOT NULL,
    result         TEXT    NOT NULL,
    failed_at      TEXT,
    reason         TEXT,
    niche          TEXT,
    engagement     REAL,
    follower_count INTEGER,
    PRIMARY KEY (handle, platform)
);

CREATE INDEX IF NOT EXISTS idx_result   ON processed_handles(result);
CREATE INDEX IF NOT EXISTS idx_niche    ON processed_handles(niche);
CREATE INDEX IF NOT EXISTS idx_checked  ON processed_handles(checked_at);
"""


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def is_processed(handle: str, platform: str, db_path: Path = DB_PATH) -> bool:
    handle = handle.lstrip("@").lower()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_handles WHERE handle = ? AND platform = ?",
            (handle, platform),
        ).fetchone()
    return row is not None


def record_result(result: FilterResult, db_path: Path = DB_PATH) -> None:
    handle = result.handle.lstrip("@").lower()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO processed_handles
              (handle, platform, checked_at, result, failed_at, reason,
               niche, engagement, follower_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handle,
                result.platform,
                datetime.now(timezone.utc).isoformat(),
                "approved" if result.passed else "rejected",
                result.failed_at,
                result.reason,
                result.niche,
                result.engagement_rate,
                result.follower_count,
            ),
        )
        conn.commit()


def filter_unseen(handles: list[str], platform: str, db_path: Path = DB_PATH) -> list[str]:
    """Returner kun handles vi IKKE har sett før — bevarer rekkefølge."""
    if not handles:
        return []
    norm = [h.lstrip("@").lower() for h in handles]
    with _connect(db_path) as conn:
        placeholders = ",".join("?" * len(norm))
        rows = conn.execute(
            f"SELECT handle FROM processed_handles "
            f"WHERE platform = ? AND handle IN ({placeholders})",
            (platform, *norm),
        ).fetchall()
    seen = {r["handle"] for r in rows}
    return [orig for orig, n in zip(handles, norm) if n not in seen]


def get_stats(db_path: Path = DB_PATH) -> dict:
    with _connect(db_path) as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM processed_handles").fetchone()["c"]
        approved = conn.execute(
            "SELECT COUNT(*) AS c FROM processed_handles WHERE result = 'approved'"
        ).fetchone()["c"]
        by_platform = {
            r["platform"]: r["c"]
            for r in conn.execute(
                "SELECT platform, COUNT(*) AS c FROM processed_handles GROUP BY platform"
            )
        }
        by_failure = {
            r["failed_at"]: r["c"]
            for r in conn.execute(
                "SELECT failed_at, COUNT(*) AS c FROM processed_handles "
                "WHERE result = 'rejected' GROUP BY failed_at ORDER BY c DESC"
            )
        }
    return {
        "total": total,
        "approved": approved,
        "rejected": total - approved,
        "by_platform": by_platform,
        "by_failure": by_failure,
    }


def list_approved(db_path: Path = DB_PATH) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT handle, platform, checked_at, niche, engagement, follower_count "
            "FROM processed_handles WHERE result = 'approved' ORDER BY checked_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]
