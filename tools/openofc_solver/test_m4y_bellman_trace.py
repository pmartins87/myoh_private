from __future__ import annotations

from dataclasses import dataclass

from hu_continuation import HUContinuationState, all_states, zero_continuation_values
from m4w_outcome_model import FantasyOutcomeExample, OUTCOME_COUNT
from m4y_bellman_trace import (
    EVIDENCE_FIXTURE,
    assess_trace_coverage,
    benchmark_m4w_on_trace,
    derive_trace_family,
    freeze_bellman_trace,
)


def _vectors():
    states = all_states()
    reference = HUContinuationState(0, 0, 0)
    moving = next(state for state in states if state != reference)
    other = next(state for state in states if state not in (reference, moving))
    rows = []
    for a, b, offset in (
        (0.0, 0.0, 11.0),
        (1.0, 0.0, -4.0),
        (2.0, 0.5, 7.5),
        (2.5, 0.7, 3.0),
        (5.0, 1.0, -9.0),
    ):
        values = zero_continuation_values()
        # Raw Bellman images may differ by a gauge constant. M4Y must remove it.
        for state in values:
            values[state] += offset
        values[moving] += a
        values[other] += b
        rows.append(values)
    return rows


def test_trace_normalization_and_sha_determinism() -> None:
    kwargs = dict(
        provenance="synthetic M4Y regression fixture",
        oracle_manifest_sha256="1" * 64,
        evidence_kind=EVIDENCE_FIXTURE,
    )
    a = freeze_bellman_trace(_vectors(), **kwargs)
    b = freeze_bellman_trace(_vectors(), **kwargs)
    assert a.sha256 == b.sha256
    assert len(a.points) == 5
    reference = HUContinuationState(0, 0, 0)
    assert all(abs(point.as_mapping()[reference]) < 1e-12 for point in a.points)
    assert [point.gain_anchor for point in a.points] == [11.0, -4.0, 7.5, 3.0, -9.0]


def test_training_only_family_and_holdout_escape_detection() -> None:
    trace = freeze_bellman_trace(
        _vectors(),
        provenance="synthetic M4Y regression fixture",
        oracle_manifest_sha256="2" * 64,
        evidence_kind=EVIDENCE_FIXTURE,
    )
    derivation = derive_trace_family(trace, training_points=3, anchor_count=2)
    again = derive_trace_family(trace, training_points=3, anchor_count=2)
    assert derivation.anchor_indices == again.anchor_indices
    assert derivation.family.sha256 == again.family.sha256
    assert derivation.training_indices == (0, 1, 2)
    assert derivation.holdout_indices == (3, 4)
    # The far future fixture deliberately leaves the training cover.
    coverage = assess_trace_coverage(trace, derivation)
    assert coverage.status == "SYNTHETIC_FIXTURE_ONLY"
    assert coverage.holdout_points == 2
    assert 0.0 <= coverage.holdout_inside_fraction <= 1.0
    assert coverage.max_holdout_distance_linf >= coverage.mean_holdout_distance_linf


@dataclass
class PerfectPredictor:
    row: FantasyOutcomeExample

    def predict_features(self, state_features, action_features):
        assert tuple(state_features) == self.row.state_features
        assert tuple(action_features) == self.row.action_features
        return self.row.immediate_target, self.row.next_mode_distribution


def test_m4w_benchmark_is_exact_for_perfect_predictor() -> None:
    trace = freeze_bellman_trace(
        _vectors(),
        provenance="synthetic M4Y regression fixture",
        oracle_manifest_sha256="3" * 64,
        evidence_kind=EVIDENCE_FIXTURE,
    )
    distribution = [0.0] * OUTCOME_COUNT
    distribution[0] = 0.25
    distribution[-1] = 0.75
    example = FantasyOutcomeExample(
        state_features=(1, 7, 9),
        action_features=(3, 5),
        player=1,
        current_button=1,
        immediate_target=-2.5,
        next_mode_distribution=tuple(distribution),
        source="synthetic-m4y-perfect-predictor-fixture",
    )
    report = benchmark_m4w_on_trace(
        PerfectPredictor(example),
        (example,),
        trace,
        point_indices=(3, 4),
    )
    assert report.examples == 1
    assert report.q_observations == 2
    assert report.mean_immediate_abs_error == 0.0
    assert report.mean_outcome_brier == 0.0
    assert report.mean_q_abs_error < 1e-12
    assert report.max_q_abs_error < 1e-12
    assert report.status == "SYNTHETIC_FIXTURE_ONLY"


def test_real_evidence_label_is_not_inferred() -> None:
    try:
        freeze_bellman_trace(
            _vectors(),
            provenance="bad evidence label",
            oracle_manifest_sha256="4" * 64,
            evidence_kind="REALISH",
        )
    except ValueError as exc:
        assert "evidence kind" in str(exc)
    else:
        raise AssertionError("M4Y accepted an undeclared evidence kind")


def main() -> None:
    test_trace_normalization_and_sha_determinism()
    test_training_only_family_and_holdout_escape_detection()
    test_m4w_benchmark_is_exact_for_perfect_predictor()
    test_real_evidence_label_is_not_inferred()
    print(
        "OPENOFC_M4Y_BELLMAN_TRACE=PASS "
        "fixture_only=TRUE family_selection=TRAIN_ONLY "
        "holdout=MEASURED m4w_q_transport=VERIFIED"
    )


if __name__ == "__main__":
    main()
