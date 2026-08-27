from __future__ import annotations

import inspect
import random

from engine import Board
from fantasy_fantasy_kernel import FantasyFantasyWorld, sample_fantasy_fantasy_plan
from hu_continuation import HUContinuationState, zero_continuation_values
from m4x_robust_support import (
    LIPSCHITZ_GAP_CONSTANT,
    STATUS,
    audit_robust_support,
    continuation_region_membership,
    evaluate_robust_support_at,
    freeze_continuation_family,
    generate_robust_union_support,
    robust_support_gap_bound,
)


def meta() -> HUContinuationState:
    return HUContinuationState(button=1, p0_fantasy_cards=14, p1_fantasy_cards=14)


def completed_board(packet) -> Board:
    return Board(
        top=tuple(packet[0:3]),
        middle=tuple(packet[3:8]),
        bottom=tuple(packet[8:13]),
    )


def vectors():
    v0 = zero_continuation_values()
    v1 = dict(v0)
    v1[HUContinuationState(0, 14, 14)] = 0.20
    return v0, v1


def family():
    v0, v1 = vectors()
    return freeze_continuation_family(
        {"anchor-0": v0, "anchor-1": v1},
        radius_linf=0.11,
        provenance="M4X_TEST_FIXTURE_NOT_STRATEGIC_EVIDENCE",
        source_sha256="1" * 64,
    )


def test_family_is_sha_bound_and_gauge_normalized() -> None:
    v0, v1 = vectors()
    a = family()
    b = freeze_continuation_family(
        {"anchor-1": v1, "anchor-0": v0},
        radius_linf=0.11,
        provenance="M4X_TEST_FIXTURE_NOT_STRATEGIC_EVIDENCE",
        source_sha256="1" * 64,
    )
    assert a.sha256 == b.sha256
    assert tuple(anchor.label for anchor in a.anchors) == ("anchor-0", "anchor-1")
    changed_radius = freeze_continuation_family(
        {"anchor-0": v0, "anchor-1": v1},
        radius_linf=0.12,
        provenance="M4X_TEST_FIXTURE_NOT_STRATEGIC_EVIDENCE",
        source_sha256="1" * 64,
    )
    assert changed_radius.sha256 != a.sha256

    shifted = {state: value + 1.0 for state, value in v0.items()}
    try:
        freeze_continuation_family(
            {"shifted": shifted},
            radius_linf=0.1,
            provenance="BAD_GAUGE_TEST",
            source_sha256="2" * 64,
        )
    except ValueError as exc:
        assert "gauge" in str(exc)
    else:
        raise AssertionError("M4X accepted a continuation vector in a different gauge")


def test_union_support_is_own_information_only_and_contains_every_anchor_support() -> None:
    signature = inspect.signature(generate_robust_union_support)
    forbidden = {"opponent_packet", "opponent_board", "world", "payoff_matrix"}
    assert forbidden.isdisjoint(signature.parameters)

    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(20260827), current)
    )
    robust = generate_robust_union_support(
        world.plan.packet_for(0),
        current_meta=current,
        player=0,
        family=family(),
        synthetic_worlds_per_anchor=1,
        max_candidates_per_anchor=2,
        base_seed=9102,
    )
    assert 1 <= robust.candidate_count <= 4
    union = set(robust.canonical_action_keys)
    assert len(union) == robust.candidate_count
    for _label, keys in robust.anchor_action_keys:
        assert set(keys).issubset(union)
    assert robust.status == STATUS


def test_exact_anchor_audit_and_linf_extension_bound() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(77291), current)
    )
    fam = family()
    robust = generate_robust_union_support(
        world.plan.packet_for(0),
        current_meta=current,
        player=0,
        family=fam,
        synthetic_worlds_per_anchor=1,
        max_candidates_per_anchor=2,
        base_seed=441,
    )
    opponent = completed_board(world.plan.packet_for(1))
    audit = audit_robust_support(robust, opponent, fam)
    assert len(audit.anchor_results) == 2
    assert audit.max_anchor_gap >= 0.0
    assert all(row.support_gap >= 0.0 for row in audit.anchor_results)
    assert all(
        abs(
            row.declared_ball_gap_upper_bound
            - (row.support_gap + LIPSCHITZ_GAP_CONSTANT * fam.radius_linf)
        )
        <= 1e-12
        for row in audit.anchor_results
    )

    # Midpoint is 0.10 away from both anchors, inside the declared 0.11 balls.
    probe = zero_continuation_values()
    probe[HUContinuationState(0, 14, 14)] = 0.10
    membership = continuation_region_membership(fam, probe)
    assert membership.inside
    assert abs(membership.distance_linf - 0.10) <= 1e-12

    theorem = robust_support_gap_bound(audit, fam, probe)
    actual = evaluate_robust_support_at(robust, opponent, probe)
    assert actual.support_gap <= theorem.gap_upper_bound + 1e-9

    outside = zero_continuation_values()
    outside[HUContinuationState(0, 14, 14)] = 0.60
    assert not continuation_region_membership(fam, outside).inside
    try:
        robust_support_gap_bound(audit, fam, outside)
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("M4X produced a regional bound outside its declared region")


def main() -> None:
    test_family_is_sha_bound_and_gauge_normalized()
    test_union_support_is_own_information_only_and_contains_every_anchor_support()
    test_exact_anchor_audit_and_linf_extension_bound()
    print(
        "OPENOFC_M4X_ROBUST_SUPPORT=PASS "
        "support=ANCHOR_UNION teacher=M4N_EXACT "
        "extension=Linf_2LIPSCHITZ strategic_coverage=NOT_CLAIMED"
    )


if __name__ == "__main__":
    main()
