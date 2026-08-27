from __future__ import annotations

import hashlib
from pathlib import Path
import random
import tempfile

from engine import full_deck
from hu_continuation import HUContinuationState, zero_continuation_values
from normal_fantasy_cfr import NormalFantasyOutcomeSampling
from normal_fantasy_kernel import (
    NormalFantasyDealPlan,
    NormalFantasyState,
    child_normal_state,
    exact_terminal_utility_for_normal,
    legal_normal_actions,
    sample_normal_fantasy_plan,
)
from normal_fantasy_symmetry import canonical_information_key
from normal_fantasy_terminal import (
    CertifiedMLPNormalFantasyTerminalEvaluator,
    ExactOnePassNormalFantasyTerminalEvaluator,
    TerminalEvaluation,
    TerminalModelCertificate,
)


class FixedTerminalEvaluator:
    def __init__(self, value: float = 3.25) -> None:
        self.value = float(value)

    def evaluate(self, state, continuation_values):
        assert state.terminal()
        return TerminalEvaluation(
            utility_for_normal=self.value,
            source="TEST_FIXED_TERMINAL",
            used_exact=False,
            abstention_reason=None,
            certified_error_bound=999.0,
        )


def meta() -> HUContinuationState:
    return HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=0)


def completed_state(seed: int = 91) -> NormalFantasyState:
    plan = sample_normal_fantasy_plan(random.Random(seed), 14)
    state = NormalFantasyState(current_meta=meta(), plan=plan)
    while not state.terminal():
        actions = legal_normal_actions(state)
        assert actions
        state = child_normal_state(state, actions[0])
    return state


def test_exact_onepass_matches_independent_two_pass() -> None:
    state = completed_state()
    values = zero_continuation_values()
    onepass = ExactOnePassNormalFantasyTerminalEvaluator()
    observed = onepass.evaluate(state, values).utility_for_normal
    expected = exact_terminal_utility_for_normal(state, values)
    assert observed == expected
    assert onepass.exact_misses == 1
    repeated = onepass.evaluate(state, values).utility_for_normal
    assert repeated == observed
    assert onepass.exact_hits == 1


def test_visible_policy_key_does_not_depend_on_hidden_fantasy_packet() -> None:
    rng = random.Random(20260826)
    plan = sample_normal_fantasy_plan(rng, 14)
    used = set(plan.all_cards())
    replacement = next(card for card in full_deck(2) if card not in used)
    fantasy = list(plan.fantasy_packet)
    fantasy[0] = replacement
    alternate = NormalFantasyDealPlan(
        fantasy_packet=tuple(sorted(fantasy)),
        normal_opening=plan.normal_opening,
        normal_rounds=plan.normal_rounds,
    )
    a = NormalFantasyState(current_meta=meta(), plan=plan)
    b = NormalFantasyState(current_meta=meta(), plan=alternate)
    assert plan.fantasy_packet != alternate.fantasy_packet
    assert canonical_information_key(a)[0] == canonical_information_key(b)[0]


def test_checkpoint_resume_is_byte_deterministic() -> None:
    values = zero_continuation_values()
    solver = NormalFantasyOutcomeSampling(
        current_meta=meta(),
        continuation_values=values,
        terminal_evaluator=FixedTerminalEvaluator(),
        seed=7123,
        epsilon=0.4,
    )
    solver.run(3)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "m4l.json.gz"
        solver.save_checkpoint(path)
        resumed = NormalFantasyOutcomeSampling.load_checkpoint(
            path, terminal_evaluator=FixedTerminalEvaluator()
        )
        solver.run_iteration()
        resumed.run_iteration()
        assert solver.checkpoint_payload() == resumed.checkpoint_payload()
    stats = solver.stats()
    assert stats.max_actions == 232
    assert stats.approximate_terminal_evaluations == 4
    assert stats.exact_terminal_evaluations == 0


def test_certificate_is_sha_bound_and_fail_closed_before_model_load() -> None:
    model_bytes = b"not-a-model"
    model_sha = hashlib.sha256(model_bytes).hexdigest()
    evidence_sha = hashlib.sha256(b"exact-heldout-evidence").hexdigest()
    cert = TerminalModelCertificate(
        model_sha256=model_sha,
        allowed_fantasy_counts=(14, 15),
        allowed_joker_counts=(0, 1, 2),
        confidence_low=0.1,
        confidence_high=0.9,
        continuation_delta_min=-100.0,
        continuation_delta_max=100.0,
        max_utility_abs_error=2.5,
        heldout_worlds=10000,
        evidence_sha256=evidence_sha,
    )
    restored = TerminalModelCertificate.from_payload(cert.payload())
    assert restored == cert

    tampered = cert.payload()
    tampered["max_utility_abs_error"] = 1.0
    try:
        TerminalModelCertificate.from_payload(tampered)
    except ValueError:
        pass
    else:
        raise AssertionError("tampered certificate was accepted")

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "model.npz"
        path.write_bytes(model_bytes)
        wrong = TerminalModelCertificate(
            model_sha256="0" * 64,
            allowed_fantasy_counts=(14,),
            allowed_joker_counts=(0,),
            confidence_low=0.1,
            confidence_high=0.9,
            continuation_delta_min=-20.0,
            continuation_delta_max=20.0,
            max_utility_abs_error=1.0,
            heldout_worlds=100,
            evidence_sha256=evidence_sha,
        )
        try:
            CertifiedMLPNormalFantasyTerminalEvaluator(path, wrong)
        except ValueError as exc:
            assert "model SHA-256" in str(exc)
        else:
            raise AssertionError("mismatched model/certificate pair was accepted")


def main() -> None:
    test_visible_policy_key_does_not_depend_on_hidden_fantasy_packet()
    test_checkpoint_resume_is_byte_deterministic()
    test_certificate_is_sha_bound_and_fail_closed_before_model_load()
    test_exact_onepass_matches_independent_two_pass()
    print(
        "OPENOFC_M4L_NORMAL_FANTASY_STRATEGIC=PASS "
        "policy_hidden_leakage=ABSENT terminal=M4H_ONEPASS_EXACT "
        "checkpoint=BYTE_DETERMINISTIC certified_mlp=FAIL_CLOSED"
    )


if __name__ == "__main__":
    main()
