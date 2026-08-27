from __future__ import annotations

"""Held-out evidence producer for M5E Fantasy/Fantasy route certification.

The five M5E strategic metrics are measured from the same sealed support/model
objects that will face the Bellman operator, while exact complete-world teachers
remain offline:

* M4N exact unrestricted response versus the M4X robust support;
* exact M4P support-restricted unilateral deviation;
* exact M4V per-action Q targets versus M4W predictions;
* chance-world standard error of the support-policy profile value.

Thresholds are never inferred here.  They are caller-supplied through
`FantasyEvidenceBudgets` and forwarded unchanged to M5E.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Callable, Mapping, Sequence

from engine import Board
from fantasy_fantasy_payoff import (
    continuation_fingerprint,
    expected_p0_value,
)
from hu_continuation import HUContinuationState, KERNEL_FANTASY_FANTASY, hand_kernel_kind
from m4u_continuation_boundary import materialize_factorized_payoff
from m4v_continuation_targets import build_continuation_linear_targets
from m4w_outcome_model import build_outcome_examples
from m4x_robust_support import (
    ContinuationFamily,
    RobustFantasySupport,
    evaluate_robust_support_at,
)
from m5a_fantasy_fantasy_oracle import model_fingerprint
from m5b_fantasy_selfplay import ContinuationAwareEpisode, snapshot_policy
from m5e_fantasy_route_certification import freeze_route_evidence

REPORT_SCHEMA = "openofc-m5f-fantasy-heldout-report-v1"
AUTHORITY = "REAL_M4X_M4N_M4P_M4V_M4W_HELDOUT_EVIDENCE_PRODUCER"
EPS = 1e-12

SupportGapEvaluator = Callable[
    [RobustFantasySupport, Board, Mapping[HUContinuationState, float]], float
]


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: Mapping[str, object]) -> str:
    raw = dict(payload)
    raw.pop("sha256", None)
    return hashlib.sha256(_canonical_bytes(raw)).hexdigest()


def _is_sha256(value: object) -> bool:
    text = str(value)
    if len(text) != 64:
        return False
    try:
        int(text, 16)
    except ValueError:
        return False
    return True


def exact_support_gap(
    support: RobustFantasySupport,
    opponent_board: Board,
    continuation_values: Mapping[HUContinuationState, float],
) -> float:
    """Production M4N teacher hook used unless a CI fixture explicitly injects one."""
    return float(
        evaluate_robust_support_at(
            support, opponent_board, continuation_values
        ).support_gap
    )


@dataclass(frozen=True)
class FantasyEvidenceBudgets:
    max_support_gap: float
    max_support_deviation_gain: float
    max_model_q_mae: float
    max_model_q_error: float
    max_standard_error: float

    def __post_init__(self) -> None:
        for value in (
            self.max_support_gap,
            self.max_support_deviation_gain,
            self.max_model_q_mae,
            self.max_model_q_error,
            self.max_standard_error,
        ):
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise ValueError("M5F evidence budgets must be finite/non-negative")


@dataclass(frozen=True)
class HeldoutFantasyEpisode:
    seed: int
    episode: ContinuationAwareEpisode
    p0_support: RobustFantasySupport
    p1_support: RobustFantasySupport

    def __post_init__(self) -> None:
        meta = self.episode.world.current_meta
        if hand_kernel_kind(meta) != KERNEL_FANTASY_FANTASY:
            raise ValueError("M5F held-out episode must be Fantasy/Fantasy")
        if self.p0_support.player != 0 or self.p1_support.player != 1:
            raise ValueError("M5F held-out support player mismatch")
        if self.p0_support.current_meta != meta or self.p1_support.current_meta != meta:
            raise ValueError("M5F held-out support meta-state mismatch")
        if tuple(self.p0_support.candidates) != tuple(self.episode.p0_support):
            raise ValueError("M5F P0 robust support differs from factorized episode")
        if tuple(self.p1_support.candidates) != tuple(self.episode.p1_support):
            raise ValueError("M5F P1 robust support differs from factorized episode")
        if self.p0_support.family_sha256 != self.p1_support.family_sha256:
            raise ValueError("M5F held-out supports belong to different M4X families")


@dataclass(frozen=True)
class FantasyHeldoutWorldMetric:
    seed: int
    profile_p0_value: float
    max_support_gap: float
    support_deviation_gain: float
    mean_q_abs_error: float
    max_q_abs_error: float
    q_targets: int


@dataclass(frozen=True)
class FantasyRouteHeldoutReport:
    state: str
    continuation_sha256: str
    family_sha256: str
    model_sha256: str
    oracle_id: str
    worlds: int
    distinct_seeds: int
    mean_profile_p0_value: float
    standard_error: float
    max_support_gap: float
    max_support_deviation_gain: float
    model_q_mae: float
    model_q_max_error: float
    q_targets: int
    world_metrics: tuple[FantasyHeldoutWorldMetric, ...]
    provenance: str
    sha256: str
    schema: str = REPORT_SCHEMA
    authority: str = AUTHORITY
    promotion_blocked: bool = True


@dataclass(frozen=True)
class FantasyEvidenceBundle:
    report: FantasyRouteHeldoutReport
    route_evidence: Mapping[str, object]


def _mean_standard_error(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise ValueError("M5F requires held-out profile values")
    mean = sum(values) / len(values)
    if len(values) == 1:
        return float(mean), 0.0
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return float(mean), float(math.sqrt(max(0.0, variance) / len(values)))


def _support_gap_for_world(
    row: HeldoutFantasyEpisode,
    continuation_values: Mapping[HUContinuationState, float],
    evaluator: SupportGapEvaluator,
) -> float:
    gaps: list[float] = []
    # Conservative full-support audit: every candidate opponent board is an
    # admissible pure response.  Max conditional support gap upper-bounds the
    # omitted-action loss against any mixture over those opponent support boards.
    for opponent in row.p1_support.candidates:
        gaps.append(
            float(evaluator(row.p0_support, opponent.board, continuation_values))
        )
    for opponent in row.p0_support.candidates:
        gaps.append(
            float(evaluator(row.p1_support, opponent.board, continuation_values))
        )
    if not gaps or any(not math.isfinite(value) or value < -EPS for value in gaps):
        raise ValueError("M5F support-gap evaluator returned invalid value")
    return max(0.0, max(gaps))


def collect_fantasy_route_evidence(
    oracle: object,
    state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
    heldout: Sequence[HeldoutFantasyEpisode],
    budgets: FantasyEvidenceBudgets,
    *,
    implementation_sha256: str,
    reference_authority: str,
    provenance: str,
    support_gap_evaluator: SupportGapEvaluator = exact_support_gap,
) -> FantasyEvidenceBundle:
    """Measure real held-out metrics and freeze the corresponding M5E record."""
    if hand_kernel_kind(state) != KERNEL_FANTASY_FANTASY:
        raise ValueError("M5F only evaluates Fantasy/Fantasy routes")
    rows = tuple(heldout)
    if not rows:
        raise ValueError("M5F requires held-out worlds")
    if not _is_sha256(implementation_sha256):
        raise ValueError("M5F implementation SHA-256 is invalid")
    if not str(reference_authority).strip() or not str(provenance).strip():
        raise ValueError("M5F requires reference authority/provenance")

    model = getattr(oracle, "model", None)
    family = getattr(oracle, "family", None)
    snapshot = getattr(oracle, "snapshot", None)
    oracle_id = str(getattr(oracle, "oracle_id", ""))
    if model is None or not isinstance(family, ContinuationFamily) or snapshot is None:
        raise ValueError("M5F oracle must expose model, M4X family and snapshot")
    if not oracle_id:
        raise ValueError("M5F oracle must expose oracle_id")
    model_sha = model_fingerprint(model)
    if str(getattr(snapshot, "model_sha256", "")) != model_sha:
        raise ValueError("M5F oracle snapshot/model SHA mismatch")
    if str(getattr(snapshot, "family_sha256", "")) != family.sha256:
        raise ValueError("M5F oracle snapshot/family SHA mismatch")

    checked, continuation_sha = continuation_fingerprint(continuation_values)
    world_metrics: list[FantasyHeldoutWorldMetric] = []
    all_q_errors: list[float] = []
    profile_values: list[float] = []

    for row in rows:
        episode = row.episode
        if episode.world.current_meta != state:
            raise ValueError("M5F held-out world belongs to another route state")
        if row.p0_support.family_sha256 != family.sha256:
            raise ValueError("M5F held-out support belongs to another M4X family")

        policy = snapshot_policy(model, episode, checked)
        matrix = materialize_factorized_payoff(episode.factor, checked)
        profile_value = expected_p0_value(
            matrix, policy.p0_policy, policy.p1_policy
        )
        if abs(profile_value - policy.diagnostic.profile_p0_value) > 1e-9:
            raise AssertionError("M5F profile value disagrees with M4P diagnostic")

        linear = build_continuation_linear_targets(
            episode.factor,
            p0_opponent_policy=policy.p1_policy,
            p1_opponent_policy=policy.p0_policy,
        )
        examples = build_outcome_examples(
            episode.world,
            episode.p0_support,
            episode.p1_support,
            linear,
            source="m5f-heldout-exact-m4v-target",
        )
        targets = tuple(linear.p0_targets) + tuple(linear.p1_targets)
        if len(examples) != len(targets):
            raise AssertionError("M5F M4W example/target cardinality mismatch")
        q_errors: list[float] = []
        for example, target in zip(examples, targets, strict=True):
            predicted = model.predict_q_features(
                example.state_features,
                example.action_features,
                current_meta=state,
                player=example.player,
                continuation_values=checked,
            )
            exact = target.value(checked)
            error = abs(float(predicted) - float(exact))
            if not math.isfinite(error):
                raise AssertionError("M5F M4W Q error became non-finite")
            q_errors.append(error)
            all_q_errors.append(error)

        support_gap = _support_gap_for_world(
            row, checked, support_gap_evaluator
        )
        deviation = float(policy.diagnostic.total_support_deviation_gain)
        if not math.isfinite(deviation) or deviation < -EPS:
            raise AssertionError("M5F support deviation became invalid")
        profile_values.append(float(profile_value))
        world_metrics.append(
            FantasyHeldoutWorldMetric(
                seed=int(row.seed),
                profile_p0_value=float(profile_value),
                max_support_gap=float(support_gap),
                support_deviation_gain=max(0.0, deviation),
                mean_q_abs_error=sum(q_errors) / len(q_errors),
                max_q_abs_error=max(q_errors),
                q_targets=len(q_errors),
            )
        )

    if not all_q_errors:
        raise AssertionError("M5F produced no held-out Q targets")
    mean_value, standard_error = _mean_standard_error(profile_values)
    max_gap = max(metric.max_support_gap for metric in world_metrics)
    max_deviation = max(metric.support_deviation_gain for metric in world_metrics)
    q_mae = sum(all_q_errors) / len(all_q_errors)
    q_max = max(all_q_errors)
    distinct_seeds = len({metric.seed for metric in world_metrics})
    if distinct_seeds <= 0:
        raise AssertionError("M5F lost held-out seed provenance")

    payload: dict[str, object] = {
        "schema": REPORT_SCHEMA,
        "authority": AUTHORITY,
        "state": state.as_key(),
        "continuation_sha256": continuation_sha,
        "family_sha256": family.sha256,
        "model_sha256": model_sha,
        "oracle_id": oracle_id,
        "worlds": len(world_metrics),
        "distinct_seeds": distinct_seeds,
        "mean_profile_p0_value": mean_value,
        "standard_error": standard_error,
        "max_support_gap": max_gap,
        "max_support_deviation_gain": max_deviation,
        "model_q_mae": q_mae,
        "model_q_max_error": q_max,
        "q_targets": len(all_q_errors),
        "world_metrics": [
            {
                "seed": metric.seed,
                "profile_p0_value": metric.profile_p0_value,
                "max_support_gap": metric.max_support_gap,
                "support_deviation_gain": metric.support_deviation_gain,
                "mean_q_abs_error": metric.mean_q_abs_error,
                "max_q_abs_error": metric.max_q_abs_error,
                "q_targets": metric.q_targets,
            }
            for metric in world_metrics
        ],
        "provenance": str(provenance).strip(),
        "promotion_blocked": True,
    }
    report = FantasyRouteHeldoutReport(
        state=state.as_key(),
        continuation_sha256=continuation_sha,
        family_sha256=family.sha256,
        model_sha256=model_sha,
        oracle_id=oracle_id,
        worlds=len(world_metrics),
        distinct_seeds=distinct_seeds,
        mean_profile_p0_value=mean_value,
        standard_error=standard_error,
        max_support_gap=max_gap,
        max_support_deviation_gain=max_deviation,
        model_q_mae=q_mae,
        model_q_max_error=q_max,
        q_targets=len(all_q_errors),
        world_metrics=tuple(world_metrics),
        provenance=str(provenance).strip(),
        sha256=_sha(payload),
    )

    evidence = freeze_route_evidence(
        state,
        checked,
        family,
        oracle_id=oracle_id,
        model_sha256=model_sha,
        implementation_sha256=implementation_sha256,
        support_gap=max_gap,
        support_deviation_gain=max_deviation,
        model_q_mae=q_mae,
        model_q_max_error=q_max,
        standard_error=standard_error,
        heldout_worlds=len(world_metrics),
        heldout_seeds=distinct_seeds,
        max_support_gap=budgets.max_support_gap,
        max_support_deviation_gain=budgets.max_support_deviation_gain,
        max_model_q_mae=budgets.max_model_q_mae,
        max_model_q_error=budgets.max_model_q_error,
        max_standard_error=budgets.max_standard_error,
        reference_authority=str(reference_authority).strip(),
        provenance=(
            f"{str(provenance).strip()} | M5F report {report.sha256}"
        ),
    )
    return FantasyEvidenceBundle(report=report, route_evidence=evidence)
