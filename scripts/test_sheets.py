"""
Live-test av Google Sheets-eksport.

Skriver en testrad til arket og sletter den etterpa, slik at arket
forblir i samme tilstand som for testen.
"""
from src.filters import FilterResult
from src.sheets import _open_worksheet, append_approved, verify_connection


def main() -> int:
    print("1. Verifiserer tilkobling og deling...")
    info = verify_connection()
    print(f"   Dokument: {info['spreadsheet_title']}")
    print(f"   Fane:     {info['worksheet_title']}")
    print(f"   Rader i arket: {info['current_data_rows']}")

    print("\n2. Skriver test-rad (godkjent fake creator)...")
    fake = FilterResult(
        handle="abahne_test_row_DELETE_ME",
        platform="instagram",
        passed=True,
        niche="stoicism",
        engagement_rate=3.42,
        follower_count=42_000,
        language="en",
    )
    n = append_approved([fake])
    print(f"   Skrev {n} rad(er).")

    print("\n3. Sjekker at raden faktisk er i arket...")
    ws = _open_worksheet()
    all_values = ws.get_all_values()
    last_row = all_values[-1] if all_values else []
    print(f"   Siste rad: {last_row}")
    assert any("abahne_test_row_DELETE_ME" in cell for cell in last_row), \
        "Testraden finnes ikke i arket"

    print("\n4. Rydder opp testraden...")
    ws.delete_rows(len(all_values))
    print("   Slettet.")

    print("\nLive-test fullfort. Google Sheets-eksport fungerer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
