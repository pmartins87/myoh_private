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


CORPUS_VERSION = "openofc-r3-dealer-sampled-backup-v1"
MANIFEST_VERSION = "openofc-r3-dealer-shards-v1"


@dataclass(frozen=True)
class ShardSpec:
    index: int
    seed_index: int
    seed: int
    start_deal: int
    attempts: int
    path: Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_float(left: object, right: float) -> bool:
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return False


def summarize_records(path: Path) -> dict:
    records = 0
    informative = 0
    certified = 0
    known_joker = 0
    opponent_tie_records = 0
    legal_action_evaluations = 0
    seen: set[tuple[int, int]] = set()
    first_key = None
    last_key = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (int(row["base_seed"]), int(row["deal_id"]))
            if key in seen:
                raise RuntimeError(f"duplicate R3 key inside shard: {key}")
            seen.add(key)
            first_key = key if first_key is None else first_key
            last_key = key
            records += 1
            informative += int(bool(row.get("informative_action_values")))
            certified += int(bool(row.get("certified_unique_best")))
            known_joker += int(bool(row.get("contains_known_joker")))
            action_values = row.get("action_values", [])
            legal_action_evaluations += len(action_values) * int(row["sample_count"])
            opponent_tie_records += int(any(
                int(value.get("opponent_r4_tie_worlds", 0)) > 0
                for value in action_values
            ))
    return {
        "records": records,
        "informative_records": informative,
        "certified_records": certified,
        "known_joker_records": known_joker,
        "opponent_tie_records": opponent_tie_records,
        "legal_action_world_evaluations": legal_action_evaluations,
        "first_key": None if first_key is None else list(first_key),
        "last_key": None if last_key is None else list(last_key),
    }


def validate_existing(
    spec: ShardSpec,
    samples: int,
    confidence_delta: float,
) -> dict | None:
    """Accept an old shard only if its complete mathematical identity matches."""
    marker = spec.path.with_suffix(spec.path.suffix + ".done.json")
    if (
        not spec.path.is_file()
        or spec.path.stat().st_size == 0
        or not marker.is_file()
    ):
        return None
    try:
        summary = summarize_records(spec.path)
        meta = json.loads(marker.read_text(encoding="utf-8"))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, RuntimeError):
        return None
    if summary["records"] != spec.attempts:
        return None
    expected = {
        "schema": MANIFEST_VERSION,
        "status": "PASS",
        "shard_index": spec.index,
        "seed_index": spec.seed_index,
        "base_seed": spec.seed,
        "start_deal": spec.start_deal,
        "attempts": spec.attempts,
        "samples_per_action": samples,
    }
    if any(meta.get(key) != value for key, value in expected.items()):
        return None
    if not _same_float(meta.get("confidence_delta"), confidence_delta):
        return None
    if meta.get("sha256") != sha256_file(spec.path):
        return None
    for key, value in summary.items():
        if meta.get(key) != value:
            return None
    with spec.path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            deal_id = int(row.get("deal_id", -1))
            if (
                row.get("schema") != CORPUS_VERSION
                or int(row.get("base_seed", -1)) != spec.seed
                or deal_id < spec.start_deal
                or deal_id >= spec.start_deal + spec.attempts
                or int(row.get("sample_count", -1)) != samples
                or not _same_float(row.get("confidence_delta"), confidence_delta)
            ):
                return None
    return {
        **meta,
        "file": spec.path.name,
        "marker": marker.name,
    }


def run_one(
    root: Path,
    spec: ShardSpec,
    workers_per_shard: int,
    samples: int,
    confidence_delta: float,
) -> dict:
    existing = validate_existing(spec, samples, confidence_delta)
    if existing is not None:
        return {**existing, "resumed": True}

    spec.path.parent.mkdir(parents=True, exist_ok=True)
    temp = spec.path.with_suffix(spec.path.suffix + ".tmp")
    temp.unlink(missing_ok=True)
    command = [
        sys.executable,
        str(root / "tools/openofc_solver/generate_r3_dealer_corpus.py"),
        "--out", str(temp),
        "--seed", str(spec.seed),
        "--start-deal", str(spec.start_deal),
        "--attempts", str(spec.attempts),
        "--samples", str(samples),
        "--confidence-delta", str(confidence_delta),
        "--workers", str(workers_per_shard),
    ]
    started = time.time()
    generated = subprocess.run(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if generated.returncode != 0:
        raise RuntimeError(
            f"R3 shard {spec.index} generation failed rc={generated.returncode}\n"
            f"STDOUT:\n{generated.stdout}\nSTDERR:\n{generated.stderr}"
        )
    if not temp.is_file():
        raise RuntimeError(f"R3 shard {spec.index} did not create {temp}")

    # Independent deterministic recomputation is part of shard acceptance.
    audited = subprocess.run(
        [
            sys.executable,
            str(root / "tools/openofc_solver/audit_r3_dealer_corpus.py"),
            str(temp),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if audited.returncode != 0:
        raise RuntimeError(
            f"R3 shard {spec.index} audit failed rc={audited.returncode}\n"
            f"STDOUT:\n{audited.stdout}\nSTDERR:\n{audited.stderr}"
        )

    summary = summarize_records(temp)
    if summary["records"] != spec.attempts:
        raise RuntimeError(
            f"R3 shard {spec.index} emitted {summary['records']} records for "
            f"{spec.attempts} attempts"
        )
    os.replace(temp, spec.path)
    marker = spec.path.with_suffix(spec.path.suffix + ".done.json")
    meta = {
        "schema": MANIFEST_VERSION,
        "status": "PASS",
        "shard_index": spec.index,
        "seed_index": spec.seed_index,
        "base_seed": spec.seed,
        "start_deal": spec.start_deal,
        "attempts": spec.attempts,
        "samples_per_action": samples,
        "confidence_delta": confidence_delta,
        **summary,
        "sha256": sha256_file(spec.path),
        "file": spec.path.name,
        "marker": marker.name,
        "seconds": round(time.time() - started, 3),
        "workers_per_shard": workers_per_shard,
        "generator_stdout": generated.stdout.strip(),
        "audit_stdout": audited.stdout.strip(),
        "resumed": False,
    }
    marker.write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return meta


def build_specs(
    out_dir: Path,
    seeds: list[int],
    start_deal: int,
    attempts_per_seed: int,
    attempts_per_shard: int,
) -> list[ShardSpec]:
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be a non-empty unique list")
    if attempts_per_seed <= 0 or attempts_per_shard <= 0:
        raise ValueError("attempt counts must be positive")
    specs: list[ShardSpec] = []
    global_index = 0
    for seed_index, seed in enumerate(seeds):
        offset = 0
        while offset < attempts_per_seed:
            attempts = min(attempts_per_shard, attempts_per_seed - offset)
            shard_start = start_deal + offset
            filename = (
                f"r3_dealer_seed{seed}_"
                f"{shard_start:012d}_{attempts:08d}.jsonl"
            )
            specs.append(ShardSpec(
                global_index,
                seed_index,
                seed,
                shard_start,
                attempts,
                out_dir / filename,
            ))
            global_index += 1
            offset += attempts
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate resumable, independently audited, multi-seed dealer-R3 "
            "sampled-backup shards"
        )
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--seed",
        type=int,
        action="append",
        dest="seeds",
        help="repeat for independent reachability/state seeds",
    )
    parser.add_argument("--start-deal", type=int, default=0)
    parser.add_argument("--attempts", type=int, required=True,
                        help="states attempted per seed")
    parser.add_argument("--attempts-per-shard", type=int, default=100)
    parser.add_argument("--samples", type=int, default=64,
                        help="common hidden worlds evaluated per legal action")
    parser.add_argument("--confidence-delta", type=float, default=0.01)
    parser.add_argument("--parallel-shards", type=int, default=1)
    parser.add_argument(
        "--workers-per-shard",
        type=int,
        default=max(1, min(4, (os.cpu_count() or 2) - 1)),
    )
    args = parser.parse_args()

    seeds = args.seeds or [20260825]
    if args.samples <= 0:
        raise SystemExit("samples must be positive")
    if not 0.0 < args.confidence_delta < 1.0:
        raise SystemExit("confidence-delta must be between zero and one")
    if args.parallel_shards <= 0 or args.workers_per_shard <= 0:
        raise SystemExit("parallelism values must be positive")

    root = Path(__file__).resolve().parents[2]
    materialized = subprocess.run(
        [
            sys.executable,
            str(root / "tools/openofc_solver/apply_m1b_joker_semantics.py"),
        ],
        cwd=root,
        check=False,
    )
    if materialized.returncode != 0:
        raise SystemExit("M1b materialization failed; no M3a shards generated")

    out_dir = args.out_dir.resolve()
    specs = build_specs(
        out_dir,
        seeds,
        args.start_deal,
        args.attempts,
        args.attempts_per_shard,
    )
    requested_processes = args.parallel_shards * args.workers_per_shard
    logical_cpus = os.cpu_count() or 1
    if requested_processes > logical_cpus:
        print(
            f"WARNING: requested {requested_processes} workers on "
            f"{logical_cpus} logical CPUs; oversubscription may reduce throughput",
            file=sys.stderr,
        )

    results: list[dict] = []
    if args.parallel_shards == 1:
        for spec in specs:
            results.append(run_one(
                root,
                spec,
                args.workers_per_shard,
                args.samples,
                args.confidence_delta,
            ))
    else:
        with ThreadPoolExecutor(max_workers=args.parallel_shards) as pool:
            futures = {
                pool.submit(
                    run_one,
                    root,
                    spec,
                    args.workers_per_shard,
                    args.samples,
                    args.confidence_delta,
                ): spec
                for spec in specs
            }
            for future in as_completed(futures):
                results.append(future.result())
    results.sort(key=lambda item: int(item["shard_index"]))

    manifest = {
        "schema": MANIFEST_VERSION,
        "status": "PASS",
        "corpus_schema": CORPUS_VERSION,
        "seeds": seeds,
        "start_deal": args.start_deal,
        "attempts_per_seed": args.attempts,
        "total_attempts": args.attempts * len(seeds),
        "attempts_per_shard": args.attempts_per_shard,
        "samples_per_action": args.samples,
        "confidence_delta": args.confidence_delta,
        "parallel_shards": args.parallel_shards,
        "workers_per_shard": args.workers_per_shard,
        "records": sum(int(item["records"]) for item in results),
        "informative_records": sum(
            int(item["informative_records"]) for item in results
        ),
        "certified_records": sum(
            int(item["certified_records"]) for item in results
        ),
        "legal_action_world_evaluations": sum(
            int(item["legal_action_world_evaluations"]) for item in results
        ),
        "shards": results,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("OPENOFC_R3_SHARD_RUN=" + json.dumps({
        "status": "PASS",
        "manifest": str(manifest_path),
        "seeds": seeds,
        "shards": len(results),
        "records": manifest["records"],
        "samples_per_action": args.samples,
        "resumed_shards": sum(1 for item in results if item.get("resumed")),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
