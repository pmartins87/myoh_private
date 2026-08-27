from __future__ import annotations

"""Held-out metrics for the M4K terminal-frontier MLP."""

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np

from fantasy_frontier_corpus import POINT_LIMIT
from fantasy_frontier_mlp import DenseWorld, TerminalFrontierMLP, stack_worlds

DEFAULT_CONTINUATION_DELTAS = (-100.0, -50.0, -20.0, 0.0, 20.0, 50.0, 100.0)


@dataclass(frozen=True)
class MLPMetrics:
    worlds: int
    reach_accuracy: float
    reachable_point_mae: float
    reachable_point_rmse: float
    confident_worlds: int
    confident_coverage: float
    utility_cases: int
    utility_mean_abs_error: float
    utility_max_abs_error: float

    def payload(self) -> dict:
        return self.__dict__.copy()


def _exact_utility(world: DenseWorld, delta: float) -> float:
    options: list[float] = []
    if world.reachable[0] > 0.5:
        options.append(float(world.points[0]) * POINT_LIMIT)
    if world.reachable[1] > 0.5:
        options.append(float(world.points[1]) * POINT_LIMIT + float(delta))
    if not options:
        raise AssertionError("exact world has no reachable Fantasy branch")
    return max(options)


def evaluate(
    model: TerminalFrontierMLP,
    worlds: Sequence[DenseWorld],
    *,
    confidence_low: float = 0.10,
    confidence_high: float = 0.90,
    continuation_deltas: Sequence[float] = DEFAULT_CONTINUATION_DELTAS,
) -> MLPMetrics:
    if not worlds:
        raise ValueError("evaluation requires worlds")
    x, reach, point_norm = stack_worlds(worlds)
    reach_prob, point_pred = model.predict(x)
    reach_hits = int(((reach_prob >= 0.5) == (reach >= 0.5)).sum())
    reachable_mask = reach >= 0.5
    exact_points = point_norm * POINT_LIMIT
    errors = (point_pred - exact_points)[reachable_mask]
    mae = float(np.abs(errors).mean()) if errors.size else 0.0
    rmse = float(np.sqrt(np.mean(errors * errors))) if errors.size else 0.0

    confident = 0
    utility_errors: list[float] = []
    for i, world in enumerate(worlds):
        predicted: list[float | None] = [None, None]
        valid = True
        for branch in (0, 1):
            p = float(reach_prob[i, branch])
            if p <= confidence_low:
                predicted[branch] = None
            elif p >= confidence_high:
                predicted[branch] = float(point_pred[i, branch])
            else:
                valid = False
                break
        if not valid or all(value is None for value in predicted):
            continue
        confident += 1
        for delta in continuation_deltas:
            options: list[float] = []
            if predicted[0] is not None:
                options.append(float(predicted[0]))
            if predicted[1] is not None:
                options.append(float(predicted[1]) + float(delta))
            approx = max(options)
            utility_errors.append(approx - _exact_utility(world, float(delta)))

    return MLPMetrics(
        worlds=len(worlds),
        reach_accuracy=reach_hits / (len(worlds) * 2),
        reachable_point_mae=mae,
        reachable_point_rmse=rmse,
        confident_worlds=confident,
        confident_coverage=confident / len(worlds),
        utility_cases=len(utility_errors),
        utility_mean_abs_error=(
            sum(abs(x) for x in utility_errors) / max(1, len(utility_errors))
        ),
        utility_max_abs_error=max((abs(x) for x in utility_errors), default=0.0),
    )


def stratified_metrics(
    model: TerminalFrontierMLP,
    worlds: Sequence[DenseWorld],
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for count in (14, 15, 16, 17):
        subset = [world for world in worlds if world.fantasy_count == count]
        if subset:
            result[f"F{count}"] = evaluate(model, subset).payload()
    for joker_count in (0, 1, 2):
        subset = [world for world in worlds if world.joker_count == joker_count]
        if subset:
            result[f"J{joker_count}"] = evaluate(model, subset).payload()
    return result
