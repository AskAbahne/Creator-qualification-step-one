"""
Instagram-klient med konto-rotasjon, dedikerte proxyer og helse-tracking.

Eksponerer:
  - InstagramPool: holder en pool av Client-instanser, én per aktiv konto
  - login_all() / next_client(): hente neste konto i round-robin
  - fetch_profile() / fetch_recent_posts(): tar Client som argument

Helse-events logges automatisk til SQLite ved login, profilkall og posthenting.
"""
from __future__ import annotations

import itertools
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    ClientError,
    LoginRequired,
    PleaseWaitFewMinutes,
)

from .config import SESSIONS_DIR, load_config
from .database import log_health_event

log = logging.getLogger(__name__)

POSTS_PER_PROFILE = 20
MEDIA_TYPE_PHOTO = 1
MEDIA_TYPE_VIDEO = 2
MEDIA_TYPE_CAROUSEL = 8


def _polite_delay() -> None:
    time.sleep(random.uniform(2.0, 8.0))


def _session_file(label: str) -> Path:
    return SESSIONS_DIR / f"instagram_session_{label}.json"


@dataclass
class AccountSlot:
    label: str
    username: str
    password: str
    proxy: str
    client: Optional[Client] = None
    session_id: Optional[int] = None


@dataclass
class InstagramPool:
    """Pool av Instagram-kontoer med round-robin-rotasjon."""
    slots: list[AccountSlot] = field(default_factory=list)
    _cycle: Optional[itertools.cycle] = None

    def __post_init__(self):
        self._cycle = itertools.cycle(self.slots) if self.slots else None

    @classmethod
    def from_config(cls, session_id: Optional[int] = None) -> "InstagramPool":
        cfg = load_config()
        slots = []
        for acc in cfg["instagram_accounts"]:
            if acc.get("warmup_mode", False):
                log.info("Hopper over konto %s (warmup_mode)", acc["label"])
                continue
            slots.append(AccountSlot(
                label=acc["label"],
                username=acc["username"],
                password=acc["password"],
                proxy=acc.get("proxy", ""),
                session_id=session_id,
            ))
        if not slots:
            raise RuntimeError(
                "Ingen aktive Instagram-kontoer (alle i warmup_mode?). "
                "Sett minst én konto med warmup_mode: false."
            )
        return cls(slots=slots)

    def login_all(self) -> None:
        for slot in self.slots:
            self._login_slot(slot)

    def _login_slot(self, slot: AccountSlot) -> None:
        cl = Client()
        if slot.proxy:
            cl.set_proxy(slot.proxy)
            log.info("[%s] Bruker proxy", slot.label)

        sess_file = _session_file(slot.label)
        try:
            if sess_file.exists():
                cl.load_settings(sess_file)
                cl.login(slot.username, slot.password)
                cl.get_timeline_feed()
                log.info("[%s] Logget inn via persistert sesjon", slot.label)
            else:
                cl.login(slot.username, slot.password)
                cl.dump_settings(sess_file)
                log.info("[%s] Fersk login fullført", slot.label)
            log_health_event(slot.label, "login_ok", session_id=slot.session_id)
        except ChallengeRequired as e:
            log_health_event(slot.label, "challenge_required",
                             details=str(e), session_id=slot.session_id)
            raise
        except (LoginRequired, ClientError) as e:
            log_health_event(slot.label, "login_fail",
                             details=str(e), session_id=slot.session_id)
            sess_file.unlink(missing_ok=True)
            raise
        slot.client = cl

    def next_client(self) -> AccountSlot:
        """Round-robin neste konto. Hopper over slots som er pauset."""
        for _ in range(len(self.slots) * 2):
            slot = next(self._cycle)
            if slot.client is not None:
                return slot
        raise RuntimeError("Ingen tilgjengelige kontoer i pool")

    def pause_account(self, label: str, reason: str) -> None:
        for slot in self.slots:
            if slot.label == label:
                slot.client = None
                log_health_event(label, "paused", details=reason,
                                 session_id=slot.session_id)
                log.warning("Pauser konto %s: %s", label, reason)


def fetch_profile(cl: Client, handle: str, account_label: str = "?",
                  session_id: Optional[int] = None) -> dict:
    handle = handle.lstrip("@")
    try:
        user = cl.user_info_by_username(handle)
        _polite_delay()
    except PleaseWaitFewMinutes as e:
        log_health_event(account_label, "rate_limited",
                         details=str(e), session_id=session_id)
        raise
    except ChallengeRequired as e:
        log_health_event(account_label, "challenge_required",
                         details=str(e), session_id=session_id)
        raise
    except Exception as e:
        log_health_event(account_label, "api_error",
                         details=str(e)[:200], session_id=session_id)
        raise

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


def fetch_recent_posts(cl: Client, user_id, amount: int = POSTS_PER_PROFILE,
                       account_label: str = "?",
                       session_id: Optional[int] = None) -> list[dict]:
    try:
        medias = cl.user_medias(user_id, amount=amount)
        _polite_delay()
    except PleaseWaitFewMinutes as e:
        log_health_event(account_label, "rate_limited",
                         details=str(e), session_id=session_id)
        raise
    except ChallengeRequired as e:
        log_health_event(account_label, "challenge_required",
                         details=str(e), session_id=session_id)
        raise
    except Exception as e:
        log_health_event(account_label, "api_error",
                         details=str(e)[:200], session_id=session_id)
        raise

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


# Bakoverkompatibilitet: gammel login() returnerer første aktive Client
def login(force_fresh: bool = False) -> Client:
    pool = InstagramPool.from_config()
    pool.login_all()
    return pool.slots[0].client
