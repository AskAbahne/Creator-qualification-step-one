"""
Hovedscript - kjorer en full discovery- og filtreringssesjon.

Sesjonsflyt (spec seksjon 9.5):
  1. Discovery (3 kilder) per valgt plattform
  2. Deduplisering mot SQLite
  3. Filtrering med early-exit + konto-rotasjon
  4. Selvforsterkende seeds: godkjente legges automatisk til seed-listen
  5. Logging til SQLite (ingen automatisk Sheets-eksport)

Bruk:
    python main.py                              # IG + TikTok, alle nisjer
    python main.py --platforms instagram        # kun Instagram
    python main.py --platforms tiktok           # kun TikTok
    python main.py --niches stoicism weightloss # kun valgte nisjer
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
from src.database import (
    filter_unseen, finalize_session, get_account_health,
    get_stats, record_result, start_session,
)
from src.discovery.hashtag_search import (
    hashtags_from_niches, search_many_hashtags, search_tiktok_hashtags,
)
from src.discovery.keyword_search import (
    build_queries, search_instagram_accounts, search_tiktok_accounts,
)
from src.discovery.seed_profiles import (
    add_seed, all_seeds_grouped, find_similar_accounts,
)
from src.filters import FilterResult, check_creator
from src.instagram_client import (
    InstagramPool, fetch_profile as ig_fetch_profile,
    fetch_recent_posts as ig_fetch_posts,
)
from src.niches import NICHES
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


def _discover_instagram(pool: InstagramPool, niches, cfg, update) -> list[tuple[str, str, str]]:
    """Returner alle discovered handles fra IG som (handle, source_type, source_value)."""
    all_results: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def add_batch(batch: list[tuple[str, str, str]]):
        for h, st, sv in batch:
            if h.lower() not in seen:
                seen.add(h.lower())
                all_results.append((h, st, sv))

    # Bruk første client til discovery
    slot = pool.next_client()
    cl = slot.client

    update("[IG] Kilde 1: keyword-sok...")
    queries = build_queries(niches)
    add_batch(search_instagram_accounts(cl, queries))
    update(f"[IG]  Etter kilde 1: {len(all_results)} unike")

    update("[IG] Kilde 2: seed-profiler...")
    seeds_grouped = {n: s for n, s in all_seeds_grouped(cfg).items() if n in niches}
    if seeds_grouped:
        add_batch(find_similar_accounts(cl, seeds_grouped))
        update(f"[IG]  Etter kilde 2: {len(all_results)} unike")
    else:
        update("[IG]  Ingen seeds for valgte nisjer - kilde 2 hoppes over")

    update("[IG] Kilde 3: hashtag-sok...")
    tags = hashtags_from_niches(niches)
    add_batch(search_many_hashtags(cl, tags))
    update(f"[IG]  Etter kilde 3: {len(all_results)} unike")

    return all_results


def _discover_tiktok(niches, update) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    def add_batch(batch):
        for h, st, sv in batch:
            if h.lower() not in seen:
                seen.add(h.lower())
                out.append((h, st, sv))

    update("[TT] Kilde 1: keyword-sok...")
    queries = build_queries(niches)
    add_batch(search_tiktok_accounts(queries))
    update(f"[TT]  Etter kilde 1: {len(out)} unike")

    update("[TT] Kilde 2: seed-profiler (kun Instagram - hoppes over)")

    update("[TT] Kilde 3: hashtag-sok...")
    tags = hashtags_from_niches(niches)
    add_batch(search_tiktok_hashtags(tags))
    update(f"[TT]  Etter kilde 3: {len(out)} unike")
    return out


def _filter_ig(pool: InstagramPool, handle: str,
               session_id: int) -> tuple[Optional[FilterResult], Optional[str], float]:
    slot = pool.next_client()
    t0 = time.time()
    try:
        profile = ig_fetch_profile(slot.client, handle,
                                   account_label=slot.label, session_id=session_id)
        posts = ig_fetch_posts(slot.client, profile["user_id"],
                               account_label=slot.label, session_id=session_id)
    except Exception as e:
        # Helse-event er allerede logget i klienten
        return None, slot.label, time.time() - t0
    result = check_creator(profile, posts, platform="instagram")
    return result, slot.label, time.time() - t0


def _filter_tt(handle: str) -> tuple[Optional[FilterResult], Optional[str], float]:
    t0 = time.time()
    try:
        profile = tt_fetch_profile(handle)
        posts = tt_fetch_posts(handle)
    except Exception:
        return None, "tiktok_msToken", time.time() - t0
    result = check_creator(profile, posts, platform="tiktok")
    return result, "tiktok_msToken", time.time() - t0


def _check_and_pause_unhealthy(pool: InstagramPool, update) -> None:
    """Hvis en konto har rød helse, pause den."""
    for slot in list(pool.slots):
        if slot.client is None:
            continue
        health = get_account_health(slot.label)
        if health["status"] == "red":
            update(f"⚠️  Konto {slot.label}: {health['recommendation']} "
                   f"({health['challenges_24h']} challenges, "
                   f"{health['api_error_rate']}% API-feilrate)")
            pool.pause_account(slot.label, health["recommendation"])


def run_session(
    platforms: Optional[list[str]] = None,
    niches: Optional[list[str]] = None,
    max_handles: Optional[int] = None,
    progress_callback=None,
) -> tuple[SessionStats, int]:
    """Kjor en sesjon. Returner (stats, session_id).

    Ingen automatisk Sheets-eksport. Godkjente lagres i DB og kan eksporteres
    manuelt via /download-endepunktet.
    """
    stats = SessionStats()
    platforms = platforms or list(VALID_PLATFORMS)
    invalid = [p for p in platforms if p not in VALID_PLATFORMS]
    if invalid:
        raise ValueError(f"Ugyldige plattformer: {invalid}. Gyldige: {VALID_PLATFORMS}")
    niches = niches or list(NICHES.keys())
    if not niches:
        raise ValueError("Minst én nisje må velges")
    cfg = load_config()

    # Start sesjon i DB
    accounts_for_session: list[str] = []
    if "instagram" in platforms:
        accounts_for_session.extend(
            a["label"] for a in cfg["instagram_accounts"]
            if not a.get("warmup_mode", False)
        )
    if "tiktok" in platforms:
        accounts_for_session.append("tiktok_msToken")
    session_id = start_session(platforms, niches, max_handles, accounts_for_session)

    def update(msg: str):
        log.info(msg)
        if progress_callback:
            progress_callback(msg, stats)

    update(f"Sesjon #{session_id} startet (plattformer: {', '.join(platforms)}, nisjer: {len(niches)})")

    pool: Optional[InstagramPool] = None
    if "instagram" in platforms:
        update("Logger inn pa Instagram-kontoer...")
        pool = InstagramPool.from_config(session_id=session_id)
        pool.login_all()
        update(f"IG-innlogging OK ({len(pool.slots)} kontoer aktive)")

    # ---- 1. Discovery ----
    discovery_by_platform: dict[str, list[tuple[str, str, str]]] = {}
    if "instagram" in platforms:
        discovery_by_platform["instagram"] = _discover_instagram(pool, niches, cfg, update)
    if "tiktok" in platforms:
        discovery_by_platform["tiktok"] = _discover_tiktok(niches, update)

    stats.discovered = sum(len(d) for d in discovery_by_platform.values())

    # ---- 2. Dedup ----
    update("Dedupliserer mot SQLite...")
    unseen_by_platform: dict[str, list[tuple[str, str, str]]] = {}
    for p, items in discovery_by_platform.items():
        all_handles = [h for h, _, _ in items]
        unseen_set = set(filter_unseen(all_handles, p))
        unseen = [(h, st, sv) for h, st, sv in items if h in unseen_set]
        unseen_by_platform[p] = unseen
        update(f"  [{p}] {len(unseen)} av {len(items)} er nye")

    if max_handles:
        total = sum(len(u) for u in unseen_by_platform.values())
        if total > max_handles:
            limit_per = max(1, max_handles // len(platforms))
            for p in unseen_by_platform:
                unseen_by_platform[p] = unseen_by_platform[p][:limit_per]
            update(f"  Begrenser til {max_handles} totalt ({limit_per} per plattform)")

    stats.after_dedup = sum(len(u) for u in unseen_by_platform.values())

    # ---- 3. Filter ----
    approved_results: list[tuple[FilterResult, str]] = []  # (result, niche)
    for platform, items in unseen_by_platform.items():
        if not items:
            continue
        update(f"Filtrerer {len(items)} handles pa {platform}...")
        for i, (handle, src_type, src_val) in enumerate(items, 1):
            update(f"  [{platform} {i}/{len(items)}] @{handle}  (kilde: {src_type}={src_val})")

            if platform == "instagram":
                if pool is None or all(s.client is None for s in pool.slots):
                    update("  Alle IG-kontoer pauset - stopper IG-filtrering")
                    break
                result, account_label, t_taken = _filter_ig(pool, handle, session_id)
            else:
                result, account_label, t_taken = _filter_tt(handle)

            if result is None:
                continue

            stats.processed += 1
            stats.by_platform[platform] = stats.by_platform.get(platform, 0) + 1
            record_result(
                result, session_id=session_id,
                discovery_source_type=src_type, discovery_source_value=src_val,
                account_used=account_label, time_taken_sec=t_taken,
                near_miss=result.near_miss, near_miss_detail=result.near_miss_detail,
            )

            if result.passed:
                stats.approved += 1
                approved_results.append((result, result.niche))
                update(f"    ✓ GODKJENT (nisje={result.niche}, ER={result.engagement_rate}%)")
            else:
                stats.rejected += 1
                stats.by_failure[result.failed_at] = stats.by_failure.get(result.failed_at, 0) + 1

            # Sjekk helse hvert 20. creator på IG
            if platform == "instagram" and i % 20 == 0:
                _check_and_pause_unhealthy(pool, update)

    # ---- 4. Selvforsterkende seeds ----
    if approved_results:
        max_seeds = cfg.get("seed_max_per_niche", 15)
        added = 0
        for result, niche in approved_results:
            if niche and add_seed(niche, result.handle, max_seeds):
                added += 1
        if added > 0:
            update(f"Selvforsterkende: {added} nye seeds lagt til config")

    # ---- 5. Finalize ----
    finalize_session(
        session_id,
        discovered=stats.discovered, after_dedup=stats.after_dedup,
        processed=stats.processed, approved=stats.approved, rejected=stats.rejected,
    )

    m = stats.elapsed_seconds / 60
    update(f"\nSesjon #{session_id} ferdig pa {m:.1f} min: "
           f"{stats.approved} godkjent, {stats.rejected} avvist av {stats.processed} prosessert")
    return stats, session_id


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Abahne creator discovery - Steg 1")
    parser.add_argument("--platforms", nargs="+", choices=list(VALID_PLATFORMS))
    parser.add_argument("--niches", nargs="+")
    parser.add_argument("--max", type=int)
    parser.add_argument("--stats-only", action="store_true")
    args = parser.parse_args()

    if args.stats_only:
        print("Database-statistikk:")
        for k, v in get_stats().items():
            print(f"  {k}: {v}")
        return 0

    run_session(platforms=args.platforms, niches=args.niches, max_handles=args.max)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
