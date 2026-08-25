from __future__ import annotations

from pathlib import Path
import random
import tempfile

from strategic_cfr import (
    DealPlan,
    HUState,
    OutcomeSamplingMCCFR,
    child_state,
    information_state_key,
    legal_action_pairs,
    sample_deal_plan,
    terminal_utility,
)


def _swap_hidden_dealer_cards(plan: DealPlan) -> DealPlan:
    dealer_open = list(plan.opening[1])
    rounds = [[list(packets[0]), list(packets[1])] for packets in plan.rounds]
    dealer_open[0], rounds[0][1][0] = rounds[0][1][0], dealer_open[0]
    opening = (plan.opening[0], tuple(sorted(dealer_open)))
    rebuilt = tuple(
        (tuple(sorted(packets[0])), tuple(sorted(packets[1])))
        for packets in rounds
    )
    return DealPlan(opening=opening, rounds=rebuilt)  # type: ignore[arg-type]


def test_deal_and_opening_action_space() -> None:
    plan = sample_deal_plan(random.Random(7))
    assert len(plan.dealt_cards()) == 34
    assert len(set(plan.dealt_cards())) == 34
    state = HUState(plan=plan)
    assert len(legal_action_pairs(state)) == 232


def test_nondealer_information_key_hides_dealer_private_cards() -> None:
    plan = sample_deal_plan(random.Random(11))
    altered = _swap_hidden_dealer_cards(plan)
    assert altered.opening[1] != plan.opening[1]
    assert altered.rounds[0][1] != plan.rounds[0][1]
    assert information_state_key(HUState(plan=plan)) == information_state_key(
        HUState(plan=altered)
    )


def test_public_history_exposes_placements_not_opponent_discard() -> None:
    plan = sample_deal_plan(random.Random(13))
    state = HUState(plan=plan)

    # Opening: non-dealer acts, then dealer acts.
    state = child_state(state, legal_action_pairs(state)[0][1])
    dealer_key = information_state_key(state)
    for card in plan.opening[0]:
        assert str(card) in dealer_key  # opening placements are all public
    state = child_state(state, legal_action_pairs(state)[0][1])
    assert state.round_index == 1 and state.actor == 0

    # R1 non-dealer places two and privately discards one.
    incoming = plan.rounds[0][0]
    _key, action = legal_action_pairs(state)[0]
    assert action.discard_index is not None
    discarded = incoming[action.discard_index]
    state = child_state(state, action)
    assert discarded in state.discards[0]
    assert state.actor == 1
    dealer_key = information_state_key(state)
    # Physical cards are unique, so absence of this token proves that the
    # opponent information state did not accidentally serialize the discard.
    assert str(discarded) not in dealer_key
    event = state.public_history[-1]
    assert all(card != str(discarded) for card, _row in event.placements)


def test_complete_state_and_zero_sum_terminal_utility() -> None:
    plan = sample_deal_plan(random.Random(17))
    rng = random.Random(19)
    state = HUState(plan=plan)
    while not state.terminal():
        pairs = legal_action_pairs(state)
        state = child_state(state, pairs[rng.randrange(len(pairs))][1])
    u0 = terminal_utility(state, 0)
    u1 = terminal_utility(state, 1)
    assert u0 == -u1
    assert state.boards[0].count() == state.boards[1].count() == 13
    assert len(state.discards[0]) == len(state.discards[1]) == 4


def test_outcome_sampling_smoke_and_checkpoint() -> None:
    solver = OutcomeSamplingMCCFR(seed=23, epsilon=0.6, cfr_plus=True)
    stats = solver.run(3)
    assert stats.iterations == 3 and stats.episodes == 6
    assert stats.infosets > 0 and stats.total_visits > 0
    assert stats.max_actions == 232
    for key, node in solver.nodes.items():
        policy = solver.policy_for_key(key)
        assert set(policy) == set(node.action_keys)
        assert abs(sum(policy.values()) - 1.0) < 1e-9
        assert all(p >= 0.0 for p in policy.values())
        assert all(x >= 0.0 for x in node.cumulative_regrets)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "solver.json.gz"
        solver.save_checkpoint(path)
        restored = OutcomeSamplingMCCFR.load_checkpoint(path)
        assert restored.iterations == solver.iterations
        assert restored.episodes == solver.episodes
        assert restored.nodes.keys() == solver.nodes.keys()
        for key in solver.nodes:
            a = solver.nodes[key]
            b = restored.nodes[key]
            assert a.action_keys == b.action_keys
            assert a.cumulative_regrets == b.cumulative_regrets
            assert a.cumulative_policy == b.cumulative_policy
            assert a.visits == b.visits


def main() -> None:
    test_deal_and_opening_action_space()
    test_nondealer_information_key_hides_dealer_private_cards()
    test_public_history_exposes_placements_not_opponent_discard()
    test_complete_state_and_zero_sum_terminal_utility()
    test_outcome_sampling_smoke_and_checkpoint()
    print("OPENOFC_STRATEGIC_CFR_TEST=PASS")


if __name__ == "__main__":
    main()
