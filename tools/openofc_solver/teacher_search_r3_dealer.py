from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Sequence

from engine import Action, Board, Card, apply_action, full_deck, legal_actions
from teacher_search import solve_r4_exact
from teacher_search_nondealer import solve_r4_nondealer_uniform_belief


# A complete heads-up score is bounded by six row/scoop points plus at most
# 97 royalties (top 22, middle 50, bottom 25) in either direction.
TERMINAL_POINT_ABS_BOUND = 103
BELIEF = (
    "UNIFORM_HIDDEN_OPPONENT_R1_R3_DISCARDS_AND_DISJOINT_R4_PACKETS_"
    "UNDER_CARD_BLIND_REACHABILITY_V1"
)


@dataclass(frozen=True)
class R3DealerWorld:
    opponent_hidden_discards: tuple[Card, ...]
    opponent_r4_packet: tuple[Card, ...]
    dealer_r4_packet: tuple[Card, ...]


@dataclass(frozen=True)
class R3DealerActionEstimate:
    action: Action
    samples: int
    lower_points_sum: int
    upper_points_sum: int
    lower_mean: float
    upper_mean: float
    observed_min: int
    observed_max: int
    confidence_lower: float
    confidence_upper: float
    opponent_r4_tie_worlds: int


@dataclass(frozen=True)
class R3DealerBackupResult:
    known_count: int
    unseen_count: int
    samples: int
    seed: int
    confidence_delta: float
    hoeffding_margin: float
    belief_model: str
    certified_unique_best: R3DealerActionEstimate | None
    empirical_robust_best: tuple[R3DealerActionEstimate, ...]
    all_actions: tuple[R3DealerActionEstimate, ...]


def _known_cards(
    dealer_before: Board,
    opponent_after_r3: Board,
    dealer_incoming: Sequence[Card],
    dealer_known_discards: Sequence[Card],
) -> tuple[Card, ...]:
    return (
        dealer_before.top + dealer_before.middle + dealer_before.bottom
        + opponent_after_r3.top + opponent_after_r3.middle
        + opponent_after_r3.bottom
        + tuple(dealer_incoming) + tuple(dealer_known_discards)
    )


def _validate_state(
    dealer_before: Board,
    opponent_after_r3: Board,
    dealer_incoming: Sequence[Card],
    dealer_known_discards: Sequence[Card],
) -> tuple[Card, ...]:
    if dealer_before.count() != 9:
        raise ValueError("dealer R3 requires exactly 9 placed dealer cards")
    if opponent_after_r3.count() != 11:
        raise ValueError("dealer R3 requires the opponent's 11 public cards")
    if len(dealer_incoming) != 3:
        raise ValueError("dealer R3 requires exactly 3 dealer incoming cards")
    if len(dealer_known_discards) != 2:
        raise ValueError("dealer R3 requires the dealer's two prior discards")
    known = _known_cards(
        dealer_before,
        opponent_after_r3,
        dealer_incoming,
        dealer_known_discards,
    )
    if len(known) != 25:
        raise AssertionError("dealer R3 information set must contain 25 cards")
    if len(set(known)) != 25:
        raise ValueError("duplicate physical card in dealer R3 information set")
    deck = set(full_deck(2))
    if any(card not in deck for card in known):
        raise ValueError("dealer R3 information set contains an invalid card")
    unseen = tuple(sorted(deck - set(known)))
    if len(unseen) != 29:
        raise AssertionError(f"dealer R3 must have 29 unseen cards, got {len(unseen)}")
    return unseen


def _validate_world(world: R3DealerWorld, unseen: Sequence[Card]) -> None:
    groups = (
        world.opponent_hidden_discards,
        world.opponent_r4_packet,
        world.dealer_r4_packet,
    )
    if any(len(group) != 3 for group in groups):
        raise ValueError("every dealer R3 hidden-world group must contain 3 cards")
    physical = tuple(card for group in groups for card in group)
    if len(set(physical)) != 9:
        raise ValueError("dealer R3 hidden-world groups must be disjoint")
    if any(card not in set(unseen) for card in physical):
        raise ValueError("dealer R3 hidden world contains a visible/invalid card")


def sample_r3_dealer_worlds(
    unseen: Sequence[Card],
    sample_count: int,
    seed: int,
) -> tuple[R3DealerWorld, ...]:
    """Draw independent uniform physical determinizations of one R3 info set.

    Each shuffle partitions the 29 unseen cards into the opponent's three
    hidden R1-R3 discards, the non-dealer R4 packet, the dealer R4 packet and
    20 undealt cards.  The same worlds are reused for every candidate R3
    action (common random numbers), reducing action-difference variance.
    """
    if sample_count <= 0:
        raise ValueError("dealer R3 sample_count must be positive")
    if len(unseen) != 29 or len(set(unseen)) != 29:
        raise ValueError("dealer R3 world sampler requires 29 unique unseen cards")
    rng = random.Random(seed)
    worlds: list[R3DealerWorld] = []
    for _ in range(sample_count):
        shuffled = list(unseen)
        rng.shuffle(shuffled)
        worlds.append(R3DealerWorld(
            tuple(sorted(shuffled[0:3])),
            tuple(sorted(shuffled[3:6])),
            tuple(sorted(shuffled[6:9])),
        ))
    return tuple(worlds)


def _terminal_interval_for_world(
    dealer_after_r3: Board,
    opponent_after_r3: Board,
    world: R3DealerWorld,
) -> tuple[int, int, bool]:
    # Opponent is the non-dealer on R4.  Their teacher sees only their legal
    # information set: both public 11-card boards, their packet and their own
    # hidden previous discards.  It integrates over the dealer packet instead
    # of receiving the actual sampled dealer packet.
    opponent_r4 = solve_r4_nondealer_uniform_belief(
        opponent_after_r3,
        dealer_after_r3,
        world.opponent_r4_packet,
        world.opponent_hidden_discards,
    )
    dealer_values: list[int] = []
    for opponent_value in opponent_r4.optimal_actions:
        opponent_final = apply_action(
            opponent_after_r3,
            world.opponent_r4_packet,
            opponent_value.action,
        )
        dealer_r4 = solve_r4_exact(
            dealer_after_r3,
            opponent_final,
            world.dealer_r4_packet,
        )
        dealer_values.append(dealer_r4.best_points)
    if not dealer_values:
        raise AssertionError("non-dealer R4 teacher returned no optimal action")
    return min(dealer_values), max(dealer_values), len(dealer_values) > 1


def solve_r3_dealer_sampled_backup(
    dealer_before: Board,
    opponent_after_r3: Board,
    dealer_incoming: Sequence[Card],
    dealer_known_discards: Sequence[Card],
    *,
    sample_count: int = 64,
    seed: int = 20260825,
    confidence_delta: float = 0.01,
    worlds: Sequence[R3DealerWorld] | None = None,
) -> R3DealerBackupResult:
    """Back up dealer/button R3 through both certified R4 teachers.

    The result is an auditable sampled Q interval, not an exact finite-tree
    oracle.  A label is called `certified_unique_best` only when one action's
    lower Hoeffding confidence bound is strictly above every competing upper
    bound, including the interval induced by point-optimal opponent R4 ties.
    Otherwise the complete Q interval is returned without inventing a class.
    """
    if not 0.0 < confidence_delta < 1.0:
        raise ValueError("confidence_delta must be between zero and one")
    unseen = _validate_state(
        dealer_before,
        opponent_after_r3,
        dealer_incoming,
        dealer_known_discards,
    )
    if worlds is None:
        selected_worlds = sample_r3_dealer_worlds(unseen, sample_count, seed)
    else:
        selected_worlds = tuple(worlds)
        if not selected_worlds:
            raise ValueError("dealer R3 explicit world set is empty")
        if sample_count != 64 and sample_count != len(selected_worlds):
            raise ValueError("sample_count conflicts with explicit world count")
        sample_count = len(selected_worlds)
    for world in selected_worlds:
        _validate_world(world, unseen)

    actions = legal_actions(dealer_before, dealer_incoming, 3)
    if not actions:
        raise ValueError("dealer has no legal R3 action")
    # Union bound over both the lower and upper sample means of every action.
    mean_count = 2 * len(actions)
    point_range = 2 * TERMINAL_POINT_ABS_BOUND
    margin = point_range * math.sqrt(
        math.log((2.0 * mean_count) / confidence_delta)
        / (2.0 * sample_count)
    )

    estimates: list[R3DealerActionEstimate] = []
    for action in actions:
        dealer_after = apply_action(dealer_before, dealer_incoming, action)
        lower_values: list[int] = []
        upper_values: list[int] = []
        tie_worlds = 0
        for world in selected_worlds:
            low, high, tied = _terminal_interval_for_world(
                dealer_after,
                opponent_after_r3,
                world,
            )
            lower_values.append(low)
            upper_values.append(high)
            tie_worlds += int(tied)
        lower_mean = sum(lower_values) / sample_count
        upper_mean = sum(upper_values) / sample_count
        estimates.append(R3DealerActionEstimate(
            action=action,
            samples=sample_count,
            lower_points_sum=sum(lower_values),
            upper_points_sum=sum(upper_values),
            lower_mean=lower_mean,
            upper_mean=upper_mean,
            observed_min=min(lower_values),
            observed_max=max(upper_values),
            confidence_lower=max(
                -TERMINAL_POINT_ABS_BOUND, lower_mean - margin),
            confidence_upper=min(
                TERMINAL_POINT_ABS_BOUND, upper_mean + margin),
            opponent_r4_tie_worlds=tie_worlds,
        ))

    best_lower_mean = max(value.lower_mean for value in estimates)
    robust_best = tuple(
        value for value in estimates if value.lower_mean == best_lower_mean
    )
    certified: R3DealerActionEstimate | None = None
    for candidate in estimates:
        other_upper = max(
            (other.confidence_upper for other in estimates if other is not candidate),
            default=-math.inf,
        )
        if candidate.confidence_lower > other_upper:
            certified = candidate
            break

    return R3DealerBackupResult(
        known_count=25,
        unseen_count=29,
        samples=sample_count,
        seed=seed,
        confidence_delta=confidence_delta,
        hoeffding_margin=margin,
        belief_model=BELIEF,
        certified_unique_best=certified,
        empirical_robust_best=robust_best,
        all_actions=tuple(estimates),
    )
