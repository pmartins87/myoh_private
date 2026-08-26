from __future__ import annotations

"""Regression tests for continuation-coupled normal/normal strategic utility."""

from hu_continuation import (
    HUContinuationState,
    identity_for_role,
    next_state_from_terminal_boards,
    zero_continuation_values,
)
from strategic_cfr import HUState, child_state, legal_action_pairs, sample_deal_plan, terminal_utility
from strategic_continuation_cfr import (
    ContinuationObjective,
    SuitCanonicalContinuationMCCFR,
)


def terminal_fixture(seed: int = 20260825) -> HUState:
    import random

    state = HUState(plan=sample_deal_plan(random.Random(seed)))
    while not state.terminal():
        pairs = legal_action_pairs(state)
        if not pairs:
            raise AssertionError("fixture reached a nonterminal state with no legal action")
        state = child_state(state, pairs[0][1])
    return state


def persistent_boards(meta: HUContinuationState, terminal: HUState):
    boards = [None, None]
    for role in (0, 1):
        boards[identity_for_role(meta, role)] = terminal.boards[role]
    assert boards[0] is not None and boards[1] is not None
    return boards[0], boards[1]


def test_zero_vector_reproduces_current_hand_utility() -> None:
    terminal = terminal_fixture()
    for button in (0, 1):
        objective = ContinuationObjective(
            HUContinuationState(button, 0, 0), zero_continuation_values()
        )
        solver = SuitCanonicalContinuationMCCFR(objective=objective, seed=17)
        for role in (0, 1):
            got = solver.terminal_value(terminal, role)
            expected = terminal_utility(terminal, role)
            assert got == expected, (button, role, got, expected)


def test_nonzero_next_state_value_is_mapped_by_persistent_identity() -> None:
    terminal = terminal_fixture(20260826)
    for button in (0, 1):
        meta = HUContinuationState(button, 0, 0)
        b0, b1 = persistent_boards(meta, terminal)
        nxt = next_state_from_terminal_boards(meta, b0, b1)
        values = zero_continuation_values()
        values[nxt] = 7.25
        solver = SuitCanonicalContinuationMCCFR(
            objective=ContinuationObjective(meta, values), seed=19
        )
        for role in (0, 1):
            persistent = identity_for_role(meta, role)
            shift = 7.25 if persistent == 0 else -7.25
            expected = terminal_utility(terminal, role) + shift
            got = solver.terminal_value(terminal, role)
            assert abs(got - expected) < 1e-12, (
                button, role, persistent, got, expected, nxt
            )


def test_objective_fingerprint_binds_every_continuation_value() -> None:
    meta = HUContinuationState(1, 0, 0)
    zero = zero_continuation_values()
    a = ContinuationObjective(meta, zero)
    changed = dict(zero)
    changed[next(iter(changed))] = 0.125
    b = ContinuationObjective(meta, changed)
    assert a.fingerprint != b.fingerprint
    restored = ContinuationObjective.from_payload(a.payload())
    assert restored.current_state == a.current_state
    assert restored.fingerprint == a.fingerprint
    assert dict(restored.values) == dict(a.values)


def test_non_normal_meta_state_is_rejected() -> None:
    try:
        ContinuationObjective(
            HUContinuationState(0, 14, 0), zero_continuation_values()
        )
    except ValueError as exc:
        assert "normal/normal" in str(exc)
    else:
        raise AssertionError("normal/normal solver accepted a Fantasy meta-state")


def test_one_iteration_smoke() -> None:
    solver = SuitCanonicalContinuationMCCFR(
        objective=ContinuationObjective(
            HUContinuationState(1, 0, 0), zero_continuation_values()
        ),
        seed=20260825,
        epsilon=0.6,
    )
    stats = solver.run(1)
    assert stats.iterations == 1 and stats.episodes == 2
    assert stats.infosets > 0 and stats.max_actions == 232
    payload = solver.checkpoint_payload()
    assert payload["authority"].startswith("STRATEGIC_APPROX")
    assert payload["continuation_objective"]["sha256"] == solver.objective.fingerprint


def main() -> None:
    test_zero_vector_reproduces_current_hand_utility()
    test_nonzero_next_state_value_is_mapped_by_persistent_identity()
    test_objective_fingerprint_binds_every_continuation_value()
    test_non_normal_meta_state_is_rejected()
    test_one_iteration_smoke()
    print(
        "OPENOFC_M4B_CONTINUATION_CFR=PASS "
        "zero_vector=CURRENT_HAND_PARITY nonzero=BELLMAN_SHIFT "
        "role_mapping=PERSISTENT_IDENTITY objective=SHA256_BOUND action_abstraction=0"
    )


if __name__ == "__main__":
    main()
