"""
Discovery-kilde 3: hashtag-søk (spec seksjon 9.4).

Returnerer (handle, source_type, source_value) per discovered handle.
"""
from __future__ import annotations

import logging

from instagrapi import Client

from ..niches import NICHES

log = logging.getLogger(__name__)

POSTS_PER_HASHTAG_TOP = 30
POSTS_PER_HASHTAG_RECENT = 30


def search_instagram_hashtag(cl: Client, hashtag: str) -> list[tuple[str, str, str]]:
    hashtag = hashtag.lstrip("#")
    out: list[tuple[str, str, str]] = []
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
                out.append((h, "hashtag", hashtag))
    return out


def search_many_hashtags(cl: Client, hashtags: list[str]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for tag in hashtags:
        for handle, src_type, src_val in search_instagram_hashtag(cl, tag):
            if handle.lower() not in seen:
                seen.add(handle.lower())
                out.append((handle, src_type, src_val))
    return out


async def _search_tiktok_hashtag_async(hashtags: list[str]) -> list[tuple[str, str, str]]:
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
        for tag in hashtags:
            tag_name = tag.lstrip("#")
            try:
                tag_obj = api.hashtag(name=tag_name)
                async for video in tag_obj.videos(count=POSTS_PER_HASHTAG_RECENT):
                    v = video.as_dict
                    author = v.get("author") or {}
                    handle = author.get("uniqueId") or author.get("unique_id")
                    if handle and handle.lower() not in seen:
                        seen.add(handle.lower())
                        out.append((handle, "hashtag", tag_name))
            except Exception as e:
                log.warning("TikTok hashtag-søk feilet for #%s: %s", tag_name, e)
                continue
    return out


def search_tiktok_hashtags(hashtags: list[str]) -> list[tuple[str, str, str]]:
    import asyncio
    return asyncio.run(_search_tiktok_hashtag_async(hashtags))


def hashtags_from_niches(niches: list[str] | None = None) -> list[str]:
    if niches is None:
        niches = list(NICHES.keys())
    out: list[str] = []
    seen: set[str] = set()
    for niche in niches:
        if niche not in NICHES:
            continue
        for kw in NICHES[niche]["strong"]:
            if kw not in seen:
                seen.add(kw)
                out.append(kw)
    return out
