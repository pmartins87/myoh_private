from __future__ import annotations

"""Bounded own-information-only action support for sealed Fantasy/Fantasy HU.

This is a proposal mechanism, not policy authority.  It converts a million-plus
raw Fantasy arrangements into a bounded candidate support by sampling synthetic
opponent worlds conditioned only on the player's own packet and public meta-state,
then asking the exact M4N poker teacher for branchwise responses.

The actual hidden opponent packet/board is never an input.  Candidate-support
loss can later be measured against M4N on held-out complete worlds.
"""

from dataclasses import dataclass
import hashlib
import json
import random
from typing import Mapping, Sequence

from engine import Board, Card, full_deck, resolve_board, score_heads_up
from fantasy_counterfactual_frontier import build_fantasy_counterfactual_frontier
from fantasy_fantasy_kernel import FantasyArrangement, validate_arrangement
from fantasy_response_frontier import evaluate_fantasy_response_frontier
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    hand_kernel_kind,
    next_state_from_terminal_boards,
)
from strategic_continuation_cfr import validate_continuation_values
from strategic_suit_symmetry import SUIT_PERMUTATIONS, permute_card

AUTHORITY = "BOUNDED_FANTASY_FANTASY_OWN_INFORMATION_PROPOSAL_V1"
POLICY_STATUS = "PROPOSAL_SUPPORT_ONLY_NOT_SOLVED_POLICY"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _visible_key_under_map(
    packet: Sequence[Card],
    current_meta: HUContinuationState,
    player: int,
    suit_map: Sequence[int],
) -> str:
    payload = {
        "v": 1,
        "player": player,
        "button": current_meta.button,
        "p0_fantasy_count": current_meta.p0_fantasy_cards,
        "p1_fantasy_count": current_meta.p1_fantasy_cards,
        "own_packet": tuple(
            sorted(str(permute_card(card, suit_map)) for card in packet)
        ),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def canonical_visible_packet(
    packet: Sequence[Card],
    current_meta: HUContinuationState,
    player: int,
) -> tuple[str, tuple[Card, ...], tuple[int, int, int, int]]:
    if player not in (0, 1):
        raise ValueError("HU player must be 0 or 1")
    cards = tuple(packet)
    expected = current_meta.mode_for(player)
    if expected not in (14, 15, 16, 17) or len(cards) != expected:
        raise ValueError("own packet count does not match Fantasy mode")
    key, suit_map = min(
        (
            _visible_key_under_map(cards, current_meta, player, suit_map),
            suit_map,
        )
        for suit_map in SUIT_PERMUTATIONS
    )
    canonical = tuple(sorted(permute_card(card, suit_map) for card in cards))
    return key, canonical, suit_map


def _inverse_suit_map(suit_map: Sequence[int]) -> tuple[int, int, int, int]:
    inverse = [0, 0, 0, 0]
    for source, target in enumerate(suit_map):
        inverse[int(target)] = int(source)
    return tuple(inverse)  # type: ignore[return-value]


def _arrangement_key(arrangement: FantasyArrangement) -> str:
    payload = {
        "top": tuple(sorted(str(card) for card in arrangement.board.top)),
        "middle": tuple(sorted(str(card) for card in arrangement.board.middle)),
        "bottom": tuple(sorted(str(card) for card in arrangement.board.bottom)),
        "discarded": tuple(sorted(str(card) for card in arrangement.discarded)),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _remap_arrangement(
    arrangement: FantasyArrangement,
    inverse_suit_map: Sequence[int],
) -> FantasyArrangement:
    def row(cards):
        return tuple(sorted(permute_card(card, inverse_suit_map) for card in cards))
    return FantasyArrangement(
        board=Board(
            top=row(arrangement.board.top),
            middle=row(arrangement.board.middle),
            bottom=row(arrangement.board.bottom),
        ),
        discarded=row(arrangement.discarded),
    )


def _continuation_fingerprint(
    continuation_values: Mapping[HUContinuationState, float],
) -> tuple[dict[HUContinuationState, float], str]:
    checked = validate_continuation_values(continuation_values)
    payload = {
        state.as_key(): float(checked[state])
        for state in sorted(checked)
    }
    return checked, hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _synthetic_nonfoul_board(
    opponent_packet: Sequence[Card],
    rng: random.Random,
    *,
    attempts: int = 96,
) -> Board:
    cards = list(opponent_packet)
    first: Board | None = None
    for _ in range(attempts):
        rng.shuffle(cards)
        board = Board(
            top=tuple(sorted(cards[0:3])),
            middle=tuple(sorted(cards[3:8])),
            bottom=tuple(sorted(cards[8:13])),
        )
        if first is None:
            first = board
        if resolve_board(board) is not None:
            return board
    if first is None:
        raise AssertionError("synthetic opponent packet was empty")
    return first


@dataclass(frozen=True)
class FantasyProposalSet:
    player: int
    current_meta: HUContinuationState
    own_packet: tuple[Card, ...]
    candidates: tuple[FantasyArrangement, ...]
    canonical_action_keys: tuple[str, ...]
    synthetic_worlds: int
    exact_teacher_calls: int
    max_candidates: int
    visible_fingerprint: str
    continuation_fingerprint: str
    authority: str = AUTHORITY

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


@dataclass(frozen=True)
class ProposalSupportEvaluation:
    exact_teacher_utility: float
    proposal_best_utility: float
    support_gap: float
    candidate_count: int


def generate_fantasy_proposals(
    own_packet: Sequence[Card],
    *,
    current_meta: HUContinuationState,
    player: int,
    continuation_values: Mapping[HUContinuationState, float],
    synthetic_worlds: int = 8,
    max_candidates: int = 32,
    base_seed: int = 20260827,
) -> FantasyProposalSet:
    if hand_kernel_kind(current_meta) != KERNEL_FANTASY_FANTASY:
        raise ValueError("M4O proposal generator requires Fantasy/Fantasy meta-state")
    if synthetic_worlds <= 0 or max_candidates <= 0:
        raise ValueError("synthetic_worlds and max_candidates must be positive")
    visible_key, canonical_packet, suit_map = canonical_visible_packet(
        own_packet, current_meta, player
    )
    checked_values, continuation_sha = _continuation_fingerprint(continuation_values)
    seed_material = {
        "visible_key": visible_key,
        "continuation_sha256": continuation_sha,
        "base_seed": int(base_seed),
    }
    seed = int.from_bytes(hashlib.sha256(_canonical_bytes(seed_material)).digest()[:8], "big")
    rng = random.Random(seed)

    opponent = 1 - player
    opponent_count = current_meta.mode_for(opponent)
    available = [card for card in full_deck(2) if card not in set(canonical_packet)]
    if opponent_count > len(available):
        raise AssertionError("not enough physical cards for synthetic opponent packet")

    # canonical action key -> [arrangement, occurrence count, utility sum]
    pool: dict[str, list] = {}
    teacher_calls = 0
    for _ in range(synthetic_worlds):
        opponent_packet = tuple(sorted(rng.sample(available, opponent_count)))
        opponent_board = _synthetic_nonfoul_board(opponent_packet, rng)
        frontier = build_fantasy_counterfactual_frontier(
            canonical_packet,
            opponent_board,
            current_state=current_meta,
            hero_player=player,
        )
        teacher_calls += 1
        for candidate in (frontier.no_refantasy, frontier.refantasy):
            if candidate is None:
                continue
            arrangement = FantasyArrangement(candidate.board, candidate.discarded)
            validate_arrangement(canonical_packet, arrangement)
            action_key = _arrangement_key(arrangement)
            p0 = float(checked_values[candidate.next_state])
            hero_cont = p0 if player == 0 else -p0
            utility = float(candidate.immediate_points) + hero_cont
            old = pool.get(action_key)
            if old is None:
                pool[action_key] = [arrangement, 1, utility]
            else:
                old[1] += 1
                old[2] += utility

    if not pool:
        raise AssertionError("proposal generator produced no Fantasy arrangement")
    ranked = sorted(
        pool.items(),
        key=lambda item: (
            -int(item[1][1]),
            -float(item[1][2]) / float(item[1][1]),
            item[0],
        ),
    )[:max_candidates]
    inverse = _inverse_suit_map(suit_map)
    output_candidates = []
    output_keys = []
    original_packet = tuple(sorted(own_packet))
    for action_key, row in ranked:
        mapped = _remap_arrangement(row[0], inverse)
        validate_arrangement(original_packet, mapped)
        output_candidates.append(mapped)
        output_keys.append(action_key)

    return FantasyProposalSet(
        player=player,
        current_meta=current_meta,
        own_packet=original_packet,
        candidates=tuple(output_candidates),
        canonical_action_keys=tuple(output_keys),
        synthetic_worlds=synthetic_worlds,
        exact_teacher_calls=teacher_calls,
        max_candidates=max_candidates,
        visible_fingerprint=hashlib.sha256(visible_key.encode("utf-8")).hexdigest(),
        continuation_fingerprint=continuation_sha,
    )


def _candidate_utility(
    proposal: FantasyProposalSet,
    arrangement: FantasyArrangement,
    opponent_board: Board,
    continuation_values: Mapping[HUContinuationState, float],
) -> float:
    validate_arrangement(proposal.own_packet, arrangement)
    player = proposal.player
    immediate = float(score_heads_up(arrangement.board, opponent_board).points)
    if player == 0:
        board0, board1 = arrangement.board, opponent_board
    else:
        board0, board1 = opponent_board, arrangement.board
    nxt = next_state_from_terminal_boards(proposal.current_meta, board0, board1)
    if nxt not in continuation_values:
        raise KeyError(f"continuation value missing for {nxt.as_key()}")
    p0 = float(continuation_values[nxt])
    return immediate + (p0 if player == 0 else -p0)


def evaluate_proposal_support(
    proposal: FantasyProposalSet,
    opponent_board: Board,
    continuation_values: Mapping[HUContinuationState, float],
) -> ProposalSupportEvaluation:
    checked, sha = _continuation_fingerprint(continuation_values)
    if sha != proposal.continuation_fingerprint:
        raise ValueError("proposal support must be evaluated with its generating continuation vector")
    frontier = build_fantasy_counterfactual_frontier(
        proposal.own_packet,
        opponent_board,
        current_state=proposal.current_meta,
        hero_player=proposal.player,
    )
    exact = evaluate_fantasy_response_frontier(frontier, checked).utility
    best = max(
        _candidate_utility(proposal, arrangement, opponent_board, checked)
        for arrangement in proposal.candidates
    )
    gap = float(exact) - float(best)
    if gap < -1e-9:
        raise AssertionError("bounded proposal support exceeded exact Fantasy teacher")
    return ProposalSupportEvaluation(
        exact_teacher_utility=float(exact),
        proposal_best_utility=float(best),
        support_gap=max(0.0, gap),
        candidate_count=proposal.candidate_count,
    )
