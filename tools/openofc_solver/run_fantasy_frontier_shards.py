from __future__ import annotations

"""Parallel/resumable M4I exact Fantasy-frontier shard runner."""

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from fantasy_frontier_corpus import generate_shard
from normal_fantasy_feasibility import parse_counts

INDEX_SCHEMA = "openofc-m4i-frontier-corpus-index-v1"


def _worker(args):
    path, base_seed, count, start_id, end_id = args
    manifest = generate_shard(
        Path(path),
        base_seed=base_seed,
        fantasy_count=count,
        start_id=start_id,
        end_id=end_id,
        resume=True,
    )
    return str(path), manifest


def shard_jobs(
    output_dir: Path,
    *,
    counts: tuple[int, ...],
    worlds_per_count: int,
    shard_size: int,
    base_seed: int,
):
    if worlds_per_count <= 0 or shard_size <= 0:
        raise ValueError("worlds_per_count and shard_size must be positive")
    jobs = []
    for count in counts:
        start = 0
        while start < worlds_per_count:
            end = min(worlds_per_count, start + shard_size)
            path = output_dir / f"f{count}_worlds_{start:08d}_{end:08d}.jsonl"
            jobs.append((path, base_seed, count, start, end))
            start = end
    return jobs


def run(
    output_dir: Path,
    *,
    counts: tuple[int, ...],
    worlds_per_count: int,
    shard_size: int,
    base_seed: int,
    workers: int,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = shard_jobs(
        output_dir,
        counts=counts,
        worlds_per_count=worlds_per_count,
        shard_size=shard_size,
        base_seed=base_seed,
    )
    if workers <= 0:
        workers = max(1, (os.cpu_count() or 1) - 1)
    manifests = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_worker, tuple(str(x) if isinstance(x, Path) else x for x in job)): job for job in jobs}
        for future in as_completed(futures):
            path, manifest = future.result()
            manifests.append({"path": Path(path).name, "manifest": manifest})
            print(
                "M4I_SHARD=" + Path(path).name
                + " rows=" + str(manifest["row_count"])
                + " resumed=" + str(bool(manifest.get("resumed_without_regeneration"))).lower(),
                flush=True,
            )
    manifests.sort(key=lambda item: item["path"])
    index = {
        "schema": INDEX_SCHEMA,
        "base_seed": int(base_seed),
        "counts": list(counts),
        "worlds_per_count": int(worlds_per_count),
        "shard_size": int(shard_size),
        "workers": int(workers),
        "shards": manifests,
    }
    (output_dir / "INDEX.json").write_text(
        json.dumps(index, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Run resumable M4I exact frontier shards")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--counts", default="14,15,16,17")
    parser.add_argument("--worlds-per-count", type=int, required=True)
    parser.add_argument("--shard-size", type=int, default=64)
    parser.add_argument("--base-seed", type=int, default=20260826)
    parser.add_argument("--workers", type=int, default=0)
    args = parser.parse_args()
    index = run(
        args.output_dir,
        counts=parse_counts(args.counts),
        worlds_per_count=args.worlds_per_count,
        shard_size=args.shard_size,
        base_seed=args.base_seed,
        workers=args.workers,
    )
    print(json.dumps(index, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
