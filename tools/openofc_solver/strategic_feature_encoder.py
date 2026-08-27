from __future__ import annotations

"""Lossless visible-information feature encoder for strategic generalization.

The exact tabular MCCFR key is preserved as the authority. This encoder converts
that suit-canonical information state plus one legal action into a fixed sparse
binary vector without consulting hidden cards. It is designed as the input
contract for later regret/value function approximation; the encoder itself does
not merge strategically distinct canonical information states.
"""

import json
from typing import Iterable, Sequence

from engine import Action, full_deck
from strategic_cfr import HUState
from strategic_suit_symmetry import (
    action_key_under_suit_map,
    canonical_node_view,
)

SCHEMA = "openofc-hu-visible-feature-v1"
CARD_TOKENS = tuple(str(card) for card in full_deck(2))
if len(CARD_TOKENS) != 54 or len(set(CARD_TOKENS)) != 54:
    raise AssertionError("feature encoder requires 54 unique physical card tokens")
CARD_INDEX = {token: index for index, token in enumerate(CARD_TOKENS)}
CARD_COUNT = 54

OFFSET_BIAS = 0
OFFSET_PLAYER = 1
OFFSET_ROUND = OFFSET_PLAYER + 2
OFFSET_SELF_BOARD = OFFSET_ROUND + 5
OFFSET_OPP_BOARD = OFFSET_SELF_BOARD + 3 * CARD_COUNT
OFFSET_OWN_DISCARDS = OFFSET_OPP_BOARD + 3 * CARD_COUNT
OFFSET_INCOMING = OFFSET_OWN_DISCARDS + CARD_COUNT
OFFSET_PUBLIC_HISTORY = OFFSET_INCOMING + CARD_COUNT
PUBLIC_HISTORY_SIZE = 5 * 2 * 3 * CARD_COUNT
OFFSET_ACTION = OFFSET_PUBLIC_HISTORY + PUBLIC_HISTORY_SIZE
ACTION_SIZE = 4 * CARD_COUNT  # top/middle/bottom/discard
FEATURE_DIMENSION = OFFSET_ACTION + ACTION_SIZE


def _card_index(token: str) -> int:
    try:
        return CARD_INDEX[token]
    except KeyError as exc:
        raise ValueError(f"unknown physical card token in canonical key: {token!r}") from exc


def _add_card_set(out: set[int], offset: int, cards: Iterable[str]) -> None:
    for token in cards:
        out.add(offset + _card_index(str(token)))


def encode_canonical_state_key(key: str) -> tuple[int, ...]:
    payload = json.loads(key)
    if payload.get("v") != 2 or payload.get("symmetry") != "suit24-exact":
        raise ValueError("feature encoder requires the exact suit24 canonical key")
    player = int(payload["player"])
    round_index = int(payload["round"])
    if player not in (0, 1) or round_index not in range(5):
        raise ValueError("invalid HU player/round in canonical key")

    out: set[int] = {OFFSET_BIAS, OFFSET_PLAYER + player, OFFSET_ROUND + round_index}
    for board_name, board_offset in (
        ("self_board", OFFSET_SELF_BOARD),
        ("opp_board", OFFSET_OPP_BOARD),
    ):
        rows = payload[board_name]
        if len(rows) != 3:
            raise ValueError("canonical board must contain top/middle/bottom")
        for row, cards in enumerate(rows):
            _add_card_set(out, board_offset + row * CARD_COUNT, cards)

    _add_card_set(out, OFFSET_OWN_DISCARDS, payload["own_discards"])
    _add_card_set(out, OFFSET_INCOMING, payload["incoming"])

    for event in payload["public_history"]:
        if len(event) != 3:
            raise ValueError("malformed public-history event")
        event_round = int(event[0])
        event_player = int(event[1])
        if event_round not in range(5) or event_player not in (0, 1):
            raise ValueError("invalid public-history round/player")
        for placement in event[2]:
            card, row = str(placement[0]), int(placement[1])
            if row not in (0, 1, 2):
                raise ValueError("invalid row in public-history placement")
            base = (((event_round * 2 + event_player) * 3 + row) * CARD_COUNT)
            out.add(OFFSET_PUBLIC_HISTORY + base + _card_index(card))

    result = tuple(sorted(out))
    if result[-1] >= OFFSET_ACTION:
        raise AssertionError("state features crossed into action feature range")
    return result


def encode_canonical_action_key(key: str) -> tuple[int, ...]:
    payload = json.loads(key)
    out: set[int] = set()
    for placement in payload.get("p", []):
        card, row = str(placement[0]), int(placement[1])
        if row not in (0, 1, 2):
            raise ValueError("invalid action placement row")
        out.add(OFFSET_ACTION + row * CARD_COUNT + _card_index(card))
    discard = payload.get("d")
    if discard is not None:
        out.add(OFFSET_ACTION + 3 * CARD_COUNT + _card_index(str(discard)))
    if not out:
        raise ValueError("canonical OFC action cannot be empty")
    return tuple(sorted(out))


def merge_state_action_features(
    state_features: Sequence[int], action_features: Sequence[int]
) -> tuple[int, ...]:
    result = tuple(sorted(set(int(x) for x in state_features) | set(int(x) for x in action_features)))
    if not result or result[0] < 0 or result[-1] >= FEATURE_DIMENSION:
        raise ValueError("feature index outside declared dimension")
    return result


def canonical_state_and_action_features(
    state: HUState, action: Action
) -> tuple[str, str, tuple[int, ...]]:
    state_key, pairs, suit_map = canonical_node_view(state)
    incoming = state.plan.incoming(state.round_index, state.actor)
    action_key = action_key_under_suit_map(action, incoming, suit_map)
    legal_keys = {key for key, _ in pairs}
    if action_key not in legal_keys:
        raise ValueError("action is not legal in the supplied HU state")
    state_features = encode_canonical_state_key(state_key)
    action_features = encode_canonical_action_key(action_key)
    return state_key, action_key, merge_state_action_features(state_features, action_features)


def active_feature_count(features: Sequence[int]) -> int:
    return len(tuple(features))
