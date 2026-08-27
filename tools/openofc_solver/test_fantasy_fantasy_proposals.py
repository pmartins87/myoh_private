from __future__ import annotations

import random

from engine import Board
from fantasy_fantasy_kernel import FantasyFantasyWorld, sample_fantasy_fantasy_plan, validate_arrangement
from fantasy_fantasy_proposals import (
    evaluate_proposal_support,
    generate_fantasy_proposals,
)
from hu_continuation import HUContinuationState, zero_continuation_values
from strategic_suit_symmetry import permute_card


def meta() -> HUContinuationState:
    return HUContinuationState(button=1, p0_fantasy_cards=14, p1_fantasy_cards=14)


def opponent_board(packet) -> Board:
    return Board(
        top=tuple(packet[0:3]),
        middle=tuple(packet[3:8]),
        bottom=tuple(packet[8:13]),
    )


def test_bounded_deterministic_and_own_information_only() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(20260827), current)
    )
    own = world.plan.packet_for(0)
    values = zero_continuation_values()
    a = generate_fantasy_proposals(
        own,
        current_meta=current,
        player=0,
        continuation_values=values,
        synthetic_worlds=1,
        max_candidates=4,
        base_seed=77,
    )
    b = generate_fantasy_proposals(
        own,
        current_meta=current,
        player=0,
        continuation_values=values,
        synthetic_worlds=1,
        max_candidates=4,
        base_seed=77,
    )
    assert a.canonical_action_keys == b.canonical_action_keys
    assert a.candidates == b.candidates
    assert 1 <= a.candidate_count <= 4
    assert a.exact_teacher_calls == 1
    for candidate in a.candidates:
        validate_arrangement(own, candidate)


def test_global_suit_equivariance_of_candidate_support() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(8821), current)
    )
    own = world.plan.packet_for(0)
    suit_map = (2, 0, 3, 1)
    permuted = tuple(sorted(permute_card(card, suit_map) for card in own))
    values = zero_continuation_values()
    original = generate_fantasy_proposals(
        own,
        current_meta=current,
        player=0,
        continuation_values=values,
        synthetic_worlds=1,
        max_candidates=4,
        base_seed=901,
    )
    transformed = generate_fantasy_proposals(
        permuted,
        current_meta=current,
        player=0,
        continuation_values=values,
        synthetic_worlds=1,
        max_candidates=4,
        base_seed=901,
    )
    assert original.visible_fingerprint == transformed.visible_fingerprint
    assert original.canonical_action_keys == transformed.canonical_action_keys
    for candidate in transformed.candidates:
        validate_arrangement(permuted, candidate)


def test_support_gap_is_measured_against_exact_teacher() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(4477), current)
    )
    values = zero_continuation_values()
    proposal = generate_fantasy_proposals(
        world.plan.packet_for(0),
        current_meta=current,
        player=0,
        continuation_values=values,
        synthetic_worlds=1,
        max_candidates=4,
        base_seed=123,
    )
    result = evaluate_proposal_support(
        proposal,
        opponent_board(world.plan.packet_for(1)),
        values,
    )
    assert result.candidate_count == proposal.candidate_count
    assert result.support_gap >= 0.0
    assert result.proposal_best_utility <= result.exact_teacher_utility + 1e-9


def test_continuation_vector_is_bound_to_proposal() -> None:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(990), current)
    )
    values = zero_continuation_values()
    proposal = generate_fantasy_proposals(
        world.plan.packet_for(0),
        current_meta=current,
        player=0,
        continuation_values=values,
        synthetic_worlds=1,
        max_candidates=4,
        base_seed=312,
    )
    changed = dict(values)
    first = next(iter(changed))
    changed[first] = 0.25
    try:
        evaluate_proposal_support(
            proposal,
            opponent_board(world.plan.packet_for(1)),
            changed,
        )
    except ValueError as exc:
        assert "continuation vector" in str(exc)
    else:
        raise AssertionError("proposal accepted a different continuation vector")


def main() -> None:
    test_bounded_deterministic_and_own_information_only()
    test_global_suit_equivariance_of_candidate_support()
    test_support_gap_is_measured_against_exact_teacher()
    test_continuation_vector_is_bound_to_proposal()
    print(
        "OPENOFC_M4O_FANTASY_PROPOSALS=PASS "
        "actual_hidden_input=ABSENT support=BOUNDED suit24=EQUIVARIANT "
        "quality_metric=EXACT_TEACHER_SUPPORT_GAP"
    )


if __name__ == "__main__":
    main()
