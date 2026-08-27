from __future__ import annotations

"""Deterministic exact terminal-Fantasy teacher corpus for M4I.

Rows are oracle data, not policy information.  They intentionally contain the
complete suit-canonical terminal world (hidden Fantasy packet + completed normal
board) because the terminal evaluator inside a sampled chance world is allowed
to know that world.  Policy encoders must never consume these rows directly.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from fantasy_frontier_cache_onepass import build_value_record_onepass
from normal_fantasy_feasibility import terminal_state

ROW_SCHEMA = "openofc-m4i-exact-fantasy-frontier-row-v1"
SHARD_SCHEMA = "openofc-m4i-exact-fantasy-frontier-shard-v1"
GENERATOR = "M4H_ONEPASS_EXACT_FRONTIER"
SAMPLER = "UNIFORM_LEGAL_REACHABILITY_ONLY_NOT_POLICY"
POINT_LIMIT = 103


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def world_seed(base_seed: int, fantasy_count: int, world_id: int) -> int:
    # Stable non-overlapping-ish integer mix. random.Random accepts arbitrary ints;
    # exact identity is bound into every row and manifest.
    x = int(base_seed) & ((1 << 64) - 1)
    x ^= (int(fantasy_count) * 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
    x ^= (int(world_id) * 0xD1B54A32D192ED03) & ((1 << 64) - 1)
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & ((1 << 64) - 1)
    x ^= x >> 31
    return x


def generate_row(base_seed: int, fantasy_count: int, world_id: int) -> dict:
    if fantasy_count not in (14, 15, 16, 17):
        raise ValueError("Fantasy count must be 14..17")
    seed = world_seed(base_seed, fantasy_count, world_id)
    state = terminal_state(seed, fantasy_count)
    record = build_value_record_onepass(state.plan.fantasy_packet, state.normal_board)
    points = (record.no_refantasy_points, record.refantasy_points)
    if all(value is None for value in points):
        raise AssertionError("exact terminal teacher produced no reachable branch")
    for value in points:
        if value is not None and not -POINT_LIMIT <= int(value) <= POINT_LIMIT:
            raise AssertionError("exact frontier point value outside proven HU bound")
    return {
        "schema": ROW_SCHEMA,
        "world_id": int(world_id),
        "world_seed": int(seed),
        "fantasy_count": int(fantasy_count),
        "canonical_world_key": record.key,
        "no_refantasy_points": record.no_refantasy_points,
        "refantasy_points": record.refantasy_points,
        "authority": record.authority,
        "generator": GENERATOR,
        "reachability_sampler": SAMPLER,
        "oracle_only": True,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(data_path: Path) -> Path:
    return data_path.with_suffix(data_path.suffix + ".manifest.json")


def expected_manifest_identity(
    *, base_seed: int, fantasy_count: int, start_id: int, end_id: int
) -> dict:
    if start_id < 0 or end_id <= start_id:
        raise ValueError("invalid half-open world-id range")
    return {
        "schema": SHARD_SCHEMA,
        "base_seed": int(base_seed),
        "fantasy_count": int(fantasy_count),
        "start_id": int(start_id),
        "end_id": int(end_id),
        "row_count": int(end_id - start_id),
        "generator": GENERATOR,
        "reachability_sampler": SAMPLER,
    }


def _completed_matches(data_path: Path, identity: dict) -> bool:
    meta_path = manifest_path(data_path)
    if not data_path.exists() or not meta_path.exists():
        return False
    try:
        manifest = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    for key, value in identity.items():
        if manifest.get(key) != value:
            return False
    return manifest.get("data_sha256") == _sha256(data_path)


def generate_shard(
    data_path: Path,
    *,
    base_seed: int,
    fantasy_count: int,
    start_id: int,
    end_id: int,
    resume: bool = True,
) -> dict:
    identity = expected_manifest_identity(
        base_seed=base_seed,
        fantasy_count=fantasy_count,
        start_id=start_id,
        end_id=end_id,
    )
    if resume and _completed_matches(data_path, identity):
        manifest = json.loads(manifest_path(data_path).read_text(encoding="utf-8"))
        manifest["resumed_without_regeneration"] = True
        return manifest

    data_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = data_path.with_suffix(data_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for world_id in range(start_id, end_id):
            row = generate_row(base_seed, fantasy_count, world_id)
            handle.write(_canonical_json(row) + "\n")
    tmp.replace(data_path)
    manifest = dict(identity)
    manifest.update({
        "data_file": data_path.name,
        "data_sha256": _sha256(data_path),
        "resumed_without_regeneration": False,
    })
    meta_tmp = manifest_path(data_path).with_suffix(".json.tmp")
    meta_tmp.write_text(_canonical_json(manifest) + "\n", encoding="utf-8")
    meta_tmp.replace(manifest_path(data_path))
    return manifest


def iter_rows(data_path: Path) -> Iterable[dict]:
    with data_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank row at line {line_number}")
            yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate exact M4I Fantasy frontier shard")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-seed", type=int, default=20260826)
    parser.add_argument("--fantasy-count", type=int, required=True)
    parser.add_argument("--start-id", type=int, required=True)
    parser.add_argument("--end-id", type=int, required=True)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    manifest = generate_shard(
        args.output,
        base_seed=args.base_seed,
        fantasy_count=args.fantasy_count,
        start_id=args.start_id,
        end_id=args.end_id,
        resume=not args.no_resume,
    )
    print(json.dumps(manifest, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
