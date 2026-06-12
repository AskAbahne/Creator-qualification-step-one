"""
TikTok-klient via TikTokApi (uoffisiell). Spec seksjon 7.

Bruker msToken fra Chrome-cookies for autentisert sesjon.
Hentes manuelt - se spec 0.4 for prosedyre.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time

from TikTokApi import TikTokApi

from .config import load_config

log = logging.getLogger(__name__)

POSTS_PER_PROFILE = 20


def _polite_delay() -> None:
    time.sleep(random.uniform(2.0, 8.0))


async def _fetch_profile_async(api: TikTokApi, handle: str) -> dict:
    user = api.user(username=handle)
    info = await user.info()
    stats = info.get("userInfo", {}).get("stats", {})
    user_info = info.get("userInfo", {}).get("user", {})
    return {
        "handle": user_info.get("uniqueId", handle),
        "user_id": user_info.get("id"),
        "sec_uid": user_info.get("secUid"),
        "follower_count": stats.get("followerCount", 0),
        "following_count": stats.get("followingCount", 0),
        "media_count": stats.get("videoCount", 0),
        "biography": user_info.get("signature", ""),
        "full_name": user_info.get("nickname", ""),
        "is_verified": user_info.get("verified", False),
    }


async def _fetch_recent_posts_async(api: TikTokApi, handle: str, amount: int) -> list[dict]:
    user = api.user(username=handle)
    posts: list[dict] = []
    async for video in user.videos(count=amount):
        v = video.as_dict
        stats = v.get("stats", {})
        from datetime import datetime, timezone
        create_ts = v.get("createTime", 0)
        taken_at = datetime.fromtimestamp(create_ts, tz=timezone.utc) if create_ts else None

        desc = v.get("desc", "") or ""
        hashtags = [
            (t.get("hashtagName") or "").lower().lstrip("#")
            for t in v.get("textExtra", []) or []
            if t.get("hashtagName")
        ]
        posts.append({
            "id": str(v.get("id", "")),
            "is_video": True,
            "taken_at": taken_at,
            "like_count": stats.get("diggCount", 0),
            "comment_count": stats.get("commentCount", 0),
            "share_count": stats.get("shareCount", 0),
            "view_count": stats.get("playCount", 0),
            "caption_text": desc,
            "hashtags": hashtags,
        })
        if len(posts) >= amount:
            break
    return posts


async def _with_api(work):
    cfg = load_config()
    ms_token = cfg["tiktok_ms_token"]
    proxy = cfg.get("proxy", "").strip()

    async with TikTokApi() as api:
        session_kwargs = {"ms_tokens": [ms_token], "num_sessions": 1, "sleep_after": 3}
        if proxy:
            session_kwargs["proxies"] = [proxy]
            log.info("Bruker proxy for TikTok-sesjon")
        await api.create_sessions(**session_kwargs)
        return await work(api)


def fetch_profile(handle: str) -> dict:
    """Synkron wrapper for å hente TikTok-profil."""
    handle = handle.lstrip("@")
    result = asyncio.run(_with_api(lambda api: _fetch_profile_async(api, handle)))
    _polite_delay()
    return result


def fetch_recent_posts(handle: str, amount: int = POSTS_PER_PROFILE) -> list[dict]:
    """Synkron wrapper for å hente siste N TikTok-videoer."""
    handle = handle.lstrip("@")
    result = asyncio.run(_with_api(lambda api: _fetch_recent_posts_async(api, handle, amount)))
    _polite_delay()
    return result
