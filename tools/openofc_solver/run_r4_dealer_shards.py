from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

CORPUS_VERSION = "openofc-r4-dealer-exact-v1"
MANIFEST_VERSION = "openofc-r4-dealer-shards-v1"


@dataclass(frozen=True)
class ShardSpec:
    index: int
    start_deal: int
    attempts: int
    path: Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_records(path: Path) -> int:
    with path.open("r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def first_last_key(path: Path) -> tuple[tuple[int, int] | None, tuple[int, int] | None]:
    first = None
    last = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (int(row["base_seed"]), int(row["deal_id"]))
            if first is None:
                first = key
            last = key
    return first, last


def validate_existing(spec: ShardSpec, base_seed: int) -> dict | None:
    """Return metadata when an existing shard is safe to resume; else None."""
    if not spec.path.exists() or spec.path.stat().st_size == 0:
        return None
    records = 0
    seen_ids: set[int] = set()
    min_id = None
    max_id = None
    with spec.path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("schema") != CORPUS_VERSION:
                return None
            if int(row.get("base_seed", -1)) != base_seed:
                return None
            deal_id = int(row["deal_id"])
            if deal_id < spec.start_deal or deal_id >= spec.start_deal + spec.attempts:
                return None
            if deal_id in seen_ids:
                return None
            seen_ids.add(deal_id)
            min_id = deal_id if min_id is None else min(min_id, deal_id)
            max_id = deal_id if max_id is None else max(max_id, deal_id)
            records += 1
    # Generator may filter all-actions-foul states, so emitted record count can
    # be lower than attempts. A completed marker, not record count, decides
    # whether a shard may be skipped.
    marker = spec.path.with_suffix(spec.path.suffix + ".done.json")
    if not marker.exists():
        return None
    meta = json.loads(marker.read_text(encoding="utf-8"))
    if (
        meta.get("status") != "PASS"
        or int(meta.get("base_seed", -1)) != base_seed
        or int(meta.get("start_deal", -1)) != spec.start_deal
        or int(meta.get("attempts", -1)) != spec.attempts
        or meta.get("sha256") != sha256_file(spec.path)
        or int(meta.get("records", -1)) != records
    ):
        return None
    return meta


def run_one(root: Path, spec: ShardSpec, base_seed: int, workers_per_shard: int,
            include_all_foul: bool) -> dict:
    existing = validate_existing(spec, base_seed)
    if existing is not None:
        return {**existing, "resumed": True}

    spec.path.parent.mkdir(parents=True, exist_ok=True)
    temp = spec.path.with_suffix(spec.path.suffix + ".tmp")
    temp.unlink(missing_ok=True)
    command = [
        sys.executable,
        str(root / "tools/openofc_solver/generate_r4_dealer_corpus.py"),
        "--out", str(temp),
        "--seed", str(base_seed),
        "--start-deal", str(spec.start_deal),
        "--attempts", str(spec.attempts),
        "--workers", str(workers_per_shard),
    ]
    if include_all_foul:
        command.append("--include-all-foul")
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"shard {spec.index} failed rc={proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    if not temp.exists():
        raise RuntimeError(f"shard {spec.index} did not create {temp}")

    # Recompute every stored label before accepting the shard. This is slower
    # than trusting generation, but M2 teacher corruption is much costlier than
    # an audit pass and the audit is embarrassingly parallel across shards.
    audit = subprocess.run(
        [
            sys.executable,
            str(root / "tools/openofc_solver/audit_r4_dealer_corpus.py"),
            str(temp),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if audit.returncode != 0:
        raise RuntimeError(
            f"shard {spec.index} audit failed rc={audit.returncode}\n"
            f"STDOUT:\n{audit.stdout}\nSTDERR:\n{audit.stderr}"
        )

    os.replace(temp, spec.path)
    records = count_records(spec.path)
    first, last = first_last_key(spec.path)
    meta = {
        "schema": MANIFEST_VERSION,
        "status": "PASS",
        "shard_index": spec.index,
        "base_seed": base_seed,
        "start_deal": spec.start_deal,
        "attempts": spec.attempts,
        "records": records,
        "first_key": first,
        "last_key": last,
        "sha256": sha256_file(spec.path),
        "seconds": round(time.time() - started, 3),
        "workers_per_shard": workers_per_shard,
        "include_all_foul": include_all_foul,
        "generator_stdout": proc.stdout.strip(),
        "audit_stdout": audit.stdout.strip(),
        "resumed": False,
    }
    spec.path.with_suffix(spec.path.suffix + ".done.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return meta


def build_specs(out_dir: Path, start_deal: int, total_attempts: int,
                attempts_per_shard: int) -> list[ShardSpec]:
    if total_attempts <= 0 or attempts_per_shard <= 0:
        raise ValueError("attempt counts must be positive")
    specs = []
    offset = 0
    index = 0
    while offset < total_attempts:
        attempts = min(attempts_per_shard, total_attempts - offset)
        shard_start = start_deal + offset
        path = out_dir / f"r4_dealer_{shard_start:012d}_{attempts:08d}.jsonl"
        specs.append(ShardSpec(index, shard_start, attempts, path))
        offset += attempts
        index += 1
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate resumable, audited dealer-R4 teacher shards"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--start-deal", type=int, default=0)
    parser.add_argument("--attempts", type=int, required=True)
    parser.add_argument("--attempts-per-shard", type=int, default=25000)
    parser.add_argument("--parallel-shards", type=int, default=1)
    parser.add_argument(
        "--workers-per-shard",
        type=int,
        default=max(1, (os.cpu_count() or 2) - 1),
    )
    parser.add_argument("--include-all-foul", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    # Materialize the certified M1b evaluator once before spawning worker
    # processes; generate_r4_dealer_corpus.py also fails closed independently.
    materialize = subprocess.run(
        [sys.executable, str(root / "tools/openofc_solver/apply_m1b_joker_semantics.py")],
        cwd=root,
        check=False,
    )
    if materialize.returncode != 0:
        raise SystemExit("M1b materialization failed; no M2 shards were generated")

    specs = build_specs(
        args.out_dir.resolve(), args.start_deal, args.attempts, args.attempts_per_shard
    )
    if args.parallel_shards <= 0 or args.workers_per_shard <= 0:
        raise SystemExit("parallelism values must be positive")
    total_processes = args.parallel_shards * args.workers_per_shard
    cpu = os.cpu_count() or 1
    if total_processes > cpu:
        print(
            f"WARNING: requested {total_processes} worker processes on {cpu} logical CPUs; "
            "oversubscription can reduce throughput",
            file=sys.stderr,
        )

    results: list[dict] = []
    if args.parallel_shards == 1:
        for spec in specs:
            results.append(run_one(
                root, spec, args.seed, args.workers_per_shard, args.include_all_foul
            ))
    else:
        with ThreadPoolExecutor(max_workers=args.parallel_shards) as pool:
            future_map = {
                pool.submit(
                    run_one, root, spec, args.seed,
                    args.workers_per_shard, args.include_all_foul,
                ): spec
                for spec in specs
            }
            for future in as_completed(future_map):
                results.append(future.result())

    results.sort(key=lambda x: int(x["shard_index"]))
    manifest = {
        "schema": MANIFEST_VERSION,
        "status": "PASS",
        "corpus_schema": CORPUS_VERSION,
        "base_seed": args.seed,
        "start_deal": args.start_deal,
        "attempts": args.attempts,
        "attempts_per_shard": args.attempts_per_shard,
        "parallel_shards": args.parallel_shards,
        "workers_per_shard": args.workers_per_shard,
        "include_all_foul": args.include_all_foul,
        "records": sum(int(x["records"]) for x in results),
        "shards": results,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("OPENOFC_R4_SHARD_RUN=" + json.dumps({
        "status": "PASS",
        "manifest": str(manifest_path),
        "shards": len(results),
        "records": manifest["records"],
        "attempts": args.attempts,
        "resumed_shards": sum(1 for x in results if x.get("resumed")),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
