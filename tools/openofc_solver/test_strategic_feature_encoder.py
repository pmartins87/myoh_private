from __future__ import annotations

"""Tests for the lossless suit-canonical visible-information feature contract."""

import json
import random

from strategic_cfr import DealPlan, HUState, legal_action_pairs, sample_deal_plan
from strategic_feature_encoder import (
    FEATURE_DIMENSION,
    OFFSET_ACTION,
    encode_canonical_action_key,
    encode_canonical_state_key,
    canonical_state_and_action_features,
)
from strategic_suit_symmetry import canonical_node_view, permute_card


def permute_plan(plan: DealPlan, suit_map: tuple[int, int, int, int]) -> DealPlan:
    def packet(cards):
        return tuple(permute_card(card, suit_map) for card in cards)

    return DealPlan(
        opening=(packet(plan.opening[0]), packet(plan.opening[1])),
        rounds=tuple((packet(a), packet(b)) for a, b in plan.rounds),  # type: ignore[arg-type]
    )


def test_declared_dimension_and_ranges() -> None:
    assert FEATURE_DIMENSION == 2276
    state = HUState(plan=sample_deal_plan(random.Random(1)))
    key, pairs, _ = canonical_node_view(state)
    sf = encode_canonical_state_key(key)
    assert sf and max(sf) < OFFSET_ACTION
    af = encode_canonical_action_key(pairs[0][0])
    assert af and min(af) >= OFFSET_ACTION and max(af) < FEATURE_DIMENSION


def test_all_232_opening_actions_remain_distinct() -> None:
    state = HUState(plan=sample_deal_plan(random.Random(2)))
    _key, pairs, _ = canonical_node_view(state)
    assert len(pairs) == 232
    encoded = {encode_canonical_action_key(key) for key, _ in pairs}
    assert len(encoded) == 232


def test_hidden_cards_do_not_change_features() -> None:
    visible = sample_deal_plan(random.Random(3))
    hidden = sample_deal_plan(random.Random(4))
    hybrid = DealPlan(
        opening=(visible.opening[0], hidden.opening[1]),
        rounds=hidden.rounds,
    )
    a = HUState(plan=visible)
    b = HUState(plan=hybrid)
    key_a, _pairs_a, _ = canonical_node_view(a)
    key_b, _pairs_b, _ = canonical_node_view(b)
    assert key_a == key_b
    assert encode_canonical_state_key(key_a) == encode_canonical_state_key(key_b)


def test_global_suit_permutation_is_feature_invariant() -> None:
    plan = sample_deal_plan(random.Random(5))
    permuted = permute_plan(plan, (2, 0, 3, 1))
    a = HUState(plan=plan)
    b = HUState(plan=permuted)
    key_a, pairs_a, _ = canonical_node_view(a)
    key_b, pairs_b, _ = canonical_node_view(b)
    assert key_a == key_b
    assert encode_canonical_state_key(key_a) == encode_canonical_state_key(key_b)
    assert [key for key, _ in pairs_a] == [key for key, _ in pairs_b]


def test_public_history_is_not_discarded_by_encoder() -> None:
    state = HUState(plan=sample_deal_plan(random.Random(6)))
    key, _pairs, _ = canonical_node_view(state)
    payload = json.loads(key)
    base = encode_canonical_state_key(key)
    card = payload["incoming"][0]
    payload["public_history"] = [[0, 0, [[card, 0]]]]
    changed_key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    changed = encode_canonical_state_key(changed_key)
    assert base != changed


def test_state_action_feature_pair_is_suit_invariant() -> None:
    plan = sample_deal_plan(random.Random(7))
    state = HUState(plan=plan)
    action = legal_action_pairs(state)[37][1]
    permuted_state = HUState(plan=permute_plan(plan, (1, 3, 0, 2)))
    _sk1, _ak1, f1 = canonical_state_and_action_features(state, action)
    _sk2, _ak2, f2 = canonical_state_and_action_features(permuted_state, action)
    assert f1 == f2


def main() -> None:
    test_declared_dimension_and_ranges()
    test_all_232_opening_actions_remain_distinct()
    test_hidden_cards_do_not_change_features()
    test_global_suit_permutation_is_feature_invariant()
    test_public_history_is_not_discarded_by_encoder()
    test_state_action_feature_pair_is_suit_invariant()
    print(
        "OPENOFC_M4C_VISIBLE_FEATURE_ENCODER=PASS "
        "dimension=2276 opening_actions=232 hidden_leak=0 suit24=INVARIANT "
        "public_history=PRESERVED action_abstraction=0"
    )


if __name__ == "__main__":
    main()
