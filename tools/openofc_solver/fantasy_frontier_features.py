from __future__ import annotations

"""Lossless feature contract for exact terminal Fantasy-world approximation.

Unlike policy features, this oracle-only encoder is allowed to include the hidden
Fantasy packet because it is evaluated after a chance world has been sampled.
It must never be wired into a player's information-set policy input.
"""

import json
from typing import Sequence

from engine import full_deck

SCHEMA = "openofc-m4i-terminal-world-feature-v1"
CARD_TOKENS = tuple(str(card) for card in full_deck(2))
CARD_INDEX = {token: index for index, token in enumerate(CARD_TOKENS)}
CARD_COUNT = 54
if len(CARD_TOKENS) != CARD_COUNT or len(CARD_INDEX) != CARD_COUNT:
    raise AssertionError("terminal frontier encoder requires 54 physical cards")

OFFSET_BIAS = 0
OFFSET_COUNT = 1
OFFSET_PACKET = OFFSET_COUNT + 4
OFFSET_BOARD = OFFSET_PACKET + CARD_COUNT
FEATURE_DIMENSION = OFFSET_BOARD + 3 * CARD_COUNT


def _card_index(token: str) -> int:
    try:
        return CARD_INDEX[token]
    except KeyError as exc:
        raise ValueError(f"unknown physical card token: {token!r}") from exc


def encode_canonical_world_key(key: str) -> tuple[int, ...]:
    payload = json.loads(key)
    if payload.get("v") != 1:
        raise ValueError("unsupported canonical frontier key version")
    count = int(payload["fantasy_count"])
    if count not in (14, 15, 16, 17):
        raise ValueError("invalid Fantasy count in canonical world key")
    packet = tuple(str(x) for x in payload["packet"])
    rows = payload["normal_board"]
    if len(packet) != count or len(rows) != 3:
        raise ValueError("canonical terminal world cardinality mismatch")
    out = {OFFSET_BIAS, OFFSET_COUNT + (count - 14)}
    for token in packet:
        out.add(OFFSET_PACKET + _card_index(token))
    for row_index, row in enumerate(rows):
        expected = 3 if row_index == 0 else 5
        if len(row) != expected:
            raise ValueError("canonical normal board row cardinality mismatch")
        for token in row:
            out.add(OFFSET_BOARD + row_index * CARD_COUNT + _card_index(str(token)))
    result = tuple(sorted(out))
    if result[0] < 0 or result[-1] >= FEATURE_DIMENSION:
        raise AssertionError("terminal world feature outside declared dimension")
    # 1 bias + 1 count + fantasy packet + 13 board cards.
    if len(result) != 15 + count:
        raise AssertionError("terminal world feature lost or duplicated a physical card")
    return result


def feature_dimension() -> int:
    return FEATURE_DIMENSION
