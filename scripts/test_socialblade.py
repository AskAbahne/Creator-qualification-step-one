"""Live-test av Social Blade-scraping mot en kjent offentlig profil."""
import sys

from src.socialblade import scrape_weekly_growth


def main() -> int:
    handle = sys.argv[1] if len(sys.argv) > 1 else "garyvee"
    platform = sys.argv[2] if len(sys.argv) > 2 else "instagram"

    print(f"Scraper Social Blade for @{handle} ({platform})...")
    data = scrape_weekly_growth(handle, platform)

    if not data:
        print("Ingen data hentet.")
        print("Mulige arsaker: profil ikke pa Social Blade, anti-bot, eller selektorer endret.")
        return 1

    print(f"Hentet {len(data)} ukentlige snapshots")
    print("\nNyeste 5 uker:")
    for snap in data[:5]:
        print(f"  {snap['date'].date()}  delta: {snap['follower_delta']:+,}")

    spikes = [s for s in data if s["follower_delta"] >= 5000]
    print(f"\nTotalt {len(spikes)} uker med 5k+ vekst-spike (specens fake-follower-terskel)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
