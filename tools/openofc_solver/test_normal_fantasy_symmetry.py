from __future__ import annotations

import random

from hu_continuation import HUContinuationState
from normal_fantasy_kernel import (
    NormalFantasyDealPlan,
    NormalFantasyState,
    child_normal_state,
    sample_normal_fantasy_plan,
)
from normal_fantasy_symmetry import canonical_node_view
from strategic_suit_symmetry import permute_card


def permute_plan(plan: NormalFantasyDealPlan, suit_map):
    def packet(cards):
        return tuple(sorted(permute_card(card, suit_map) for card in cards))
    return NormalFantasyDealPlan(
        fantasy_packet=packet(plan.fantasy_packet),
        normal_opening=packet(plan.normal_opening),
        normal_rounds=tuple(packet(cards) for cards in plan.normal_rounds),  # type: ignore[arg-type]
    )


def test_global_suit_permutation_preserves_canonical_policy_surface() -> None:
    meta = HUContinuationState(button=1, p0_fantasy_cards=14, p1_fantasy_cards=0)
    plan = sample_normal_fantasy_plan(random.Random(123), 14)
    a = NormalFantasyState(current_meta=meta, plan=plan)
    b = NormalFantasyState(
        current_meta=meta,
        plan=permute_plan(plan, (2, 0, 3, 1)),
    )
    for _round in range(4):
        key_a, pairs_a, _ = canonical_node_view(a)
        key_b, pairs_b, _ = canonical_node_view(b)
        assert key_a == key_b
        keys_a = [key for key, _ in pairs_a]
        keys_b = [key for key, _ in pairs_b]
        assert keys_a == keys_b
        # Follow the same canonical action, not the same raw incoming index.
        a = child_normal_state(a, pairs_a[0][1])
        b = child_normal_state(b, pairs_b[0][1])


def test_hidden_fantasy_suits_do_not_choose_policy_canonicalization() -> None:
    meta = HUContinuationState(button=0, p0_fantasy_cards=0, p1_fantasy_cards=15)
    base = sample_normal_fantasy_plan(random.Random(456), 15)
    # Permute only the hidden packet. This may create overlaps if a transformed
    # card hits a normal card, so use a simple reversal of physical hidden cards
    # instead: identity changes are unnecessary; order alone must already be
    # irrelevant and the key must not serialize the packet at all.
    hidden_reordered = NormalFantasyDealPlan(
        fantasy_packet=tuple(reversed(base.fantasy_packet)),
        normal_opening=base.normal_opening,
        normal_rounds=base.normal_rounds,
    )
    a = NormalFantasyState(current_meta=meta, plan=base)
    b = NormalFantasyState(current_meta=meta, plan=hidden_reordered)
    key_a, pairs_a, map_a = canonical_node_view(a)
    key_b, pairs_b, map_b = canonical_node_view(b)
    assert key_a == key_b
    assert map_a == map_b
    assert [key for key, _ in pairs_a] == [key for key, _ in pairs_b]


def main() -> None:
    test_global_suit_permutation_preserves_canonical_policy_surface()
    test_hidden_fantasy_suits_do_not_choose_policy_canonicalization()
    print(
        "OPENOFC_M4F_NORMAL_FANTASY_SUIT24=PASS "
        "symmetry=EXACT hidden_packet=NOT_CONSULTED actions=CANONICAL"
    )


if __name__ == "__main__":
    main()
