from __future__ import annotations

"""Deterministic multiseed benchmark for the bounded HU strategic model.

This benchmark answers two separate questions without conflating either with an
exploitability certificate:

1. Can the bounded model reproduce exact-tabular MCCFR policy structure on
   disjoint information states across independent deal seeds?
2. Does it learn Bellman-safe late-round structure on exact dealer-R4 states
   whose next continuation state is action-invariant?

The exact R4 subset is stronger than a current-hand heuristic: because every
legal action has the same next Fantasy mode, its optimal set is valid for any
continuation vector.  Transition-variant R4 states are reported but never used
as exact training labels.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Sequence

from strategic_advantage_model import DeterministicReservoir, SparseActionAdvantageModel
from strategic_policy_distillation import distill_solver_nodes, evaluate_model_on_solver, is_holdout_key
from strategic_suit_symmetry import SuitCanonicalOutcomeSamplingMCCFR
from strategic_teacher_anchors import (
    ExactR4Anchor,
    add_invariant_r4_teachers,
    evaluate_exact_r4_anchors,
    generate_exact_r4_anchors,
)

SCHEMA = "openofc-hu-m4c3-multiseed-benchmark-v1"
AUTHORITY = "GENERALIZATION_DIAGNOSTIC_NOT_EXPLOITABILITY_CERTIFICATE"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _parse_seeds(text: str) -> tuple[int, ...]:
    seeds = tuple(int(item.strip()) for item in text.split(",") if item.strip())
    if len(seeds) < 2 or len(set(seeds)) != len(seeds):
        raise ValueError("multiseed benchmark requires at least two distinct seeds")
    return seeds


def _anchor_stream(
    seed: int,
    *,
    min_train: int,
    min_holdout: int,
    batch_size: int = 12,
    max_batches: int = 32,
) -> tuple[ExactR4Anchor, ...]:
    anchors: list[ExactR4Anchor] = []
    train = 0
    holdout = 0
    for batch in range(max_batches):
        batch_seed = int(seed) ^ (0x9E3779B1 * (batch + 1))
        fresh = generate_exact_r4_anchors(batch_seed, batch_size)
        anchors.extend(fresh)
        for anchor in fresh:
            if not anchor.continuation_invariant:
                continue
            if is_holdout_key(anchor.key):
                holdout += 1
            else:
                train += 1
        if train >= min_train and holdout >= min_holdout:
            return tuple(anchors)
    raise RuntimeError(
        f"seed {seed}: exact-R4 stream did not reach requested split "
        f"train={train}/{min_train} holdout={holdout}/{min_holdout}"
    )


@dataclass(frozen=True)
class SeedBenchmark:
    seed: int
    cfr_infosets: int
    cfr_visits: int
    exact_r4_total: int
    exact_r4_invariant: int
    exact_r4_holdout_invariant: int
    policy_holdout: dict
    exact_r4_holdout: dict

    def payload(self) -> dict:
        return {
            "seed": self.seed,
            "cfr_infosets": self.cfr_infosets,
            "cfr_visits": self.cfr_visits,
            "exact_r4_total": self.exact_r4_total,
            "exact_r4_invariant": self.exact_r4_invariant,
            "exact_r4_holdout_invariant": self.exact_r4_holdout_invariant,
            "policy_holdout": self.policy_holdout,
            "exact_r4_holdout": self.exact_r4_holdout,
        }


def run_benchmark(
    seeds: Sequence[int],
    *,
    cfr_iterations: int = 24,
    max_teacher_nodes_per_seed: int = 256,
    min_r4_train_per_seed: int = 6,
    min_r4_holdout_per_seed: int = 3,
    replay_capacity: int = 30000,
    epochs: int = 4,
    buckets: int = 1 << 14,
) -> dict:
    seeds = tuple(int(seed) for seed in seeds)
    if len(seeds) < 2 or len(set(seeds)) != len(seeds):
        raise ValueError("run_benchmark requires at least two distinct seeds")
    if cfr_iterations <= 0 or max_teacher_nodes_per_seed <= 0:
        raise ValueError("CFR benchmark budgets must be positive")

    replay = DeterministicReservoir(capacity=replay_capacity, seed=20260826)
    solvers = []
    anchor_sets = []
    teacher_reports = []

    for seed in seeds:
        solver = SuitCanonicalOutcomeSamplingMCCFR(
            seed=seed, epsilon=0.6, cfr_plus=True
        )
        solver.run(cfr_iterations)
        policy_report = distill_solver_nodes(
            solver,
            replay,
            max_nodes=max_teacher_nodes_per_seed,
        )
        anchors = _anchor_stream(
            seed,
            min_train=min_r4_train_per_seed,
            min_holdout=min_r4_holdout_per_seed,
        )
        r4_report = add_invariant_r4_teachers(anchors, replay)
        solvers.append(solver)
        anchor_sets.append(anchors)
        teacher_reports.append({
            "seed": seed,
            "tabular": policy_report,
            "exact_r4": r4_report,
        })

    model = SparseActionAdvantageModel(
        buckets=buckets,
        learning_rate=0.06,
        l2=1e-6,
        huber_delta=1.0,
        seed=20260826,
    )
    fit = model.fit(replay, epochs=epochs)

    seed_reports: list[SeedBenchmark] = []
    for seed, solver, anchors in zip(seeds, solvers, anchor_sets):
        policy = evaluate_model_on_solver(
            model, solver, holdout_only=True, max_nodes=512
        )
        r4 = evaluate_exact_r4_anchors(
            model, anchors, holdout_only=True, require_continuation_invariant=True
        )
        stats = solver.stats()
        invariant = [a for a in anchors if a.continuation_invariant]
        holdout_invariant = [a for a in invariant if is_holdout_key(a.key)]
        seed_reports.append(SeedBenchmark(
            seed=seed,
            cfr_infosets=stats.infosets,
            cfr_visits=stats.total_visits,
            exact_r4_total=len(anchors),
            exact_r4_invariant=len(invariant),
            exact_r4_holdout_invariant=len(holdout_invariant),
            policy_holdout=policy.payload(),
            exact_r4_holdout=r4.payload(),
        ))

    r4_top1 = [row.exact_r4_holdout["optimal_top1_accuracy"] for row in seed_reports]
    r4_greedy = [row.exact_r4_holdout["mean_greedy_point_regret"] for row in seed_reports]
    r4_expected = [row.exact_r4_holdout["mean_expected_point_regret"] for row in seed_reports]
    r4_uniform = [row.exact_r4_holdout["mean_uniform_point_regret"] for row in seed_reports]
    policy_top1 = [row.policy_holdout["top1_accuracy"] for row in seed_reports]
    policy_l1 = [row.policy_holdout["mean_policy_l1"] for row in seed_reports]

    aggregate = {
        "mean_policy_top1": sum(policy_top1) / len(policy_top1),
        "mean_policy_l1": sum(policy_l1) / len(policy_l1),
        "mean_exact_r4_top1": sum(r4_top1) / len(r4_top1),
        "mean_exact_r4_greedy_point_regret": sum(r4_greedy) / len(r4_greedy),
        "mean_exact_r4_expected_point_regret": sum(r4_expected) / len(r4_expected),
        "mean_exact_r4_uniform_point_regret": sum(r4_uniform) / len(r4_uniform),
        "exact_r4_expected_regret_improvement_vs_uniform": (
            sum(r4_uniform) - sum(r4_expected)
        ) / len(r4_uniform),
    }

    base = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "seeds": list(seeds),
        "config": {
            "cfr_iterations": cfr_iterations,
            "max_teacher_nodes_per_seed": max_teacher_nodes_per_seed,
            "min_r4_train_per_seed": min_r4_train_per_seed,
            "min_r4_holdout_per_seed": min_r4_holdout_per_seed,
            "replay_capacity": replay_capacity,
            "epochs": epochs,
            "buckets": buckets,
        },
        "teacher_reports": teacher_reports,
        "fit": fit,
        "replay": {
            "size": len(replay.items),
            "seen": replay.seen,
            "capacity": replay.capacity,
        },
        "per_seed": [row.payload() for row in seed_reports],
        "aggregate": aggregate,
        # Passing this smoke benchmark only proves deterministic plumbing and a
        # measurable held-out surface.  Numerical promotion thresholds are set
        # only after a Ryzen-scale baseline distribution exists.
        "promotion_ready": False,
        "next_gate": "RYZEN_SCALE_BASELINE_THEN_THRESHOLDS",
    }
    base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenOFC M4C3 multiseed benchmark")
    parser.add_argument("--seeds", default="20260826,20260827,20260828")
    parser.add_argument("--cfr-iterations", type=int, default=24)
    parser.add_argument("--teacher-nodes", type=int, default=256)
    parser.add_argument("--r4-train", type=int, default=6)
    parser.add_argument("--r4-holdout", type=int, default=3)
    parser.add_argument("--replay-capacity", type=int, default=30000)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--buckets", type=int, default=1 << 14)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_benchmark(
        _parse_seeds(args.seeds),
        cfr_iterations=args.cfr_iterations,
        max_teacher_nodes_per_seed=args.teacher_nodes,
        min_r4_train_per_seed=args.r4_train,
        min_r4_holdout_per_seed=args.r4_holdout,
        replay_capacity=args.replay_capacity,
        epochs=args.epochs,
        buckets=args.buckets,
    )
    raw = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw, end="")


if __name__ == "__main__":
    main()
