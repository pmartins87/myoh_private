from __future__ import annotations

"""Exact 24-way suit-isomorphism reduction for the HU strategic solver.

Poker suits have no intrinsic ordering in KKPoker OFC.  Applying one global
permutation of clubs/diamonds/hearts/spades to every card in an information
state preserves legal actions, hand ranks, royalties, fouls and terminal score.
This module canonicalizes that exact game automorphism instead of asking the
trainer to rediscover the same strategy up to 24 times.

Crucially, the permutation is selected from *only the acting player's
information state*.  Hidden opponent packets/discards and future cards are not
consulted.  The full public action history is transformed too, so strategic
signalling and perfect recall are preserved.
"""

from itertools import permutations
import json
import math
from typing import Sequence

from engine import Action, Card
from strategic_cfr import (
    HUState,
    OutcomeSamplingMCCFR,
    child_state,
    terminal_utility,
)

SUIT_PERMUTATIONS: tuple[tuple[int, int, int, int], ...] = tuple(
    permutations(range(4))
)
SOLVER_KIND = "suit24-exact"


def permute_card(card: Card, suit_map: Sequence[int]) -> Card:
    if len(suit_map) != 4 or sorted(int(x) for x in suit_map) != [0, 1, 2, 3]:
        raise ValueError("suit_map must be a permutation of 0..3")
    if card.joker:
        return card
    return Card(rank=card.rank, suit=int(suit_map[card.suit]))


def _token(card: Card, suit_map: Sequence[int]) -> str:
    return str(permute_card(card, suit_map))


def _token_from_text(text: str, suit_map: Sequence[int]) -> str:
    return _token(Card.parse(text), suit_map)


def _board_payload(board, suit_map: Sequence[int]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(sorted(_token(card, suit_map) for card in row))
        for row in board.rows()
    )


def information_key_under_suit_map(
    state: HUState,
    suit_map: Sequence[int],
) -> str:
    if state.terminal():
        raise ValueError("terminal state has no information state")
    player = state.actor
    opponent = 1 - player
    incoming = state.plan.incoming(state.round_index, player)
    history = tuple(
        (
            event.round_index,
            event.player,
            tuple(sorted(
                (_token_from_text(card, suit_map), int(row))
                for card, row in event.placements
            )),
        )
        for event in state.public_history
    )
    payload = {
        "v": 2,
        "symmetry": SOLVER_KIND,
        "player": player,
        "position": "nondealer_first" if player == 0 else "dealer_button_second",
        "round": state.round_index,
        "self_board": _board_payload(state.boards[player], suit_map),
        "opp_board": _board_payload(state.boards[opponent], suit_map),
        "own_discards": tuple(sorted(
            _token(card, suit_map) for card in state.discards[player]
        )),
        "incoming": tuple(sorted(_token(card, suit_map) for card in incoming)),
        "public_history": history,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def canonical_information_key(state: HUState) -> tuple[str, tuple[int, int, int, int]]:
    """Return lexicographically canonical visible information and suit map."""
    candidates = (
        (information_key_under_suit_map(state, suit_map), suit_map)
        for suit_map in SUIT_PERMUTATIONS
    )
    return min(candidates, key=lambda item: (item[0], item[1]))


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
    return json.dumps(
        {"p": placements, "d": discard},
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_action_pairs(
    state: HUState,
    suit_map: Sequence[int],
) -> list[tuple[str, Action]]:
    if state.terminal():
        return []
    from engine import legal_actions

    incoming = state.plan.incoming(state.round_index, state.actor)
    pairs = [
        (action_key_under_suit_map(action, incoming, suit_map), action)
        for action in legal_actions(
            state.boards[state.actor], incoming, state.round_index
        )
    ]
    pairs.sort(key=lambda item: item[0])
    if len({key for key, _action in pairs}) != len(pairs):
        raise AssertionError("suit-canonical legal action keys collided")
    return pairs


def canonical_node_view(
    state: HUState,
) -> tuple[str, list[tuple[str, Action]], tuple[int, int, int, int]]:
    key, suit_map = canonical_information_key(state)
    return key, canonical_action_pairs(state, suit_map), suit_map


def _sample_index(probabilities: Sequence[float], rng) -> int:
    x = rng.random()
    cumulative = 0.0
    for i, p in enumerate(probabilities):
        if p < 0.0 or not math.isfinite(p):
            raise ValueError("invalid policy probability")
        cumulative += p
        if x < cumulative or i == len(probabilities) - 1:
            return i
    raise AssertionError("probability sampling fell through")


class SuitCanonicalOutcomeSamplingMCCFR(OutcomeSamplingMCCFR):
    """Outcome-sampling MCCFR with exact suit-isomorphic infoset merging."""

    solver_kind = SOLVER_KIND

    def _episode(
        self,
        state: HUState,
        update_player: int,
        *,
        my_reach: float,
        opp_reach: float,
        sample_reach: float,
    ) -> float:
        if state.terminal():
            return terminal_utility(state, update_player)

        current = state.actor
        key, pairs, _suit_map = canonical_node_view(state)
        action_keys = [action_key for action_key, _ in pairs]
        actions = [action for _, action in pairs]
        node = self._node(key, action_keys)
        policy = node.current_policy()

        if current == update_player:
            uniform = 1.0 / len(policy)
            sample_policy = [
                self.epsilon * uniform + (1.0 - self.epsilon) * p
                for p in policy
            ]
        else:
            sample_policy = list(policy)

        sampled = _sample_index(sample_policy, self.rng)
        if current == update_player:
            new_my_reach = my_reach * policy[sampled]
            new_opp_reach = opp_reach
        else:
            new_my_reach = my_reach
            new_opp_reach = opp_reach * policy[sampled]
        new_sample_reach = sample_reach * sample_policy[sampled]
        child_value = self._episode(
            child_state(state, actions[sampled]),
            update_player,
            my_reach=new_my_reach,
            opp_reach=new_opp_reach,
            sample_reach=new_sample_reach,
        )

        child_values = [0.0] * len(policy)
        child_values[sampled] = child_value / sample_policy[sampled]
        value_estimate = sum(
            policy[i] * child_values[i] for i in range(len(policy))
        )

        if current == update_player:
            if sample_reach <= 0.0:
                raise AssertionError("sample reach became non-positive")
            scale = opp_reach / sample_reach
            cf_value = value_estimate * scale
            for i in range(len(policy)):
                delta = child_values[i] * scale - cf_value
                updated = node.cumulative_regrets[i] + delta
                node.cumulative_regrets[i] = (
                    max(0.0, updated) if self.cfr_plus else updated
                )
            for i in range(len(policy)):
                node.cumulative_policy[i] += (
                    my_reach * policy[i] / sample_reach
                )
            node.visits += 1

        return value_estimate
