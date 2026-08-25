from __future__ import annotations

"""Practical resource probe for the exact-action HU strategic solver.

This module does not change the game, prune actions or claim convergence. It
measures whether the current exact/suit-canonical MCCFR implementation is
practical on the machine that will actually train it. The report is deliberately
separate from exploitability: throughput and low memory use are engineering
facts, not poker-optimality certificates.
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
SCHEMA = "openofc-hu-strategic-feasibility-v1"


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
            "Resource feasibility is not exploitability and does not promote "
            "STRATEGIC_APPROX authority."
        ),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure practical cost of the exact-action HU suit-canonical MCCFR"
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
