"""
Valideringsskript for Byggesteg 10 (TikTok-integrasjon).

Bruk:
    python -m scripts.test_tiktok <handle>

Eksempel:
    python -m scripts.test_tiktok mrbeast
"""
import sys

from src.tiktok_client import fetch_profile, fetch_recent_posts


def main() -> int:
    if len(sys.argv) < 2:
        print("Bruk: python -m scripts.test_tiktok <handle>")
        return 2

    handle = sys.argv[1]
    print(f"Henter TikTok-profil: @{handle}")
    profile = fetch_profile(handle)
    for k, v in profile.items():
        print(f"  {k}: {v}")

    print(f"\nHenter siste 20 videoer fra @{handle}...")
    posts = fetch_recent_posts(handle)
    print(f"  Antall videoer hentet: {len(posts)}")
    if posts:
        sample = posts[0]
        print("\n  Eksempel - forste video:")
        print(f"    Tatt: {sample['taken_at']}")
        print(f"    Likes: {sample['like_count']:,} | Kommentarer: {sample['comment_count']:,}")
        print(f"    Shares: {sample['share_count']:,} | Views: {sample['view_count']:,}")
        print(f"    Caption (forste 100 tegn): {sample['caption_text'][:100]}")
        print(f"    Hashtags: {sample['hashtags'][:10]}")

    print("\nByggesteg 10 validert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
