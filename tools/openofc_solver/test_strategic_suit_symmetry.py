from __future__ import annotations

import random

from engine import Action, Card
from strategic_cfr import DealPlan, HUState, child_state, legal_action_pairs, sample_deal_plan
from strategic_suit_symmetry import (
    SuitCanonicalOutcomeSamplingMCCFR,
    canonical_action_pairs,
    canonical_information_key,
    canonical_node_view,
    permute_card,
)


def _permute_packet(packet, suit_map):
    return tuple(sorted(permute_card(card, suit_map) for card in packet))


def _permute_plan(plan: DealPlan, suit_map) -> DealPlan:
    opening = (
        _permute_packet(plan.opening[0], suit_map),
        _permute_packet(plan.opening[1], suit_map),
    )
    rounds = tuple(
        (
            _permute_packet(packets[0], suit_map),
            _permute_packet(packets[1], suit_map),
        )
        for packets in plan.rounds
    )
    return DealPlan(opening=opening, rounds=rounds)  # type: ignore[arg-type]


def _mapped_action(
    action: Action,
    original_incoming,
    transformed_incoming,
    suit_map,
) -> Action:
    index_of = {card: i for i, card in enumerate(transformed_incoming)}
    placements = tuple(
        (
            index_of[permute_card(original_incoming[index], suit_map)],
            row,
        )
        for index, row in action.placements
    )
    discard = None
    if action.discard_index is not None:
        discard = index_of[
            permute_card(original_incoming[action.discard_index], suit_map)
        ]
    return Action(placements=placements, discard_index=discard)


def test_initial_infoset_and_action_set_are_suit_invariant() -> None:
    plan = sample_deal_plan(random.Random(7001))
    suit_map = (2, 0, 3, 1)
    transformed = _permute_plan(plan, suit_map)
    a = HUState(plan=plan)
    b = HUState(plan=transformed)
    key_a, map_a = canonical_information_key(a)
    key_b, map_b = canonical_information_key(b)
    assert key_a == key_b
    actions_a = {key for key, _ in canonical_action_pairs(a, map_a)}
    actions_b = {key for key, _ in canonical_action_pairs(b, map_b)}
    assert actions_a == actions_b
    assert len(actions_a) == 232


def test_public_history_is_canonicalized_with_cards() -> None:
    plan = sample_deal_plan(random.Random(7002))
    suit_map = (1, 3, 0, 2)
    tplan = _permute_plan(plan, suit_map)
    a = HUState(plan=plan)
    b = HUState(plan=tplan)

    # Non-dealer opening.
    _akey, action_a = legal_action_pairs(a)[37]
    incoming_a = a.plan.incoming(0, 0)
    incoming_b = b.plan.incoming(0, 0)
    action_b = _mapped_action(action_a, incoming_a, incoming_b, suit_map)
    a = child_state(a, action_a)
    b = child_state(b, action_b)
    assert canonical_information_key(a)[0] == canonical_information_key(b)[0]

    # Dealer opening.  This checks a history containing both players.
    _akey, action_a = legal_action_pairs(a)[81]
    incoming_a = a.plan.incoming(0, 1)
    incoming_b = b.plan.incoming(0, 1)
    action_b = _mapped_action(action_a, incoming_a, incoming_b, suit_map)
    a = child_state(a, action_a)
    b = child_state(b, action_b)
    assert canonical_information_key(a)[0] == canonical_information_key(b)[0]


def test_node_view_is_deterministic() -> None:
    state = HUState(plan=sample_deal_plan(random.Random(7003)))
    k1, p1, m1 = canonical_node_view(state)
    k2, p2, m2 = canonical_node_view(state)
    assert k1 == k2 and m1 == m2
    assert [x for x, _ in p1] == [x for x, _ in p2]


def test_suit_canonical_mccfr_smoke() -> None:
    solver = SuitCanonicalOutcomeSamplingMCCFR(
        seed=7004, epsilon=0.6, cfr_plus=True
    )
    stats = solver.run(3)
    assert stats.iterations == 3
    assert stats.episodes == 6
    assert stats.max_actions == 232
    assert stats.infosets > 0
    for node in solver.nodes.values():
        assert abs(sum(node.average_policy()) - 1.0) < 1e-9


def main() -> None:
    test_initial_infoset_and_action_set_are_suit_invariant()
    test_public_history_is_canonicalized_with_cards()
    test_node_view_is_deterministic()
    test_suit_canonical_mccfr_smoke()
    print("OPENOFC_STRATEGIC_SUIT_SYMMETRY_TEST=PASS")


if __name__ == "__main__":
    main()
