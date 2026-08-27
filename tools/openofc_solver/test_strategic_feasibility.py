from __future__ import annotations

from pathlib import Path
import tempfile

from strategic_feasibility import AUTHORITY, SCOPE, SOLVER_KIND, run_probe


def test_hu_scope_resource_and_exact_key_reuse_report() -> None:
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

        reuse = report["reuse"]
        assert reuse["node_touches"] == report["episodes"] * 10 == 40
        assert reuse["unique_infosets"] == report["infosets"]
        assert 0.0 <= reuse["infoset_reuse_fraction"] <= 1.0
        assert reuse["regret_updates"] == report["total_visits"] == 20
        assert 0.0 <= reuse["regret_reuse_fraction"] <= 1.0
        assert reuse["max_regret_visits"] >= 1
        assert set(reuse["by_round"]) == {"0", "1", "2", "3", "4"}
        assert sum(row["infosets"] for row in reuse["by_round"].values()) == report["infosets"]
        for row in reuse["by_round"].values():
            assert row["node_touches"] == report["episodes"] * 2 == 8
            assert 0.0 <= row["infoset_reuse_fraction"] <= 1.0
            assert 0.0 <= row["regret_reuse_fraction"] <= 1.0


def main() -> None:
    test_hu_scope_resource_and_exact_key_reuse_report()
    print("OPENOFC_STRATEGIC_FEASIBILITY_TEST=PASS")


if __name__ == "__main__":
    main()
