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


def build_queries(niches: list[str] | None = None) -> list[str]:
    """Hent sterke nøkkelord fra valgte nisjer (eller alle) til søkequeries."""
    if niches is None:
        niches = list(NICHES.keys())
    queries: list[str] = []
    for niche in niches:
        for kw in NICHES[niche]["strong"]:
            queries.append(_query_for_keyword(kw))
    return queries
