from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Sequence

from engine import Action, Board, Card, ResolvedBoard, apply_action, full_deck, legal_actions, resolve_board


@dataclass(frozen=True)
class R4NonDealerActionValue:
    action: Action
    expected_points_num: int
    expected_points_den: int
    packet_min_points: int
    packet_max_points: int
    fantasy_cards: int
    foul: bool


@dataclass(frozen=True)
class R4NonDealerOracleResult:
    unseen_count: int
    opponent_packet_count: int
    best_expected_points_num: int
    best_expected_points_den: int
    optimal_actions: tuple[R4NonDealerActionValue, ...]
    all_actions: tuple[R4NonDealerActionValue, ...]


def _require_m1b_materialized() -> None:
    doc = resolve_board.__doc__ or ""
    if "row-local semantics" not in doc:
        raise RuntimeError(
            "M1b Joker semantics are not materialized. Run "
            "`python tools/openofc_solver/apply_m1b_joker_semantics.py` first; "
            "refusing to compute information-set teacher values with the "
            "superseded Joker evaluator."
        )


def _score_points_from_resolved(
    hero: ResolvedBoard | None,
    opponent: ResolvedBoard | None,
) -> int:
    """Current-hand heads-up points using already-resolved boards.

    This is the integer point projection of engine.score_heads_up. The oracle
    resolves each final board once and reuses it across thousands of terminal
    pairings; tests cross-check this projection against the canonical engine.
    """
    if hero is None and opponent is None:
        return 0
    if hero is None:
        assert opponent is not None
        return -6 - opponent.royalties
    if opponent is None:
        return 6 + hero.royalties

    row_points = tuple(
        1 if hero.ranks[i] > opponent.ranks[i]
        else -1 if hero.ranks[i] < opponent.ranks[i]
        else 0
        for i in range(3)
    )
    scoop = 3 if row_points == (1, 1, 1) else -3 if row_points == (-1, -1, -1) else 0
    return sum(row_points) + scoop + hero.royalties - opponent.royalties


def _known_cards(
    hero_before: Board,
    opponent_before: Board,
    hero_incoming: Sequence[Card],
    hero_known_discards: Sequence[Card],
) -> tuple[Card, ...]:
    return (
        hero_before.top + hero_before.middle + hero_before.bottom
        + opponent_before.top + opponent_before.middle + opponent_before.bottom
        + tuple(hero_incoming) + tuple(hero_known_discards)
    )


def solve_r4_nondealer_uniform_belief(
    hero_before: Board,
    opponent_before: Board,
    hero_incoming: Sequence[Card],
    hero_known_discards: Sequence[Card],
) -> R4NonDealerOracleResult:
    """Solve the non-dealer R4 current-hand information set exactly.

    Contract for M2b-v1:
    - Hero/non-dealer acts first on R4 with 11 placed cards and 3 known incoming.
    - Opponent has 11 public placed cards but their R4 3-card packet is hidden.
    - Hero knows their own three prior discards; opponent prior discards stay hidden.
    - Under the current M2 reachability sampler, earlier actions are uniformly
      sampled from legal actions and are card-identity blind. Hidden card
      identities are therefore exchangeable conditional on Hero's information.
      The opponent R4 packet is exactly uniform over 3-card subsets of the 26
      cards unseen by Hero.
    - After Hero acts, opponent sees Hero's final board and chooses an exact
      current-hand best response. KKPoker hand points are zero-sum, so that
      response minimizes Hero's current-hand points.

    This is exact for CURRENT-HAND points under that explicit uniform belief.
    Fantasy continuation EV is deliberately not converted into heuristic points.
    Later self-play must replace the reachability belief with a strategic belief.
    """
    _require_m1b_materialized()
    if hero_before.count() != 11 or opponent_before.count() != 11:
        raise ValueError("non-dealer R4 requires 11 placed cards for both players")
    if len(hero_incoming) != 3:
        raise ValueError("non-dealer R4 requires exactly 3 Hero incoming cards")
    if len(hero_known_discards) != 3:
        raise ValueError("non-dealer R4 requires Hero's 3 known prior discards")

    deck = tuple(full_deck(2))
    known = _known_cards(hero_before, opponent_before, hero_incoming, hero_known_discards)
    if len(known) != 28:
        raise AssertionError("non-dealer R4 information set must contain 28 known physical cards")
    if len(set(known)) != len(known):
        raise ValueError("duplicate physical card in non-dealer R4 information set")
    deck_set = set(deck)
    if any(card not in deck_set for card in known):
        raise ValueError("non-dealer R4 information set contains a card outside the 54-card deck")

    unseen = tuple(sorted(deck_set - set(known)))
    if len(unseen) != 26:
        raise AssertionError(f"expected 26 unseen cards, got {len(unseen)}")
    packet_count = comb(len(unseen), 3)
    if packet_count != 2600:
        raise AssertionError(f"expected 2600 opponent packets, got {packet_count}")

    hero_actions = legal_actions(hero_before, hero_incoming, 4)
    if not hero_actions:
        raise ValueError("Hero has no legal R4 action")
    hero_finals = [apply_action(hero_before, hero_incoming, action) for action in hero_actions]

    resolved_cache: dict[Board, ResolvedBoard | None] = {}

    def resolved(board: Board) -> ResolvedBoard | None:
        if board not in resolved_cache:
            resolved_cache[board] = resolve_board(board)
        return resolved_cache[board]

    hero_resolved = [resolved(board) for board in hero_finals]
    sums = [0 for _ in hero_actions]
    minima = [10**9 for _ in hero_actions]
    maxima = [-10**9 for _ in hero_actions]
    observed_packets = 0

    # Opponent packet order is strategically irrelevant; every physical 3-card
    # subset has equal probability under the certified uniform-unseen belief.
    for packet in combinations(unseen, 3):
        opponent_actions = legal_actions(opponent_before, packet, 4)
        if not opponent_actions:
            raise AssertionError("reachable opponent R4 packet has no legal action")
        opponent_finals = [apply_action(opponent_before, packet, a) for a in opponent_actions]
        opponent_resolved = [resolved(board) for board in opponent_finals]

        for i, hr in enumerate(hero_resolved):
            # Opponent acts second and best-responds after seeing Hero's final
            # board. Because current-hand score is zero-sum, choose the minimum
            # Hero point outcome. Tied best responses remain equivalent here;
            # continuation EV will distinguish them in later milestones.
            worst = min(_score_points_from_resolved(hr, vr) for vr in opponent_resolved)
            sums[i] += worst
            minima[i] = min(minima[i], worst)
            maxima[i] = max(maxima[i], worst)
        observed_packets += 1

    if observed_packets != packet_count:
        raise AssertionError("opponent chance enumeration was incomplete")

    values: list[R4NonDealerActionValue] = []
    for i, action in enumerate(hero_actions):
        hr = hero_resolved[i]
        values.append(R4NonDealerActionValue(
            action=action,
            expected_points_num=sums[i],
            expected_points_den=packet_count,
            packet_min_points=minima[i],
            packet_max_points=maxima[i],
            fantasy_cards=0 if hr is None else hr.fantasy_cards,
            foul=hr is None,
        ))

    best_num = max(v.expected_points_num for v in values)
    optimal = tuple(v for v in values if v.expected_points_num == best_num)
    return R4NonDealerOracleResult(
        unseen_count=len(unseen),
        opponent_packet_count=packet_count,
        best_expected_points_num=best_num,
        best_expected_points_den=packet_count,
        optimal_actions=optimal,
        all_actions=tuple(values),
    )
