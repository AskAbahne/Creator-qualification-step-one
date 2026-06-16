"""
Discovery-kilde 2: lignende kontoer fra seed-profiler (spec seksjon 9.3).

Returnerer (handle, 'seed', seed_handle) per discovered handle.
Selvforsterkende: godkjente creators kan legges til som nye seeds via add_seed().
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from instagrapi import Client

from ..config import CONFIG_PATH, load_config

log = logging.getLogger(__name__)


def find_similar_accounts(cl: Client, seed_handles_by_niche: dict[str, list[str]]) -> list[tuple[str, str, str]]:
    """For hver seed: hent 'lignende kontoer' fra Instagram.

    seed_handles_by_niche: {niche: [seed1, seed2, ...]}
    Returnerer (handle, 'seed', seed_handle).
    """
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for niche, seeds in seed_handles_by_niche.items():
        for seed in seeds:
            seed = seed.lstrip("@")
            try:
                user_id = cl.user_id_from_username(seed)
            except Exception as e:
                log.warning("Klarte ikke å slå opp seed @%s: %s", seed, e)
                continue

            try:
                recommended = cl.discover_recommended_accounts_for_category_v1(user_id)
            except Exception as e:
                log.warning("Ingen anbefalinger for @%s: %s", seed, e)
                recommended = []

            try:
                extra = cl.fetch_suggestion_details(user_id)
            except Exception:
                extra = []

            for user in list(recommended) + list(extra):
                h = getattr(user, "username", None)
                if h and h.lower() not in seen and h.lower() != seed.lower():
                    seen.add(h.lower())
                    out.append((h, "seed", seed))

    return out


def all_seeds_grouped(cfg: dict) -> dict[str, list[str]]:
    """Returner {niche: [seeds]} fra config."""
    seeds_cfg = cfg.get("seed_profiles", {}) or {}
    return {n: list(seeds) for n, seeds in seeds_cfg.items() if seeds}


def add_seed(niche: str, handle: str, max_per_niche: int = 15,
             config_path: Path = CONFIG_PATH) -> bool:
    """Legg en ny seed til en nisje i config.json. Returnerer True hvis lagt til.

    Hopper over hvis den allerede finnes eller hvis nisjen er full (max_per_niche).
    """
    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    seeds = cfg.setdefault("seed_profiles", {}).setdefault(niche, [])
    handle_norm = handle.lstrip("@").lower()
    if any(s.lower() == handle_norm for s in seeds):
        return False
    if len(seeds) >= max_per_niche:
        return False
    seeds.append(handle.lstrip("@"))

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    return True
