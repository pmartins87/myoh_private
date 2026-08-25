from __future__ import annotations

"""Parallel, deterministic multi-seed runner for the HU strategic solver.

Independent CFR seeds are useful for two different purposes:

1. use all available CPU cores without introducing asynchronous shared-regret
   races that would change the algorithm;
2. provide genuinely independent convergence / held-out evidence.

The checkpoints are NEVER merged by summing regrets. CFR updates are nonlinear,
so that operation would have no certified interpretation. The manifest instead
preserves each complete strategy independently and defines an optional uniform
*per-hand* mixture: select one checkpoint at the start of a hand and keep that
strategy for the entire hand. This is a valid mixed HU strategy and keeps the
perfect-recall policy of each member intact.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any, Iterable

from strategic_cfr_runner import (
    load_runner_checkpoint,
    run_chunked,
)
from strategic_suit_symmetry import SuitCanonicalOutcomeSamplingMCCFR

SCHEMA = "openofc-hu-strategic-multiseed-v1"
AUTHORITY = "STRATEGIC_APPROX_MULTI_SEED_HU"
SCOPE = "HU_ONLY"
SOLVER_KIND = "suit24-exact"
MIXTURE_SCOPE = "SELECT_ONE_MEMBER_AT_HAND_START"


@dataclass(frozen=True)
class SeedResult:
    seed: int
    iterations: int
    episodes: int
    infosets: int
    total_visits: int
    max_actions: int
    mean_actions: float
    checkpoint: str
    checkpoint_sha256: str
    checkpoint_bytes: int
    resumed: bool


def _parse_seeds(text: str) -> list[int]:
    values: list[int] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        values.append(int(token))
    if not values:
        raise ValueError("at least one seed is required")
    if len(set(values)) != len(values):
        raise ValueError("seeds must be unique")
    return values


def _checkpoint_path(root: Path, seed: int) -> Path:
    return root / f"seed{seed}.json.gz"


def _run_seed_job(
    seed: int,
    additional_iterations: int,
    checkpoint_every: int,
    epsilon: float,
    checkpoint_text: str,
    resume: bool,
) -> SeedResult:
    checkpoint = Path(checkpoint_text)
    resumed = False
    if resume and checkpoint.exists():
        solver, _digest = load_runner_checkpoint(checkpoint)
        if getattr(solver, "solver_kind", None) != SOLVER_KIND:
            raise ValueError(
                f"seed {seed}: resume checkpoint is not {SOLVER_KIND}"
            )
        if int(solver.seed) != int(seed):
            raise ValueError(
                f"seed {seed}: checkpoint seed mismatch ({solver.seed})"
            )
        if abs(float(solver.epsilon) - float(epsilon)) > 1e-12:
            raise ValueError(f"seed {seed}: checkpoint epsilon mismatch")
        resumed = True
    else:
        solver = SuitCanonicalOutcomeSamplingMCCFR(
            seed=int(seed), epsilon=float(epsilon), cfr_plus=True
        )

    report = run_chunked(
        solver,
        additional_iterations=int(additional_iterations),
        checkpoint_every=int(checkpoint_every),
        checkpoint=checkpoint,
    )
    if report["solver_kind"] != SOLVER_KIND:
        raise AssertionError("multi-seed worker changed solver kind")
    if int(report["max_actions"]) != 232:
        raise AssertionError("full 232-action opening was not preserved")

    return SeedResult(
        seed=int(seed),
        iterations=int(report["iterations"]),
        episodes=int(report["episodes"]),
        infosets=int(report["infosets"]),
        total_visits=int(report["total_visits"]),
        max_actions=int(report["max_actions"]),
        mean_actions=float(report["mean_actions"]),
        checkpoint=str(checkpoint),
        checkpoint_sha256=str(report["checkpoint_sha256"]),
        checkpoint_bytes=int(checkpoint.stat().st_size),
        resumed=resumed,
    )


def run_multiseed(
    *,
    seeds: Iterable[int],
    additional_iterations: int,
    checkpoint_every: int,
    epsilon: float,
    output_dir: Path,
    workers: int,
    resume: bool = False,
) -> dict[str, Any]:
    seed_list = [int(seed) for seed in seeds]
    if not seed_list or len(set(seed_list)) != len(seed_list):
        raise ValueError("seeds must be non-empty and unique")
    if additional_iterations <= 0:
        raise ValueError("additional_iterations must be positive")
    if checkpoint_every <= 0:
        raise ValueError("checkpoint_every must be positive")
    if workers <= 0:
        raise ValueError("workers must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[SeedResult] = []
    max_workers = min(int(workers), len(seed_list))

    if max_workers == 1:
        for seed in seed_list:
            results.append(
                _run_seed_job(
                    seed,
                    additional_iterations,
                    checkpoint_every,
                    epsilon,
                    str(_checkpoint_path(output_dir, seed)),
                    resume,
                )
            )
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _run_seed_job,
                    seed,
                    additional_iterations,
                    checkpoint_every,
                    epsilon,
                    str(_checkpoint_path(output_dir, seed)),
                    resume,
                ): seed
                for seed in seed_list
            }
            for future in as_completed(futures):
                results.append(future.result())

    results.sort(key=lambda row: row.seed)
    weights = {
        str(row.seed): 1.0 / len(results)
        for row in results
    }
    manifest = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "scope": SCOPE,
        "player_count": 2,
        "solver_kind": SOLVER_KIND,
        "action_abstraction": False,
        "member_count": len(results),
        "parallel_workers": max_workers,
        "additional_iterations_requested_per_seed": int(additional_iterations),
        "checkpoint_every": int(checkpoint_every),
        "epsilon": float(epsilon),
        "resume_requested": bool(resume),
        "members": [asdict(row) for row in results],
        "ensemble": {
            "kind": "uniform-root-mixture",
            "selection_scope": MIXTURE_SCOPE,
            "weights_by_seed": weights,
            "regrets_merged": False,
            "policy_switch_within_hand": False,
        },
        "warning": (
            "Independent seeds are convergence evidence and a valid per-hand "
            "mixed strategy. They are not an exploitability certificate, and "
            "their regret tables must not be summed."
        ),
    }
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parallel independent-seed HU suit-canonical MCCFR runner"
    )
    parser.add_argument("--seeds", required=True,
                        help="comma-separated unique integer seeds")
    parser.add_argument("--iterations", type=int, required=True,
                        help="additional iterations per seed")
    parser.add_argument("--checkpoint-every", type=int, default=10000)
    parser.add_argument("--epsilon", type=float, default=0.6)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    manifest = run_multiseed(
        seeds=_parse_seeds(args.seeds),
        additional_iterations=args.iterations,
        checkpoint_every=args.checkpoint_every,
        epsilon=args.epsilon,
        output_dir=args.output_dir,
        workers=args.workers,
        resume=args.resume,
    )
    text = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False)
    target = args.manifest or (args.output_dir / "manifest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n", encoding="utf-8")
    print("OPENOFC_STRATEGIC_MULTISEED=" + json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
