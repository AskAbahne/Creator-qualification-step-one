"""
Valideringsskript for Byggesteg 1 og 2 (specens 0.9 rad 1 og 2).
Kjøres MANUELT først når Instagram-kontoen er moden (lørdag/søndag).

Kriterier:
- Steg 1: hent profil for én kjent creator uten feil.
- Steg 2: hent siste 20 poster med captions og hashtags.

Bruk:
    python -m scripts.test_instagram_login <handle>

Eksempel:
    python -m scripts.test_instagram_login natgeo
"""
import logging
import sys

from src.instagram_client import fetch_profile, fetch_recent_posts, login

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> int:
    if len(sys.argv) < 2:
        print("Bruk: python -m scripts.test_instagram_login <handle>")
        return 2

    handle = sys.argv[1]

    print("Logger inn på Instagram...")
    cl = login()
    print("OK — innlogging vellykket.\n")

    print(f"Henter profil: @{handle}")
    profile = fetch_profile(cl, handle)
    for key, value in profile.items():
        print(f"  {key}: {value}")
    print("\nByggesteg 1 validert.\n")

    print(f"Henter siste 20 poster fra @{handle}...")
    posts = fetch_recent_posts(cl, profile["user_id"])
    print(f"  Antall poster hentet: {len(posts)}")
    videos = [p for p in posts if p["is_video"]]
    print(f"  Videoer (Reels): {len(videos)}")
    print(f"  Total likes (siste 20): {sum(p['like_count'] for p in posts):,}")
    print(f"  Total kommentarer (siste 20): {sum(p['comment_count'] for p in posts):,}")

    if posts:
        sample = posts[0]
        print("\n  Eksempel - første post:")
        print(f"    Tatt: {sample['taken_at']}")
        print(f"    Likes: {sample['like_count']:,} | Kommentarer: {sample['comment_count']:,} | Views: {sample['view_count']:,}")
        print(f"    Caption (første 100 tegn): {sample['caption_text'][:100]}")
        print(f"    Hashtags: {sample['hashtags'][:10]}")

    print("\nByggesteg 2 validert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
