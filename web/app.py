"""
Web-grensesnitt for Abahne Discovery.

Endpoints:
  GET  /                       Hovedside
  POST /run                    Start sesjon i bakgrunnen
  GET  /status                 JSON live-progress
  GET  /dbstats                Database-statistikk
  GET  /download/session       CSV med GODKJENTE fra siste sesjon
  GET  /download/diagnostics   JSON med all diagnostikk
"""
from __future__ import annotations

import csv
import io
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file

from main import run_session
from src.database import get_session_approved, get_stats, get_stats_by_niche, list_approved
from src.diagnostics import build_diagnostics_json
from src.niches import NICHES

app = Flask(__name__)

SESSION_STATE = {
    "running": False,
    "started_at": None,
    "log": deque(maxlen=300),
    "stats": None,
    "error": None,
    "last_session_id": None,
}
_lock = threading.Lock()


def _log(msg: str, stats=None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    SESSION_STATE["log"].append(f"[{timestamp}] {msg}")
    if stats:
        SESSION_STATE["stats"] = {
            "discovered": stats.discovered,
            "after_dedup": stats.after_dedup,
            "processed": stats.processed,
            "approved": stats.approved,
            "rejected": stats.rejected,
            "elapsed_min": round(stats.elapsed_seconds / 60, 1),
        }


def _run_in_background(platforms, niches, max_handles):
    try:
        SESSION_STATE["running"] = True
        SESSION_STATE["error"] = None
        SESSION_STATE["log"].clear()
        SESSION_STATE["started_at"] = datetime.now().strftime("%H:%M:%S")
        SESSION_STATE["last_session_id"] = None
        stats, session_id = run_session(
            platforms=platforms,
            niches=niches,
            max_handles=max_handles,
            progress_callback=_log,
        )
        SESSION_STATE["last_session_id"] = session_id
    except Exception as e:
        SESSION_STATE["error"] = str(e)
        _log(f"FEIL: {e}")
    finally:
        SESSION_STATE["running"] = False


@app.route("/")
def index():
    return render_template(
        "index.html",
        stats=get_stats(),
        niche_stats=get_stats_by_niche(),
        approved_recent=list_approved()[:10],
        running=SESSION_STATE["running"],
        all_niches=sorted(NICHES.keys()),
    )


@app.route("/run", methods=["POST"])
def run():
    with _lock:
        if SESSION_STATE["running"]:
            return jsonify({"ok": False, "error": "En sesjon kjorer allerede"}), 409

        platform_choice = request.form.get("platform_choice", "both")
        if platform_choice == "instagram":
            platforms = ["instagram"]
        elif platform_choice == "tiktok":
            platforms = ["tiktok"]
        else:
            platforms = ["instagram", "tiktok"]

        niches = request.form.getlist("niches")
        if not niches:
            return jsonify({"ok": False, "error": "Minst én nisje må velges"}), 400

        max_handles = request.form.get("max", type=int)

        t = threading.Thread(
            target=_run_in_background,
            args=(platforms, niches, max_handles),
            daemon=True,
        )
        t.start()
    return jsonify({"ok": True})


@app.route("/status")
def status():
    return jsonify({
        "running": SESSION_STATE["running"],
        "started_at": SESSION_STATE["started_at"],
        "log": list(SESSION_STATE["log"]),
        "stats": SESSION_STATE["stats"],
        "error": SESSION_STATE["error"],
        "last_session_id": SESSION_STATE["last_session_id"],
    })


@app.route("/dbstats")
def dbstats():
    return jsonify(get_stats())


@app.route("/download/session")
def download_session_csv():
    """CSV med kun denne sesjonens godkjente creators."""
    session_id = SESSION_STATE["last_session_id"]
    if session_id is None:
        return Response("Ingen sesjon ferdig enda.", status=404)

    rows = get_session_approved(session_id)
    if not rows:
        return Response("Sesjonen hadde ingen godkjente.", status=404)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Handle", "Plattform", "Nisje", "Engagement %",
        "Følgere", "Språk", "Discovery-kilde", "Søkeord", "Sjekket",
    ])
    for r in rows:
        writer.writerow([
            f"@{r['handle']}",
            r["platform"],
            r["niche"] or "",
            f"{r['engagement']:.2f}%" if r["engagement"] is not None else "",
            r["follower_count"] or "",
            r["language"] or "",
            r["discovery_source_type"] or "",
            r["discovery_source_value"] or "",
            (r["checked_at"] or "")[:10],
        ])
    csv_bytes = output.getvalue().encode("utf-8-sig")
    return send_file(
        io.BytesIO(csv_bytes),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"godkjente_sesjon_{session_id}_{datetime.now().strftime('%Y-%m-%d')}.csv",
    )


@app.route("/download/diagnostics")
def download_diagnostics():
    """Komplett JSON-diagnostikk for opplasting til Claude-analyse."""
    data = build_diagnostics_json()
    return send_file(
        io.BytesIO(data.encode("utf-8")),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"discovery_diagnostikk_{datetime.now().strftime('%Y-%m-%d')}.json",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
