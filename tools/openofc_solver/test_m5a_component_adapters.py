from __future__ import annotations

import math

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import HUContinuationState, zero_continuation_values
from m4w_outcome_model import (
    SparseFantasyOutcomeModel,
    policy_api_has_hidden_opponent_argument as m4w_hidden_api,
)
from m4x_robust_support import freeze_continuation_family
from m4z_outer_bellman import default_blocked_registry
from m5a_fantasy_fantasy_oracle import (
    FantasyFantasyFixedModelOracle,
    freeze_policy_snapshot as freeze_ff_snapshot,
)
from m5a_normal_normal_oracle import (
    NormalNormalFixedPolicyOracle,
    freeze_policy_snapshot as freeze_nn_snapshot,
    policy_api_has_hidden_opponent_argument as nn_hidden_api,
)
from strategic_advantage_model import SparseActionAdvantageModel


def test_normal_normal_fixed_policy_oracle_is_deterministic_and_sha_bound() -> None:
    values = zero_continuation_values()
    model = SparseActionAdvantageModel(buckets=1 << 8)
    snapshot = freeze_nn_snapshot(
        model,
        training_continuation_values=values,
        provenance="m5a-nn-unit-fixture",
    )
    oracle = NormalNormalFixedPolicyOracle(
        model,
        snapshot,
        samples=2,
        base_seed=17,
    )
    state = HUContinuationState(0, 0, 0)
    first = oracle.evaluate(state, values)
    second = oracle.evaluate(state, values)
    _checked, expected_sha = continuation_fingerprint(values)
    assert first == second
    assert first.continuation_sha256 == expected_sha
    assert first.samples == 2
    assert math.isfinite(first.p0_value)
    assert first.standard_error >= 0.0
    assert not nn_hidden_api()


def test_fantasy_fantasy_oracle_fails_closed_outside_m4x_region() -> None:
    zero = zero_continuation_values()
    family = freeze_continuation_family(
        {"anchor0": zero},
        radius_linf=0.0,
        provenance="m5a-ff-unit-fixture",
        source_sha256="a" * 64,
    )
    model = SparseFantasyOutcomeModel(buckets=1 << 8)
    snapshot = freeze_ff_snapshot(
        model,
        family,
        synthetic_worlds_per_anchor=1,
        max_candidates_per_anchor=2,
        provenance="m5a-ff-unit-fixture",
    )
    oracle = FantasyFantasyFixedModelOracle(
        model,
        family,
        snapshot,
        samples=1,
        base_seed=19,
    )
    escaped = dict(zero)
    escaped[HUContinuationState(1, 14, 14)] = 1.0
    try:
        oracle.evaluate(HUContinuationState(0, 14, 14), escaped)
    except RuntimeError as exc:
        assert "escaped M4X" in str(exc)
    else:
        raise AssertionError(
            "Fantasy/Fantasy oracle accepted V outside M4X region"
        )
    assert not m4w_hidden_api()


def test_all_real_routes_remain_blocked_until_certification() -> None:
    manifest = default_blocked_registry().freeze_manifest()
    assert manifest.blocked == 50
    assert manifest.ready_certified == 0


def main() -> None:
    test_normal_normal_fixed_policy_oracle_is_deterministic_and_sha_bound()
    test_fantasy_fantasy_oracle_fails_closed_outside_m4x_region()
    test_all_real_routes_remain_blocked_until_certification()
    print("OPENOFC_M5A_COMPONENT_ADAPTERS_GATE=PASS")


if __name__ == "__main__":
    main()
