from __future__ import annotations

"""Lossless own-information state/action features for sealed Fantasy/Fantasy HU.

The encoder is intentionally separate from terminal/oracle feature contracts.
It accepts only public meta-state, the acting player's own Fantasy packet and
one candidate arrangement from that packet.  Opponent cards and boards cannot
enter through this API.
"""

from engine import Board, Card, full_deck
from fantasy_fantasy_kernel import FantasyArrangement, validate_arrangement
from fantasy_fantasy_proposals import canonical_visible_packet
from hu_continuation import HUContinuationState, KERNEL_FANTASY_FANTASY, hand_kernel_kind
from strategic_suit_symmetry import permute_card

SCHEMA = "openofc-m4p-fantasy-fantasy-policy-feature-v1"
CARD_TOKENS = tuple(str(card) for card in full_deck(2))
CARD_INDEX = {token: index for index, token in enumerate(CARD_TOKENS)}
CARD_COUNT = 54
if len(CARD_TOKENS) != CARD_COUNT or len(CARD_INDEX) != CARD_COUNT:
    raise AssertionError("Fantasy policy encoder requires 54 distinct physical cards")

OFFSET_BIAS = 0
OFFSET_PLAYER = 1
OFFSET_BUTTON = OFFSET_PLAYER + 2
OFFSET_P0_COUNT = OFFSET_BUTTON + 2
OFFSET_P1_COUNT = OFFSET_P0_COUNT + 4
OFFSET_PACKET = OFFSET_P1_COUNT + 4
OFFSET_TOP = OFFSET_PACKET + CARD_COUNT
OFFSET_MIDDLE = OFFSET_TOP + CARD_COUNT
OFFSET_BOTTOM = OFFSET_MIDDLE + CARD_COUNT
OFFSET_DISCARD = OFFSET_BOTTOM + CARD_COUNT
FEATURE_DIMENSION = OFFSET_DISCARD + CARD_COUNT
STATE_FEATURE_LIMIT = OFFSET_TOP


def _index(card: Card) -> int:
    try:
        return CARD_INDEX[str(card)]
    except KeyError as exc:
        raise ValueError(f"unknown physical card: {card}") from exc


def _canonical_arrangement(
    arrangement: FantasyArrangement,
    suit_map: tuple[int, int, int, int],
) -> FantasyArrangement:
    def row(cards):
        return tuple(sorted(permute_card(card, suit_map) for card in cards))
    return FantasyArrangement(
        board=Board(
            top=row(arrangement.board.top),
            middle=row(arrangement.board.middle),
            bottom=row(arrangement.board.bottom),
        ),
        discarded=row(arrangement.discarded),
    )


def canonical_policy_view(
    own_packet: tuple[Card, ...] | list[Card],
    arrangement: FantasyArrangement,
    *,
    current_meta: HUContinuationState,
    player: int,
) -> tuple[str, tuple[Card, ...], FantasyArrangement]:
    if hand_kernel_kind(current_meta) != KERNEL_FANTASY_FANTASY:
        raise ValueError("Fantasy policy features require Fantasy/Fantasy meta-state")
    cards = tuple(own_packet)
    validate_arrangement(cards, arrangement)
    visible_key, canonical_packet, suit_map = canonical_visible_packet(
        cards, current_meta, player
    )
    canonical_arrangement = _canonical_arrangement(arrangement, suit_map)
    validate_arrangement(canonical_packet, canonical_arrangement)
    return visible_key, canonical_packet, canonical_arrangement


def encode_policy_state(
    own_packet: tuple[Card, ...] | list[Card],
    *,
    current_meta: HUContinuationState,
    player: int,
) -> tuple[int, ...]:
    if hand_kernel_kind(current_meta) != KERNEL_FANTASY_FANTASY:
        raise ValueError("Fantasy policy state requires Fantasy/Fantasy meta-state")
    cards = tuple(own_packet)
    _key, canonical_packet, _suit_map = canonical_visible_packet(
        cards, current_meta, player
    )
    out = {
        OFFSET_BIAS,
        OFFSET_PLAYER + player,
        OFFSET_BUTTON + current_meta.button,
        OFFSET_P0_COUNT + (current_meta.p0_fantasy_cards - 14),
        OFFSET_P1_COUNT + (current_meta.p1_fantasy_cards - 14),
    }
    for card in canonical_packet:
        out.add(OFFSET_PACKET + _index(card))
    result = tuple(sorted(out))
    if result[-1] >= STATE_FEATURE_LIMIT:
        raise AssertionError("Fantasy policy state feature escaped state range")
    return result


def encode_policy_action(
    own_packet: tuple[Card, ...] | list[Card],
    arrangement: FantasyArrangement,
    *,
    current_meta: HUContinuationState,
    player: int,
) -> tuple[int, ...]:
    _key, _canonical_packet, canonical = canonical_policy_view(
        own_packet, arrangement, current_meta=current_meta, player=player
    )
    out: set[int] = set()
    for card in canonical.board.top:
        out.add(OFFSET_TOP + _index(card))
    for card in canonical.board.middle:
        out.add(OFFSET_MIDDLE + _index(card))
    for card in canonical.board.bottom:
        out.add(OFFSET_BOTTOM + _index(card))
    for card in canonical.discarded:
        out.add(OFFSET_DISCARD + _index(card))
    result = tuple(sorted(out))
    if not result or result[0] < STATE_FEATURE_LIMIT or result[-1] >= FEATURE_DIMENSION:
        raise AssertionError("Fantasy policy action feature escaped action range")
    if len(result) != len(tuple(own_packet)):
        # 13 placed cards plus N-13 discards = N action-membership features.
        raise AssertionError("Fantasy policy action feature lost a physical card")
    return result


def encode_policy_state_action(
    own_packet: tuple[Card, ...] | list[Card],
    arrangement: FantasyArrangement,
    *,
    current_meta: HUContinuationState,
    player: int,
) -> tuple[int, ...]:
    state = encode_policy_state(own_packet, current_meta=current_meta, player=player)
    action = encode_policy_action(
        own_packet, arrangement, current_meta=current_meta, player=player
    )
    return state + action


def feature_dimension() -> int:
    return FEATURE_DIMENSION
