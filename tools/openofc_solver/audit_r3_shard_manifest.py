from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


CORPUS_VERSION = "openofc-r3-dealer-sampled-backup-v1"
MANIFEST_VERSION = "openofc-r3-dealer-shards-v1"


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


def audit(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_VERSION:
        raise RuntimeError("dealer R3 manifest schema mismatch")
    if manifest.get("status") != "PASS":
        raise RuntimeError("dealer R3 manifest is not PASS")
    if manifest.get("corpus_schema") != CORPUS_VERSION:
        raise RuntimeError("dealer R3 corpus schema mismatch")

    seeds = [int(seed) for seed in manifest.get("seeds", [])]
    if not seeds or len(set(seeds)) != len(seeds):
        raise RuntimeError("manifest seeds must be non-empty and unique")
    start_deal = int(manifest["start_deal"])
    attempts_per_seed = int(manifest["attempts_per_seed"])
    samples = int(manifest["samples_per_action"])
    confidence_delta = float(manifest["confidence_delta"])
    if attempts_per_seed <= 0 or samples <= 0:
        raise RuntimeError("manifest attempts/samples must be positive")
    if not 0.0 < confidence_delta < 1.0:
        raise RuntimeError("manifest confidence delta is invalid")

    shards = sorted(
        manifest.get("shards", []),
        key=lambda item: int(item["shard_index"]),
    )
    if not shards:
        raise RuntimeError("manifest contains no shards")
    root = manifest_path.parent
    expected_start = {seed: start_deal for seed in seeds}
    attempts_by_seed = Counter()
    global_keys: set[tuple[int, int]] = set()
    records = 0
    informative = 0
    certified = 0
    known_joker = 0
    opponent_tie_records = 0
    legal_action_evaluations = 0
    legal_histogram: Counter[int] = Counter()
    digest = hashlib.sha256()

    forbidden = {
        "opponent_hidden_discards",
        "opponent_r3_packet",
        "opponent_r4_packet",
        "dealer_r4_packet",
        "actual_hidden_worlds",
        "sampled_hidden_worlds",
    }
    for expected_index, meta in enumerate(shards):
        if int(meta["shard_index"]) != expected_index:
            raise RuntimeError("shard indices are not contiguous from zero")
        if meta.get("schema") != MANIFEST_VERSION or meta.get("status") != "PASS":
            raise RuntimeError(f"shard {expected_index} marker is not certified")
        seed = int(meta["base_seed"])
        if seed not in expected_start:
            raise RuntimeError(f"shard {expected_index} uses undeclared seed")
        if int(meta.get("seed_index", -1)) != seeds.index(seed):
            raise RuntimeError(f"shard {expected_index} seed index mismatch")
        shard_start = int(meta["start_deal"])
        shard_attempts = int(meta["attempts"])
        if shard_start != expected_start[seed]:
            raise RuntimeError(
                f"seed {seed} range discontinuity: expected "
                f"{expected_start[seed]}, got {shard_start}"
            )
        if shard_attempts <= 0:
            raise RuntimeError(f"shard {expected_index} has no attempts")
        expected_start[seed] += shard_attempts
        attempts_by_seed[seed] += shard_attempts
        if int(meta.get("samples_per_action", -1)) != samples:
            raise RuntimeError(f"shard {expected_index} sample count mismatch")
        if not _same_float(meta.get("confidence_delta"), confidence_delta):
            raise RuntimeError(f"shard {expected_index} confidence mismatch")

        filename = meta["file"]
        marker_name = meta["marker"]
        shard_path = root / filename
        marker_path = root / marker_name
        if not shard_path.is_file() or not marker_path.is_file():
            raise RuntimeError(f"shard {expected_index} file/marker missing")
        actual_sha = sha256_file(shard_path)
        if actual_sha != meta.get("sha256"):
            raise RuntimeError(f"shard {expected_index} SHA-256 mismatch")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        for key in (
            "schema", "status", "shard_index", "seed_index", "base_seed",
            "start_deal", "attempts", "records", "samples_per_action",
            "confidence_delta", "sha256", "informative_records",
            "certified_records", "legal_action_world_evaluations",
        ):
            if marker.get(key) != meta.get(key):
                raise RuntimeError(
                    f"shard {expected_index} marker/manifest mismatch: {key}"
                )

        shard_records = 0
        shard_informative = 0
        shard_certified = 0
        shard_joker = 0
        shard_ties = 0
        shard_evaluations = 0
        with shard_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                shard_records += 1
                if row.get("schema") != CORPUS_VERSION:
                    raise RuntimeError(f"shard {expected_index} row schema mismatch")
                if int(row.get("base_seed", -1)) != seed:
                    raise RuntimeError(f"shard {expected_index} row seed mismatch")
                deal_id = int(row["deal_id"])
                if not shard_start <= deal_id < shard_start + shard_attempts:
                    raise RuntimeError(f"shard {expected_index} deal outside range")
                key = (seed, deal_id)
                if key in global_keys:
                    raise RuntimeError(f"duplicate dealer R3 corpus key: {key}")
                global_keys.add(key)
                if int(row.get("sample_count", -1)) != samples:
                    raise RuntimeError(f"deal {key} sample count mismatch")
                if not _same_float(row.get("confidence_delta"), confidence_delta):
                    raise RuntimeError(f"deal {key} confidence mismatch")
                if row.get("hidden_world_persisted") is not False:
                    raise RuntimeError(f"deal {key} hidden-world guard is not false")
                leaked = forbidden.intersection(row)
                if leaked:
                    raise RuntimeError(f"deal {key} leaked hidden data: {sorted(leaked)}")

                values = row.get("action_values", [])
                legal_count = int(row.get("legal_action_count", -1))
                if not values or len(values) != legal_count:
                    raise RuntimeError(f"deal {key} legal action vector mismatch")
                intervals = {
                    (int(value["lower_points_sum"]), int(value["upper_points_sum"]))
                    for value in values
                }
                distinct = len(intervals)
                if int(row.get("distinct_action_interval_count", -1)) != distinct:
                    raise RuntimeError(f"deal {key} interval cardinality mismatch")
                if bool(row.get("informative_action_values")) != (distinct > 1):
                    raise RuntimeError(f"deal {key} informative flag mismatch")
                if any(int(value.get("samples", -1)) != samples for value in values):
                    raise RuntimeError(f"deal {key} per-action samples mismatch")
                certified_action = row.get("certified_unique_best_action")
                if bool(row.get("certified_unique_best")) != (
                    certified_action is not None
                ):
                    raise RuntimeError(f"deal {key} certificate flag/action mismatch")
                if not row.get("empirical_robust_best_actions"):
                    raise RuntimeError(f"deal {key} has no empirical robust-best action")

                row_informative = int(distinct > 1)
                row_certified = int(bool(row.get("certified_unique_best")))
                row_joker = int(bool(row.get("contains_known_joker")))
                row_tie = int(any(
                    int(value.get("opponent_r4_tie_worlds", 0)) > 0
                    for value in values
                ))
                evaluations = legal_count * samples
                shard_informative += row_informative
                shard_certified += row_certified
                shard_joker += row_joker
                shard_ties += row_tie
                shard_evaluations += evaluations
                legal_histogram[legal_count] += 1

        expected_summary = {
            "records": shard_records,
            "informative_records": shard_informative,
            "certified_records": shard_certified,
            "known_joker_records": shard_joker,
            "opponent_tie_records": shard_ties,
            "legal_action_world_evaluations": shard_evaluations,
        }
        for key, value in expected_summary.items():
            if int(meta.get(key, -1)) != value:
                raise RuntimeError(
                    f"shard {expected_index} summary mismatch: {key}"
                )
        if shard_records != shard_attempts:
            raise RuntimeError(f"shard {expected_index} did not emit every attempt")
        records += shard_records
        informative += shard_informative
        certified += shard_certified
        known_joker += shard_joker
        opponent_tie_records += shard_ties
        legal_action_evaluations += shard_evaluations
        digest.update(f"{filename}:{actual_sha}\n".encode("ascii"))

    for seed in seeds:
        if attempts_by_seed[seed] != attempts_per_seed:
            raise RuntimeError(f"seed {seed} attempt coverage mismatch")
        if expected_start[seed] != start_deal + attempts_per_seed:
            raise RuntimeError(f"seed {seed} terminal range mismatch")
    total_attempts = attempts_per_seed * len(seeds)
    if int(manifest.get("total_attempts", -1)) != total_attempts:
        raise RuntimeError("manifest total-attempt count mismatch")
    aggregate_expected = {
        "records": records,
        "informative_records": informative,
        "certified_records": certified,
        "legal_action_world_evaluations": legal_action_evaluations,
    }
    for key, value in aggregate_expected.items():
        if int(manifest.get(key, -1)) != value:
            raise RuntimeError(f"manifest aggregate mismatch: {key}")

    return {
        "schema": MANIFEST_VERSION,
        "status": "PASS",
        "seeds": seeds,
        "start_deal": start_deal,
        "attempts_per_seed": attempts_per_seed,
        "total_attempts": total_attempts,
        "shards": len(shards),
        "records": records,
        "unique_keys": len(global_keys),
        "samples_per_action": samples,
        "confidence_delta": confidence_delta,
        "informative_records": informative,
        "informative_rate": informative / records,
        "certified_records": certified,
        "certified_rate": certified / records,
        "known_joker_records": known_joker,
        "opponent_tie_records": opponent_tie_records,
        "legal_action_histogram": {
            str(count): legal_histogram[count] for count in sorted(legal_histogram)
        },
        "legal_action_world_evaluations": legal_action_evaluations,
        "aggregate_content_sha256": digest.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit an OpenOFC multi-seed dealer-R3 shard manifest"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit(args.manifest.resolve())
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("OPENOFC_R3_SHARD_MANIFEST_AUDIT=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
