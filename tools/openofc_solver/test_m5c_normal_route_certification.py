from __future__ import annotations

from dataclasses import dataclass

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import HUContinuationState, zero_continuation_values
from m4z_outer_bellman import OneHandOracleResult, default_blocked_registry
from m5c_normal_route_certification import (
    ROUTE_BLOCKED,
    ROUTE_CERTIFIED,
    CertifiedAdaptiveNormalOracle,
    certification_route,
    freeze_certification,
    freeze_route_evidence,
    register_certified_normal_routes,
    validate_certification,
)

CONFIG_SHA = "1" * 64
IMPLEMENTATION_SHA = "2" * 64
SOURCE_SHA = "3" * 64


@dataclass
class DummyOracle:
    oracle_id: str
    value: float

    def evaluate(self, state, continuation_values):
        _checked, continuation_sha = continuation_fingerprint(continuation_values)
        return OneHandOracleResult(
            state=state,
            p0_value=self.value,
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=64,
            standard_error=0.01,
        )


def _evidence(state, values, oracle_id: str, *, model=0.20, reference=0.19, max_error=0.02):
    return freeze_route_evidence(
        state,
        values,
        oracle_id=oracle_id,
        oracle_config_sha256=CONFIG_SHA,
        implementation_sha256=IMPLEMENTATION_SHA,
        model_value=model,
        reference_value=reference,
        standard_error=0.01,
        samples=64,
        max_abs_value_error=max_error,
        max_standard_error=0.02,
        reference_authority="INDEPENDENT_HELDOUT_REFERENCE_FIXTURE",
        provenance="m5c-unit-fixture",
    )


def test_exact_continuation_sha_is_mandatory() -> None:
    values = zero_continuation_values()
    state = HUContinuationState(0, 0, 0)
    evidence = _evidence(state, values, "dummy-nn")
    cert = freeze_certification(
        [evidence],
        values,
        source_report_sha256=SOURCE_SHA,
        provenance="m5c-unit-fixture",
    )
    assert certification_route(cert, state, values) == ROUTE_CERTIFIED

    changed = dict(values)
    changed[HUContinuationState(1, 14, 14)] = 0.5
    assert certification_route(cert, state, changed) == ROUTE_BLOCKED

    wrapped = CertifiedAdaptiveNormalOracle(DummyOracle("dummy-nn", 0.20), state, cert)
    try:
        wrapped.evaluate(state, changed)
    except RuntimeError as exc:
        assert "not certified" in str(exc)
    else:
        raise AssertionError("M5C accepted stale continuation certificate")


def test_failed_evidence_cannot_be_promoted() -> None:
    values = zero_continuation_values()
    state = HUContinuationState(0, 0, 0)
    failed = _evidence(
        state,
        values,
        "dummy-nn",
        model=0.50,
        reference=0.10,
        max_error=0.02,
    )
    assert failed["passed"] is False
    try:
        freeze_certification(
            [failed],
            values,
            source_report_sha256=SOURCE_SHA,
            provenance="m5c-unit-fixture",
        )
    except ValueError as exc:
        assert "failed held-out evidence" in str(exc)
    else:
        raise AssertionError("M5C certified failed held-out evidence")


def test_partial_evidence_only_opens_exact_routes() -> None:
    values = zero_continuation_values()
    nn_state = HUContinuationState(0, 0, 0)
    nf_state = HUContinuationState(0, 0, 14)
    nn = DummyOracle("dummy-nn", 0.20)
    nf = DummyOracle("dummy-nf", -0.10)
    evidence = _evidence(nn_state, values, nn.oracle_id)
    cert = freeze_certification(
        [evidence],
        values,
        source_report_sha256=SOURCE_SHA,
        provenance="m5c-unit-fixture",
    )

    registry = default_blocked_registry()
    added = register_certified_normal_routes(
        registry,
        cert,
        normal_normal_oracle=nn,
        normal_fantasy_oracle=nf,
    )
    manifest = registry.freeze_manifest()
    assert added == 1
    assert manifest.ready_certified == 1
    assert manifest.blocked == 49
    assert certification_route(cert, nf_state, values) == ROUTE_BLOCKED

    result = registry.oracle_for(nn_state).evaluate(nn_state, values)
    assert result.p0_value == 0.20
    assert result.samples == 64
    assert result.oracle_id.startswith("m5c:")


def test_manifest_tampering_is_rejected() -> None:
    values = zero_continuation_values()
    state = HUContinuationState(0, 0, 14)
    evidence = _evidence(state, values, "dummy-nf")
    cert = freeze_certification(
        [evidence],
        values,
        source_report_sha256=SOURCE_SHA,
        provenance="m5c-unit-fixture",
    )
    tampered = dict(cert)
    tampered["certified_route_count"] = 2
    try:
        validate_certification(tampered)
    except ValueError as exc:
        assert "SHA-256 mismatch" in str(exc)
    else:
        raise AssertionError("M5C accepted tampered certification")


def main() -> None:
    test_exact_continuation_sha_is_mandatory()
    test_failed_evidence_cannot_be_promoted()
    test_partial_evidence_only_opens_exact_routes()
    test_manifest_tampering_is_rejected()
    print("OPENOFC_M5C_NORMAL_ROUTE_CERTIFICATION_GATE=PASS")


if __name__ == "__main__":
    main()
