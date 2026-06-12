"""Test at nisje-matching fungerer som specens seksjon 5 sier."""
from src.niches import NICHES, match_niche


def run() -> int:
    print("Antall nisjer:", len(NICHES))

    cases = [
        ("My weightlosstransformation journey", "weightloss", "sterkt nokkelord"),
        ("healing therapy wellness mindfulness extra", "mental_health", "4 svake (rene, ingen overlapp)"),
        ("healing therapy wellness extra", None, "kun 3 svake -> ingen match"),
        ("nice day at the beach", None, "generisk -> ingen match"),
        ("stoicism diet fitness healthy", "stoicism", "sterkt slar svakt"),
        ("gym workout gymlife fit", "strength_training", "4 svake fra strength_training"),
        ("Just sharing my macros and mealprep", "nutrition", "sterke i nutrition"),
        ("textinggirls and datingtips", "dating_men", "sterke i dating_men"),
        ("discipline only", "productivity", "discipline er STERKT i productivity (spec-overlapp)"),
    ]

    failures = 0
    for text, expected, label in cases:
        got = match_niche(text)
        ok = got == expected
        status = "OK " if ok else "FEIL"
        print(f"  [{status}] {label}: forventet={expected}, fikk={got}")
        if not ok:
            failures += 1

    print()
    if failures:
        print(f"{failures} test(er) feilet.")
        return 1
    print("Alle tester passerte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
