from __future__ import annotations

from pathlib import Path
import tempfile

from strategic_multiseed import (
    AUTHORITY,
    MIXTURE_SCOPE,
    SCOPE,
    SOLVER_KIND,
    run_multiseed,
)


def test_multiseed_manifest_and_exact_resume() -> None:
    seeds = (501, 502)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = run_multiseed(
            seeds=seeds,
            additional_iterations=1,
            checkpoint_every=1,
            epsilon=0.6,
            output_dir=root,
            workers=1,
            resume=False,
        )
        assert first["authority"] == AUTHORITY
        assert first["scope"] == SCOPE == "HU_ONLY"
        assert first["player_count"] == 2
        assert first["solver_kind"] == SOLVER_KIND == "suit24-exact"
        assert first["action_abstraction"] is False
        assert first["member_count"] == 2
        assert first["ensemble"]["selection_scope"] == MIXTURE_SCOPE
        assert first["ensemble"]["regrets_merged"] is False
        assert first["ensemble"]["policy_switch_within_hand"] is False
        assert abs(sum(first["ensemble"]["weights_by_seed"].values()) - 1.0) < 1e-12
        assert all(row["iterations"] == 1 for row in first["members"])
        assert all(row["episodes"] == 2 for row in first["members"])
        assert all(row["max_actions"] == 232 for row in first["members"])
        assert all(len(row["checkpoint_sha256"]) == 64 for row in first["members"])
        assert all(row["resumed"] is False for row in first["members"])

        second = run_multiseed(
            seeds=seeds,
            additional_iterations=1,
            checkpoint_every=1,
            epsilon=0.6,
            output_dir=root,
            workers=1,
            resume=True,
        )
        assert all(row["iterations"] == 2 for row in second["members"])
        assert all(row["episodes"] == 4 for row in second["members"])
        assert all(row["resumed"] is True for row in second["members"])


def main() -> None:
    test_multiseed_manifest_and_exact_resume()
    print("OPENOFC_STRATEGIC_MULTISEED_TEST=PASS")


if __name__ == "__main__":
    main()
