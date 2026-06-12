"""
Web-grensesnitt for Abahne Discovery.

Endpoints:
  GET  /           - Hovedside med stats + start-knapp
  POST /run        - Start en sesjon i bakgrunnen
  GET  /status     - JSON med live-progress
"""
from __future__ import annotations

import threading
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, render_template, request

from main import run_session
from src.database import get_stats, list_approved

app = Flask(__name__)

SESSION_STATE = {
    "running": False,
    "started_at": None,
    "log": deque(maxlen=200),
    "stats": None,
    "error": None,
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


def _run_in_background(platforms, niches, max_handles, export_to_sheets):
    try:
        SESSION_STATE["running"] = True
        SESSION_STATE["error"] = None
        SESSION_STATE["log"].clear()
        SESSION_STATE["started_at"] = datetime.now().strftime("%H:%M:%S")
        run_session(
            platforms=platforms,
            niches=niches,
            export_to_sheets=export_to_sheets,
            max_handles=max_handles,
            progress_callback=_log,
        )
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
        approved_recent=list_approved()[:10],
        running=SESSION_STATE["running"],
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
        niches = request.form.getlist("niches") or None
        max_handles = request.form.get("max", type=int)
        export_to_sheets = request.form.get("export") == "on"

        t = threading.Thread(
            target=_run_in_background,
            args=(platforms, niches, max_handles, export_to_sheets),
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
    })


@app.route("/dbstats")
def dbstats():
    return jsonify(get_stats())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
