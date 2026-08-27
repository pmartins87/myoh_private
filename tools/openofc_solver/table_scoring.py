from __future__ import annotations

"""KKPoker OFC table scoring for 2/3 players, including the win/loss cap.

The captured KKPoker scoring screen defines pairwise row/royalty/scoop scoring,
then specifies the three-player settlement order:

    UTG vs MP, UTG vs BTN, MP vs BTN.

It also states that a player's maximum win or loss is the amount that player
had on the table at the start of the hand.  Because a capped player can make a
later comparison unable to settle in full, settlement order is strategically
relevant whenever the cap can bind.

This module keeps the already-certified board score in ``engine.score_heads_up``
and adds only the table-level settlement layer.  It is exact for the stated
sequential-cap interpretation: each pair settles in rule order up to both
players' remaining final-net capacity, so every final net remains within
[-starting_funds, +starting_funds] and total transfer remains zero.
"""

from dataclasses import dataclass
import math
from typing import Sequence

from engine import Board, ScoreResult, score_heads_up


@dataclass(frozen=True)
class PairScore:
    first: int
    second: int
    points_for_first: int


@dataclass(frozen=True)
class PairSettlement:
    first: int
    second: int
    points_for_first: int
    requested_transfer: float
    applied_transfer: float
    unsettled_gap: float
    winner: int | None
    loser: int | None


@dataclass(frozen=True)
class TableScoreResult:
    dealer: int
    pair_scores: tuple[PairScore, ...]
    settlements: tuple[PairSettlement, ...]
    net_profit: tuple[float, ...]
    total_unsettled_gap: float
    cap_bound: bool


def scoring_order(player_count: int, dealer: int) -> tuple[tuple[int, int], ...]:
    """Return KKPoker pair-scoring order for 2 or 3 clockwise seats."""
    n = int(player_count)
    if n not in (2, 3):
        raise ValueError("KKPoker OFC table scoring currently supports 2 or 3 players")
    if dealer < 0 or dealer >= n:
        raise ValueError("dealer index outside table")
    if n == 2:
        nondealer = (dealer + 1) % 2
        return ((nondealer, dealer),)
    utg = (dealer + 1) % 3
    mp = (dealer + 2) % 3
    btn = dealer
    return ((utg, mp), (utg, btn), (mp, btn))


def _validate_funds(starting_funds: Sequence[float], n: int) -> tuple[float, ...]:
    if len(starting_funds) != n:
        raise ValueError("starting_funds length must equal player count")
    funds = tuple(float(x) for x in starting_funds)
    if any((not math.isfinite(x)) or x < 0.0 for x in funds):
        raise ValueError("starting funds must be finite and non-negative")
    return funds


def settle_pair_scores(
    pair_scores: Sequence[PairScore],
    *,
    starting_funds: Sequence[float],
    blind: float = 1.0,
) -> tuple[tuple[PairSettlement, ...], tuple[float, ...]]:
    """Apply the start-of-hand win/loss cap in the supplied rule order.

    ``points_for_first`` is signed.  Positive means ``first`` wins from
    ``second``; negative means the reverse.  The winner can receive at most
    ``starting_funds[winner] - current_net[winner]`` before reaching its +cap,
    and the loser can pay at most ``starting_funds[loser] + current_net[loser]``
    before reaching its -cap.
    """
    if blind <= 0.0 or not math.isfinite(blind):
        raise ValueError("blind must be finite and positive")
    n = len(starting_funds)
    funds = _validate_funds(starting_funds, n)
    net = [0.0] * n
    settlements: list[PairSettlement] = []

    for pair in pair_scores:
        if pair.first == pair.second:
            raise ValueError("pair score cannot compare a player with itself")
        if not (0 <= pair.first < n and 0 <= pair.second < n):
            raise ValueError("pair score player index outside table")
        raw = int(pair.points_for_first)
        requested = abs(raw) * float(blind)
        if raw == 0:
            settlements.append(PairSettlement(
                pair.first, pair.second, raw, 0.0, 0.0, 0.0, None, None
            ))
            continue

        if raw > 0:
            winner, loser = pair.first, pair.second
        else:
            winner, loser = pair.second, pair.first

        winner_capacity = max(0.0, funds[winner] - net[winner])
        loser_capacity = max(0.0, funds[loser] + net[loser])
        applied = min(requested, winner_capacity, loser_capacity)
        gap = max(0.0, requested - applied)
        net[winner] += applied
        net[loser] -= applied
        settlements.append(PairSettlement(
            pair.first,
            pair.second,
            raw,
            requested,
            applied,
            gap,
            winner,
            loser,
        ))

    tolerance = 1e-9
    if abs(sum(net)) > tolerance:
        raise AssertionError("table settlement must conserve money")
    for i, value in enumerate(net):
        if value > funds[i] + tolerance or value < -funds[i] - tolerance:
            raise AssertionError("table settlement exceeded a start-of-hand cap")
    return tuple(settlements), tuple(net)


def raw_pair_scores(boards: Sequence[Board], dealer: int) -> tuple[PairScore, ...]:
    n = len(boards)
    order = scoring_order(n, dealer)
    if any(not board.complete() for board in boards):
        raise ValueError("table scoring requires every player board to be complete")
    out: list[PairScore] = []
    for first, second in order:
        result: ScoreResult = score_heads_up(boards[first], boards[second])
        out.append(PairScore(first, second, int(result.points)))
    return tuple(out)


def score_table(
    boards: Sequence[Board],
    *,
    dealer: int,
    starting_funds: Sequence[float],
    blind: float = 1.0,
) -> TableScoreResult:
    """Score and settle a complete 2/3-player KKPoker OFC hand."""
    pairs = raw_pair_scores(boards, dealer)
    settlements, net = settle_pair_scores(
        pairs,
        starting_funds=starting_funds,
        blind=blind,
    )
    total_gap = sum(row.unsettled_gap for row in settlements)
    return TableScoreResult(
        dealer=int(dealer),
        pair_scores=pairs,
        settlements=settlements,
        net_profit=net,
        total_unsettled_gap=total_gap,
        cap_bound=total_gap > 0.0,
    )
