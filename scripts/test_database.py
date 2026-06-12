"""End-to-end test av SQLite-databasen mot en midlertidig fil."""
import tempfile
from pathlib import Path

from src.database import filter_unseen, get_stats, is_processed, list_approved, record_result
from src.filters import FilterResult


def main() -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Path(tmp) / "test.db"
        print(f"Bruker midlertidig DB: {db}")

        # 1. Tom DB - ingen handles er sett
        assert not is_processed("alice", "instagram", db)
        print("  [OK] Tom DB: is_processed returnerer False")

        # 2. Lagre en godkjent creator
        approved = FilterResult(
            handle="alice", platform="instagram", passed=True,
            niche="weightloss", engagement_rate=3.2, follower_count=50_000,
        )
        record_result(approved, db)
        assert is_processed("alice", "instagram", db)
        print("  [OK] Etter record_result: is_processed returnerer True")

        # 3. Samme handle på TikTok - skal være separat
        assert not is_processed("alice", "tiktok", db)
        print("  [OK] Samme handle pa annen plattform er separat")

        # 4. Lagre en avvist creator
        rejected = FilterResult(
            handle="bob", platform="instagram", passed=False,
            failed_at="1_follower_count", reason="for fa folgere",
            follower_count=3_000,
        )
        record_result(rejected, db)

        # 5. filter_unseen
        unseen = filter_unseen(["alice", "bob", "charlie", "dave"], "instagram", db)
        assert unseen == ["charlie", "dave"], f"Got {unseen}"
        print(f"  [OK] filter_unseen returnerer kun nye: {unseen}")

        # 6. Stats
        stats = get_stats(db)
        assert stats["total"] == 2
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        print(f"  [OK] Stats: {stats}")

        # 7. list_approved
        approved_list = list_approved(db)
        assert len(approved_list) == 1
        assert approved_list[0]["handle"] == "alice"
        assert approved_list[0]["niche"] == "weightloss"
        print(f"  [OK] list_approved returnerer kun godkjente: {approved_list[0]['handle']} ({approved_list[0]['niche']})")

        # 8. Case-insensitive handle-matching
        assert is_processed("ALICE", "instagram", db)
        assert is_processed("@alice", "instagram", db)
        print("  [OK] Handle-normalisering (case, @-prefix) fungerer")

        # 9. Re-lagre samme handle - skal oppdatere, ikke duplisere
        updated = FilterResult(
            handle="alice", platform="instagram", passed=True,
            niche="nutrition", engagement_rate=5.0, follower_count=60_000,
        )
        record_result(updated, db)
        stats2 = get_stats(db)
        assert stats2["total"] == 2, f"Forventet 2, fikk {stats2['total']}"
        approved_after = list_approved(db)
        assert approved_after[0]["niche"] == "nutrition"
        print("  [OK] Re-lagring oppdaterer eksisterende rad")

    print("\nAlle databasetester passerte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
