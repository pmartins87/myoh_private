from __future__ import annotations

"""One-command staged exact-corpus pilot for the user's Ryzen host.

Counts run sequentially so F17 cannot accidentally launch alongside F14/F15/F16
and multiply peak RAM.  Each count still uses a separate process pool.  The
initial defaults are intentionally conservative; the generated timing report is
used to raise worker counts safely on the actual machine.
"""

import argparse
import json
import time
from pathlib import Path

from audit_fantasy_frontier_corpus import audit_shard
from run_fantasy_frontier_shards import run as run_shards

SCHEMA = "openofc-m4k-ryzen-pilot-v1"
DEFAULT_WORKERS = {14: 8, 15: 8, 16: 4, 17: 2}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run M4K exact frontier Ryzen pilot")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--worlds-per-count", type=int, default=1000)
    parser.add_argument("--shard-size", type=int, default=25)
    parser.add_argument("--base-seed", type=int, default=20260826)
    parser.add_argument("--workers-f14", type=int, default=DEFAULT_WORKERS[14])
    parser.add_argument("--workers-f15", type=int, default=DEFAULT_WORKERS[15])
    parser.add_argument("--workers-f16", type=int, default=DEFAULT_WORKERS[16])
    parser.add_argument("--workers-f17", type=int, default=DEFAULT_WORKERS[17])
    parser.add_argument(
        "--recompute-one-per-count",
        action="store_true",
        help="independently recompute one exact row per Fantasy size after generation",
    )
    args = parser.parse_args()
    if args.worlds_per_count <= 0 or args.shard_size <= 0:
        raise SystemExit("worlds-per-count and shard-size must be positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    workers = {
        14: args.workers_f14,
        15: args.workers_f15,
        16: args.workers_f16,
        17: args.workers_f17,
    }
    report_rows = []
    total_start = time.perf_counter()
    for count in (14, 15, 16, 17):
        count_dir = args.output_dir / f"F{count}"
        start = time.perf_counter()
        index = run_shards(
            count_dir,
            counts=(count,),
            worlds_per_count=args.worlds_per_count,
            shard_size=args.shard_size,
            base_seed=args.base_seed,
            workers=workers[count],
        )
        elapsed = time.perf_counter() - start
        shard_paths = sorted(count_dir.glob("*.jsonl"))
        if not shard_paths:
            raise RuntimeError(f"F{count} generated no exact shards")
        audited_rows = 0
        for shard_index, path in enumerate(shard_paths):
            audit = audit_shard(
                path,
                recompute_rows=(
                    1 if args.recompute_one_per_count and shard_index == 0 else 0
                ),
            )
            audited_rows += int(audit["row_count"])
        if audited_rows != args.worlds_per_count:
            raise RuntimeError(
                f"F{count} audit cardinality mismatch: {audited_rows} != {args.worlds_per_count}"
            )
        row = {
            "fantasy_count": count,
            "workers": workers[count],
            "worlds": args.worlds_per_count,
            "shards": len(shard_paths),
            "elapsed_seconds": elapsed,
            "worlds_per_second": args.worlds_per_count / elapsed,
            "seconds_per_world_effective": elapsed / args.worlds_per_count,
            "index_schema": index["schema"],
            "status": "PASS",
        }
        report_rows.append(row)
        print(
            f"M4K_RYZEN_F{count}=PASS workers={workers[count]} "
            f"worlds={args.worlds_per_count} elapsed={elapsed:.3f}s "
            f"rate={row['worlds_per_second']:.6f}/s",
            flush=True,
        )

    report = {
        "schema": SCHEMA,
        "base_seed": args.base_seed,
        "worlds_per_count": args.worlds_per_count,
        "shard_size": args.shard_size,
        "rows": report_rows,
        "total_elapsed_seconds": time.perf_counter() - total_start,
        "authority": "EXACT_CORPUS_ENGINEERING_PILOT",
        "promotion_blocked": True,
        "next_action": (
            "Use measured F14-F17 throughput and host RAM telemetry to tune worker "
            "caps, then grow the exact corpus before freezing M4K quality thresholds."
        ),
    }
    out = args.output_dir / "M4K_RYZEN_PILOT_REPORT.json"
    out.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
