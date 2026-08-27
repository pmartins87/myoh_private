from __future__ import annotations

"""Visible-only sparse features for the delayed Normal/Fantasy HU kernel.

The source key is the exact suit24 canonical key emitted by
``normal_fantasy_symmetry.canonical_node_view``. The encoder deliberately
reuses the global strategic feature ranges so the existing sparse action model
can be shared without creating a second optimizer implementation.

The opponent-board slice is unused by the delayed Normal/Fantasy information
model and is therefore reserved here for seven public metadata bits. Hidden
Fantasy cards are neither accepted nor encoded.
"""

import json
from typing import Mapping

from strategic_feature_encoder import (
    CARD_COUNT,
    CARD_INDEX,
    OFFSET_ACTION,
    OFFSET_BIAS,
    OFFSET_INCOMING,
    OFFSET_OPP_BOARD,
    OFFSET_OWN_DISCARDS,
    OFFSET_PLAYER,
    OFFSET_ROUND,
    OFFSET_SELF_BOARD,
    encode_canonical_action_key,
)

SCHEMA_VERSION = 2
SYMMETRY_KIND = "normal-fantasy-suit24-exact"
ALLOWED_FIELDS = frozenset(
    {
        "v",
        "symmetry",
        "normal_player",
        "fantasy_player",
        "button",
        "fantasy_count",
        "round",
        "normal_board",
        "own_discards",
        "incoming",
    }
)
FANTASY_COUNTS = (14, 15, 16, 17)

# This state slice would otherwise hold an observed opponent board. The delayed
# model has no observed Fantasy board before the normal player finishes, so use
# a tiny, collision-free prefix of it for public/asymmetric metadata.
META_NORMAL_PLAYER = OFFSET_OPP_BOARD
META_BUTTON = OFFSET_OPP_BOARD + 2
META_FANTASY_COUNT = OFFSET_OPP_BOARD + 4


def _card_index(token: object) -> int:
    try:
        return CARD_INDEX[str(token)]
    except KeyError as exc:
        raise ValueError(
            f"unknown physical card token in Normal/Fantasy key: {token!r}"
        ) from exc


def _add_cards(out: set[int], offset: int, cards) -> None:
    for token in cards:
        out.add(offset + _card_index(token))


def _parse_key(key: str) -> Mapping[str, object]:
    payload = json.loads(key)
    if not isinstance(payload, dict):
        raise ValueError("Normal/Fantasy canonical key must decode to an object")
    if set(payload) != ALLOWED_FIELDS:
        extra = sorted(set(payload) - ALLOWED_FIELDS)
        missing = sorted(ALLOWED_FIELDS - set(payload))
        raise ValueError(
            f"Normal/Fantasy canonical key schema mismatch; missing={missing} extra={extra}"
        )
    if payload.get("v") != SCHEMA_VERSION or payload.get("symmetry") != SYMMETRY_KIND:
        raise ValueError(
            "feature encoder requires exact Normal/Fantasy suit24 canonical key"
        )
    return payload


def encode_normal_fantasy_state_key(key: str) -> tuple[int, ...]:
    payload = _parse_key(key)
    normal_player = int(payload["normal_player"])
    fantasy_player = int(payload["fantasy_player"])
    button = int(payload["button"])
    fantasy_count = int(payload["fantasy_count"])
    round_index = int(payload["round"])
    if normal_player not in (0, 1) or fantasy_player != 1 - normal_player:
        raise ValueError("Normal/Fantasy player identities are invalid")
    if button not in (0, 1) or fantasy_count not in FANTASY_COUNTS:
        raise ValueError("Normal/Fantasy public metadata is invalid")
    if round_index not in range(5):
        raise ValueError("Normal/Fantasy round must be 0..4")

    board = payload["normal_board"]
    if not isinstance(board, (list, tuple)) or len(board) != 3:
        raise ValueError("normal board must contain top/middle/bottom")

    out: set[int] = {
        OFFSET_BIAS,
        OFFSET_PLAYER + normal_player,
        OFFSET_ROUND + round_index,
        META_NORMAL_PLAYER + normal_player,
        META_BUTTON + button,
        META_FANTASY_COUNT + FANTASY_COUNTS.index(fantasy_count),
    }
    for row, cards in enumerate(board):
        _add_cards(out, OFFSET_SELF_BOARD + row * CARD_COUNT, cards)
    _add_cards(out, OFFSET_OWN_DISCARDS, payload["own_discards"])
    _add_cards(out, OFFSET_INCOMING, payload["incoming"])

    result = tuple(sorted(out))
    if not result or result[0] < 0 or result[-1] >= OFFSET_ACTION:
        raise AssertionError("Normal/Fantasy state features crossed action boundary")
    return result


def encode_normal_fantasy_action_key(key: str) -> tuple[int, ...]:
    """The public action JSON surface is identical to the normal/normal encoder."""
    return encode_canonical_action_key(key)
