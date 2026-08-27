from __future__ import annotations

from dataclasses import dataclass
import hashlib

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import (
    HUContinuationState,
    KERNEL_FANTASY_FANTASY,
    KERNEL_NORMAL_FANTASY,
    KERNEL_NORMAL_NORMAL,
    all_states,
    hand_kernel_kind,
    zero_continuation_values,
)
from m4x_robust_support import freeze_continuation_family
from m4y_bellman_trace import EVIDENCE_REAL
from m4z_outer_bellman import OneHandOracleResult
from m5c_normal_route_certification import (
    freeze_certification as freeze_normal_certification,
    freeze_route_evidence as freeze_normal_route_evidence,
)
from m5e_fantasy_route_certification import (
    freeze_certification as freeze_fantasy_certification,
    freeze_route_evidence as freeze_fantasy_route_evidence,
)
from m5g_full_registry_factory import (
    CompleteCertifiedRegistryFactory,
    PerVRoutePackage,
    assemble_certified_registry,
    validate_route_package,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class FakeNormalOracle:
    def __init__(self, oracle_id: str, value: float) -> None:
        self.oracle_id = oracle_id
        self.value = float(value)

    def evaluate(self, state, continuation_values) -> OneHandOracleResult:
        _checked, continuation_sha = continuation_fingerprint(continuation_values)
        return OneHandOracleResult(
            state=state,
            p0_value=self.value,
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=8,
            standard_error=0.0,
        )


@dataclass(frozen=True)
class FakeFantasySnapshot:
    model_sha256: str


class FakeFantasyOracle:
    def __init__(self, family, oracle_id: str, model_sha: str) -> None:
        self.family = family
        self.oracle_id = oracle_id
        self.snapshot = FakeFantasySnapshot(model_sha256=model_sha)

    def evaluate(self, state, continuation_values) -> OneHandOracleResult:
        _checked, continuation_sha = continuation_fingerprint(continuation_values)
        return OneHandOracleResult(
            state=state,
            p0_value=0.25,
            continuation_sha256=continuation_sha,
            oracle_id=self.oracle_id,
            samples=8,
            standard_error=0.0,
        )


def _package(values, *, omit_state: HUContinuationState | None = None):
    nn_id = "m5g-fixture-normal-normal"
    nf_id = "m5g-fixture-normal-fantasy"
    ff_id = "m5g-fixture-fantasy-fantasy"
    nn = FakeNormalOracle(nn_id, 0.10)
    nf = FakeNormalOracle(nf_id, -0.05)

    family = freeze_continuation_family(
        {"current-v": values},
        radius_linf=0.0,
        provenance="M5G exact-current-V fixture family",
        source_sha256=_sha("m5g-family-source|" + continuation_fingerprint(values)[1]),
    )
    model_sha = _sha("m5g-fantasy-model")
    ff = FakeFantasyOracle(family, ff_id, model_sha)

    normal_rows = []
    fantasy_rows = []
    for state in sorted(all_states()):
        if state == omit_state:
            continue
        kind = hand_kernel_kind(state)
        if kind in (KERNEL_NORMAL_NORMAL, KERNEL_NORMAL_FANTASY):
            oracle_id = nn_id if kind == KERNEL_NORMAL_NORMAL else nf_id
            normal_rows.append(
                freeze_normal_route_evidence(
                    state,
                    values,
                    oracle_id=oracle_id,
                    oracle_config_sha256=_sha("m5g-normal-config|" + kind),
                    implementation_sha256=_sha("m5g-normal-impl|" + kind),
                    model_value=0.0,
                    reference_value=0.0,
                    standard_error=0.0,
                    samples=32,
                    max_abs_value_error=0.01,
                    max_standard_error=0.01,
                    reference_authority="M5G_CI_FIXTURE_REFERENCE",
                    provenance="M5G route coverage regression fixture",
                )
            )
        elif kind == KERNEL_FANTASY_FANTASY:
            fantasy_rows.append(
                freeze_fantasy_route_evidence(
                    state,
                    values,
                    family,
                    oracle_id=ff_id,
                    model_sha256=model_sha,
                    implementation_sha256=_sha("m5g-fantasy-impl"),
                    support_gap=0.0,
                    support_deviation_gain=0.0,
                    model_q_mae=0.0,
                    model_q_max_error=0.0,
                    standard_error=0.0,
                    heldout_worlds=32,
                    heldout_seeds=4,
                    max_support_gap=0.01,
                    max_support_deviation_gain=0.01,
                    max_model_q_mae=0.01,
                    max_model_q_error=0.01,
                    max_standard_error=0.01,
                    reference_authority="M5G_CI_FIXTURE_REFERENCE",
                    provenance="M5G route coverage regression fixture",
                )
            )
        else:
            raise AssertionError("unexpected kernel")

    normal_manifest = freeze_normal_certification(
        normal_rows,
        values,
        source_report_sha256=_sha("m5g-normal-source-report"),
        provenance="M5G complete Normal CI fixture",
    )
    fantasy_manifest = freeze_fantasy_certification(
        fantasy_rows,
        values,
        family,
        source_report_sha256=_sha("m5g-fantasy-source-report"),
        provenance="M5G complete Fantasy CI fixture",
    )
    return PerVRoutePackage(
        normal_manifest=normal_manifest,
        fantasy_manifest=fantasy_manifest,
        normal_normal_oracle=nn,
        normal_fantasy_oracle=nf,
        fantasy_oracle=ff,
        provenance="M5G complete exact-V route package fixture",
    )


def test_complete_package_materializes_exactly_50_ready_routes() -> None:
    values = zero_continuation_values()
    package = _package(values)
    continuation_sha = validate_route_package(package, values)
    assert continuation_sha == continuation_fingerprint(values)[1]

    registry = assemble_certified_registry(package, values)
    manifest = registry.assert_ready_for(EVIDENCE_REAL)
    assert manifest.ready_certified == 50
    assert manifest.ready_fixture == 0
    assert manifest.blocked == 0
    counts = manifest.kernel_counts()
    assert counts[KERNEL_NORMAL_NORMAL] == 2
    assert counts[KERNEL_NORMAL_FANTASY] == 16
    assert counts[KERNEL_FANTASY_FANTASY] == 32

    # Verify wrappers preserve exact current-V binding when actually invoked.
    for state in (
        HUContinuationState(0, 0, 0),
        HUContinuationState(1, 0, 14),
        HUContinuationState(0, 14, 14),
    ):
        result = registry.oracle_for(state).evaluate(state, values)
        assert result.state == state
        assert result.continuation_sha256 == continuation_sha


def test_one_missing_route_blocks_full_registry() -> None:
    values = zero_continuation_values()
    missing = HUContinuationState(1, 17, 17)
    package = _package(values, omit_state=missing)
    try:
        validate_route_package(package, values)
    except RuntimeError as exc:
        assert "32/32" in str(exc)
    else:
        raise AssertionError("M5G accepted incomplete Fantasy route coverage")


def test_stale_package_is_rejected_and_factory_rebuilds_for_new_v() -> None:
    values = zero_continuation_values()
    stale = _package(values)
    changed = zero_continuation_values()
    changed[HUContinuationState(0, 14, 14)] = 0.125
    try:
        validate_route_package(stale, changed)
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("M5G accepted stale exact-V certification")

    calls = []

    def provider(current):
        calls.append(continuation_fingerprint(current)[1])
        return _package(current)

    factory = CompleteCertifiedRegistryFactory(provider)
    first = factory(values).freeze_manifest()
    second = factory(changed).freeze_manifest()
    assert factory.calls == 2
    assert len(calls) == 2 and calls[0] != calls[1]
    assert first.ready_certified == 50 and second.ready_certified == 50
    assert factory.last_continuation_sha256 == calls[-1]
    assert factory.last_registry_manifest_sha256 == second.sha256


def main() -> None:
    test_complete_package_materializes_exactly_50_ready_routes()
    test_one_missing_route_blocks_full_registry()
    test_stale_package_is_rejected_and_factory_rebuilds_for_new_v()
    print("OPENOFC_M5G_FULL_REGISTRY_FACTORY_GATE=PASS")


if __name__ == "__main__":
    main()
