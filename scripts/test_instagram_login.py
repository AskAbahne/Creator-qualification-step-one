"""
Valideringsskript for Byggesteg 1 (specens 0.9 rad 1).
Kjøres MANUELT først når Instagram-kontoen er moden (lørdag/søndag).

Kriterium: hent profil for én kjent creator uten feil.

Bruk:
    python -m scripts.test_instagram_login <handle>

Eksempel:
    python -m scripts.test_instagram_login natgeo
"""
import logging
import sys

from src.instagram_client import fetch_profile, login

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main() -> int:
    if len(sys.argv) < 2:
        print("Bruk: python -m scripts.test_instagram_login <handle>")
        return 2

    handle = sys.argv[1]

    print(f"Logger inn på Instagram...")
    cl = login()
    print("OK — innlogging vellykket.\n")

    print(f"Henter profil: @{handle}")
    profile = fetch_profile(cl, handle)
    for key, value in profile.items():
        print(f"  {key}: {value}")

    print("\nByggesteg 1 validert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
