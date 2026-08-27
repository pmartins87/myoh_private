from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from engine import Action, Board, Card, apply_action, legal_actions, resolve_board, score_heads_up


@dataclass(frozen=True)
class R4ActionValue:
    action: Action
    points: int
    fantasy_cards: int
    foul: bool


@dataclass(frozen=True)
class R4OracleResult:
    best_points: int
    optimal_actions: tuple[R4ActionValue, ...]
    all_actions: tuple[R4ActionValue, ...]


def solve_r4_exact(hero_before: Board, opponent_final: Board,
                   incoming: Sequence[Card]) -> R4OracleResult:
    """Exact terminal oracle for a fully observed heads-up round-4 decision.

    This exhausts every legal place-2/discard-1 action and optimizes current-hand
    KKPoker points. Fantasy continuation is metadata rather than a fabricated
    heuristic reward, so ties can later be resolved by a learned continuation EV.
    """
    if hero_before.count() != 11:
        raise ValueError("R4 hero board must contain exactly 11 placed cards")
    if not opponent_final.complete():
        raise ValueError("R4 exact oracle requires opponent final 13-card board")
    actions = legal_actions(hero_before, incoming, 4)
    values: list[R4ActionValue] = []
    for action in actions:
        final_board = apply_action(hero_before, incoming, action)
        score = score_heads_up(final_board, opponent_final)
        resolved = resolve_board(final_board)
        values.append(R4ActionValue(
            action=action,
            points=score.points,
            fantasy_cards=0 if resolved is None else resolved.fantasy_cards,
            foul=resolved is None,
        ))
    best = max(v.points for v in values)
    optimal = tuple(v for v in values if v.points == best)
    return R4OracleResult(best, optimal, tuple(values))
