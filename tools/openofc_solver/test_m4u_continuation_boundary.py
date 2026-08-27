from __future__ import annotations

import copy
import random

from engine import Board
from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
)
from fantasy_fantasy_payoff import build_exact_support_payoff_matrix
from hu_continuation import HUContinuationState, all_states, zero_continuation_values
from m4u_continuation_boundary import (
    ROUTE_BLOCKED,
    ROUTE_CERTIFIED,
    build_factorized_support_payoff,
    certification_route,
    freeze_certification,
    materialize_factorized_payoff,
    validate_certification,
)
from plan_m4t_adaptive_scale import (
    Requirements,
    Targets,
    build_plan,
    sha,
)


def two_arrangements(packet):
    cards = list(packet)
    a = arrangement_from_board(
        packet,
        Board(
            top=tuple(cards[0:3]),
            middle=tuple(cards[3:8]),
            bottom=tuple(cards[8:13]),
        ),
    )
    cards[0], cards[9] = cards[9], cards[0]
    b = arrangement_from_board(
        packet,
        Board(
            top=tuple(cards[0:3]),
            middle=tuple(cards[3:8]),
            bottom=tuple(cards[8:13]),
        ),
    )
    return a, b


def fake_report(seed: int):
    states = ("b0:p0f14:p1f14", "b1:p0f14:p1f14")
    heldout = []
    for state in states:
        for world in range(2):
            heldout.append(
                {
                    "state": state,
                    "world_index": world,
                    "p0_candidates": 4,
                    "p1_candidates": 4,
                    "p0_jokers": 0,
                    "p1_jokers": 0,
                    "support_restricted_deviation": 0.1,
                    "p0_support_deviation": 0.05,
                    "p1_support_deviation": 0.05,
                    "action_value_mae": 0.1,
                    "action_value_max_abs_error": 0.2,
                    "p0_sampled_exact_support_gap": 0.1,
                    "p1_sampled_exact_support_gap": 0.1,
                    "support_gap_samples_per_player": 2,
                }
            )
    report = {
        "schema": "openofc-m4s-heldout-report-v1",
        "authority": "test",
        "promotion_blocked": True,
        "generator_fingerprint": "generator-v1",
        "continuation_fingerprint": "continuation-anchor-v1",
        "states": list(states),
        "config": {
            "base_seed": seed,
            "train_worlds_per_state": 2,
            "heldout_worlds_per_state": 2,
            "synthetic_worlds": 2,
            "max_candidates": 8,
            "selfplay_iterations": 2,
            "epochs_per_iteration": 2,
            "temperature": 1.0,
            "model_buckets": 65536,
            "replay_capacity": 100000,
            "support_gap_samples": 2,
        },
        "train_iterations": [],
        "heldout": heldout,
        "heldout_aggregate": {},
        "model_checkpoint_sha256": "model",
        "error_budgets": {},
        "next_action": "test",
    }
    report["sha256"] = sha(report)
    return report


def test_factorization_exact_under_multiple_continuations() -> None:
    meta = HUContinuationState(0, 14, 14)
    world = FantasyFantasyWorld(
        meta, sample_fantasy_fantasy_plan(random.Random(20260829), meta)
    )
    support0 = two_arrangements(world.plan.packet_for(0))
    support1 = two_arrangements(world.plan.packet_for(1))
    factor = build_factorized_support_payoff(world, support0, support1)

    zero = zero_continuation_values()
    direct0 = build_exact_support_payoff_matrix(world, support0, support1, zero)
    moved0 = materialize_factorized_payoff(factor, zero)
    assert direct0.p0_values == moved0.p0_values
    assert direct0.continuation_fingerprint == moved0.continuation_fingerprint

    changed = dict(zero)
    for index, state in enumerate(all_states()):
        changed[state] = ((index % 11) - 5) * 0.125
    direct1 = build_exact_support_payoff_matrix(world, support0, support1, changed)
    moved1 = materialize_factorized_payoff(factor, changed)
    assert direct1.p0_values == moved1.p0_values
    assert direct1.continuation_fingerprint == moved1.continuation_fingerprint
    assert moved0.p0_values != moved1.p0_values


def test_certificate_is_state_and_continuation_sha_bound() -> None:
    reports = [fake_report(seed) for seed in (1, 2, 3)]
    plan = build_plan(
        reports,
        Requirements(3, 6, 12),
        Targets(0.2, 0.2, 0.2, 0.3),
    )
    manifest = freeze_certification(
        plan, reports[0], provenance="synthetic-regression-only"
    )
    validate_certification(manifest)
    assert set(manifest["certified_states"]) == {
        "b0:p0f14:p1f14",
        "b1:p0f14:p1f14",
    }

    # The synthetic report fingerprint is deliberately not a real continuation
    # SHA, so no runtime continuation vector can accidentally match it.
    values = zero_continuation_values()
    state = HUContinuationState(0, 14, 14)
    assert certification_route(manifest, state, values) == ROUTE_BLOCKED

    # Bind a test copy to the exact zero-vector fingerprint and re-hash it.
    from fantasy_fantasy_payoff import continuation_fingerprint
    from m4u_continuation_boundary import _sha

    bound = copy.deepcopy(manifest)
    bound["continuation_fingerprint"] = continuation_fingerprint(values)[1]
    bound["sha256"] = _sha(bound)
    assert certification_route(bound, state, values) == ROUTE_CERTIFIED
    assert (
        certification_route(bound, HUContinuationState(0, 14, 15), values)
        == ROUTE_BLOCKED
    )

    changed = dict(values)
    changed[HUContinuationState(1, 0, 0)] = 0.01
    assert certification_route(bound, state, changed) == ROUTE_BLOCKED


def test_partial_tier_cannot_be_frozen() -> None:
    reports = [fake_report(seed) for seed in (1, 2, 3)]
    for report in reports:
        report["states"] = ["b0:p0f14:p1f14"]
        report["heldout"] = [
            row for row in report["heldout"] if row["state"] == "b0:p0f14:p1f14"
        ]
        report["sha256"] = sha(report)
    plan = build_plan(
        reports,
        Requirements(3, 6, 12),
        Targets(0.2, 0.2, 0.2, 0.3),
    )
    try:
        freeze_certification(plan, reports[0], provenance="partial-tier-test")
        raise AssertionError("partial coverage tier was incorrectly certified")
    except ValueError as exc:
        assert "no complete" in str(exc)


def main() -> None:
    test_factorization_exact_under_multiple_continuations()
    test_certificate_is_state_and_continuation_sha_bound()
    test_partial_tier_cannot_be_frozen()
    print("OPENOFC_M4U_CONTINUATION_BOUNDARY=PASS")


if __name__ == "__main__":
    main()
