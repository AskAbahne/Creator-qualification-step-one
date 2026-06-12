"""
Hovedscript - kjorer en full discovery- og filtreringssesjon.

Sesjonsflyt (spec seksjon 9.5):
  1. Discovery-kilde 1: keyword-sok pa kontoer
  2. Discovery-kilde 2: lignende kontoer fra seed-profiler  (kun Instagram)
  3. Discovery-kilde 3: hashtag-sok
  4. Deduplisering mot SQLite
  5. Filtrering med early-exit
  6. Eksport av godkjente til Google Sheets
  7. Logging av alle resultater til SQLite

Bruk:
    python main.py                              # full sesjon, IG + TikTok, alle nisjer
    python main.py --platforms instagram        # kun Instagram
    python main.py --platforms tiktok           # kun TikTok
    python main.py --niches stoicism            # kun en nisje
    python main.py --no-sheets                  # hopp over Sheets-eksport
    python main.py --max 20                     # bare prosesser 20 handles totalt
    python main.py --stats-only                 # vis DB-statistikk og avslutt
"""
from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from src.config import load_config
from src.database import filter_unseen, get_stats, record_result
from src.discovery.hashtag_search import (
    hashtags_from_niches,
    search_many_hashtags,
    search_tiktok_hashtags,
)
from src.discovery.keyword_search import (
    build_queries,
    search_instagram_accounts,
    search_tiktok_accounts,
)
from src.discovery.seed_profiles import all_seeds_from_config, find_similar_accounts
from src.filters import FilterResult, check_creator
from src.instagram_client import (
    fetch_profile as ig_fetch_profile,
    fetch_recent_posts as ig_fetch_posts,
    login as ig_login,
)
from src.niches import NICHES
from src.sheets import append_approved
from src.tiktok_client import (
    fetch_profile as tt_fetch_profile,
    fetch_recent_posts as tt_fetch_posts,
)

log = logging.getLogger("discovery")

VALID_PLATFORMS = ("instagram", "tiktok")


@dataclass
class SessionStats:
    discovered: int = 0
    after_dedup: int = 0
    processed: int = 0
    approved: int = 0
    rejected: int = 0
    by_failure: dict = field(default_factory=dict)
    by_platform: dict = field(default_factory=dict)
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
            f"  Per plattform: {self.by_platform}\n"
            f"  Top-frafall: {dict(list(self.by_failure.items())[:5])}"
        )


def _dedup(handles: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for h in handles:
        n = h.lower()
        if n not in seen:
            seen.add(n)
            out.append(h)
    return out


def _discover_instagram(cl, niches, cfg, update) -> list[str]:
    handles: list[str] = []
    update("[IG] Kilde 1: keyword-sok...")
    queries = build_queries(niches)
    handles += search_instagram_accounts(cl, queries)
    update(f"[IG]  Kilde 1 totalt unike: {len(set(h.lower() for h in handles))}")

    update("[IG] Kilde 2: seed-profiler...")
    seeds = all_seeds_from_config(cfg)
    if seeds:
        handles += find_similar_accounts(cl, seeds)
        update(f"[IG]  Kilde 2 totalt unike: {len(set(h.lower() for h in handles))}")
    else:
        update("[IG]  Ingen seed-profiler i config - kilde 2 hoppes over")

    update("[IG] Kilde 3: hashtag-sok...")
    tags = hashtags_from_niches(niches)
    handles += search_many_hashtags(cl, tags)
    update(f"[IG]  Kilde 3 totalt unike: {len(set(h.lower() for h in handles))}")
    return _dedup(handles)


def _discover_tiktok(niches, update) -> list[str]:
    handles: list[str] = []
    update("[TT] Kilde 1: keyword-sok...")
    queries = build_queries(niches)
    handles += search_tiktok_accounts(queries)
    update(f"[TT]  Kilde 1 totalt unike: {len(set(h.lower() for h in handles))}")

    update("[TT] Kilde 2: seed-profiler (kun Instagram - hoppes over)")

    update("[TT] Kilde 3: hashtag-sok...")
    tags = hashtags_from_niches(niches)
    handles += search_tiktok_hashtags(tags)
    update(f"[TT]  Kilde 3 totalt unike: {len(set(h.lower() for h in handles))}")
    return _dedup(handles)


def _filter_instagram_handle(cl, handle: str) -> Optional[FilterResult]:
    profile = ig_fetch_profile(cl, handle)
    posts = ig_fetch_posts(cl, profile["user_id"])
    return check_creator(profile, posts, platform="instagram")


def _filter_tiktok_handle(handle: str) -> Optional[FilterResult]:
    profile = tt_fetch_profile(handle)
    posts = tt_fetch_posts(handle)
    return check_creator(profile, posts, platform="tiktok")


def run_session(
    platforms: Optional[list[str]] = None,
    niches: Optional[list[str]] = None,
    export_to_sheets: bool = True,
    max_handles: Optional[int] = None,
    progress_callback=None,
) -> SessionStats:
    """Kjor en komplett discovery + filter + eksport-sesjon.

    platforms: liste med "instagram" og/eller "tiktok". Default = begge.
    """
    stats = SessionStats()
    platforms = platforms or list(VALID_PLATFORMS)
    invalid = [p for p in platforms if p not in VALID_PLATFORMS]
    if invalid:
        raise ValueError(f"Ugyldige plattformer: {invalid}. Gyldige: {VALID_PLATFORMS}")
    niches = niches or list(NICHES.keys())
    cfg = load_config()

    def update(msg: str):
        log.info(msg)
        if progress_callback:
            progress_callback(msg, stats)

    update(f"Starter sesjon (plattformer: {', '.join(platforms)}, nisjer: {len(niches)})")

    cl = None
    if "instagram" in platforms:
        update("Logger inn pa Instagram...")
        cl = ig_login()
        update("IG-innlogging OK.")

    # ----- 1. Discovery -----
    all_handles: dict[str, list[str]] = {p: [] for p in platforms}

    if "instagram" in platforms:
        all_handles["instagram"] = _discover_instagram(cl, niches, cfg, update)
    if "tiktok" in platforms:
        all_handles["tiktok"] = _discover_tiktok(niches, update)

    stats.discovered = sum(len(h) for h in all_handles.values())

    # ----- 2. Dedup -----
    update("Dedupliserer mot SQLite...")
    unseen_by_platform: dict[str, list[str]] = {}
    for p, hs in all_handles.items():
        unseen = filter_unseen(hs, p)
        unseen_by_platform[p] = unseen
        update(f"  [{p}] {len(unseen)} av {len(hs)} er nye")

    if max_handles:
        total_unseen = sum(len(hs) for hs in unseen_by_platform.values())
        if total_unseen > max_handles:
            update(f"  Begrenser til {max_handles} handles totalt (fordelt jevnt)")
            limit_per_platform = max_handles // len(platforms)
            for p in unseen_by_platform:
                unseen_by_platform[p] = unseen_by_platform[p][:limit_per_platform]

    stats.after_dedup = sum(len(hs) for hs in unseen_by_platform.values())

    # ----- 3. Filter -----
    approved_results: list[FilterResult] = []

    for platform, handles in unseen_by_platform.items():
        if not handles:
            continue
        update(f"Filtrerer {len(handles)} handles pa {platform}...")
        for i, handle in enumerate(handles, 1):
            update(f"  [{platform} {i}/{len(handles)}] @{handle}")
            try:
                if platform == "instagram":
                    result = _filter_instagram_handle(cl, handle)
                else:
                    result = _filter_tiktok_handle(handle)
            except Exception as e:
                log.warning("  Feil for @%s (%s): %s", handle, platform, e)
                continue

            if result is None:
                continue
            stats.processed += 1
            stats.by_platform[platform] = stats.by_platform.get(platform, 0) + 1
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
    parser.add_argument(
        "--platforms",
        nargs="+",
        choices=list(VALID_PLATFORMS),
        help=f"Velg plattform(er). Default: begge ({', '.join(VALID_PLATFORMS)})",
    )
    parser.add_argument("--niches", nargs="*", help="Begrens til disse nisjene")
    parser.add_argument("--no-sheets", action="store_true", help="Hopp over Sheets-eksport")
    parser.add_argument("--max", type=int, help="Maks antall handles a prosessere totalt")
    parser.add_argument("--stats-only", action="store_true", help="Skriv DB-statistikk og avslutt")
    args = parser.parse_args()

    if args.stats_only:
        print("Database-statistikk:")
        for k, v in get_stats().items():
            print(f"  {k}: {v}")
        return 0

    run_session(
        platforms=args.platforms,
        niches=args.niches,
        export_to_sheets=not args.no_sheets,
        max_handles=args.max,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
