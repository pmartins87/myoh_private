from __future__ import annotations

import json
import tempfile
from pathlib import Path

from audit_fantasy_frontier_corpus import audit_shard
from fantasy_frontier_corpus import (
    ROW_SCHEMA,
    generate_shard,
    iter_rows,
    manifest_path,
    world_seed,
)
from fantasy_frontier_features import FEATURE_DIMENSION, encode_canonical_world_key


def test_world_seed_is_deterministic_and_count_scoped() -> None:
    assert world_seed(7, 14, 3) == world_seed(7, 14, 3)
    assert world_seed(7, 14, 3) != world_seed(7, 15, 3)
    assert world_seed(7, 14, 3) != world_seed(7, 14, 4)


def test_one_row_shard_resume_audit_and_features() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "f14.jsonl"
        first = generate_shard(
            path,
            base_seed=20260826,
            fantasy_count=14,
            start_id=0,
            end_id=1,
            resume=True,
        )
        assert first["row_count"] == 1
        assert first["resumed_without_regeneration"] is False
        row = next(iter(iter_rows(path)))
        assert row["schema"] == ROW_SCHEMA
        assert row["oracle_only"] is True
        features = encode_canonical_world_key(row["canonical_world_key"])
        assert FEATURE_DIMENSION == 221
        assert len(features) == 29  # bias + count + F14 packet + 13 board cards
        report = audit_shard(path, recompute_rows=1)
        assert report["status"] == "PASS"
        assert report["recomputed_rows"] == 1
        assert report["unique_canonical_keys"] == 1

        second = generate_shard(
            path,
            base_seed=20260826,
            fantasy_count=14,
            start_id=0,
            end_id=1,
            resume=True,
        )
        assert second["resumed_without_regeneration"] is True
        assert second["data_sha256"] == first["data_sha256"]

        manifest = json.loads(manifest_path(path).read_text(encoding="utf-8"))
        assert manifest["data_sha256"] == first["data_sha256"]


def test_auditor_rejects_tampering() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "f14.jsonl"
        generate_shard(
            path,
            base_seed=20260827,
            fantasy_count=14,
            start_id=0,
            end_id=1,
        )
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        try:
            audit_shard(path)
        except ValueError as exc:
            assert "SHA-256" in str(exc)
        else:
            raise AssertionError("tampered M4I shard must fail closed")


def main() -> None:
    test_world_seed_is_deterministic_and_count_scoped()
    test_one_row_shard_resume_audit_and_features()
    test_auditor_rejects_tampering()
    print(
        "OPENOFC_M4I_EXACT_FRONTIER_CORPUS=PASS "
        "resume=EXACT sha256=BOUND recompute=INDEPENDENT features=LOSSLESS_ORACLE_ONLY"
    )


if __name__ == "__main__":
    main()
