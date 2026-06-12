import logging
import random
import time
from pathlib import Path

from instagrapi import Client

from .config import SESSIONS_DIR, load_config

log = logging.getLogger(__name__)

SESSION_FILE: Path = SESSIONS_DIR / "instagram_session.json"

POSTS_PER_PROFILE = 20

MEDIA_TYPE_PHOTO = 1
MEDIA_TYPE_VIDEO = 2
MEDIA_TYPE_CAROUSEL = 8


def _polite_delay() -> None:
    time.sleep(random.uniform(2.0, 8.0))


def login(force_fresh: bool = False) -> Client:
    cfg = load_config()
    cl = Client()

    proxy = cfg.get("proxy", "").strip()
    if proxy:
        cl.set_proxy(proxy)
        log.info("Bruker proxy for Instagram-sesjon")

    username = cfg["instagram_username"]
    password = cfg["instagram_password"]

    if SESSION_FILE.exists() and not force_fresh:
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(username, password)
            cl.get_timeline_feed()
            log.info("Logget inn via persistert sesjon: %s", username)
            return cl
        except Exception as e:
            log.warning("Persistert sesjon ugyldig (%s) — gjør fersk login", e)
            SESSION_FILE.unlink(missing_ok=True)

    cl.login(username, password)
    cl.dump_settings(SESSION_FILE)
    log.info("Fersk login fullført og sesjon persistert: %s", username)
    return cl


def fetch_profile(cl: Client, handle: str) -> dict:
    handle = handle.lstrip("@")
    user = cl.user_info_by_username(handle)
    _polite_delay()
    return {
        "handle": user.username,
        "user_id": user.pk,
        "follower_count": user.follower_count,
        "following_count": user.following_count,
        "media_count": user.media_count,
        "biography": user.biography,
        "is_private": user.is_private,
        "is_verified": user.is_verified,
        "full_name": user.full_name,
    }


def fetch_recent_posts(cl: Client, user_id: int | str, amount: int = POSTS_PER_PROFILE) -> list[dict]:
    medias = cl.user_medias(user_id, amount=amount)
    _polite_delay()

    posts: list[dict] = []
    for m in medias:
        posts.append({
            "id": str(m.pk),
            "media_type": m.media_type,
            "is_video": m.media_type == MEDIA_TYPE_VIDEO,
            "taken_at": m.taken_at,
            "like_count": m.like_count or 0,
            "comment_count": m.comment_count or 0,
            "view_count": getattr(m, "view_count", None) or getattr(m, "play_count", None) or 0,
            "caption_text": m.caption_text or "",
            "hashtags": [tag.lower().lstrip("#") for tag in (m.hashtags or [])],
        })
    return posts
