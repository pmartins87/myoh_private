from __future__ import annotations

from dataclasses import replace

from hu_continuation import (
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    all_states,
    hand_kernel_kind,
    zero_continuation_values,
)
from fantasy_fantasy_payoff import continuation_fingerprint
from m4z_outer_bellman import OneHandOracleResult, OracleRegistry
from m5c_route_certification import (
    EVIDENCE_HELDOUT,
    EVIDENCE_TEST,
    STATUS_BLOCKED,
    STATUS_READY,
    STATUS_TEST_ONLY,
    KernelThresholds,
    certification_summary,
    certify_route,
    freeze_route_evidence,
    freeze_threshold_manifest,
    register_certified_route,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


def state_for(kind: str):
    return next(state for state in all_states() if hand_kernel_kind(state) == kind)


def thresholds():
    return freeze_threshold_manifest(
        normal_normal=KernelThresholds(
            min_heldout_seeds=2,
            min_heldout_samples=100,
            max_value_standard_error=0.10,
            max_unilateral_deviation=0.20,
        ),
        normal_fantasy=KernelThresholds(
            min_heldout_seeds=2,
            min_heldout_samples=100,
            max_value_standard_error=0.10,
            max_unilateral_deviation=0.20,
        ),
        fantasy_fantasy=KernelThresholds(
            min_heldout_seeds=2,
            min_heldout_samples=100,
            max_value_standard_error=0.10,
            max_unilateral_deviation=0.20,
            max_support_gap=0.15,
            max_model_q_error=0.12,
        ),
        provenance="TEST_ONLY_EXPLICIT_THRESHOLDS_DO_NOT_DEFINE_PRODUCTION_BUDGETS",
    )


def evidence(kind: str, *, evidence_kind: str = EVIDENCE_HELDOUT, **overrides):
    state = state_for(kind)
    data = dict(
        state=state,
        oracle_id=f"oracle:{state.as_key()}",
        implementation_sha256=SHA_A,
        continuation_evidence_sha256=SHA_B,
        heldout_seed_ids=("seed-1", "seed-2"),
        heldout_samples=200,
        value_standard_error=0.05,
        max_unilateral_deviation=0.10,
        support_gap=0.08 if kind == KERNEL_FANTASY_FANTASY else None,
        model_q_error=0.07 if kind == KERNEL_FANTASY_FANTASY else None,
        evidence_kind=evidence_kind,
        provenance="independent-heldout-test-fixture",
    )
    data.update(overrides)
    return freeze_route_evidence(**data)


def test_all_kernel_classes_can_be_evaluated_against_explicit_thresholds() -> None:
    manifest = thresholds()
    for kind in (
        KERNEL_NORMAL_NORMAL,
        KERNEL_NORMAL_FANTASY,
        KERNEL_FANTASY_FANTASY,
    ):
        cert = certify_route(evidence(kind), manifest)
        assert cert.status == STATUS_READY
        assert cert.ready_for_real_bellman
        assert not cert.failures


def test_one_failed_strategic_metric_blocks_route() -> None:
    cert = certify_route(
        evidence(
            KERNEL_FANTASY_FANTASY,
            max_unilateral_deviation=0.201,
        ),
        thresholds(),
    )
    assert cert.status == STATUS_BLOCKED
    assert not cert.ready_for_real_bellman
    assert "UNILATERAL_DEVIATION_EXCEEDS_THRESHOLD" in cert.failures


def test_insufficient_heldout_provenance_blocks_route() -> None:
    cert = certify_route(
        evidence(
            KERNEL_NORMAL_FANTASY,
            heldout_seed_ids=("only-one",),
            heldout_samples=99,
        ),
        thresholds(),
    )
    assert cert.status == STATUS_BLOCKED
    assert "INSUFFICIENT_HELDOUT_SEEDS" in cert.failures
    assert "INSUFFICIENT_HELDOUT_SAMPLES" in cert.failures


def test_synthetic_evidence_can_never_become_real_route() -> None:
    cert = certify_route(
        evidence(KERNEL_NORMAL_NORMAL, evidence_kind=EVIDENCE_TEST),
        thresholds(),
    )
    # Synthetic evidence is explicitly distinguishable even if every number is small.
    assert cert.status in (STATUS_BLOCKED, STATUS_TEST_ONLY)
    assert not cert.ready_for_real_bellman

    class DummyOracle:
        oracle_id = cert.oracle_id

        def evaluate(self, state, continuation_values):
            _checked, sha = continuation_fingerprint(continuation_values)
            return OneHandOracleResult(
                state=state,
                p0_value=0.0,
                continuation_sha256=sha,
                oracle_id=self.oracle_id,
            )

    registry = OracleRegistry()
    try:
        register_certified_route(registry, DummyOracle(), cert)
    except RuntimeError:
        pass
    else:
        raise AssertionError("synthetic M5C evidence reached a REAL Bellman route")


def test_fantasy_evidence_requires_support_and_model_error() -> None:
    state = state_for(KERNEL_FANTASY_FANTASY)
    try:
        freeze_route_evidence(
            state=state,
            oracle_id="oracle",
            implementation_sha256=SHA_A,
            continuation_evidence_sha256=SHA_B,
            heldout_seed_ids=("s1", "s2"),
            heldout_samples=200,
            value_standard_error=0.01,
            max_unilateral_deviation=0.01,
            support_gap=None,
            model_q_error=None,
            provenance="missing-required-ff-metrics",
        )
    except ValueError as exc:
        assert "support_gap" in str(exc)
    else:
        raise AssertionError("Fantasy/Fantasy evidence accepted missing exact metrics")


def test_certificate_is_bound_to_oracle_identity() -> None:
    cert = certify_route(evidence(KERNEL_NORMAL_NORMAL), thresholds())

    class WrongOracle:
        oracle_id = "different-oracle"

    registry = OracleRegistry()
    try:
        register_certified_route(registry, WrongOracle(), cert)
    except ValueError as exc:
        assert "identity mismatch" in str(exc)
    else:
        raise AssertionError("M5C accepted an oracle identity mismatch")


def test_summary_requires_exact_50_state_surface() -> None:
    manifest = thresholds()
    one = certify_route(evidence(KERNEL_NORMAL_NORMAL), manifest)
    summary = certification_summary((one,))
    assert summary["ready_for_real_bellman"] == 1
    assert not summary["complete_50_state_surface"]


def main() -> None:
    test_all_kernel_classes_can_be_evaluated_against_explicit_thresholds()
    test_one_failed_strategic_metric_blocks_route()
    test_insufficient_heldout_provenance_blocks_route()
    test_synthetic_evidence_can_never_become_real_route()
    test_fantasy_evidence_requires_support_and_model_error()
    test_certificate_is_bound_to_oracle_identity()
    test_summary_requires_exact_50_state_surface()
    print("OPENOFC_M5C_ROUTE_CERTIFICATION_GATE=PASS")


if __name__ == "__main__":
    main()
