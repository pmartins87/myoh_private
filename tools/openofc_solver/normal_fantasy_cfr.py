from __future__ import annotations

"""Outcome-sampling strategic learner for normal-vs-hidden-Fantasy HU states.

Only the normal player acts before terminal resolution under the field-supported
delayed-response timing contract.  The hidden Fantasy packet and all future
normal cards are sampled chance variables.  The policy information key is the
M4F suit-canonical visible state and therefore never contains the hidden packet.

Terminal authority is injected.  The default is the exact M4H one-pass oracle;
a later certified M4K evaluator may be supplied without changing policy inputs.
"""

from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
import random
from typing import Mapping, Protocol, Sequence

from hu_continuation import (
    HUContinuationState,
    KERNEL_NORMAL_FANTASY,
    all_states,
    hand_kernel_kind,
)
from normal_fantasy_kernel import (
    NormalFantasyState,
    child_normal_state,
    sample_normal_fantasy_plan,
)
from normal_fantasy_symmetry import canonical_node_view
from normal_fantasy_terminal import (
    ExactOnePassNormalFantasyTerminalEvaluator,
    TerminalEvaluation,
)
from strategic_cfr import InfoSetNode, _require_m1b_materialized, _sample_index
from strategic_continuation_cfr import validate_continuation_values

AUTHORITY = "STRATEGIC_APPROX_NORMAL_VS_HIDDEN_FANTASY_WITH_CONTINUATION"
CHECKPOINT_SCHEMA = "openofc-m4l-normal-fantasy-outcome-sampling-v1"
SOLVER_KIND = "normal-fantasy-suit24-outcome-sampling"


class TerminalEvaluator(Protocol):
    def evaluate(
        self,
        state: NormalFantasyState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> TerminalEvaluation: ...


@dataclass(frozen=True)
class NormalFantasySolverStats:
    iterations: int
    episodes: int
    infosets: int
    total_visits: int
    max_actions: int
    mean_actions: float
    epsilon: float
    exact_terminal_evaluations: int
    approximate_terminal_evaluations: int


def _state_from_key(key: str) -> HUContinuationState:
    try:
        button_part, p0_part, p1_part = key.split(":")
        return HUContinuationState(
            int(button_part.removeprefix("B")),
            int(p0_part.removeprefix("P0F")),
            int(p1_part.removeprefix("P1F")),
        )
    except Exception as exc:
        raise ValueError(f"invalid HU continuation state key: {key!r}") from exc


def _continuation_payload(
    values: Mapping[HUContinuationState, float],
) -> dict:
    checked = validate_continuation_values(values)
    base = {
        "values": {
            state.as_key(): float(checked[state])
            for state in sorted(all_states())
        }
    }
    base["sha256"] = hashlib.sha256(
        json.dumps(
            base, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    return base


def _continuation_from_payload(payload: Mapping[str, object]) -> dict[HUContinuationState, float]:
    raw = dict(payload)
    expected = str(raw.pop("sha256", ""))
    actual = hashlib.sha256(
        json.dumps(
            raw, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    if expected != actual:
        raise ValueError("normal/Fantasy continuation vector SHA-256 mismatch")
    raw_values = raw.get("values")
    if not isinstance(raw_values, dict):
        raise ValueError("normal/Fantasy continuation vector missing values")
    return validate_continuation_values(
        {_state_from_key(str(key)): float(value) for key, value in raw_values.items()}
    )


def _jsonable_rng_state(value):
    if isinstance(value, tuple):
        return [_jsonable_rng_state(x) for x in value]
    return value


def _tuple_rng_state(value):
    if isinstance(value, list):
        return tuple(_tuple_rng_state(x) for x in value)
    return value


class NormalFantasyOutcomeSampling:
    solver_kind = SOLVER_KIND
    authority = AUTHORITY

    def __init__(
        self,
        *,
        current_meta: HUContinuationState,
        continuation_values: Mapping[HUContinuationState, float],
        terminal_evaluator: TerminalEvaluator | None = None,
        epsilon: float = 0.6,
        seed: int = 20260826,
        cfr_plus: bool = True,
    ) -> None:
        _require_m1b_materialized()
        if hand_kernel_kind(current_meta) != KERNEL_NORMAL_FANTASY:
            raise ValueError("M4L requires exactly one normal and one Fantasy player")
        if not 0.0 < epsilon <= 1.0:
            raise ValueError("epsilon must be in (0, 1]")
        self.current_meta = current_meta
        self.continuation_values = validate_continuation_values(continuation_values)
        self.terminal_evaluator = (
            terminal_evaluator or ExactOnePassNormalFantasyTerminalEvaluator()
        )
        self.epsilon = float(epsilon)
        self.seed = int(seed)
        self.cfr_plus = bool(cfr_plus)
        self.rng = random.Random(self.seed)
        self.nodes: dict[str, InfoSetNode] = {}
        self.iterations = 0
        self.episodes = 0
        self.exact_terminal_evaluations = 0
        self.approximate_terminal_evaluations = 0

    @property
    def fantasy_count(self) -> int:
        fantasy_player = (
            0 if self.current_meta.p0_fantasy_cards > 0 else 1
        )
        return self.current_meta.mode_for(fantasy_player)

    def _node(self, key: str, action_keys: Sequence[str]) -> InfoSetNode:
        keys = tuple(action_keys)
        node = self.nodes.get(key)
        if node is None:
            node = InfoSetNode.create(keys)
            self.nodes[key] = node
        elif node.action_keys != keys:
            raise AssertionError(
                "same asymmetric information state produced different legal actions"
            )
        return node

    def terminal_value(self, state: NormalFantasyState) -> float:
        result = self.terminal_evaluator.evaluate(state, self.continuation_values)
        if result.used_exact:
            self.exact_terminal_evaluations += 1
        else:
            self.approximate_terminal_evaluations += 1
        return float(result.utility_for_normal)

    def _episode(
        self,
        state: NormalFantasyState,
        *,
        my_reach: float,
        sample_reach: float,
    ) -> float:
        if state.terminal():
            return self.terminal_value(state)

        key, pairs, _suit_map = canonical_node_view(state)
        action_keys = [action_key for action_key, _action in pairs]
        actions = [action for _action_key, action in pairs]
        node = self._node(key, action_keys)
        policy = node.current_policy()

        uniform = 1.0 / len(policy)
        sample_policy = [
            self.epsilon * uniform + (1.0 - self.epsilon) * probability
            for probability in policy
        ]
        sampled = _sample_index(sample_policy, self.rng)
        child_value = self._episode(
            child_normal_state(state, actions[sampled]),
            my_reach=my_reach * policy[sampled],
            sample_reach=sample_reach * sample_policy[sampled],
        )

        child_values = [0.0] * len(policy)
        child_values[sampled] = child_value / sample_policy[sampled]
        value_estimate = sum(
            policy[index] * child_values[index]
            for index in range(len(policy))
        )

        if sample_reach <= 0.0:
            raise AssertionError("asymmetric sample reach became non-positive")
        scale = 1.0 / sample_reach
        cf_value = value_estimate * scale
        for index in range(len(policy)):
            delta = child_values[index] * scale - cf_value
            updated = node.cumulative_regrets[index] + delta
            node.cumulative_regrets[index] = (
                max(0.0, updated) if self.cfr_plus else updated
            )
            node.cumulative_policy[index] += (
                my_reach * policy[index] / sample_reach
            )
        node.visits += 1
        return value_estimate

    def run_iteration(self) -> float:
        plan = sample_normal_fantasy_plan(self.rng, self.fantasy_count)
        state = NormalFantasyState(current_meta=self.current_meta, plan=plan)
        value = self._episode(state, my_reach=1.0, sample_reach=1.0)
        self.episodes += 1
        self.iterations += 1
        return value

    def run(self, iterations: int) -> NormalFantasySolverStats:
        if iterations <= 0:
            raise ValueError("iterations must be positive")
        for _ in range(iterations):
            self.run_iteration()
        return self.stats()

    def stats(self) -> NormalFantasySolverStats:
        action_counts = [len(node.action_keys) for node in self.nodes.values()]
        return NormalFantasySolverStats(
            iterations=self.iterations,
            episodes=self.episodes,
            infosets=len(self.nodes),
            total_visits=sum(node.visits for node in self.nodes.values()),
            max_actions=max(action_counts, default=0),
            mean_actions=(
                sum(action_counts) / len(action_counts) if action_counts else 0.0
            ),
            epsilon=self.epsilon,
            exact_terminal_evaluations=self.exact_terminal_evaluations,
            approximate_terminal_evaluations=self.approximate_terminal_evaluations,
        )

    def policy_for_key(self, key: str, *, average: bool = True) -> dict[str, float]:
        node = self.nodes[key]
        probabilities = node.average_policy() if average else node.current_policy()
        return dict(zip(node.action_keys, probabilities))

    def checkpoint_payload(self) -> dict:
        return {
            "schema": CHECKPOINT_SCHEMA,
            "solver_kind": self.solver_kind,
            "authority": self.authority,
            "current_meta": self.current_meta.as_key(),
            "continuation": _continuation_payload(self.continuation_values),
            "epsilon": self.epsilon,
            "seed": self.seed,
            "cfr_plus": self.cfr_plus,
            "iterations": self.iterations,
            "episodes": self.episodes,
            "exact_terminal_evaluations": self.exact_terminal_evaluations,
            "approximate_terminal_evaluations": self.approximate_terminal_evaluations,
            "rng_state": _jsonable_rng_state(self.rng.getstate()),
            "nodes": [
                {
                    "key": key,
                    "action_keys": list(node.action_keys),
                    "cumulative_regrets": node.cumulative_regrets,
                    "cumulative_policy": node.cumulative_policy,
                    "visits": node.visits,
                }
                for key, node in sorted(self.nodes.items())
            ],
        }

    def save_checkpoint(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(
            self.checkpoint_payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if path.suffix == ".gz":
            with gzip.open(path, "wb", compresslevel=6) as handle:
                handle.write(raw)
        else:
            path.write_bytes(raw)

    @classmethod
    def load_checkpoint(
        cls,
        path: Path,
        *,
        terminal_evaluator: TerminalEvaluator | None = None,
    ) -> "NormalFantasyOutcomeSampling":
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as handle:
                payload = json.loads(handle.read().decode("utf-8"))
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != CHECKPOINT_SCHEMA:
            raise ValueError("unsupported M4L normal/Fantasy checkpoint schema")
        solver = cls(
            current_meta=_state_from_key(str(payload["current_meta"])),
            continuation_values=_continuation_from_payload(payload["continuation"]),
            terminal_evaluator=terminal_evaluator,
            epsilon=float(payload["epsilon"]),
            seed=int(payload["seed"]),
            cfr_plus=bool(payload["cfr_plus"]),
        )
        solver.iterations = int(payload["iterations"])
        solver.episodes = int(payload["episodes"])
        solver.exact_terminal_evaluations = int(payload["exact_terminal_evaluations"])
        solver.approximate_terminal_evaluations = int(
            payload["approximate_terminal_evaluations"]
        )
        solver.rng.setstate(_tuple_rng_state(payload["rng_state"]))
        for row in payload["nodes"]:
            node = InfoSetNode(
                action_keys=tuple(row["action_keys"]),
                cumulative_regrets=[float(x) for x in row["cumulative_regrets"]],
                cumulative_policy=[float(x) for x in row["cumulative_policy"]],
                visits=int(row["visits"]),
            )
            if not (
                len(node.action_keys)
                == len(node.cumulative_regrets)
                == len(node.cumulative_policy)
            ):
                raise ValueError("corrupt M4L checkpoint node")
            solver.nodes[str(row["key"])] = node
        return solver
