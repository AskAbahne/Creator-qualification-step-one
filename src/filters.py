"""
Early exit-filter med specens 11 kriterier (seksjon 8).

Kjeden stopper ved første kriterium som feiler. Returnerer et FilterResult
med passed-flagg, failed_at-steg, og beregnede verdier.

Plattformer:
  "instagram"  — ER-terskel 2.5%, engagement = likes + kommentarer
  "tiktok"     — ER-terskel 4.0%, engagement = likes + kommentarer + shares
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Optional

from langdetect import DetectorFactory, LangDetectException, detect

from .niches import match_niche

DetectorFactory.seed = 0

FOLLOWER_MIN = 20_000
FOLLOWER_MAX = 150_000
ROUGH_ER_MIN_PCT = 1.0
IG_ER_MIN_PCT = 2.5
TT_ER_MIN_PCT = 4.0
MIN_AVG_VIEWS = 10_000
MIN_POSTS_PER_WEEK = 3
CONSISTENCY_WEEKS = 7
ACCEPTED_LANGS = {"en", "no", "sv", "da"}
SOCIALBLADE_GROWTH_SPIKE = 5_000
SOCIALBLADE_VIEW_MULTIPLIER = 10


NEAR_MISS_MARGIN_PCT = 0.10  # innenfor 10% av terskel = near-miss


@dataclass
class FilterResult:
    handle: str
    platform: str
    passed: bool
    failed_at: Optional[str] = None
    reason: Optional[str] = None
    follower_count: Optional[int] = None
    engagement_rate: Optional[float] = None
    avg_views: Optional[float] = None
    niche: Optional[str] = None
    language: Optional[str] = None
    posts_evaluated: int = 0
    near_miss: bool = False
    near_miss_detail: Optional[str] = None
    extras: dict = field(default_factory=dict)


def _check_near_miss(failed_at: str, follower_count: int, er_pct: float,
                     avg_views: float, platform: str) -> tuple[bool, Optional[str]]:
    if failed_at == "1_follower_count":
        if FOLLOWER_MIN * (1 - NEAR_MISS_MARGIN_PCT) <= follower_count < FOLLOWER_MIN:
            return True, f"{follower_count:,} ({FOLLOWER_MIN - follower_count:,} under {FOLLOWER_MIN:,})"
        if FOLLOWER_MAX < follower_count <= FOLLOWER_MAX * (1 + NEAR_MISS_MARGIN_PCT):
            return True, f"{follower_count:,} ({follower_count - FOLLOWER_MAX:,} over {FOLLOWER_MAX:,})"
    elif failed_at == "6_engagement_full":
        threshold = TT_ER_MIN_PCT if platform == "tiktok" else IG_ER_MIN_PCT
        if er_pct >= threshold * (1 - NEAR_MISS_MARGIN_PCT):
            return True, f"ER={er_pct:.2f}% ({threshold - er_pct:.2f} under {threshold}%)"
    elif failed_at == "7_avg_views":
        if avg_views >= MIN_AVG_VIEWS * (1 - NEAR_MISS_MARGIN_PCT):
            return True, f"avg_views={avg_views:.0f} ({MIN_AVG_VIEWS - avg_views:.0f} under {MIN_AVG_VIEWS:,})"
    return False, None


def _safe_detect(text: str) -> Optional[str]:
    text = (text or "").strip()
    if len(text) < 20:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None


def _engagement_per_post(post: dict, platform: str) -> int:
    base = post["like_count"] + post["comment_count"]
    if platform == "tiktok":
        base += post.get("share_count", 0)
    return base


def _annotate_near_miss(result: FilterResult, platform: str) -> None:
    if result.failed_at is None:
        return
    near, detail = _check_near_miss(
        result.failed_at,
        result.follower_count or 0,
        result.engagement_rate or 0.0,
        result.avg_views or 0.0,
        platform,
    )
    result.near_miss = near
    result.near_miss_detail = detail


def _group_by_calendar_week(dates: list[datetime]) -> Counter:
    weeks: Counter = Counter()
    for d in dates:
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        iso = d.isocalendar()
        weeks[(iso.year, iso.week)] += 1
    return weeks


def check_creator(
    profile: dict,
    posts: list[dict],
    platform: str = "instagram",
    socialblade: Optional[list[dict]] = None,
) -> FilterResult:
    """Kjør alle 11 kriterier i rekkefølge. Avbryt ved første feil.

    socialblade: valgfritt — liste med ukentlige snapshots
                 [{"date": datetime, "follower_delta": int}, ...]
                 Hvis None hoppes kriterium 11 over (vil ikke avvise creatoren).
    """
    handle = profile.get("handle", "?")
    result = FilterResult(handle=handle, platform=platform, passed=False)

    # ---- Kriterium 1: følgertall ----
    follower_count = profile.get("follower_count", 0) or 0
    result.follower_count = follower_count
    if not (FOLLOWER_MIN <= follower_count <= FOLLOWER_MAX):
        result.failed_at = "1_follower_count"
        result.reason = f"{follower_count:,} utenfor [{FOLLOWER_MIN:,}, {FOLLOWER_MAX:,}]"
        _annotate_near_miss(result, platform)
        return result

    # ---- Kriterium 3: språk (bio) ----  (kjøres før 2 fordi 2 trenger poster)
    bio_lang = _safe_detect(profile.get("biography", ""))
    if bio_lang and bio_lang not in ACCEPTED_LANGS:
        result.language = bio_lang
        result.failed_at = "3_language_bio"
        result.reason = f"bio-språk={bio_lang} utenfor {sorted(ACCEPTED_LANGS)}"
        return result

    # ---- Kriterium 4: nisjefilter (bio) ----
    bio_niche = match_niche(profile.get("biography", ""))
    if not bio_niche:
        result.failed_at = "4_niche_bio"
        result.reason = "ingen nisjematch i bio"
        _annotate_near_miss(result, platform)
        return result
    result.niche = bio_niche
    result.extras["niche_bio"] = bio_niche

    # ---- Kriterium 5: hente 20 poster (dataforutsetning) ----
    if not posts:
        result.failed_at = "5_no_posts"
        result.reason = "ingen poster tilgjengelig"
        return result
    result.posts_evaluated = len(posts)

    # ---- Kriterium 2 + 6: engagement rate (full beregning) ----
    avg_eng = mean(_engagement_per_post(p, platform) for p in posts)
    er_pct = (avg_eng / follower_count) * 100
    result.engagement_rate = round(er_pct, 2)
    if er_pct < ROUGH_ER_MIN_PCT:
        result.failed_at = "2_rough_engagement"
        result.reason = f"ER={er_pct:.2f}% under {ROUGH_ER_MIN_PCT}% (grov)"
        return result
    er_threshold = TT_ER_MIN_PCT if platform == "tiktok" else IG_ER_MIN_PCT
    if er_pct < er_threshold:
        result.failed_at = "6_engagement_full"
        result.reason = f"ER={er_pct:.2f}% under {er_threshold}% ({platform})"
        _annotate_near_miss(result, platform)
        return result

    # ---- Kriterium 7: snitt videovisninger ----
    if platform == "instagram":
        videos = [p for p in posts if p.get("is_video")]
    else:
        videos = posts  # alle TikToks er videoer
    if not videos:
        result.failed_at = "7_no_videos"
        result.reason = "ingen videoer i siste 20 poster"
        return result
    avg_views = mean(v["view_count"] for v in videos)
    result.avg_views = round(avg_views, 0)
    if avg_views < MIN_AVG_VIEWS:
        result.failed_at = "7_avg_views"
        result.reason = f"snitt views={avg_views:,.0f} under {MIN_AVG_VIEWS:,}"
        _annotate_near_miss(result, platform)
        return result

    # ---- Kriterium 8: postingsfrekvens (≥3 per uke i 7 uker bakover) ----
    # Ekskluderer den nåværende ufullstendige uka — vi krever 7 KOMPLETTE uker.
    post_dates = [p["taken_at"] for p in posts if p.get("taken_at")]
    now_utc = datetime.now(timezone.utc)
    this_monday = (now_utc - timedelta(days=now_utc.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cutoff = this_monday - timedelta(weeks=CONSISTENCY_WEEKS)
    weekly = _group_by_calendar_week(post_dates)
    relevant_weeks = {
        (year, w): count for (year, w), count in weekly.items()
        if cutoff <= datetime.fromisocalendar(year, w, 1).replace(tzinfo=timezone.utc) < this_monday
    }
    if len(relevant_weeks) < CONSISTENCY_WEEKS:
        result.failed_at = "8_consistency_weeks"
        result.reason = f"kun {len(relevant_weeks)} av {CONSISTENCY_WEEKS} uker har poster"
        return result
    under = [(yw, c) for yw, c in relevant_weeks.items() if c < MIN_POSTS_PER_WEEK]
    if under:
        result.failed_at = "8_posting_frequency"
        result.reason = f"{len(under)} uker har under {MIN_POSTS_PER_WEEK} poster"
        return result

    # ---- Kriterium 9: nisjefilter (full = bio + captions + hashtags) ----
    full_text = profile.get("biography", "")
    for p in posts:
        full_text += " " + (p.get("caption_text") or "")
        full_text += " " + " ".join(p.get("hashtags") or [])
    full_niche = match_niche(full_text)
    if not full_niche:
        result.failed_at = "9_niche_full"
        result.reason = "ingen nisjematch i full tekst"
        return result
    result.niche = full_niche  # full er mer presis enn bio-only

    # ---- Kriterium 10: språk (full = captions) ----
    captions = " ".join(p.get("caption_text", "") for p in posts).strip()
    full_lang = _safe_detect(captions)
    result.language = full_lang or bio_lang
    if full_lang and full_lang not in ACCEPTED_LANGS:
        result.failed_at = "10_language_full"
        result.reason = f"caption-språk={full_lang} utenfor {sorted(ACCEPTED_LANGS)}"
        return result

    # ---- Kriterium 11: fake-follower-sjekk via Social Blade ----
    if socialblade is not None:
        for snap in socialblade:
            delta = snap.get("follower_delta", 0)
            if delta < SOCIALBLADE_GROWTH_SPIKE:
                continue
            snap_date = snap["date"]
            same_week_videos = [
                v for v in videos
                if v.get("taken_at")
                and abs((v["taken_at"] - snap_date).days) <= 7
            ]
            threshold = avg_views * SOCIALBLADE_VIEW_MULTIPLIER
            if not any(v["view_count"] >= threshold for v in same_week_videos):
                result.failed_at = "11_fake_followers"
                result.reason = (
                    f"vekstspike +{delta:,} følgere uten viral video "
                    f"(under {threshold:,.0f} views)"
                )
                return result

    result.passed = True
    return result
