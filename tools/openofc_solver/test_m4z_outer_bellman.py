from __future__ import annotations

from dataclasses import dataclass

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    all_states,
    zero_continuation_values,
)
from m4y_bellman_trace import EVIDENCE_FIXTURE, EVIDENCE_REAL
from m4z_outer_bellman import (
    OneHandOracleResult,
    OracleRegistry,
    ROUTE_READY_FIXTURE,
    default_blocked_registry,
    evaluate_bellman_image,
    run_relative_value_iteration,
)


@dataclass
class FixtureOracle:
    oracle_id: str = "m4z-synthetic-contraction-fixture"

    def evaluate(self, state, continuation_values):
        checked, sha = continuation_fingerprint(continuation_values)
        # A deterministic contraction with a state-specific bounded bias.
        bias = (
            0.02 * state.button
            + 0.001 * state.p0_fantasy_cards
            - 0.0015 * state.p1_fantasy_cards
        )
        partner = HUContinuationState(
            1 - state.button,
            state.p1_fantasy_cards,
            state.p0_fantasy_cards,
        )
        return OneHandOracleResult(
            state=state,
            p0_value=bias + 0.25 * checked[partner],
            continuation_sha256=sha,
            oracle_id=self.oracle_id,
            samples=1,
            standard_error=0.0,
        )


@dataclass
class WrongShaOracle(FixtureOracle):
    oracle_id: str = "m4z-wrong-sha-fixture"

    def evaluate(self, state, continuation_values):
        result = super().evaluate(state, continuation_values)
        return OneHandOracleResult(
            state=result.state,
            p0_value=result.p0_value,
            continuation_sha256="f" * 64,
            oracle_id=self.oracle_id,
            samples=1,
        )


def _fixture_registry(oracle=None):
    registry = OracleRegistry()
    oracle = oracle or FixtureOracle()
    for state in all_states():
        registry.register(
            state,
            oracle,
            status=ROUTE_READY_FIXTURE,
            authority="SYNTHETIC_M4Z_REGRESSION_FIXTURE",
            implementation_sha256="a" * 64,
        )
    return registry


def test_default_registry_is_complete_and_truthfully_blocked() -> None:
    registry = default_blocked_registry()
    manifest = registry.freeze_manifest()
    counts = manifest.kernel_counts()
    assert len(manifest.routes) == 50
    assert manifest.blocked == 50
    assert counts[KERNEL_NORMAL_NORMAL] == 2
    assert counts[KERNEL_NORMAL_FANTASY] == 16
    assert counts[KERNEL_FANTASY_FANTASY] == 32
    try:
        evaluate_bellman_image(
            registry, zero_continuation_values(), evidence_kind=EVIDENCE_REAL
        )
    except RuntimeError as exc:
        assert "50 routes" in str(exc)
    else:
        raise AssertionError("blocked registry produced a real Bellman image")


def test_fixture_full_image_and_relative_value_trace() -> None:
    registry = _fixture_registry()
    image = evaluate_bellman_image(
        registry, zero_continuation_values(), evidence_kind=EVIDENCE_FIXTURE
    )
    assert len(image.values) == 50
    run = run_relative_value_iteration(
        registry,
        zero_continuation_values(),
        max_iterations=12,
        tolerance_linf=1e-7,
        minimum_iterations=2,
        evidence_kind=EVIDENCE_FIXTURE,
        provenance="synthetic M4Z contraction regression fixture",
    )
    assert 2 <= len(run.steps) <= 12
    assert len(run.trace.points) == len(run.steps)
    assert run.trace.evidence_kind == EVIDENCE_FIXTURE
    assert run.field_promotion_blocked is True
    assert abs(run.final_mapping()[HUContinuationState(0, 0, 0)]) < 1e-12
    # Contraction should reach the requested numerical tolerance.
    assert run.converged_numerically is True
    assert run.steps[-1].residual_linf <= 1e-7 + 1e-12


def test_fixture_routes_cannot_be_relabelled_real() -> None:
    registry = _fixture_registry()
    try:
        evaluate_bellman_image(
            registry, zero_continuation_values(), evidence_kind=EVIDENCE_REAL
        )
    except RuntimeError as exc:
        assert "not READY_CERTIFIED" in str(exc)
    else:
        raise AssertionError("fixture oracle was accepted as real evidence")


def test_continuation_sha_binding_is_enforced() -> None:
    registry = _fixture_registry(WrongShaOracle())
    try:
        evaluate_bellman_image(
            registry, zero_continuation_values(), evidence_kind=EVIDENCE_FIXTURE
        )
    except AssertionError as exc:
        assert "continuation SHA" in str(exc)
    else:
        raise AssertionError("M4Z accepted oracle output bound to wrong V")


def main() -> None:
    test_default_registry_is_complete_and_truthfully_blocked()
    test_fixture_full_image_and_relative_value_trace()
    test_fixture_routes_cannot_be_relabelled_real()
    test_continuation_sha_binding_is_enforced()
    print(
        "OPENOFC_M4Z_OUTER_BELLMAN=PASS "
        "routes=50 normal_normal=2 normal_fantasy=16 fantasy_fantasy=32 "
        "real_fallback=ABSENT fixture_trace=VERIFIED"
    )


if __name__ == "__main__":
    main()
