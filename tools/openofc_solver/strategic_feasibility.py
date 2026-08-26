from __future__ import annotations

"""Practical resource/reuse probe for the exact-action HU strategic solver.

This module does not change the game, prune actions or claim convergence. It
measures whether the current exact/suit-canonical MCCFR implementation is
practical on the machine that will actually train it. The report is deliberately
separate from exploitability: throughput, memory and information-set reuse are
engineering/statistical facts, not poker-optimality certificates.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Iterable

from strategic_cfr_runner import save_runner_checkpoint
from strategic_suit_symmetry import SuitCanonicalOutcomeSamplingMCCFR

AUTHORITY = "HU_FEASIBILITY_MEASUREMENT_ONLY"
SCOPE = "HU_ONLY"
SOLVER_KIND = "suit24-exact"
SCHEMA = "openofc-hu-strategic-feasibility-v2"
DECISIONS_PER_EPISODE = 10  # 5 rounds x 2 players; no early terminal in normal OFC.
DECISIONS_PER_ROUND_PER_EPISODE = 2


def _current_rss_bytes() -> int | None:
    """Best-effort current resident set size using only the standard library."""
    if sys.platform.startswith("linux"):
        try:
            pages = int(Path("/proc/self/statm").read_text().split()[1])
            return pages * int(os.sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError, IndexError):
            pass

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            )
            if ok:
                return int(counters.WorkingSetSize)
        except (AttributeError, OSError, ValueError):
            pass

    return None


def _peak_rss_bytes() -> int | None:
    try:
        import resource

        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux reports KiB; macOS/BSD commonly report bytes.
        if sys.platform.startswith("linux"):
            return value * 1024
        return value
    except (ImportError, AttributeError, OSError, ValueError):
        return None


def _parse_projection_iterations(text: str) -> list[int]:
    values: list[int] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        value = int(token)
        if value <= 0:
            raise ValueError("projection iterations must be positive")
        values.append(value)
    return sorted(set(values))


def _first_order_projections(
    *,
    measured_iterations: int,
    elapsed_seconds: float,
    infosets: int,
    checkpoint_bytes: int,
    targets: Iterable[int],
) -> list[dict[str, Any]]:
    iterations_per_second = measured_iterations / elapsed_seconds
    rows: list[dict[str, Any]] = []
    for target in targets:
        scale = target / measured_iterations
        rows.append(
            {
                "iterations": int(target),
                "wall_seconds_if_current_throughput_holds": (
                    target / iterations_per_second
                ),
                "infosets_if_linear_growth_holds": infosets * scale,
                "checkpoint_bytes_if_linear_growth_holds": checkpoint_bytes * scale,
                "authority": "DIAGNOSTIC_FIRST_ORDER_ONLY",
            }
        )
    return rows


def _clamp_fraction(value: float) -> float:
    if value < 0.0 and value > -1e-12:
        return 0.0
    if value > 1.0 and value < 1.0 + 1e-12:
        return 1.0
    return value


def _infoset_reuse_diagnostics(
    solver: SuitCanonicalOutcomeSamplingMCCFR,
) -> dict[str, Any]:
    """Measure whether exact tabular information states are actually revisited.

    Outcome-sampling walks all ten decision points in each HU normal-hand
    episode. `_node` is called even when that player is not the current regret
    updater, so episode_count * 10 is the exact information-state lookup count.
    The fraction below therefore measures exact-key reuse after certified suit
    canonicalization without adding any abstraction.
    """
    node_touches = int(solver.episodes) * DECISIONS_PER_EPISODE
    infosets = len(solver.nodes)
    if node_touches < infosets:
        raise AssertionError("unique infosets cannot exceed information-state touches")
    reuse_fraction = (
        0.0 if node_touches == 0
        else _clamp_fraction(1.0 - infosets / node_touches)
    )

    by_round: dict[int, dict[str, int]] = {
        r: {"infosets": 0, "updated_infosets": 0, "regret_updates": 0}
        for r in range(5)
    }
    updated_infosets = 0
    revisited_updated_infosets = 0
    max_regret_visits = 0

    for key, node in solver.nodes.items():
        try:
            round_index = int(json.loads(key)["round"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AssertionError("strategic infoset key lost round metadata") from exc
        if round_index not in by_round:
            raise AssertionError(f"unexpected normal-hand round in infoset: {round_index}")
        row = by_round[round_index]
        row["infosets"] += 1
        if node.visits > 0:
            updated_infosets += 1
            row["updated_infosets"] += 1
            row["regret_updates"] += int(node.visits)
            if node.visits > 1:
                revisited_updated_infosets += 1
            max_regret_visits = max(max_regret_visits, int(node.visits))

    regret_updates = sum(node.visits for node in solver.nodes.values())
    if regret_updates <= 0:
        regret_reuse_fraction = 0.0
    else:
        regret_reuse_fraction = _clamp_fraction(
            1.0 - updated_infosets / regret_updates
        )

    expected_round_touches = int(solver.episodes) * DECISIONS_PER_ROUND_PER_EPISODE
    round_report: dict[str, dict[str, Any]] = {}
    for round_index, row in sorted(by_round.items()):
        unique = row["infosets"]
        if unique > expected_round_touches:
            raise AssertionError("round infosets exceed exact round touch count")
        round_report[str(round_index)] = {
            **row,
            "node_touches": expected_round_touches,
            "infoset_reuse_fraction": (
                0.0 if expected_round_touches == 0
                else _clamp_fraction(1.0 - unique / expected_round_touches)
            ),
            "regret_reuse_fraction": (
                0.0 if row["regret_updates"] == 0
                else _clamp_fraction(
                    1.0 - row["updated_infosets"] / row["regret_updates"]
                )
            ),
        }

    return {
        "node_touches": node_touches,
        "unique_infosets": infosets,
        "infoset_reuse_fraction": reuse_fraction,
        "regret_updates": int(regret_updates),
        "updated_infosets": updated_infosets,
        "revisited_updated_infosets": revisited_updated_infosets,
        "regret_reuse_fraction": regret_reuse_fraction,
        "max_regret_visits": max_regret_visits,
        "by_round": round_report,
        "interpretation": (
            "Low reuse means the exact tabular representation is spending most "
            "samples creating new information states instead of accumulating "
            "regret at old ones. That is a practical scale signal, not an "
            "optimality statement."
        ),
    }


def run_probe(
    *,
    iterations: int,
    seed: int,
    epsilon: float,
    checkpoint: Path,
    projection_iterations: Iterable[int] = (10_000, 100_000, 1_000_000),
    max_wall_seconds: float | None = None,
    max_rss_mb: float | None = None,
    max_checkpoint_mb: float | None = None,
) -> dict[str, Any]:
    if iterations <= 0:
        raise ValueError("iterations must be positive")

    rss_before = _current_rss_bytes()
    solver = SuitCanonicalOutcomeSamplingMCCFR(
        seed=seed,
        epsilon=epsilon,
        cfr_plus=True,
    )

    start = time.perf_counter()
    stats = solver.run(iterations)
    elapsed = time.perf_counter() - start
    if elapsed <= 0.0:
        elapsed = 1e-12

    reuse = _infoset_reuse_diagnostics(solver)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_sha256 = save_runner_checkpoint(solver, checkpoint)
    checkpoint_bytes = checkpoint.stat().st_size
    rss_after = _current_rss_bytes()
    peak_rss = _peak_rss_bytes()

    if stats.max_actions != 232:
        raise AssertionError(
            f"full HU opening action set was not observed: {stats.max_actions}"
        )

    observed_rss = max(
        [x for x in (rss_before, rss_after, peak_rss) if x is not None],
        default=None,
    )
    budget_checks: dict[str, dict[str, Any]] = {}

    def add_budget(name: str, measured: float, limit: float | None, unit: str) -> None:
        budget_checks[name] = {
            "measured": measured,
            "limit": limit,
            "unit": unit,
            "status": "UNBOUNDED" if limit is None else (
                "PASS" if measured <= limit else "FAIL"
            ),
        }

    add_budget("wall", elapsed, max_wall_seconds, "seconds")
    add_budget(
        "checkpoint",
        checkpoint_bytes / (1024.0 * 1024.0),
        max_checkpoint_mb,
        "MiB",
    )
    if observed_rss is None:
        budget_checks["rss"] = {
            "measured": None,
            "limit": max_rss_mb,
            "unit": "MiB",
            "status": "UNAVAILABLE",
        }
    else:
        add_budget(
            "rss",
            observed_rss / (1024.0 * 1024.0),
            max_rss_mb,
            "MiB",
        )

    failed = [
        name for name, row in budget_checks.items() if row["status"] == "FAIL"
    ]

    report = {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "scope": SCOPE,
        "player_count": 2,
        "solver_kind": SOLVER_KIND,
        "exact_reductions": ["global-24-way-suit-isomorphism"],
        "action_abstraction": False,
        "iterations": stats.iterations,
        "episodes": stats.episodes,
        "elapsed_seconds": elapsed,
        "iterations_per_second": stats.iterations / elapsed,
        "episodes_per_second": stats.episodes / elapsed,
        "infosets": stats.infosets,
        "infosets_per_iteration": stats.infosets / stats.iterations,
        "total_visits": stats.total_visits,
        "max_actions": stats.max_actions,
        "mean_actions": stats.mean_actions,
        "reuse": reuse,
        "rss_before_bytes": rss_before,
        "rss_after_bytes": rss_after,
        "peak_rss_bytes": peak_rss,
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint_bytes,
        "checkpoint_sha256": checkpoint_sha256,
        "budget_checks": budget_checks,
        "budget_status": "FAIL" if failed else "PASS",
        "failed_budgets": failed,
        "projections": _first_order_projections(
            measured_iterations=stats.iterations,
            elapsed_seconds=elapsed,
            infosets=stats.infosets,
            checkpoint_bytes=checkpoint_bytes,
            targets=projection_iterations,
        ),
        "projection_warning": (
            "First-order engineering projection only; infoset growth and "
            "throughput are not assumed linear for certification."
        ),
        "optimality_warning": (
            "Resource/reuse feasibility is not exploitability and does not "
            "promote STRATEGIC_APPROX authority."
        ),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure practical cost/reuse of the exact-action HU suit-canonical MCCFR"
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--epsilon", type=float, default=0.6)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--project-iterations",
        default="10000,100000,1000000",
        help="comma-separated diagnostic projection targets",
    )
    parser.add_argument("--max-wall-seconds", type=float)
    parser.add_argument("--max-rss-mb", type=float)
    parser.add_argument("--max-checkpoint-mb", type=float)
    args = parser.parse_args()

    if args.checkpoint is None:
        tmp = tempfile.NamedTemporaryFile(
            prefix="openofc_hu_feasibility_", suffix=".json.gz", delete=False
        )
        tmp.close()
        checkpoint = Path(tmp.name)
        remove_checkpoint = True
    else:
        checkpoint = args.checkpoint
        remove_checkpoint = False

    try:
        report = run_probe(
            iterations=args.iterations,
            seed=args.seed,
            epsilon=args.epsilon,
            checkpoint=checkpoint,
            projection_iterations=_parse_projection_iterations(
                args.project_iterations
            ),
            max_wall_seconds=args.max_wall_seconds,
            max_rss_mb=args.max_rss_mb,
            max_checkpoint_mb=args.max_checkpoint_mb,
        )
        text = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text + "\n", encoding="utf-8")
        print(text)
        if report["budget_status"] != "PASS":
            raise SystemExit(2)
    finally:
        if remove_checkpoint:
            try:
                checkpoint.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    main()
