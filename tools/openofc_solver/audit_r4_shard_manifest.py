from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CORPUS_VERSION = "openofc-r4-dealer-exact-v1"
MANIFEST_VERSION = "openofc-r4-dealer-shards-v1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_action(action: dict) -> str:
    return json.dumps(action, sort_keys=True, separators=(",", ":"))


def audit(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_VERSION or manifest.get("status") != "PASS":
        raise RuntimeError("manifest schema/status is not certified")
    if manifest.get("corpus_schema") != CORPUS_VERSION:
        raise RuntimeError("manifest corpus schema mismatch")

    root = manifest_path.parent
    base_seed = int(manifest["base_seed"])
    expected_start = int(manifest["start_deal"])
    expected_attempts = int(manifest["attempts"])
    shards = sorted(manifest.get("shards", []), key=lambda x: int(x["shard_index"]))
    if not shards:
        raise RuntimeError("manifest has no shards")

    global_ids: set[int] = set()
    total_records = 0
    total_attempts = 0
    joker_states = 0
    point_tie_states = 0
    fantasy_award_states = 0
    all_actions_foul = 0
    best_min = None
    best_max = None
    digest = hashlib.sha256()

    next_start = expected_start
    for expected_index, meta in enumerate(shards):
        if int(meta["shard_index"]) != expected_index:
            raise RuntimeError("shard indices are not contiguous from zero")
        if meta.get("status") != "PASS" or meta.get("schema") != MANIFEST_VERSION:
            raise RuntimeError(f"shard {expected_index} marker metadata is not PASS")
        if int(meta["base_seed"]) != base_seed:
            raise RuntimeError(f"shard {expected_index} seed mismatch")
        start = int(meta["start_deal"])
        attempts = int(meta["attempts"])
        if start != next_start:
            raise RuntimeError(
                f"shard {expected_index} range discontinuity: expected {next_start}, got {start}"
            )
        if attempts <= 0:
            raise RuntimeError(f"shard {expected_index} has non-positive attempts")
        next_start += attempts
        total_attempts += attempts

        filename = meta.get("file") or f"r4_dealer_{start:012d}_{attempts:08d}.jsonl"
        marker_name = meta.get("marker") or filename + ".done.json"
        shard_path = root / filename
        marker_path = root / marker_name
        if not shard_path.is_file() or not marker_path.is_file():
            raise RuntimeError(f"shard {expected_index} file/marker missing")

        actual_sha = sha256_file(shard_path)
        if actual_sha != meta.get("sha256"):
            raise RuntimeError(f"shard {expected_index} SHA-256 mismatch")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        for key in ("status", "base_seed", "start_deal", "attempts", "records", "sha256"):
            if marker.get(key) != meta.get(key):
                raise RuntimeError(f"shard {expected_index} marker/manifest mismatch: {key}")

        records = 0
        with shard_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                records += 1
                if row.get("schema") != CORPUS_VERSION:
                    raise RuntimeError(f"shard {expected_index} row schema mismatch")
                if int(row.get("base_seed", -1)) != base_seed:
                    raise RuntimeError(f"shard {expected_index} row seed mismatch")
                deal_id = int(row["deal_id"])
                if deal_id < start or deal_id >= start + attempts:
                    raise RuntimeError(f"shard {expected_index} deal_id outside assigned range")
                if deal_id in global_ids:
                    raise RuntimeError(f"duplicate deal_id across shards: {deal_id}")
                global_ids.add(deal_id)

                action_values = row.get("action_values", [])
                if len(action_values) != int(row.get("legal_action_count", -1)):
                    raise RuntimeError(f"deal {deal_id}: legal action count mismatch")
                if not action_values:
                    raise RuntimeError(f"deal {deal_id}: empty action value vector")
                points = [int(v["points"]) for v in action_values]
                best = max(points)
                if best != int(row["best_current_hand_points"]):
                    raise RuntimeError(f"deal {deal_id}: stored best points mismatch")
                expected_optimal = {
                    canonical_action(v["action"])
                    for v in action_values if int(v["points"]) == best
                }
                stored_optimal = {
                    canonical_action(a) for a in row.get("point_optimal_actions", [])
                }
                if stored_optimal != expected_optimal:
                    raise RuntimeError(f"deal {deal_id}: point-optimal action set mismatch")

                joker_states += int(bool(row.get("contains_joker")))
                point_tie_states += int(len(stored_optimal) > 1)
                fantasy_award_states += int(any(int(v.get("fantasy_cards", 0)) > 0 for v in action_values))
                all_actions_foul += int(bool(row.get("all_actions_foul")))
                best_min = best if best_min is None else min(best_min, best)
                best_max = best if best_max is None else max(best_max, best)

        if records != int(meta["records"]):
            raise RuntimeError(f"shard {expected_index} record count mismatch")
        total_records += records
        digest.update(f"{filename}:{actual_sha}\n".encode("ascii"))

    if total_attempts != expected_attempts or next_start != expected_start + expected_attempts:
        raise RuntimeError("aggregate shard ranges do not exactly cover manifest attempts")
    if total_records != int(manifest["records"]):
        raise RuntimeError("aggregate record count does not match manifest")

    result = {
        "status": "PASS",
        "schema": MANIFEST_VERSION,
        "base_seed": base_seed,
        "start_deal": expected_start,
        "attempts": expected_attempts,
        "shards": len(shards),
        "records": total_records,
        "unique_deal_ids": len(global_ids),
        "joker_states": joker_states,
        "point_tie_states": point_tie_states,
        "fantasy_award_states": fantasy_award_states,
        "all_actions_foul": all_actions_foul,
        "best_points_min": best_min,
        "best_points_max": best_max,
        "aggregate_content_sha256": digest.hexdigest(),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an OpenOFC dealer-R4 shard manifest")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit(args.manifest.resolve())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("OPENOFC_R4_SHARD_MANIFEST_AUDIT=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
