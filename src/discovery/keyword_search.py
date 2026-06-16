"""
Discovery-kilde 1: keyword-søk på kontoer (spec seksjon 9.2).

Returnerer liste av (handle, source_type, source_value)-tupler så
orchestrator kan spore hvilket søk som fant hver creator.
"""
from __future__ import annotations

import logging

from instagrapi import Client

from ..niches import NICHES

log = logging.getLogger(__name__)

MAX_RESULTS_PER_QUERY = 25


def _query_for_keyword(keyword: str) -> str:
    return f"{keyword} coach"


def search_instagram_accounts(cl: Client, queries: list[str]) -> list[tuple[str, str, str]]:
    """Returner liste av (handle, 'keyword', query) — unike på handle."""
    out: list[tuple[str, str, str]] = []
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
                out.append((handle, "keyword", q))
    return out


async def _search_tiktok_async(queries: list[str]) -> list[tuple[str, str, str]]:
    from TikTokApi import TikTokApi
    from ..config import load_config

    cfg = load_config()
    proxy = cfg.get("tiktok_proxy", "").strip() or cfg.get("proxy", "").strip()
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    async with TikTokApi() as api:
        session_kwargs = {"ms_tokens": [cfg["tiktok_ms_token"]], "num_sessions": 1, "sleep_after": 3}
        if proxy:
            session_kwargs["proxies"] = [proxy]
        await api.create_sessions(**session_kwargs)
        for q in queries:
            try:
                async for user in api.search.users(q, count=MAX_RESULTS_PER_QUERY):
                    info = getattr(user, "as_dict", {}) or {}
                    handle = (info.get("user_info") or {}).get("unique_id") \
                        or info.get("uniqueId") \
                        or getattr(user, "username", None)
                    if handle and handle.lower() not in seen:
                        seen.add(handle.lower())
                        out.append((handle, "keyword", q))
            except Exception as e:
                log.warning("TikTok keyword-søk feilet for %r: %s", q, e)
                continue
    return out


def search_tiktok_accounts(queries: list[str]) -> list[tuple[str, str, str]]:
    import asyncio
    return asyncio.run(_search_tiktok_async(queries))


def build_queries(niches: list[str] | None = None) -> list[str]:
    if niches is None:
        niches = list(NICHES.keys())
    queries: list[str] = []
    for niche in niches:
        if niche not in NICHES:
            continue
        for kw in NICHES[niche]["strong"]:
            queries.append(_query_for_keyword(kw))
    return queries
