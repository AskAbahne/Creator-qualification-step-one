"""
Hovedscript - kjorer en full discovery- og filtreringssesjon.

Sesjonsflyt (spec seksjon 9.5):
  1. Discovery-kilde 1: keyword-sok pa kontoer
  2. Discovery-kilde 2: lignende kontoer fra seed-profiler
  3. Discovery-kilde 3: hashtag-sok
  4. Deduplisering mot SQLite
  5. Filtrering med early-exit
  6. Eksport av godkjente til Google Sheets
  7. Logging av alle resultater til SQLite

Bruk:
    python main.py                   # full sesjon, alle nisjer, kun Instagram
    python main.py --niches stoicism # kun en nisje
    python main.py --no-sheets       # hopp over Sheets-eksport
    python main.py --max 20          # bare prosesser 20 handles totalt
"""
from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from src.config import load_config
from src.database import filter_unseen, get_stats, record_result
from src.discovery.hashtag_search import hashtags_from_niches, search_many_hashtags
from src.discovery.keyword_search import build_queries, search_instagram_accounts
from src.discovery.seed_profiles import all_seeds_from_config, find_similar_accounts
from src.filters import FilterResult, check_creator
from src.instagram_client import fetch_profile, fetch_recent_posts, login
from src.niches import NICHES
from src.sheets import append_approved

log = logging.getLogger("discovery")


@dataclass
class SessionStats:
    discovered: int = 0
    after_dedup: int = 0
    processed: int = 0
    approved: int = 0
    rejected: int = 0
    by_failure: dict = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.started_at

    def summary_text(self) -> str:
        m = self.elapsed_seconds / 60
        return (
            f"Sesjon ferdig pa {m:.1f} min:\n"
            f"  Discovered: {self.discovered}\n"
            f"  Etter dedup: {self.after_dedup}\n"
            f"  Prosessert: {self.processed}\n"
            f"  Godkjent:   {self.approved}\n"
            f"  Avvist:     {self.rejected}\n"
            f"  Top-frafall: {dict(list(self.by_failure.items())[:5])}"
        )


def run_session(
    niches: Optional[list[str]] = None,
    export_to_sheets: bool = True,
    max_handles: Optional[int] = None,
    progress_callback=None,
) -> SessionStats:
    """Kjor en komplett discovery + filter + eksport-sesjon for Instagram."""
    stats = SessionStats()
    niches = niches or list(NICHES.keys())
    cfg = load_config()

    def update(msg: str):
        log.info(msg)
        if progress_callback:
            progress_callback(msg, stats)

    update("Logger inn pa Instagram...")
    cl = login()
    update("Innlogging OK.")

    # ----- 1. Discovery -----
    handles: list[str] = []
    seen: set[str] = set()

    update("Kilde 1: keyword-sok...")
    queries = build_queries(niches)
    kw_handles = search_instagram_accounts(cl, queries)
    for h in kw_handles:
        if h.lower() not in seen:
            seen.add(h.lower())
            handles.append(h)
    update(f"  Kilde 1 ga {len(kw_handles)} handles (totalt unike: {len(handles)})")

    update("Kilde 2: seed-profiler...")
    seeds = all_seeds_from_config(cfg)
    if seeds:
        seed_handles = find_similar_accounts(cl, seeds)
        for h in seed_handles:
            if h.lower() not in seen:
                seen.add(h.lower())
                handles.append(h)
        update(f"  Kilde 2 ga {len(seed_handles)} handles (totalt unike: {len(handles)})")
    else:
        update("  Ingen seed-profiler i config - kilde 2 hoppes over")

    update("Kilde 3: hashtag-sok...")
    hashtags = hashtags_from_niches(niches)
    ht_handles = search_many_hashtags(cl, hashtags)
    for h in ht_handles:
        if h.lower() not in seen:
            seen.add(h.lower())
            handles.append(h)
    update(f"  Kilde 3 ga {len(ht_handles)} handles (totalt unike: {len(handles)})")

    stats.discovered = len(handles)

    # ----- 2. Dedup -----
    update("Dedupliserer mot SQLite...")
    unseen = filter_unseen(handles, "instagram")
    stats.after_dedup = len(unseen)
    update(f"  {len(unseen)} av {len(handles)} er nye (resten allerede prosessert)")

    if max_handles:
        unseen = unseen[:max_handles]
        update(f"  Begrenset til {max_handles} handles for denne kjoringen")

    # ----- 3. Filter -----
    update(f"Filtrerer {len(unseen)} handles...")
    approved_results: list[FilterResult] = []
    for i, handle in enumerate(unseen, 1):
        update(f"  [{i}/{len(unseen)}] @{handle}")
        try:
            profile = fetch_profile(cl, handle)
            posts = fetch_recent_posts(cl, profile["user_id"])
            result = check_creator(profile, posts, platform="instagram")
        except Exception as e:
            log.warning("  Feil for @%s: %s", handle, e)
            continue

        stats.processed += 1
        record_result(result)
        if result.passed:
            stats.approved += 1
            approved_results.append(result)
            update(f"    GODKJENT (nisje={result.niche}, ER={result.engagement_rate}%)")
        else:
            stats.rejected += 1
            stats.by_failure[result.failed_at] = stats.by_failure.get(result.failed_at, 0) + 1

    # ----- 4. Eksport -----
    if export_to_sheets and approved_results:
        update(f"Eksporterer {len(approved_results)} godkjente til Google Sheets...")
        n = append_approved(approved_results)
        update(f"  Skrev {n} rader til Sheets")
    elif export_to_sheets:
        update("Ingen godkjente - hopper over Sheets-eksport")

    update(stats.summary_text())
    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Abahne creator discovery - Steg 1")
    parser.add_argument("--niches", nargs="*", help="Begrens til disse nisjene")
    parser.add_argument("--no-sheets", action="store_true", help="Hopp over Sheets-eksport")
    parser.add_argument("--max", type=int, help="Maks antall handles a prosessere")
    parser.add_argument("--stats-only", action="store_true", help="Skriv DB-statistikk og avslutt")
    args = parser.parse_args()

    if args.stats_only:
        print("Database-statistikk:")
        for k, v in get_stats().items():
            print(f"  {k}: {v}")
        return 0

    run_session(
        niches=args.niches,
        export_to_sheets=not args.no_sheets,
        max_handles=args.max,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
