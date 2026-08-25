from __future__ import annotations

from pathlib import Path
import tempfile

from strategic_feasibility import AUTHORITY, SCOPE, SOLVER_KIND, run_probe


def test_hu_scope_and_resource_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        checkpoint = Path(tmp) / "probe.json.gz"
        report = run_probe(
            iterations=2,
            seed=404,
            epsilon=0.6,
            checkpoint=checkpoint,
            projection_iterations=(10, 100),
            max_wall_seconds=120.0,
            max_rss_mb=2048.0,
            max_checkpoint_mb=100.0,
        )
        assert report["authority"] == AUTHORITY
        assert report["scope"] == SCOPE == "HU_ONLY"
        assert report["player_count"] == 2
        assert report["solver_kind"] == SOLVER_KIND == "suit24-exact"
        assert report["action_abstraction"] is False
        assert report["max_actions"] == 232
        assert report["iterations"] == 2
        assert report["episodes"] == 4
        assert report["infosets"] > 0
        assert report["checkpoint_bytes"] > 0
        assert len(report["checkpoint_sha256"]) == 64
        assert report["budget_status"] == "PASS"
        assert len(report["projections"]) == 2
        assert all(
            row["authority"] == "DIAGNOSTIC_FIRST_ORDER_ONLY"
            for row in report["projections"]
        )


def main() -> None:
    test_hu_scope_and_resource_report()
    print("OPENOFC_STRATEGIC_FEASIBILITY_TEST=PASS")


if __name__ == "__main__":
    main()
