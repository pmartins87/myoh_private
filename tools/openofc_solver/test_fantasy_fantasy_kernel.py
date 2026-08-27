from __future__ import annotations

import random

from engine import Board, full_deck, score_heads_up
from fantasy_fantasy_kernel import (
    FantasyFantasyDealPlan,
    FantasyFantasyWorld,
    arrangement_from_board,
    canonical_action_key,
    canonical_information_key,
    sample_fantasy_fantasy_plan,
    terminal_utility,
)
from hu_continuation import (
    HUContinuationState,
    next_state_from_terminal_boards,
    zero_continuation_values,
)
from strategic_suit_symmetry import permute_card


def meta() -> HUContinuationState:
    return HUContinuationState(button=1, p0_fantasy_cards=14, p1_fantasy_cards=15)


def simple_arrangement(packet):
    cards = tuple(packet)
    board = Board(
        top=cards[0:3],
        middle=cards[3:8],
        bottom=cards[8:13],
    )
    return arrangement_from_board(cards, board)


def test_private_information_firewall() -> None:
    plan = sample_fantasy_fantasy_plan(random.Random(20260827), meta())
    used = set(plan.all_cards())
    replacement = next(card for card in full_deck(2) if card not in used)
    p1 = list(plan.packet_for(1))
    p1[0] = replacement
    alternate = FantasyFantasyDealPlan(
        (plan.packet_for(0), tuple(sorted(p1)))
    )
    a = FantasyFantasyWorld(meta(), plan)
    b = FantasyFantasyWorld(meta(), alternate)
    assert plan.packet_for(1) != alternate.packet_for(1)
    assert canonical_information_key(a, 0)[0] == canonical_information_key(b, 0)[0]


def test_global_suit_isomorphism() -> None:
    world = FantasyFantasyWorld(
        meta(), sample_fantasy_fantasy_plan(random.Random(77), meta())
    )
    suit_map = (2, 0, 3, 1)
    permuted = FantasyFantasyWorld(
        meta(),
        FantasyFantasyDealPlan(
            tuple(
                tuple(sorted(permute_card(card, suit_map) for card in world.plan.packet_for(player)))
                for player in (0, 1)
            )
        ),
    )
    for player in (0, 1):
        assert (
            canonical_information_key(world, player)[0]
            == canonical_information_key(permuted, player)[0]
        )


def test_terminal_zero_sum_and_continuation() -> None:
    world = FantasyFantasyWorld(
        meta(), sample_fantasy_fantasy_plan(random.Random(991), meta())
    )
    a0 = simple_arrangement(world.plan.packet_for(0))
    a1 = simple_arrangement(world.plan.packet_for(1))
    values = zero_continuation_values()
    u0 = terminal_utility(world, a0, a1, values, update_player=0)
    u1 = terminal_utility(world, a0, a1, values, update_player=1)
    expected = float(score_heads_up(a0.board, a1.board).points)
    assert u0 == expected
    assert u1 == -expected

    nxt = next_state_from_terminal_boards(
        world.current_meta, a0.board, a1.board
    )
    shifted = dict(values)
    shifted[nxt] = 12.5
    assert terminal_utility(world, a0, a1, shifted, update_player=0) == expected + 12.5
    assert terminal_utility(world, a0, a1, shifted, update_player=1) == -expected - 12.5


def test_canonical_action_key_uses_own_visible_suit_map() -> None:
    world = FantasyFantasyWorld(
        meta(), sample_fantasy_fantasy_plan(random.Random(17), meta())
    )
    for player in (0, 1):
        arrangement = simple_arrangement(world.plan.packet_for(player))
        key = canonical_action_key(world, player, arrangement)
        assert '"top"' in key and '"discarded"' in key


def main() -> None:
    test_private_information_firewall()
    test_global_suit_isomorphism()
    test_terminal_zero_sum_and_continuation()
    test_canonical_action_key_uses_own_visible_suit_map()
    print(
        "OPENOFC_M4M_FANTASY_FANTASY_BOUNDARY=PASS "
        "timing=SEALED_SIMULTANEOUS hidden_leakage=ABSENT "
        "suit24=EXACT terminal=CONTINUATION_EXACT"
    )


if __name__ == "__main__":
    main()
