"""
Discovery-kilde 1: keyword-søk på kontoer (spec seksjon 9.2).

Mest presis kilde. Bruker plattformenes egen rangering.
Kjøres alltid først per sesjon.
"""
from __future__ import annotations

import logging

from instagrapi import Client

from ..niches import NICHES

log = logging.getLogger(__name__)

MAX_RESULTS_PER_QUERY = 25


def _query_for_keyword(keyword: str) -> str:
    """Bygg et naturlig søkequery (f.eks. 'weightloss' -> 'weightloss coach')."""
    return f"{keyword} coach"


def search_instagram_accounts(cl: Client, queries: list[str]) -> list[str]:
    """Søk etter kontoer på Instagram for hver query. Returner unike handles."""
    handles: list[str] = []
    seen: set[str] = set()
    for q in queries:
        try:
            users = cl.fbsearch_accounts_v2(q)
        except Exception as e:
            log.warning("Instagram keyword-søk feilet for %r: %s", q, e)
            continue
        for user in users[:MAX_RESULTS_PER_QUERY]:
            handle = getattr(user, "username", None)
            if handle and handle.lower() not in seen:
                seen.add(handle.lower())
                handles.append(handle)
    return handles


async def _search_tiktok_async(queries: list[str]) -> list[str]:
    """Søk etter TikTok-brukere via TikTokApi (spec seksjon 9.2)."""
    from TikTokApi import TikTokApi
    from ..config import load_config

    cfg = load_config()
    handles: list[str] = []
    seen: set[str] = set()

    async with TikTokApi() as api:
        await api.create_sessions(ms_tokens=[cfg["tiktok_ms_token"]], num_sessions=1, sleep_after=3)
        for q in queries:
            try:
                async for user in api.search.users(q, count=MAX_RESULTS_PER_QUERY):
                    info = getattr(user, "as_dict", {}) or {}
                    handle = (info.get("user_info") or {}).get("unique_id") \
                        or info.get("uniqueId") \
                        or getattr(user, "username", None)
                    if handle and handle.lower() not in seen:
                        seen.add(handle.lower())
                        handles.append(handle)
            except Exception as e:
                log.warning("TikTok keyword-søk feilet for %r: %s", q, e)
                continue
    return handles


def search_tiktok_accounts(queries: list[str]) -> list[str]:
    """Synkron wrapper for TikTok keyword-søk."""
    import asyncio
    return asyncio.run(_search_tiktok_async(queries))


def build_queries(niches: list[str] | None = None) -> list[str]:
    """Hent sterke nøkkelord fra valgte nisjer (eller alle) til søkequeries."""
    if niches is None:
        niches = list(NICHES.keys())
    queries: list[str] = []
    for niche in niches:
        for kw in NICHES[niche]["strong"]:
            queries.append(_query_for_keyword(kw))
    return queries
