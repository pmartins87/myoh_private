from __future__ import annotations

import hashlib

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import HUContinuationState, all_states, zero_continuation_values
from m4y_bellman_trace import EVIDENCE_FIXTURE
from m4z_outer_bellman import (
    OneHandOracleResult,
    OracleRegistry,
    ROUTE_READY_FIXTURE,
)
from m5d_dynamic_certified_bellman import (
    run_dynamic_certified_relative_value_iteration,
    run_dynamic_fixture_relative_value_iteration,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ShaBoundFixtureOracle:
    def __init__(self, state: HUContinuationState, expected_sha: str, index: int) -> None:
        self.state = state
        self.expected_sha = expected_sha
        self.index = index
        self.oracle_id = f"m5d-fixture:{state.as_key()}:{expected_sha[:16]}"

    def evaluate(self, state, continuation_values) -> OneHandOracleResult:
        if state != self.state:
            raise AssertionError("fixture oracle called for wrong state")
        _checked, actual_sha = continuation_fingerprint(continuation_values)
        if actual_sha != self.expected_sha:
            raise RuntimeError("fixture oracle intentionally refuses stale V")
        # A deterministic state-only image.  After one update the normalized
        # image is a fixed point, so the second dynamic registry should converge.
        value = float(self.index) * 0.125 + float(state.button) * 0.03125
        return OneHandOracleResult(
            state=state,
            p0_value=value,
            continuation_sha256=actual_sha,
            oracle_id=self.oracle_id,
            samples=1,
            standard_error=0.0,
        )


class RecordingFixtureFactory:
    def __init__(self) -> None:
        self.input_shas: list[str] = []
        self.manifest_shas: list[str] = []

    def __call__(self, continuation_values) -> OracleRegistry:
        _checked, continuation_sha = continuation_fingerprint(continuation_values)
        self.input_shas.append(continuation_sha)
        registry = OracleRegistry()
        for index, state in enumerate(sorted(all_states())):
            oracle = ShaBoundFixtureOracle(state, continuation_sha, index)
            registry.register(
                state,
                oracle,
                status=ROUTE_READY_FIXTURE,
                authority="M5D_SYNTHETIC_SHA_BOUND_FIXTURE",
                implementation_sha256=_sha(
                    f"fixture-implementation|{continuation_sha}|{state.as_key()}"
                ),
            )
        manifest = registry.freeze_manifest()
        self.manifest_shas.append(manifest.sha256)
        return registry


def test_dynamic_driver_rebinds_registry_after_v_changes() -> None:
    factory = RecordingFixtureFactory()
    run = run_dynamic_fixture_relative_value_iteration(
        factory,
        zero_continuation_values(),
        max_iterations=4,
        minimum_iterations=2,
        tolerance_linf=0.0,
        provenance="M5D deterministic regression fixture",
    )
    assert run.evidence_kind == EVIDENCE_FIXTURE
    assert run.trace.evidence_kind == EVIDENCE_FIXTURE
    assert run.field_promotion_blocked is True
    assert run.converged_numerically is True
    assert len(run.steps) == 2
    assert len(factory.input_shas) == 2
    assert factory.input_shas[0] != factory.input_shas[1]
    assert run.steps[0].input_sha256 == factory.input_shas[0]
    assert run.steps[1].input_sha256 == factory.input_shas[1]

    # The registry itself is newly frozen at V1 rather than silently reusing V0.
    assert factory.manifest_shas[0] != factory.manifest_shas[1]
    assert run.steps[0].registry_manifest_sha256 == factory.manifest_shas[0]
    assert run.steps[1].registry_manifest_sha256 == factory.manifest_shas[1]

    # M4Y's single oracle-manifest pointer is now the immutable aggregate bundle.
    assert run.trace.oracle_manifest_sha256 == run.registry_bundle.sha256
    assert tuple(step.registry_manifest_sha256 for step in run.registry_bundle.steps) == tuple(
        factory.manifest_shas
    )
    assert run.steps[0].residual_linf > 0.0
    assert run.steps[1].residual_linf == 0.0


def test_real_entry_point_refuses_fixture_routes() -> None:
    factory = RecordingFixtureFactory()
    try:
        run_dynamic_certified_relative_value_iteration(
            factory,
            zero_continuation_values(),
            max_iterations=1,
            minimum_iterations=1,
            tolerance_linf=0.0,
            provenance="must fail because routes are fixtures",
        )
    except RuntimeError as exc:
        assert "not READY_CERTIFIED" in str(exc)
    else:
        raise AssertionError("M5D real entry point accepted fixture routes")


def test_factory_output_is_bound_to_exact_current_sha() -> None:
    factory = RecordingFixtureFactory()
    run = run_dynamic_fixture_relative_value_iteration(
        factory,
        zero_continuation_values(),
        max_iterations=2,
        minimum_iterations=2,
        tolerance_linf=0.0,
        provenance="exact-SHA rebinding regression",
    )
    assert len(run.registry_bundle.steps) == 2
    for bundle_step, rvi_step in zip(run.registry_bundle.steps, run.steps):
        assert bundle_step.continuation_sha256 == rvi_step.input_sha256
        assert bundle_step.registry_manifest_sha256 == rvi_step.registry_manifest_sha256
        assert bundle_step.bellman_image_sha256 == rvi_step.image_sha256


def main() -> None:
    test_dynamic_driver_rebinds_registry_after_v_changes()
    test_real_entry_point_refuses_fixture_routes()
    test_factory_output_is_bound_to_exact_current_sha()
    print("OPENOFC_M5D_DYNAMIC_CERTIFIED_BELLMAN_GATE=PASS")


if __name__ == "__main__":
    main()
