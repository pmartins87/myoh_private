from __future__ import annotations

"""Distill M4L tabular Normal/Fantasy policies into a visible-only generalizer."""

import math

from normal_fantasy_policy_features import (
    encode_normal_fantasy_action_key,
    encode_normal_fantasy_state_key,
)
from strategic_advantage_model import DeterministicReservoir, ReplayExample
from strategic_policy_distillation import is_holdout_key


def normal_fantasy_node_training_examples(
    key: str,
    node,
    *,
    source: str = "m5a-m4l-average-policy",
) -> list[ReplayExample]:
    if len(node.action_keys) != len(node.cumulative_policy):
        raise ValueError("M4L node action/policy cardinality mismatch")
    targets = node.average_policy()
    if len(targets) != len(node.action_keys):
        raise AssertionError("M4L average policy cardinality mismatch")
    state_features = encode_normal_fantasy_state_key(key)
    weight = 1.0 + math.log1p(max(0, int(node.visits)))
    return [
        ReplayExample(
            state_features=state_features,
            action_features=encode_normal_fantasy_action_key(action_key),
            target=float(target),
            weight=weight,
            source=source,
        )
        for action_key, target in zip(node.action_keys, targets)
    ]


def distill_normal_fantasy_solver_nodes(
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
        examples = normal_fantasy_node_training_examples(key, node)
        replay.extend(examples)
        action_examples += len(examples)
    return {
        "nodes": len(selected),
        "action_examples": action_examples,
        "replay_size": len(replay.items),
        "replay_seen": replay.seen,
    }
