"""
Discovery-kilde 3: hashtag-søk (spec seksjon 9.4).

Høyest volum-kilde, lavere presisjon enn kilde 1 og 2. Henter poster under
en hashtag og ekstraherer @handles. Sikrer at koen alltid er full.
"""
from __future__ import annotations

import logging

from instagrapi import Client

from ..niches import NICHES

log = logging.getLogger(__name__)

POSTS_PER_HASHTAG_TOP = 30
POSTS_PER_HASHTAG_RECENT = 30


def search_instagram_hashtag(cl: Client, hashtag: str) -> list[str]:
    """Hent top + recent poster under en hashtag, ekstraher handles."""
    hashtag = hashtag.lstrip("#")
    handles: list[str] = []
    seen: set[str] = set()

    for fetcher, count in (
        (cl.hashtag_medias_top, POSTS_PER_HASHTAG_TOP),
        (cl.hashtag_medias_recent, POSTS_PER_HASHTAG_RECENT),
    ):
        try:
            medias = fetcher(hashtag, amount=count)
        except Exception as e:
            log.warning("Hashtag-søk feilet for #%s (%s): %s", hashtag, fetcher.__name__, e)
            continue
        for m in medias:
            h = getattr(getattr(m, "user", None), "username", None)
            if h and h.lower() not in seen:
                seen.add(h.lower())
                handles.append(h)

    return handles


def search_many_hashtags(cl: Client, hashtags: list[str]) -> list[str]:
    """Søk flere hashtags. Returner alle unike handles."""
    handles: list[str] = []
    seen: set[str] = set()
    for tag in hashtags:
        for h in search_instagram_hashtag(cl, tag):
            if h.lower() not in seen:
                seen.add(h.lower())
                handles.append(h)
    return handles


def hashtags_from_niches(niches: list[str] | None = None) -> list[str]:
    """Plate ut alle sterke nøkkelord fra valgte nisjer som hashtags."""
    if niches is None:
        niches = list(NICHES.keys())
    out: list[str] = []
    seen: set[str] = set()
    for niche in niches:
        for kw in NICHES[niche]["strong"]:
            if kw not in seen:
                seen.add(kw)
                out.append(kw)
    return out
