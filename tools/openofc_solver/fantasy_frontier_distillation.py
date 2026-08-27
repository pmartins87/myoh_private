from __future__ import annotations

"""M4J exact-corpus distillation and held-out terminal-utility diagnostics."""

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable, Sequence

from fantasy_frontier_corpus import iter_rows
from fantasy_frontier_features import encode_canonical_world_key
from fantasy_frontier_model import FrontierExample, SparseFrontierModel

HOLDOUT_MODULO = 5
HOLDOUT_BUCKET = 0
DEFAULT_CONTINUATION_DELTAS = (-100.0, -50.0, -20.0, 0.0, 20.0, 50.0, 100.0)


def split_bucket(row: dict, modulo: int = HOLDOUT_MODULO) -> int:
    """Deterministic, stratifiable split based on the generator world id.

    M4I world ids are deterministic and independent of the exact label.  Using
    modulo five guarantees one held-out world in every contiguous block of five
    for each Fantasy count, avoiding accidental empty CI/scale splits.
    """
    if modulo <= 1:
        raise ValueError("split modulo must be greater than one")
    return int(row["world_id"]) % modulo


def is_holdout_row(row: dict) -> bool:
    return split_bucket(row) == HOLDOUT_BUCKET


def examples_from_row(row: dict) -> tuple[FrontierExample, FrontierExample]:
    key = str(row["canonical_world_key"])
    features = encode_canonical_world_key(key)
    no = row.get("no_refantasy_points")
    ref = row.get("refantasy_points")
    return (
        FrontierExample(key, features, 0, no is not None, None if no is None else int(no)),
        FrontierExample(key, features, 1, ref is not None, None if ref is None else int(ref)),
    )


def load_examples(paths: Iterable[Path], *, holdout: bool) -> list[FrontierExample]:
    examples: list[FrontierExample] = []
    for path in paths:
        for row in iter_rows(path):
            if is_holdout_row(row) != holdout:
                continue
            examples.extend(examples_from_row(row))
    return examples


@dataclass(frozen=True)
class FrontierModelMetrics:
    worlds: int
    branch_examples: int
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


def _exact_utility(branches: dict[int, int | None], delta: float) -> float:
    options = []
    if branches[0] is not None:
        options.append(float(branches[0]))
    if branches[1] is not None:
        options.append(float(branches[1]) + delta)
    if not options:
        raise AssertionError("exact world has no reachable branch")
    return max(options)


def evaluate_model(
    model: SparseFrontierModel,
    examples: Sequence[FrontierExample],
    *,
    confidence_low: float = 0.10,
    confidence_high: float = 0.90,
    continuation_deltas: Sequence[float] = DEFAULT_CONTINUATION_DELTAS,
) -> FrontierModelMetrics:
    if not examples or len(examples) % 2:
        raise ValueError("evaluation requires paired branch examples")
    by_key: dict[str, dict[int, FrontierExample]] = {}
    reach_hits = 0
    point_errors = []
    for example in examples:
        by_key.setdefault(example.world_key, {})[example.branch] = example
        probability = model.predict_reach_probability(example)
        predicted_reachable = probability >= 0.5
        reach_hits += int(predicted_reachable == example.reachable)
        if example.points is not None:
            point_errors.append(model.predict_points(example) - float(example.points))

    confident = 0
    utility_errors = []
    for _key, branches in by_key.items():
        if set(branches) != {0, 1}:
            raise ValueError("world is missing one branch example")
        exact = {branch: branches[branch].points for branch in (0, 1)}
        predicted: dict[int, float | None] = {}
        world_confident = True
        for branch in (0, 1):
            example = branches[branch]
            probability = model.predict_reach_probability(example)
            if probability <= confidence_low:
                predicted[branch] = None
            elif probability >= confidence_high:
                predicted[branch] = model.predict_points(example)
            else:
                world_confident = False
                break
        if not world_confident or all(value is None for value in predicted.values()):
            continue
        confident += 1
        for delta in continuation_deltas:
            exact_value = _exact_utility(exact, float(delta))
            options = []
            if predicted[0] is not None:
                options.append(float(predicted[0]))
            if predicted[1] is not None:
                options.append(float(predicted[1]) + float(delta))
            if not options:
                raise AssertionError("confident predicted world has no branch")
            utility_errors.append(max(options) - exact_value)

    worlds = len(by_key)
    mae = sum(abs(x) for x in point_errors) / max(1, len(point_errors))
    rmse = math.sqrt(sum(x * x for x in point_errors) / max(1, len(point_errors)))
    utility_mae = sum(abs(x) for x in utility_errors) / max(1, len(utility_errors))
    utility_max = max((abs(x) for x in utility_errors), default=0.0)
    return FrontierModelMetrics(
        worlds=worlds,
        branch_examples=len(examples),
        reach_accuracy=reach_hits / len(examples),
        reachable_point_mae=mae,
        reachable_point_rmse=rmse,
        confident_worlds=confident,
        confident_coverage=confident / worlds,
        utility_cases=len(utility_errors),
        utility_mean_abs_error=utility_mae,
        utility_max_abs_error=utility_max,
    )
