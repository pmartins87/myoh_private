from __future__ import annotations

from hu_bellman_iteration import (
    BellmanImage,
    BellmanStateEstimate,
    exchange_gauge_diagnostic,
    relative_value_step,
)
from hu_continuation import (
    HUContinuationState,
    all_states,
    hand_kernel_kind,
    swap_players,
    zero_continuation_values,
)


def estimates_from(values, *, offset=0.0, error=0.1):
    return {
        state: BellmanStateEstimate(
            value_p0=float(values[state]) + float(offset),
            kernel_kind=hand_kernel_kind(state),
            solver_kind="unit-test-kernel",
            authority="UNIT_TEST_ONLY",
            error_bound_abs=error,
            samples=100,
        )
        for state in all_states()
    }


def test_constant_bellman_gain_is_removed_by_relative_normalization() -> None:
    values = {
        state: float(index) * 0.01
        for index, state in enumerate(all_states())
    }
    image = BellmanImage(
        iteration=3,
        input_values=values,
        estimates=estimates_from(values, offset=2.5),
    )
    step = relative_value_step(image)
    assert abs(step.gain_estimate - 2.5) <= 1e-12
    assert step.sup_norm_delta <= 1e-12
    assert step.span_delta <= 1e-12
    assert abs((step.normalized_output_error_bound or 0.0) - 0.2) <= 1e-12
    assert step.output_values[HUContinuationState(0, 0, 0)] == 0.0


def test_outer_step_is_invariant_to_input_gauge_shift() -> None:
    base = {
        state: float(index % 7) - 3.0
        for index, state in enumerate(all_states())
    }
    shifted = {state: value + 19.75 for state, value in base.items()}
    image_a = BellmanImage(0, base, estimates_from(base, offset=1.25))
    image_b = BellmanImage(0, shifted, estimates_from(shifted, offset=1.25))
    step_a = relative_value_step(image_a)
    step_b = relative_value_step(image_b)
    assert step_a.output_values == step_b.output_values
    assert abs(step_a.gain_estimate - step_b.gain_estimate) <= 1e-12
    assert abs(step_a.sup_norm_delta - step_b.sup_norm_delta) <= 1e-12


def test_player_exchange_diagnostic_is_gauge_invariant() -> None:
    values = {}
    seen = set()
    for index, state in enumerate(all_states()):
        if state in seen:
            continue
        partner = swap_players(state)
        value = float((index % 9) - 4)
        values[state] = value + 7.0
        values[partner] = -value + 7.0
        seen.add(state)
        seen.add(partner)
    diagnostic = exchange_gauge_diagnostic(values)
    assert diagnostic.pair_sum_spread <= 1e-12
    assert abs(diagnostic.gauge_offset_to_antisymmetry - 7.0) <= 1e-12
    assert diagnostic.max_antisymmetry_residual_after_projection <= 1e-12


def test_kernel_ownership_mismatch_is_rejected() -> None:
    values = zero_continuation_values()
    estimates = estimates_from(values)
    state = HUContinuationState(0, 14, 14)
    estimates[state] = BellmanStateEstimate(
        value_p0=0.0,
        kernel_kind="NORMAL_NORMAL",
        solver_kind="wrong",
        authority="UNIT_TEST_ONLY",
        error_bound_abs=0.0,
    )
    try:
        BellmanImage(0, values, estimates)
    except ValueError as exc:
        assert "belongs to" in str(exc)
    else:
        raise AssertionError("wrong kernel ownership was accepted")


def test_bellman_image_payload_is_sha_bound() -> None:
    values = zero_continuation_values()
    image = BellmanImage(1, values, estimates_from(values, offset=0.5))
    payload = image.payload()
    restored = BellmanImage.from_payload(payload)
    assert restored.payload() == payload
    tampered = dict(payload)
    tampered["iteration"] = 2
    try:
        BellmanImage.from_payload(tampered)
    except ValueError as exc:
        assert "SHA" in str(exc)
    else:
        raise AssertionError("tampered Bellman image was accepted")


def test_missing_error_bound_propagates_unknown_outer_bound() -> None:
    values = zero_continuation_values()
    estimates = estimates_from(values, error=0.1)
    state = all_states()[7]
    old = estimates[state]
    estimates[state] = BellmanStateEstimate(
        value_p0=old.value_p0,
        kernel_kind=old.kernel_kind,
        solver_kind=old.solver_kind,
        authority=old.authority,
        error_bound_abs=None,
        samples=old.samples,
    )
    step = relative_value_step(BellmanImage(0, values, estimates))
    assert step.normalized_output_error_bound is None


def main() -> None:
    test_constant_bellman_gain_is_removed_by_relative_normalization()
    test_outer_step_is_invariant_to_input_gauge_shift()
    test_player_exchange_diagnostic_is_gauge_invariant()
    test_kernel_ownership_mismatch_is_rejected()
    test_bellman_image_payload_is_sha_bound()
    test_missing_error_bound_propagates_unknown_outer_bound()
    print(
        "OPENOFC_M4T_BELLMAN_IMAGE=PASS states=50 kernel_ownership=STRICT "
        "rvi=GAUGE_INVARIANT exchange=GAUGE_AWARE error_bound=PROPAGATED"
    )


if __name__ == "__main__":
    main()
