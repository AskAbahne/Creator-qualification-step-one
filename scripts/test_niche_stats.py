"""Test get_stats_by_niche() med syntetiske rader."""
import tempfile
from pathlib import Path

from src.database import get_stats_by_niche, record_result
from src.filters import FilterResult


def main() -> int:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Path(tmp) / "test.db"

        # 10 stoicism: 3 godkjent (30%)
        for i in range(7):
            record_result(FilterResult(
                handle=f"sto_rej_{i}", platform="instagram",
                passed=False, failed_at="6_engagement_full",
                niche="stoicism", follower_count=50_000,
            ), db_path=db)
        for i in range(3):
            record_result(FilterResult(
                handle=f"sto_app_{i}", platform="instagram",
                passed=True, niche="stoicism",
                engagement_rate=3.5, follower_count=60_000,
            ), db_path=db)

        # 20 weightloss: 1 godkjent (5%)
        for i in range(19):
            record_result(FilterResult(
                handle=f"wl_rej_{i}", platform="instagram",
                passed=False, failed_at="8_posting_frequency",
                niche="weightloss", follower_count=40_000,
            ), db_path=db)
        record_result(FilterResult(
            handle="wl_app_0", platform="instagram", passed=True,
            niche="weightloss", engagement_rate=4.0, follower_count=55_000,
        ), db_path=db)

        # 5 nutrition: 0 godkjent (0%)
        for i in range(5):
            record_result(FilterResult(
                handle=f"nut_rej_{i}", platform="instagram",
                passed=False, failed_at="7_avg_views",
                niche="nutrition", follower_count=45_000,
            ), db_path=db)

        # 3 uten nisje (feilet for K4) - skal IKKE telles
        for i in range(3):
            record_result(FilterResult(
                handle=f"nonich_{i}", platform="instagram",
                passed=False, failed_at="3_language_bio",
                niche=None, follower_count=30_000,
            ), db_path=db)

        stats = get_stats_by_niche(db)
        print("Niche-stats:")
        for s in stats:
            print(f"  {s['niche']:20s}  prosessert={s['processed']:3d}  "
                  f"godkjent={s['approved']:3d}  rate={s['approval_rate']:5.1f}%")

        # Verifiseringer
        by_niche = {s["niche"]: s for s in stats}
        assert by_niche["stoicism"]["processed"] == 10
        assert by_niche["stoicism"]["approved"] == 3
        assert by_niche["stoicism"]["approval_rate"] == 30.0

        assert by_niche["weightloss"]["processed"] == 20
        assert by_niche["weightloss"]["approved"] == 1
        assert by_niche["weightloss"]["approval_rate"] == 5.0

        assert by_niche["nutrition"]["processed"] == 5
        assert by_niche["nutrition"]["approved"] == 0
        assert by_niche["nutrition"]["approval_rate"] == 0.0

        # Skal sorteres etter approved DESC
        assert [s["niche"] for s in stats] == ["stoicism", "weightloss", "nutrition"]

        # Skal IKKE inkludere creators uten nisje
        assert "nonich_0" not in str(stats)

        print("\nAlle niche-stats-tester passerte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
