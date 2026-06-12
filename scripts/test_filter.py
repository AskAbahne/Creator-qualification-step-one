"""Tester 11-kriterie-filteret med syntetiske creators.

Hvert testtilfelle bygger en mock-profil + mock-poster og sjekker at filteret
enten godkjenner eller avviser med riktig årsak.
"""
from datetime import datetime, timedelta, timezone

from src.filters import check_creator


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_post(days_ago: int, likes=2000, comments=200, views=15000, caption="my fitness journey #weightloss", is_video=True):
    return {
        "id": f"p{days_ago}",
        "media_type": 2 if is_video else 1,
        "is_video": is_video,
        "taken_at": _now() - timedelta(days=days_ago),
        "like_count": likes,
        "comment_count": comments,
        "view_count": views,
        "caption_text": caption,
        "hashtags": ["weightloss", "fatloss", "fitness"],
    }


def _make_consistent_posts(weeks: int = 8, posts_per_week: int = 3):
    """Lag poster: posts_per_week stykker hver uke i `weeks` uker bakover."""
    posts = []
    for w in range(weeks):
        for i in range(posts_per_week):
            posts.append(_make_post(days_ago=w * 7 + i + 1))
    return posts


GOOD_PROFILE = {
    "handle": "test_creator",
    "user_id": 1,
    "follower_count": 75_000,
    "biography": "I help people lose weight. #weightloss coach. Daily content about #caloriedeficit and #fatlosstips for english speakers worldwide.",
    "is_private": False,
}


def case(name, expected_pass, expected_fail_step, profile, posts, platform="instagram", socialblade=None):
    res = check_creator(profile, posts, platform=platform, socialblade=socialblade)
    ok = (res.passed == expected_pass) and (res.failed_at == expected_fail_step)
    status = "OK " if ok else "FEIL"
    detail = f"passed={res.passed} failed_at={res.failed_at} reason={res.reason}"
    print(f"  [{status}] {name}")
    print(f"         {detail}")
    return ok


def main() -> int:
    print("Tester 11-kriterie-filter:\n")
    results = []

    # 1. Godkjent creator
    results.append(case(
        "Creator som passerer alle 11 kriterier",
        True, None,
        GOOD_PROFILE, _make_consistent_posts(),
    ))

    # 2. For få følgere
    profile_low = {**GOOD_PROFILE, "follower_count": 5_000}
    results.append(case(
        "K1 feil: for få følgere (5k)",
        False, "1_follower_count",
        profile_low, _make_consistent_posts(),
    ))

    # 3. For mange følgere
    profile_high = {**GOOD_PROFILE, "follower_count": 500_000}
    results.append(case(
        "K1 feil: for mange følgere (500k)",
        False, "1_follower_count",
        profile_high, _make_consistent_posts(),
    ))

    # 4. Feil språk i bio
    profile_fr = {**GOOD_PROFILE, "biography": "Bonjour je suis coach minceur, je vous aide a perdre du poids chaque jour pour rester en bonne sante mes amis"}
    results.append(case(
        "K3 feil: fransk bio",
        False, "3_language_bio",
        profile_fr, _make_consistent_posts(),
    ))

    # 5. Ingen nisje i bio
    profile_no_niche = {**GOOD_PROFILE, "biography": "Just sharing photos from my trips around the world. Love and good vibes only."}
    results.append(case(
        "K4 feil: ingen nisjematch i bio",
        False, "4_niche_bio",
        profile_no_niche, _make_consistent_posts(),
    ))

    # 6. Lav engagement rate — mellom grov (1%) og full (2.5%) terskel
    # 75k * 0.015 = 1125 eng/post -> 1100 likes + 25 comments = ER 1.5%
    low_eng_posts = _make_consistent_posts()
    for p in low_eng_posts:
        p["like_count"] = 1100
        p["comment_count"] = 25
    results.append(case(
        "K6 feil: ER under 2.5% (IG) men over grov-terskel",
        False, "6_engagement_full",
        GOOD_PROFILE, low_eng_posts,
    ))

    # 7. Lave snitt-views
    low_view_posts = _make_consistent_posts()
    for p in low_view_posts:
        p["view_count"] = 500
    results.append(case(
        "K7 feil: snitt views under 10k",
        False, "7_avg_views",
        GOOD_PROFILE, low_view_posts,
    ))

    # 8. For få poster per uke
    sparse_posts = _make_consistent_posts(weeks=8, posts_per_week=1)
    results.append(case(
        "K8 feil: kun 1 post per uke",
        False, "8_posting_frequency",
        GOOD_PROFILE, sparse_posts,
    ))

    # 9. Spike i følgere uten viral video → fake follower
    sb_data = [{"date": _now() - timedelta(days=10), "follower_delta": 20_000}]
    results.append(case(
        "K11 feil: vekstspike uten viral video",
        False, "11_fake_followers",
        GOOD_PROFILE, _make_consistent_posts(), socialblade=sb_data,
    ))

    # 10. Spike MED viral video → OK (spike-dato sammenfaller med eksisterende post)
    viral_posts = _make_consistent_posts()
    viral_posts[1]["view_count"] = 500_000  # 33x snittet
    sb_data_ok = [{"date": viral_posts[1]["taken_at"], "follower_delta": 20_000}]
    results.append(case(
        "K11 OK: vekstspike forklart av viral video",
        True, None,
        GOOD_PROFILE, viral_posts, socialblade=sb_data_ok,
    ))

    # 11. TikTok terskel (4%) - skal feile med IG-godkjent ER
    tt_posts = _make_consistent_posts()
    for p in tt_posts:
        p["share_count"] = 0
        p["like_count"] = 2000
        p["comment_count"] = 200  # ER = (2200/75000) ~ 2.9% — godkjent IG, ikke TT
    results.append(case(
        "TT-terskel: 2.9% feiler på TikTok (krav 4%)",
        False, "6_engagement_full",
        GOOD_PROFILE, tt_posts, platform="tiktok",
    ))

    failures = sum(1 for r in results if not r)
    total = len(results)
    print(f"\nResultat: {total - failures}/{total} passerte")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
