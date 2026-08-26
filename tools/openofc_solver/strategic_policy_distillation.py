from __future__ import annotations

"""Distill exact tabular MCCFR information sets into the M4C2 generalizer.

This layer deliberately keeps the exact tabular solver as the teacher.  It does
not let the learned model steer MCCFR yet.  That separation gives us a clean,
measurable question first: can the bounded function approximator reproduce
policy structure on strategically distinct information states that it did not
train on?
"""

from dataclasses import dataclass
import hashlib
import math
from typing import Iterable, Sequence

from strategic_advantage_model import (
    DeterministicReservoir,
    ReplayExample,
    SparseActionAdvantageModel,
)
from strategic_feature_encoder import (
    encode_canonical_action_key,
    encode_canonical_state_key,
)

HOLDOUT_MODULO = 5
HOLDOUT_BUCKET = 0


def stable_bucket(key: str, *, modulo: int = HOLDOUT_MODULO) -> int:
    if modulo <= 1:
        raise ValueError("holdout modulo must be greater than one")
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % modulo


def is_holdout_key(key: str) -> bool:
    return stable_bucket(key) == HOLDOUT_BUCKET


def regret_share(regrets: Sequence[float]) -> list[float]:
    if not regrets:
        raise ValueError("regret share requires actions")
    positive = [max(0.0, float(value)) for value in regrets]
    if any(not math.isfinite(value) for value in positive):
        raise ValueError("non-finite regret")
    total = sum(positive)
    if total <= 0.0:
        return [1.0 / len(positive)] * len(positive)
    return [value / total for value in positive]


def average_policy(node) -> list[float]:
    raw = [max(0.0, float(value)) for value in node.cumulative_policy]
    total = sum(raw)
    if total <= 0.0:
        return regret_share(node.cumulative_regrets)
    return [value / total for value in raw]


def node_training_examples(
    key: str,
    node,
    *,
    source: str = "exact_tabular_average_policy",
) -> list[ReplayExample]:
    if len(node.action_keys) != len(node.cumulative_policy):
        raise ValueError("tabular node action/policy cardinality mismatch")
    targets = average_policy(node)
    state_features = encode_canonical_state_key(key)
    # Repeatedly visited exact information states are better teachers.  The log
    # weight avoids allowing a single hot state to numerically dominate replay.
    weight = 1.0 + math.log1p(max(0, int(node.visits)))
    return [
        ReplayExample(
            state_features=state_features,
            action_features=encode_canonical_action_key(action_key),
            target=target,
            weight=weight,
            source=source,
        )
        for action_key, target in zip(node.action_keys, targets)
    ]


def distill_solver_nodes(
    solver,
    replay: DeterministicReservoir,
    *,
    include_holdout: bool = False,
    max_nodes: int | None = None,
) -> dict[str, int]:
    selected = []
    for key, node in sorted(solver.nodes.items()):
        if not include_holdout and is_holdout_key(key):
            continue
        selected.append((key, node))
        if max_nodes is not None and len(selected) >= max_nodes:
            break

    action_examples = 0
    for key, node in selected:
        examples = node_training_examples(key, node)
        replay.extend(examples)
        action_examples += len(examples)
    return {
        "nodes": len(selected),
        "action_examples": action_examples,
        "replay_size": len(replay.items),
        "replay_seen": replay.seen,
    }


@dataclass(frozen=True)
class DistillationMetrics:
    nodes: int
    actions: int
    mean_policy_l1: float
    mean_policy_rmse: float
    top1_accuracy: float
    mean_target_entropy: float

    def payload(self) -> dict:
        return {
            "nodes": self.nodes,
            "actions": self.actions,
            "mean_policy_l1": self.mean_policy_l1,
            "mean_policy_rmse": self.mean_policy_rmse,
            "top1_accuracy": self.top1_accuracy,
            "mean_target_entropy": self.mean_target_entropy,
        }


def _target_entropy(policy: Sequence[float]) -> float:
    return -sum(p * math.log(p) for p in policy if p > 0.0)


def evaluate_model_on_solver(
    model: SparseActionAdvantageModel,
    solver,
    *,
    holdout_only: bool = True,
    max_nodes: int | None = None,
) -> DistillationMetrics:
    node_count = 0
    action_count = 0
    l1_total = 0.0
    squared_total = 0.0
    top_hits = 0
    entropy_total = 0.0

    for key, node in sorted(solver.nodes.items()):
        if holdout_only and not is_holdout_key(key):
            continue
        if not holdout_only and is_holdout_key(key):
            continue
        target = average_policy(node)
        state_features = encode_canonical_state_key(key)
        actions = [encode_canonical_action_key(action_key) for action_key in node.action_keys]
        predicted = model.policy(state_features, actions)
        if len(predicted) != len(target):
            raise AssertionError("predicted/target policy cardinality mismatch")
        l1_total += sum(abs(a - b) for a, b in zip(predicted, target))
        squared_total += sum((a - b) ** 2 for a, b in zip(predicted, target))
        action_count += len(target)
        target_best = max(range(len(target)), key=lambda i: (target[i], -i))
        predicted_best = max(range(len(predicted)), key=lambda i: (predicted[i], -i))
        top_hits += int(target_best == predicted_best)
        entropy_total += _target_entropy(target)
        node_count += 1
        if max_nodes is not None and node_count >= max_nodes:
            break

    if node_count == 0 or action_count == 0:
        raise ValueError("no nodes available for requested distillation evaluation split")
    return DistillationMetrics(
        nodes=node_count,
        actions=action_count,
        mean_policy_l1=l1_total / node_count,
        mean_policy_rmse=math.sqrt(squared_total / action_count),
        top1_accuracy=top_hits / node_count,
        mean_target_entropy=entropy_total / node_count,
    )
