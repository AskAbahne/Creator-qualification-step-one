"""
Bygger den kumulative JSON-diagnostikkeksporten ('Hent data').

Struktur:
  metadata, summary, current_alerts, sessions, creators,
  discovery_sources, criterion_funnel, niche_stats,
  near_misses, account_health, seed_health
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import CONFIG_PATH, load_config
from .database import DB_PATH

SCHEMA_VERSION = 1


def _conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _all_sessions(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM sessions ORDER BY started_at").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for json_field in ("platforms", "niches", "accounts_used"):
            if d.get(json_field):
                try:
                    d[json_field] = json.loads(d[json_field])
                except Exception:
                    pass
        out.append(d)
    return out


def _all_creators(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM processed_handles ORDER BY checked_at").fetchall()
    return [dict(r) for r in rows]


def _discovery_source_stats(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT
          discovery_source_type AS type,
          discovery_source_value AS value,
          COUNT(*) AS discovered,
          SUM(CASE WHEN result = 'approved' THEN 1 ELSE 0 END) AS approved
        FROM processed_handles
        WHERE discovery_source_type IS NOT NULL
        GROUP BY discovery_source_type, discovery_source_value
        ORDER BY approved DESC, discovered DESC
    """).fetchall()
    out = []
    for r in rows:
        discovered = r["discovered"]
        approved = r["approved"] or 0
        rate = (approved / discovered) if discovered else 0.0
        out.append({
            "type": r["type"],
            "value": r["value"],
            "discovered": discovered,
            "approved": approved,
            "approval_rate": round(rate, 4),
        })
    return out


def _criterion_funnel(conn) -> dict:
    rows = conn.execute("""
        SELECT failed_at, COUNT(*) AS c
        FROM processed_handles
        WHERE failed_at IS NOT NULL
        GROUP BY failed_at
    """).fetchall()
    distribution = {r["failed_at"]: r["c"] for r in rows}
    total_processed = conn.execute("SELECT COUNT(*) FROM processed_handles").fetchone()[0]
    total_passed = conn.execute(
        "SELECT COUNT(*) FROM processed_handles WHERE result = 'approved'"
    ).fetchone()[0]

    median_failures = {}
    for crit in ("1_follower_count", "6_engagement_full", "7_avg_views"):
        rows = conn.execute("""
            SELECT follower_count, engagement, avg_views
            FROM processed_handles WHERE failed_at = ?
        """, (crit,)).fetchall()
        if not rows:
            continue
        vals = sorted([
            r["follower_count"] if crit.startswith("1") else
            (r["engagement"] if crit.startswith("6") else r["avg_views"])
            for r in rows if r[0] is not None
        ])
        if vals:
            median_failures[crit] = vals[len(vals) // 2]

    return {
        "total_processed": total_processed,
        "total_passed": total_passed,
        "distribution_by_failed_at": distribution,
        "median_value_at_failure": median_failures,
    }


def _niche_stats(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT niche,
               COUNT(*) AS processed,
               SUM(CASE WHEN result = 'approved' THEN 1 ELSE 0 END) AS approved
        FROM processed_handles WHERE niche IS NOT NULL
        GROUP BY niche
        ORDER BY approved DESC
    """).fetchall()
    out = []
    for r in rows:
        processed = r["processed"]
        approved = r["approved"] or 0
        rate = (approved / processed) if processed else 0.0

        top_fail = conn.execute("""
            SELECT failed_at, COUNT(*) AS c FROM processed_handles
            WHERE niche = ? AND failed_at IS NOT NULL
            GROUP BY failed_at ORDER BY c DESC LIMIT 1
        """, (r["niche"],)).fetchone()

        out.append({
            "niche": r["niche"],
            "processed": processed,
            "approved": approved,
            "approval_rate": round(rate, 4),
            "top_failure_criterion": top_fail["failed_at"] if top_fail else None,
        })
    return out


def _near_misses(conn) -> list[dict]:
    rows = conn.execute("""
        SELECT handle, platform, niche, follower_count, engagement,
               failed_at, near_miss_detail, checked_at
        FROM processed_handles WHERE near_miss = 1
        ORDER BY checked_at DESC LIMIT 200
    """).fetchall()
    return [dict(r) for r in rows]


def _account_health_summary(conn) -> dict:
    accounts = {r["account"] for r in conn.execute(
        "SELECT DISTINCT account FROM account_health_events"
    ).fetchall()}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    summary = {}
    for acc in accounts:
        rows = conn.execute("""
            SELECT event_type, COUNT(*) AS c
            FROM account_health_events
            WHERE account = ? AND timestamp >= ?
            GROUP BY event_type
        """, (acc, cutoff)).fetchall()
        counts = {r["event_type"]: r["c"] for r in rows}
        challenges = counts.get("challenge_required", 0)
        api_err = counts.get("api_error", 0)
        login_ok = counts.get("login_ok", 0)
        login_fail = counts.get("login_fail", 0)
        total = login_ok + login_fail + api_err
        err_rate = (api_err / total) if total else 0.0

        if challenges >= 3 or err_rate > 0.20:
            status = "red"
        elif challenges >= 1 or err_rate > 0.10:
            status = "yellow"
        else:
            status = "green"

        summary[acc] = {
            "status": status,
            "events_24h": counts,
            "api_error_rate": round(err_rate * 100, 1),
        }
    return summary


def _seed_health(conn, cfg: dict) -> list[dict]:
    """Per seed: hvor mange creators den har funnet, hvor mange ble godkjent."""
    rows = conn.execute("""
        SELECT discovery_source_value AS seed, niche,
               COUNT(*) AS discovered,
               SUM(CASE WHEN result = 'approved' THEN 1 ELSE 0 END) AS approved
        FROM processed_handles
        WHERE discovery_source_type = 'seed'
        GROUP BY discovery_source_value, niche
        ORDER BY approved DESC
    """).fetchall()
    out = []
    for r in rows:
        discovered = r["discovered"]
        approved = r["approved"] or 0
        rate = (approved / discovered) if discovered else 0.0
        out.append({
            "seed": r["seed"],
            "niche": r["niche"],
            "discovered": discovered,
            "approved": approved,
            "approval_rate": round(rate, 4),
            "recommendation": (
                "promote" if rate >= 0.10 else
                "keep" if rate >= 0.02 else
                "deprecate"
            ),
        })

    seeds_in_config = cfg.get("seed_profiles", {})
    in_use_seeds = {(o["seed"], o["niche"]) for o in out}
    for niche, seeds in seeds_in_config.items():
        for seed in seeds:
            if (seed, niche) not in in_use_seeds:
                out.append({
                    "seed": seed,
                    "niche": niche,
                    "discovered": 0,
                    "approved": 0,
                    "approval_rate": 0.0,
                    "recommendation": "untested",
                })
    return out


def _summary(conn, sessions: list[dict], niche_stats: list[dict],
             sources: list[dict]) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM processed_handles").fetchone()[0]
    approved = conn.execute(
        "SELECT COUNT(*) FROM processed_handles WHERE result = 'approved'"
    ).fetchone()[0]
    overall_rate = (approved / total) if total else 0.0

    avg_time = conn.execute(
        "SELECT AVG(time_taken_sec) FROM processed_handles WHERE time_taken_sec IS NOT NULL"
    ).fetchone()[0] or 0.0

    top_sources = sources[:5]

    saturated_sources = []
    for src in sources:
        if src["discovered"] >= 20 and src["approval_rate"] < 0.02:
            saturated_sources.append(src)

    completed_sessions = [s for s in sessions if s.get("completed")]
    avg_session_min = 0.0
    if completed_sessions:
        deltas = []
        for s in completed_sessions:
            try:
                start = datetime.fromisoformat(s["started_at"])
                end = datetime.fromisoformat(s["ended_at"])
                deltas.append((end - start).total_seconds() / 60)
            except Exception:
                continue
        if deltas:
            avg_session_min = sum(deltas) / len(deltas)

    return {
        "total_creators": total,
        "total_approved": approved,
        "overall_approval_rate": round(overall_rate, 4),
        "total_sessions": len(sessions),
        "completed_sessions": len(completed_sessions),
        "avg_session_minutes": round(avg_session_min, 1),
        "avg_seconds_per_creator": round(avg_time, 1),
        "top_5_niches_by_volume": niche_stats[:5],
        "top_5_sources_by_yield": top_sources,
        "low_yield_sources_to_drop": saturated_sources[:10],
    }


def _current_alerts(conn, account_health: dict, niche_stats: list[dict],
                    sources: list[dict], cfg: dict) -> list[dict]:
    alerts = []

    for acc, info in account_health.items():
        if info["status"] == "red":
            alerts.append({
                "severity": "high",
                "type": "account_health",
                "account": acc,
                "message": (
                    f"{acc} har rød helse — {info['events_24h']} hendelser siste 24t. "
                    "Pause umiddelbart."
                ),
            })
        elif info["status"] == "yellow":
            alerts.append({
                "severity": "medium",
                "type": "account_health",
                "account": acc,
                "message": f"{acc} har gul helse — vurder redusert volum.",
            })

    cumulative = sum(r["c"] for r in conn.execute(
        "SELECT failed_at, COUNT(*) AS c FROM processed_handles "
        "WHERE failed_at IS NOT NULL GROUP BY failed_at"
    ).fetchall())
    if cumulative >= 100:
        rows = conn.execute(
            "SELECT failed_at, COUNT(*) AS c FROM processed_handles "
            "WHERE failed_at IS NOT NULL GROUP BY failed_at ORDER BY c DESC"
        ).fetchall()
        top = rows[0]
        if top["c"] / cumulative > 0.5:
            alerts.append({
                "severity": "medium",
                "type": "filter_imbalance",
                "criterion": top["failed_at"],
                "message": (
                    f"{top['failed_at']} står for {top['c']/cumulative*100:.0f}% av alle "
                    f"avvisninger ({top['c']} av {cumulative}). Vurder å justere terskelen."
                ),
            })

    for niche in niche_stats:
        if niche["processed"] >= 50 and niche["approval_rate"] < 0.01:
            alerts.append({
                "severity": "low",
                "type": "niche_underperforming",
                "niche": niche["niche"],
                "message": (
                    f"Nisje '{niche['niche']}': {niche['approved']} godkjent av "
                    f"{niche['processed']} prosessert ({niche['approval_rate']*100:.1f}%). "
                    "Vurder å droppe denne nisjen."
                ),
            })

    for src in sources:
        if src["discovered"] >= 30 and src["approval_rate"] < 0.01:
            alerts.append({
                "severity": "low",
                "type": "source_low_yield",
                "source": f"{src['type']}={src['value']}",
                "message": (
                    f"{src['type']} '{src['value']}' har funnet {src['discovered']} "
                    f"handles, kun {src['approved']} godkjent ({src['approval_rate']*100:.1f}%)."
                ),
            })

    return alerts


def build_diagnostics(db_path: Path = DB_PATH) -> dict[str, Any]:
    cfg = load_config()
    with _conn(db_path) as conn:
        sessions = _all_sessions(conn)
        creators = _all_creators(conn)
        sources = _discovery_source_stats(conn)
        funnel = _criterion_funnel(conn)
        niches = _niche_stats(conn)
        near_misses = _near_misses(conn)
        health = _account_health_summary(conn)
        seed_health = _seed_health(conn, cfg)
        summary = _summary(conn, sessions, niches, sources)
        alerts = _current_alerts(conn, health, niches, sources, cfg)

    return {
        "metadata": {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": SCHEMA_VERSION,
            "db_path": str(db_path),
            "config_seed_count": sum(len(v) for v in cfg.get("seed_profiles", {}).values()),
        },
        "summary": summary,
        "current_alerts": alerts,
        "sessions": sessions,
        "creators": creators,
        "discovery_sources": sources,
        "criterion_funnel": funnel,
        "niche_stats": niches,
        "near_misses": near_misses,
        "account_health": health,
        "seed_health": seed_health,
    }


def build_diagnostics_json(db_path: Path = DB_PATH) -> str:
    data = build_diagnostics(db_path)
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)
