from __future__ import annotations

"""Exact 24-way suit reduction for normal-vs-hidden-Fantasy decisions.

The canonical suit permutation is chosen solely from information visible to the
normal player.  Hidden Fantasy cards are never consulted, so canonicalization
cannot leak opponent private information into the policy state.
"""

import json
from typing import Sequence

from engine import Action, Card
from normal_fantasy_kernel import NormalFantasyState, legal_normal_actions
from strategic_suit_symmetry import SUIT_PERMUTATIONS, permute_card

SOLVER_KIND = "normal-fantasy-suit24-exact"


def _token(card: Card, suit_map: Sequence[int]) -> str:
    return str(permute_card(card, suit_map))


def information_key_under_suit_map(
    state: NormalFantasyState,
    suit_map: Sequence[int],
) -> str:
    if state.terminal():
        raise ValueError("terminal asymmetric state has no policy information key")
    payload = {
        "v": 2,
        "symmetry": SOLVER_KIND,
        "normal_player": state.normal_player,
        "fantasy_player": state.fantasy_player,
        "button": state.current_meta.button,
        "fantasy_count": len(state.plan.fantasy_packet),
        "round": state.round_index,
        "normal_board": tuple(
            tuple(sorted(_token(card, suit_map) for card in row))
            for row in state.normal_board.rows()
        ),
        "own_discards": tuple(sorted(_token(card, suit_map) for card in state.normal_discards)),
        "incoming": tuple(sorted(_token(card, suit_map) for card in state.incoming())),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def canonical_information_key(
    state: NormalFantasyState,
) -> tuple[str, tuple[int, int, int, int]]:
    return min(
        (
            (information_key_under_suit_map(state, suit_map), suit_map)
            for suit_map in SUIT_PERMUTATIONS
        ),
        key=lambda item: (item[0], item[1]),
    )


def action_key_under_suit_map(
    action: Action,
    incoming: Sequence[Card],
    suit_map: Sequence[int],
) -> str:
    placements = sorted(
        (_token(incoming[index], suit_map), int(row))
        for index, row in action.placements
    )
    discard = None
    if action.discard_index is not None:
        discard = _token(incoming[action.discard_index], suit_map)
    return json.dumps({"p": placements, "d": discard}, sort_keys=True, separators=(",", ":"))


def canonical_node_view(
    state: NormalFantasyState,
) -> tuple[str, list[tuple[str, Action]], tuple[int, int, int, int]]:
    key, suit_map = canonical_information_key(state)
    incoming = state.incoming()
    pairs = [
        (action_key_under_suit_map(action, incoming, suit_map), action)
        for action in legal_normal_actions(state)
    ]
    pairs.sort(key=lambda item: item[0])
    if len({key for key, _action in pairs}) != len(pairs):
        raise AssertionError("asymmetric suit-canonical action keys collided")
    return key, pairs, suit_map
