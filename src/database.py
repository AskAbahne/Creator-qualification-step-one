"""
SQLite-database for deduplisering, prosesseringslogg og diagnostikk.

Tabeller:
  processed_handles    — én rad per prosessert creator (med discovery-kilde, sesjon, near-miss osv.)
  sessions             — én rad per sesjon (parametere + totals)
  account_health_events — én rad per kontohelse-hendelse (login, challenge, API-feil, proxy-feil)

PRIMARY KEY på processed_handles (handle, platform) gjør at samme handle på begge
plattformer er separate.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import DATA_DIR
from .filters import FilterResult

DB_PATH: Path = DATA_DIR / "discovery.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_handles (
    handle                 TEXT    NOT NULL,
    platform               TEXT    NOT NULL,
    checked_at             TEXT    NOT NULL,
    result                 TEXT    NOT NULL,
    failed_at              TEXT,
    reason                 TEXT,
    niche                  TEXT,
    niche_bio              TEXT,
    engagement             REAL,
    follower_count         INTEGER,
    avg_views              REAL,
    language               TEXT,
    session_id             INTEGER,
    discovery_source_type  TEXT,
    discovery_source_value TEXT,
    account_used           TEXT,
    time_taken_sec         REAL,
    near_miss              INTEGER DEFAULT 0,
    near_miss_detail       TEXT,
    PRIMARY KEY (handle, platform)
);

CREATE INDEX IF NOT EXISTS idx_result            ON processed_handles(result);
CREATE INDEX IF NOT EXISTS idx_niche             ON processed_handles(niche);
CREATE INDEX IF NOT EXISTS idx_checked           ON processed_handles(checked_at);
CREATE INDEX IF NOT EXISTS idx_session           ON processed_handles(session_id);
CREATE INDEX IF NOT EXISTS idx_discovery_value   ON processed_handles(discovery_source_value);
CREATE INDEX IF NOT EXISTS idx_near_miss         ON processed_handles(near_miss);

CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    ended_at        TEXT,
    platforms       TEXT,
    niches          TEXT,
    max_handles     INTEGER,
    accounts_used   TEXT,
    discovered      INTEGER DEFAULT 0,
    after_dedup     INTEGER DEFAULT 0,
    processed       INTEGER DEFAULT 0,
    approved        INTEGER DEFAULT 0,
    rejected        INTEGER DEFAULT 0,
    completed       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS account_health_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT NOT NULL,
    account      TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    details      TEXT,
    session_id   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_health_account ON account_health_events(account);
CREATE INDEX IF NOT EXISTS idx_health_type    ON account_health_events(event_type);
CREATE INDEX IF NOT EXISTS idx_health_time    ON account_health_events(timestamp);
"""


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate_legacy_columns(conn)
    return conn


def _migrate_legacy_columns(conn: sqlite3.Connection) -> None:
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(processed_handles)")}
    additions = [
        ("niche_bio", "TEXT"),
        ("avg_views", "REAL"),
        ("language", "TEXT"),
        ("session_id", "INTEGER"),
        ("discovery_source_type", "TEXT"),
        ("discovery_source_value", "TEXT"),
        ("account_used", "TEXT"),
        ("time_taken_sec", "REAL"),
        ("near_miss", "INTEGER DEFAULT 0"),
        ("near_miss_detail", "TEXT"),
    ]
    for col, decl in additions:
        if col not in cols:
            conn.execute(f"ALTER TABLE processed_handles ADD COLUMN {col} {decl}")


# ---------- handle-deduplication API (uendret signatur) ----------

def is_processed(handle: str, platform: str, db_path: Path = DB_PATH) -> bool:
    handle = handle.lstrip("@").lower()
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_handles WHERE handle = ? AND platform = ?",
            (handle, platform),
        ).fetchone()
    return row is not None


def filter_unseen(handles: list[str], platform: str, db_path: Path = DB_PATH) -> list[str]:
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


# ---------- record result ----------

def record_result(
    result: FilterResult,
    *,
    session_id: Optional[int] = None,
    discovery_source_type: Optional[str] = None,
    discovery_source_value: Optional[str] = None,
    account_used: Optional[str] = None,
    time_taken_sec: Optional[float] = None,
    near_miss: bool = False,
    near_miss_detail: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> None:
    handle = result.handle.lstrip("@").lower()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO processed_handles
              (handle, platform, checked_at, result, failed_at, reason,
               niche, niche_bio, engagement, follower_count, avg_views, language,
               session_id, discovery_source_type, discovery_source_value,
               account_used, time_taken_sec, near_miss, near_miss_detail)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handle,
                result.platform,
                datetime.now(timezone.utc).isoformat(),
                "approved" if result.passed else "rejected",
                result.failed_at,
                result.reason,
                result.niche,
                result.extras.get("niche_bio") if isinstance(result.extras, dict) else None,
                result.engagement_rate,
                result.follower_count,
                result.avg_views,
                result.language,
                session_id,
                discovery_source_type,
                discovery_source_value,
                account_used,
                time_taken_sec,
                1 if near_miss else 0,
                near_miss_detail,
            ),
        )
        conn.commit()


# ---------- sessions API ----------

def start_session(
    platforms: list[str],
    niches: list[str],
    max_handles: Optional[int],
    accounts_used: list[str],
    db_path: Path = DB_PATH,
) -> int:
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO sessions
              (started_at, platforms, niches, max_handles, accounts_used)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                json.dumps(platforms),
                json.dumps(niches),
                max_handles,
                json.dumps(accounts_used),
            ),
        )
        conn.commit()
        return cur.lastrowid


def finalize_session(
    session_id: int,
    *,
    discovered: int,
    after_dedup: int,
    processed: int,
    approved: int,
    rejected: int,
    db_path: Path = DB_PATH,
) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """
            UPDATE sessions SET
              ended_at = ?, discovered = ?, after_dedup = ?,
              processed = ?, approved = ?, rejected = ?, completed = 1
            WHERE id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                discovered, after_dedup, processed, approved, rejected,
                session_id,
            ),
        )
        conn.commit()


# ---------- account-health API ----------

def log_health_event(
    account: str,
    event_type: str,
    details: Optional[str] = None,
    session_id: Optional[int] = None,
    db_path: Path = DB_PATH,
) -> None:
    """Logg en kontohelse-hendelse.

    event_type: 'login_ok' | 'login_fail' | 'challenge_required'
                | 'api_error' | 'rate_limited' | 'proxy_fail' | 'paused'
    """
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO account_health_events
              (timestamp, account, event_type, details, session_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                account, event_type, details, session_id,
            ),
        )
        conn.commit()


def get_account_health(account: str, db_path: Path = DB_PATH) -> dict:
    """Returner helsestatus for én konto basert på siste 24 timer."""
    from datetime import timedelta

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT event_type, COUNT(*) AS c
            FROM account_health_events
            WHERE account = ? AND timestamp >= ?
            GROUP BY event_type
            """,
            (account, cutoff),
        ).fetchall()
    counts = {r["event_type"]: r["c"] for r in rows}
    challenges = counts.get("challenge_required", 0)
    api_errors = counts.get("api_error", 0)
    login_ok = counts.get("login_ok", 0)
    login_fail = counts.get("login_fail", 0)
    total_calls = login_ok + login_fail + api_errors

    err_rate = (api_errors / total_calls) if total_calls else 0.0

    if challenges >= 3 or err_rate > 0.20:
        status = "red"
        recommendation = "PAUSE umiddelbart"
    elif challenges >= 1 or err_rate > 0.10:
        status = "yellow"
        recommendation = "Reduser volum"
    else:
        status = "green"
        recommendation = "OK å skalere"

    return {
        "account": account,
        "status": status,
        "challenges_24h": challenges,
        "api_errors_24h": api_errors,
        "login_failures_24h": login_fail,
        "api_error_rate": round(err_rate * 100, 1),
        "recommendation": recommendation,
    }


# ---------- read-side helpers ----------

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


def get_stats_by_niche(db_path: Path = DB_PATH) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
              niche,
              COUNT(*) AS processed,
              SUM(CASE WHEN result = 'approved' THEN 1 ELSE 0 END) AS approved
            FROM processed_handles
            WHERE niche IS NOT NULL
            GROUP BY niche
            ORDER BY approved DESC, processed DESC
            """
        ).fetchall()
    out = []
    for r in rows:
        processed = r["processed"]
        approved = r["approved"] or 0
        rate = (approved / processed * 100) if processed else 0.0
        out.append({
            "niche": r["niche"],
            "processed": processed,
            "approved": approved,
            "rejected": processed - approved,
            "approval_rate": round(rate, 1),
        })
    return out


def get_session_approved(session_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """Hent alle godkjente creators fra en spesifikk sesjon."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT handle, platform, niche, engagement, follower_count, language,
                   discovery_source_type, discovery_source_value, checked_at
            FROM processed_handles
            WHERE result = 'approved' AND session_id = ?
            ORDER BY checked_at
            """,
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]
