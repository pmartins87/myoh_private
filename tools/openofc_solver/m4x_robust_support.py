from __future__ import annotations

"""M4X robust Fantasy/Fantasy action support across continuation regions.

M4O intentionally binds each proposal support to one continuation vector.  M4W,
however, can revalue a fixed action under a changing outer Bellman vector.  M4X
bridges those two facts without pretending that a support generated at V0 is
automatically adequate at V1.

The module:
  * freezes a SHA-bound family of complete, gauge-normalized continuation anchors;
  * takes the union of M4O own-information proposal supports over those anchors;
  * audits that fixed union against the exact M4N counterfactual teacher; and
  * exposes a conservative L-infinity extension theorem.

For a fixed hidden world, every legal Fantasy action has

    Q_a(V) = immediate_a +/- V(next_state),

so it is 1-Lipschitz in ||.||_infinity.  Both the unrestricted exact best
response and the best response inside a fixed support are therefore
1-Lipschitz.  Their non-negative support gap is consequently 2-Lipschitz:

    gap(V) <= gap(V_anchor) + 2 ||V - V_anchor||_infinity.

This is a mathematical bound over a *declared* continuation region.  M4X does
not prove that the future Bellman trajectory stays inside that region and does
not promote a policy to runtime authority.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from engine import Board, Card, score_heads_up
from fantasy_counterfactual_frontier import build_fantasy_counterfactual_frontier
from fantasy_fantasy_kernel import FantasyArrangement, validate_arrangement
from fantasy_fantasy_payoff import continuation_fingerprint
from fantasy_fantasy_proposals import generate_fantasy_proposals
from fantasy_response_frontier import evaluate_fantasy_response_frontier
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    all_states,
    hand_kernel_kind,
    next_state_from_terminal_boards,
)

FAMILY_SCHEMA = "openofc-m4x-continuation-family-v1"
SUPPORT_SCHEMA = "openofc-m4x-robust-union-support-v1"
AUDIT_SCHEMA = "openofc-m4x-robust-support-audit-v1"
AUTHORITY = "EXACT_M4N_AUDITED_CONTINUATION_REGION_SUPPORT"
STATUS = "DECLARED_REGION_BOUND_ONLY_NOT_BELLMAN_TRAJECTORY_CERTIFIED"
LIPSCHITZ_GAP_CONSTANT = 2.0
EPS = 1e-9


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: Mapping[str, object]) -> str:
    raw = dict(payload)
    raw.pop("sha256", None)
    return hashlib.sha256(_canonical_bytes(raw)).hexdigest()


def _is_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _board_payload(board: Board) -> dict[str, tuple[str, ...]]:
    return {
        "top": tuple(sorted(str(card) for card in board.top)),
        "middle": tuple(sorted(str(card) for card in board.middle)),
        "bottom": tuple(sorted(str(card) for card in board.bottom)),
    }


@dataclass(frozen=True)
class ContinuationAnchor:
    label: str
    values: tuple[tuple[HUContinuationState, float], ...]
    sha256: str

    def as_mapping(self) -> dict[HUContinuationState, float]:
        return {state: float(value) for state, value in self.values}


@dataclass(frozen=True)
class ContinuationFamily:
    anchors: tuple[ContinuationAnchor, ...]
    radius_linf: float
    provenance: str
    source_sha256: str
    normalization_reference: str
    sha256: str
    schema: str = FAMILY_SCHEMA
    status: str = STATUS

    def anchor(self, label: str) -> ContinuationAnchor:
        for anchor in self.anchors:
            if anchor.label == label:
                return anchor
        raise KeyError(label)


def freeze_continuation_family(
    named_vectors: Mapping[str, Mapping[HUContinuationState, float]],
    *,
    radius_linf: float,
    provenance: str,
    source_sha256: str,
    normalization_reference: HUContinuationState | None = None,
) -> ContinuationFamily:
    """Freeze deterministic continuation anchors and a declared L-infinity radius.

    All anchors must use the same relative-value gauge.  By default the normal /
    normal, button-0 state is required to be exactly zero (within EPS).
    """
    if not named_vectors:
        raise ValueError("continuation family requires at least one anchor")
    if not math.isfinite(float(radius_linf)) or float(radius_linf) < 0.0:
        raise ValueError("radius_linf must be finite and non-negative")
    if not str(provenance).strip():
        raise ValueError("continuation family provenance must be non-empty")
    if not _is_sha256(str(source_sha256)):
        raise ValueError("source_sha256 must be a 64-hex SHA-256")

    reference = normalization_reference or HUContinuationState(0, 0, 0)
    if reference not in set(all_states()):
        raise ValueError("normalization reference is outside the 50-state catalog")

    anchors: list[ContinuationAnchor] = []
    if any(not isinstance(label, str) or not label for label in named_vectors):
        raise ValueError("continuation anchor labels must be non-empty strings")
    labels = sorted(named_vectors)

    for label in labels:
        checked, fingerprint = continuation_fingerprint(named_vectors[label])
        if abs(float(checked[reference])) > EPS:
            raise ValueError(
                "all continuation anchors must share the declared zero-valued gauge"
            )
        anchors.append(
            ContinuationAnchor(
                label=label,
                values=tuple((state, float(checked[state])) for state in sorted(checked)),
                sha256=fingerprint,
            )
        )

    payload: dict[str, object] = {
        "schema": FAMILY_SCHEMA,
        "radius_linf": float(radius_linf),
        "provenance": str(provenance),
        "source_sha256": str(source_sha256).lower(),
        "normalization_reference": reference.as_key(),
        "anchors": [
            {"label": anchor.label, "continuation_sha256": anchor.sha256}
            for anchor in anchors
        ],
    }
    family_sha = _sha(payload)
    return ContinuationFamily(
        anchors=tuple(anchors),
        radius_linf=float(radius_linf),
        provenance=str(provenance),
        source_sha256=str(source_sha256).lower(),
        normalization_reference=reference.as_key(),
        sha256=family_sha,
    )


def linf_distance(
    left: Mapping[HUContinuationState, float],
    right: Mapping[HUContinuationState, float],
) -> float:
    checked_left, _ = continuation_fingerprint(left)
    checked_right, _ = continuation_fingerprint(right)
    return max(
        abs(float(checked_left[state]) - float(checked_right[state]))
        for state in checked_left
    )


@dataclass(frozen=True)
class ContinuationRegionMembership:
    inside: bool
    nearest_anchor: str
    distance_linf: float
    radius_linf: float
    family_sha256: str


def continuation_region_membership(
    family: ContinuationFamily,
    continuation_values: Mapping[HUContinuationState, float],
) -> ContinuationRegionMembership:
    checked, _ = continuation_fingerprint(continuation_values)
    reference = next(
        state for state in all_states() if state.as_key() == family.normalization_reference
    )
    if abs(float(checked[reference])) > EPS:
        raise ValueError("candidate continuation vector uses a different relative-value gauge")
    distances = [
        (linf_distance(anchor.as_mapping(), checked), anchor.label)
        for anchor in family.anchors
    ]
    distance, label = min(distances, key=lambda row: (row[0], row[1]))
    return ContinuationRegionMembership(
        inside=distance <= family.radius_linf + EPS,
        nearest_anchor=label,
        distance_linf=float(distance),
        radius_linf=family.radius_linf,
        family_sha256=family.sha256,
    )


@dataclass(frozen=True)
class RobustFantasySupport:
    player: int
    current_meta: HUContinuationState
    own_packet: tuple[Card, ...]
    candidates: tuple[FantasyArrangement, ...]
    canonical_action_keys: tuple[str, ...]
    anchor_action_keys: tuple[tuple[str, tuple[str, ...]], ...]
    synthetic_worlds_per_anchor: int
    max_candidates_per_anchor: int
    family_sha256: str
    visible_fingerprint: str
    sha256: str
    schema: str = SUPPORT_SCHEMA
    authority: str = AUTHORITY
    status: str = STATUS

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


def generate_robust_union_support(
    own_packet: Sequence[Card],
    *,
    current_meta: HUContinuationState,
    player: int,
    family: ContinuationFamily,
    synthetic_worlds_per_anchor: int = 8,
    max_candidates_per_anchor: int = 32,
    base_seed: int = 20260827,
) -> RobustFantasySupport:
    """Union M4O supports generated independently at every family anchor."""
    if player not in (0, 1):
        raise ValueError("HU player must be 0 or 1")
    if hand_kernel_kind(current_meta) != KERNEL_FANTASY_FANTASY:
        raise ValueError("M4X robust support requires Fantasy/Fantasy meta-state")
    packet = tuple(sorted(own_packet))
    if len(packet) != current_meta.mode_for(player):
        raise ValueError("own packet count does not match Fantasy mode")
    if synthetic_worlds_per_anchor <= 0 or max_candidates_per_anchor <= 0:
        raise ValueError("M4X proposal budgets must be positive")

    # canonical action key -> actual-suit arrangement for this fixed own packet.
    union: dict[str, FantasyArrangement] = {}
    anchor_rows: list[tuple[str, tuple[str, ...]]] = []
    visible_fingerprint: str | None = None

    for anchor in family.anchors:
        proposal = generate_fantasy_proposals(
            packet,
            current_meta=current_meta,
            player=player,
            continuation_values=anchor.as_mapping(),
            synthetic_worlds=synthetic_worlds_per_anchor,
            max_candidates=max_candidates_per_anchor,
            base_seed=base_seed,
        )
        if proposal.continuation_fingerprint != anchor.sha256:
            raise AssertionError("M4O proposal continuation fingerprint drifted")
        if visible_fingerprint is None:
            visible_fingerprint = proposal.visible_fingerprint
        elif visible_fingerprint != proposal.visible_fingerprint:
            raise AssertionError("visible own-information fingerprint changed across anchors")

        anchor_rows.append((anchor.label, proposal.canonical_action_keys))
        for key, arrangement in zip(
            proposal.canonical_action_keys, proposal.candidates, strict=True
        ):
            validate_arrangement(packet, arrangement)
            existing = union.get(key)
            if existing is None:
                union[key] = arrangement
            elif existing != arrangement:
                raise AssertionError(
                    "same canonical own-information action key mapped to different arrangement"
                )

    if not union or visible_fingerprint is None:
        raise AssertionError("M4X robust support is empty")

    ordered_keys = tuple(sorted(union))
    candidates = tuple(union[key] for key in ordered_keys)
    payload: dict[str, object] = {
        "schema": SUPPORT_SCHEMA,
        "player": player,
        "state": current_meta.as_key(),
        "family_sha256": family.sha256,
        "visible_fingerprint": visible_fingerprint,
        "synthetic_worlds_per_anchor": int(synthetic_worlds_per_anchor),
        "max_candidates_per_anchor": int(max_candidates_per_anchor),
        "base_seed": int(base_seed),
        "canonical_action_keys": ordered_keys,
        "anchor_action_keys": [
            {"label": label, "keys": keys} for label, keys in anchor_rows
        ],
    }
    support_sha = _sha(payload)
    return RobustFantasySupport(
        player=player,
        current_meta=current_meta,
        own_packet=packet,
        candidates=candidates,
        canonical_action_keys=ordered_keys,
        anchor_action_keys=tuple(anchor_rows),
        synthetic_worlds_per_anchor=int(synthetic_worlds_per_anchor),
        max_candidates_per_anchor=int(max_candidates_per_anchor),
        family_sha256=family.sha256,
        visible_fingerprint=visible_fingerprint,
        sha256=support_sha,
    )


@dataclass(frozen=True)
class _SupportFactor:
    action_key: str
    immediate_hero_points: float
    next_state: HUContinuationState


def _support_factors(
    support: RobustFantasySupport,
    opponent_board: Board,
) -> tuple[_SupportFactor, ...]:
    factors: list[_SupportFactor] = []
    for key, arrangement in zip(
        support.canonical_action_keys, support.candidates, strict=True
    ):
        validate_arrangement(support.own_packet, arrangement)
        # score_heads_up is from its first board's perspective, so put Hero first.
        immediate = float(score_heads_up(arrangement.board, opponent_board).points)
        if support.player == 0:
            board0, board1 = arrangement.board, opponent_board
        else:
            board0, board1 = opponent_board, arrangement.board
        nxt = next_state_from_terminal_boards(support.current_meta, board0, board1)
        factors.append(_SupportFactor(key, immediate, nxt))
    return tuple(factors)


def _factor_utility(
    factor: _SupportFactor,
    *,
    player: int,
    continuation_values: Mapping[HUContinuationState, float],
) -> float:
    p0_value = float(continuation_values[factor.next_state])
    hero_continuation = p0_value if player == 0 else -p0_value
    return float(factor.immediate_hero_points) + hero_continuation


@dataclass(frozen=True)
class RobustSupportPointEvaluation:
    exact_teacher_utility: float
    support_best_utility: float
    support_gap: float
    best_action_key: str


def evaluate_robust_support_at(
    support: RobustFantasySupport,
    opponent_board: Board,
    continuation_values: Mapping[HUContinuationState, float],
) -> RobustSupportPointEvaluation:
    checked, _ = continuation_fingerprint(continuation_values)
    frontier = build_fantasy_counterfactual_frontier(
        support.own_packet,
        opponent_board,
        current_state=support.current_meta,
        hero_player=support.player,
    )
    exact = float(evaluate_fantasy_response_frontier(frontier, checked).utility)
    factors = _support_factors(support, opponent_board)
    best_value, best_key = max(
        (
            _factor_utility(
                factor,
                player=support.player,
                continuation_values=checked,
            ),
            factor.action_key,
        )
        for factor in factors
    )
    gap = exact - float(best_value)
    if gap < -EPS:
        raise AssertionError("M4X robust support exceeded exact M4N teacher")
    return RobustSupportPointEvaluation(
        exact_teacher_utility=exact,
        support_best_utility=float(best_value),
        support_gap=max(0.0, gap),
        best_action_key=best_key,
    )


@dataclass(frozen=True)
class RobustSupportAnchorAudit:
    label: str
    continuation_sha256: str
    exact_teacher_utility: float
    support_best_utility: float
    support_gap: float
    declared_ball_gap_upper_bound: float
    best_action_key: str


@dataclass(frozen=True)
class RobustSupportAudit:
    support_sha256: str
    family_sha256: str
    opponent_board_sha256: str
    anchor_results: tuple[RobustSupportAnchorAudit, ...]
    max_anchor_gap: float
    max_declared_region_gap_upper_bound: float
    sha256: str
    schema: str = AUDIT_SCHEMA
    authority: str = AUTHORITY
    status: str = STATUS


def audit_robust_support(
    support: RobustFantasySupport,
    opponent_board: Board,
    family: ContinuationFamily,
) -> RobustSupportAudit:
    """Audit all anchors with one exact M4N frontier construction.

    M4N's branchwise immediate optima are continuation-independent, so one
    expensive exact frontier suffices for every anchor in the family.
    """
    if support.family_sha256 != family.sha256:
        raise ValueError("support was generated from a different continuation family")

    frontier = build_fantasy_counterfactual_frontier(
        support.own_packet,
        opponent_board,
        current_state=support.current_meta,
        hero_player=support.player,
    )
    factors = _support_factors(support, opponent_board)
    rows: list[RobustSupportAnchorAudit] = []

    for anchor in family.anchors:
        values = anchor.as_mapping()
        exact = float(evaluate_fantasy_response_frontier(frontier, values).utility)
        best_value, best_key = max(
            (
                _factor_utility(
                    factor,
                    player=support.player,
                    continuation_values=values,
                ),
                factor.action_key,
            )
            for factor in factors
        )
        gap = exact - float(best_value)
        if gap < -EPS:
            raise AssertionError("M4X robust support exceeded exact M4N teacher")
        gap = max(0.0, gap)
        rows.append(
            RobustSupportAnchorAudit(
                label=anchor.label,
                continuation_sha256=anchor.sha256,
                exact_teacher_utility=exact,
                support_best_utility=float(best_value),
                support_gap=gap,
                declared_ball_gap_upper_bound=(
                    gap + LIPSCHITZ_GAP_CONSTANT * family.radius_linf
                ),
                best_action_key=best_key,
            )
        )

    board_sha = hashlib.sha256(_canonical_bytes(_board_payload(opponent_board))).hexdigest()
    max_anchor_gap = max(row.support_gap for row in rows)
    max_region_bound = max(row.declared_ball_gap_upper_bound for row in rows)
    payload: dict[str, object] = {
        "schema": AUDIT_SCHEMA,
        "support_sha256": support.sha256,
        "family_sha256": family.sha256,
        "opponent_board_sha256": board_sha,
        "lipschitz_gap_constant": LIPSCHITZ_GAP_CONSTANT,
        "anchor_results": [
            {
                "label": row.label,
                "continuation_sha256": row.continuation_sha256,
                "support_gap": row.support_gap,
                "declared_ball_gap_upper_bound": row.declared_ball_gap_upper_bound,
                "best_action_key": row.best_action_key,
            }
            for row in rows
        ],
        "max_anchor_gap": max_anchor_gap,
        "max_declared_region_gap_upper_bound": max_region_bound,
        "status": STATUS,
    }
    audit_sha = _sha(payload)
    return RobustSupportAudit(
        support_sha256=support.sha256,
        family_sha256=family.sha256,
        opponent_board_sha256=board_sha,
        anchor_results=tuple(rows),
        max_anchor_gap=max_anchor_gap,
        max_declared_region_gap_upper_bound=max_region_bound,
        sha256=audit_sha,
    )


@dataclass(frozen=True)
class RobustSupportGapBound:
    nearest_anchor: str
    distance_linf: float
    anchor_support_gap: float
    gap_upper_bound: float
    inside_declared_region: bool
    theorem: str = "gap(V)<=gap(anchor)+2*||V-anchor||inf"


def robust_support_gap_bound(
    audit: RobustSupportAudit,
    family: ContinuationFamily,
    continuation_values: Mapping[HUContinuationState, float],
) -> RobustSupportGapBound:
    """Return the exact conservative extension bound for a vector inside the region."""
    if audit.family_sha256 != family.sha256:
        raise ValueError("audit and continuation family SHA mismatch")
    membership = continuation_region_membership(family, continuation_values)
    if not membership.inside:
        raise ValueError("continuation vector is outside the declared M4X region")
    row = next(
        result
        for result in audit.anchor_results
        if result.label == membership.nearest_anchor
    )
    bound = row.support_gap + LIPSCHITZ_GAP_CONSTANT * membership.distance_linf
    return RobustSupportGapBound(
        nearest_anchor=membership.nearest_anchor,
        distance_linf=membership.distance_linf,
        anchor_support_gap=row.support_gap,
        gap_upper_bound=float(bound),
        inside_declared_region=True,
    )
