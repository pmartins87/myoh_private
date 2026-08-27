from __future__ import annotations

import json

from fantasy_fantasy_payoff import continuation_fingerprint
from hu_continuation import HUContinuationState, zero_continuation_values
from m4z_outer_bellman import default_blocked_registry
from m5a_normal_fantasy_oracle import (
    NormalFantasyFixedPolicyOracle,
    freeze_policy_snapshot,
    policy_api_has_hidden_opponent_argument,
    policy_for_visible_node,
)
from normal_fantasy_policy_features import (
    encode_normal_fantasy_action_key,
    encode_normal_fantasy_state_key,
)
from strategic_advantage_model import SparseActionAdvantageModel


def _visible_key(
    *, normal_player: int = 0, button: int = 1, count: int = 14
) -> str:
    payload = {
        "v": 2,
        "symmetry": "normal-fantasy-suit24-exact",
        "normal_player": normal_player,
        "fantasy_player": 1 - normal_player,
        "button": button,
        "fantasy_count": count,
        "round": 0,
        "normal_board": [[], [], []],
        "own_discards": [],
        "incoming": ["2c", "3c", "4c", "5c", "6c"],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _action_key() -> str:
    return json.dumps(
        {
            "p": [
                ["2c", 0],
                ["3c", 0],
                ["4c", 1],
                ["5c", 1],
                ["6c", 2],
            ],
            "d": None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def test_visible_encoder_and_api_firewall() -> None:
    state_features = encode_normal_fantasy_state_key(_visible_key())
    action_features = encode_normal_fantasy_action_key(_action_key())
    assert state_features and action_features
    assert not policy_api_has_hidden_opponent_argument()

    payload = json.loads(_visible_key())
    payload["fantasy_packet"] = ["As"] * 14
    poisoned = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    try:
        encode_normal_fantasy_state_key(poisoned)
    except ValueError as exc:
        assert "schema mismatch" in str(exc)
    else:
        raise AssertionError(
            "hidden Fantasy field was accepted by visible encoder"
        )


def test_untrained_policy_is_defined() -> None:
    model = SparseActionAdvantageModel(buckets=1 << 8)
    policy = policy_for_visible_node(
        model, _visible_key(), (_action_key(),)
    )
    assert policy == (1.0,)


class _ConstantTerminalEvaluator:
    def __init__(self, value: float) -> None:
        self.value = float(value)

    def evaluate(self, state, continuation_values):
        result = type("ConstantTerminalResult", (), {})()
        result.utility_for_normal = self.value
        return result


def test_oracle_is_deterministic_sha_bound_and_uses_p0_sign() -> None:
    values = zero_continuation_values()
    model = SparseActionAdvantageModel(buckets=1 << 8)
    snapshot = freeze_policy_snapshot(
        model,
        training_continuation_values=values,
        provenance="m5a-unit-fixture",
    )
    oracle = NormalFantasyFixedPolicyOracle(
        model,
        snapshot,
        samples=2,
        base_seed=77,
        terminal_evaluator=_ConstantTerminalEvaluator(7.0),
    )
    p0_normal = HUContinuationState(1, 0, 14)
    first = oracle.evaluate(p0_normal, values)
    second = oracle.evaluate(p0_normal, values)
    _checked, expected_sha = continuation_fingerprint(values)
    assert first == second
    assert first.p0_value == 7.0
    assert first.standard_error == 0.0
    assert first.continuation_sha256 == expected_sha

    p1_normal = HUContinuationState(0, 14, 0)
    result = oracle.evaluate(p1_normal, values)
    assert result.p0_value == -7.0
    assert result.continuation_sha256 == expected_sha


def test_snapshot_is_continuation_bound_and_does_not_promote_registry() -> None:
    values = zero_continuation_values()
    model = SparseActionAdvantageModel(buckets=1 << 8)
    snapshot = freeze_policy_snapshot(
        model,
        training_continuation_values=values,
        provenance="m5a-unit-fixture",
    )
    _checked, expected_sha = continuation_fingerprint(values)
    assert snapshot.training_continuation_sha256 == expected_sha
    manifest = default_blocked_registry().freeze_manifest()
    assert manifest.blocked == 50
    assert manifest.ready_certified == 0


def main() -> None:
    test_visible_encoder_and_api_firewall()
    test_untrained_policy_is_defined()
    test_oracle_is_deterministic_sha_bound_and_uses_p0_sign()
    test_snapshot_is_continuation_bound_and_does_not_promote_registry()
    print("OPENOFC_M5A_NORMAL_FANTASY_GATE=PASS")


if __name__ == "__main__":
    main()
