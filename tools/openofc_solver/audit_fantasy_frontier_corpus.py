from __future__ import annotations

"""Independent structural + exact-label auditor for M4I frontier shards."""

import argparse
import hashlib
import json
from pathlib import Path

from engine import Board, Card
from fantasy_frontier_cache_onepass import build_value_record_onepass
from fantasy_frontier_corpus import (
    GENERATOR,
    POINT_LIMIT,
    ROW_SCHEMA,
    SAMPLER,
    SHARD_SCHEMA,
    iter_rows,
    manifest_path,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reconstruct_world(canonical_key: str) -> tuple[tuple[Card, ...], Board]:
    payload = json.loads(canonical_key)
    if payload.get("v") != 1:
        raise ValueError("unsupported canonical frontier key version")
    packet = tuple(Card.parse(str(token)) for token in payload["packet"])
    rows = payload["normal_board"]
    if len(rows) != 3:
        raise ValueError("canonical normal board must contain three rows")
    board = Board(
        top=tuple(Card.parse(str(token)) for token in rows[0]),
        middle=tuple(Card.parse(str(token)) for token in rows[1]),
        bottom=tuple(Card.parse(str(token)) for token in rows[2]),
    )
    return packet, board


def audit_shard(data_path: Path, *, recompute_rows: int = 0) -> dict:
    meta_path = manifest_path(data_path)
    if not data_path.exists() or not meta_path.exists():
        raise FileNotFoundError("frontier shard or manifest missing")
    manifest = json.loads(meta_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SHARD_SCHEMA:
        raise ValueError("wrong M4I shard schema")
    if manifest.get("generator") != GENERATOR or manifest.get("reachability_sampler") != SAMPLER:
        raise ValueError("M4I shard generator/sampler mismatch")
    actual_sha = _sha256(data_path)
    if actual_sha != manifest.get("data_sha256"):
        raise ValueError("M4I shard SHA-256 mismatch")

    start_id = int(manifest["start_id"])
    end_id = int(manifest["end_id"])
    expected_ids = list(range(start_id, end_id))
    rows = list(iter_rows(data_path))
    if len(rows) != int(manifest["row_count"]) or len(rows) != len(expected_ids):
        raise ValueError("M4I shard row count mismatch")

    seen_keys: set[str] = set()
    observed_ids: list[int] = []
    branch_counts = {"both": 0, "no_only": 0, "ref_only": 0}
    for index, row in enumerate(rows):
        if row.get("schema") != ROW_SCHEMA:
            raise ValueError(f"row {index} schema mismatch")
        if row.get("generator") != GENERATOR or row.get("reachability_sampler") != SAMPLER:
            raise ValueError(f"row {index} provenance mismatch")
        if row.get("oracle_only") is not True:
            raise ValueError(f"row {index} must be marked oracle_only")
        if int(row["fantasy_count"]) != int(manifest["fantasy_count"]):
            raise ValueError(f"row {index} Fantasy count mismatch")
        observed_ids.append(int(row["world_id"]))
        key = str(row["canonical_world_key"])
        if key in seen_keys:
            raise ValueError("duplicate canonical world key inside shard")
        seen_keys.add(key)
        no = row.get("no_refantasy_points")
        ref = row.get("refantasy_points")
        if no is None and ref is None:
            raise ValueError(f"row {index} has no reachable branch")
        for value in (no, ref):
            if value is not None and not -POINT_LIMIT <= int(value) <= POINT_LIMIT:
                raise ValueError(f"row {index} exact point outside HU bound")
        branch_counts[
            "both" if no is not None and ref is not None
            else "no_only" if no is not None
            else "ref_only"
        ] += 1

        if index < recompute_rows:
            packet, board = reconstruct_world(key)
            exact = build_value_record_onepass(packet, board)
            if exact.key != key:
                raise AssertionError("canonical key changed during independent recomputation")
            if exact.no_refantasy_points != no or exact.refantasy_points != ref:
                raise AssertionError("stored exact frontier label failed recomputation")

    if observed_ids != expected_ids:
        raise ValueError("M4I world-id interval contains a gap, reorder or duplicate")
    return {
        "schema": "openofc-m4i-frontier-audit-v1",
        "data_sha256": actual_sha,
        "fantasy_count": int(manifest["fantasy_count"]),
        "row_count": len(rows),
        "unique_canonical_keys": len(seen_keys),
        "recomputed_rows": min(recompute_rows, len(rows)),
        "branch_counts": branch_counts,
        "status": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit exact M4I Fantasy frontier shard")
    parser.add_argument("path", type=Path)
    parser.add_argument("--recompute-rows", type=int, default=0)
    args = parser.parse_args()
    report = audit_shard(args.path, recompute_rows=args.recompute_rows)
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
