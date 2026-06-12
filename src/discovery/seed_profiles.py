"""
Discovery-kilde 2: lignende kontoer fra seed-profiler (spec seksjon 9.3).

Bruker Instagrams egen 'lignende kontoer'-motor. Mest treffsikker discovery
fordi matchingen gjøres av Instagrams algoritme. Kun Instagram.

Selvforsterkende: godkjente creators legges automatisk til som nye seeds.
"""
from __future__ import annotations

import logging

from instagrapi import Client

log = logging.getLogger(__name__)


def find_similar_accounts(cl: Client, seed_handles: list[str]) -> list[str]:
    """For hver seed: hent 'lignende kontoer' fra Instagram. Returner unike handles."""
    handles: list[str] = []
    seen: set[str] = set()

    for seed in seed_handles:
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
                handles.append(h)

    return handles


def all_seeds_from_config(cfg: dict) -> list[str]:
    """Plate ut alle seed-handles fra config.json (alle nisjer)."""
    out: list[str] = []
    seen: set[str] = set()
    for niche_seeds in cfg.get("seed_profiles", {}).values():
        for h in niche_seeds:
            n = h.lstrip("@").lower()
            if n and n not in seen:
                seen.add(n)
                out.append(h.lstrip("@"))
    return out
