from __future__ import annotations

"""Convert an M4S held-out run into provisional Fantasy/Fantasy Bellman rows.

The adapter computes the chance-sample mean of the learned sealed policy's exact
M4P profile value for each measured meta-state. Descriptive standard error and
M4O/P/Q diagnostics are retained, but the rows remain uncertified because M4S has
not yet supplied a rigorous absolute one-hand value error bound.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from fantasy_fantasy_policy_model import load_checkpoint
from fantasy_fantasy_selfplay import exact_selfplay_targets, snapshot_episode_policy
from hu_bellman_rows import BellmanRowArtifact, BellmanRowBundle
from hu_continuation import HUContinuationState, KERNEL_FANTASY_FANTASY
from run_m4s_multiseed import load_cached_episode, load_continuation_values
from hu_bellman_iteration import continuation_sha256

AUTHORITY = "PROVISIONAL_M4S_HELDOUT_POLICY_MEAN_NO_ABSOLUTE_ERROR_CERTIFICATE"
SOLVER_KIND = "m4r-sealed-fantasy-generalized-selfplay"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _load_report(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("M4S report must be a JSON mapping")
    raw = dict(payload)
    expected = str(raw.pop("sha256", ""))
    actual = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
    if expected != actual:
        raise ValueError("M4S report SHA-256 mismatch")
    payload["sha256"] = expected
    return payload


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("mean requires observations")
    return sum(values) / len(values)


def _stderr(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = _mean(values)
    sample_var = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(sample_var / len(values))


def build_fantasy_rows_from_m4s(
    output_dir: Path,
    *,
    continuation_values: Mapping[HUContinuationState, float],
) -> BellmanRowBundle:
    report_path = output_dir / "M4S_HELDOUT_REPORT.json"
    checkpoint_path = output_dir / "M4S_MODEL_REPLAY.json.gz"
    report = _load_report(report_path)
    continuation_sha = continuation_sha256(continuation_values)
    if report.get("continuation_fingerprint") != continuation_sha:
        raise ValueError("M4S report was generated from a different continuation vector")
    checkpoint_sha = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    if report.get("model_checkpoint_sha256") != checkpoint_sha:
        raise ValueError("M4S model checkpoint SHA does not match held-out report")
    model, _replay = load_checkpoint(checkpoint_path)

    report_rows = {
        (str(row["state"]), int(row["world_index"])): row
        for row in report.get("heldout", [])
    }
    grouped: dict[HUContinuationState, list[dict]] = {}
    cache_paths = sorted((output_dir / "episodes" / "heldout").glob("**/world_*.json"))
    if not cache_paths:
        raise ValueError("M4S output contains no held-out cached episodes")
    for cache_path in cache_paths:
        cached = load_cached_episode(cache_path)
        episode = cached.episode
        state = episode.world.current_meta
        if state.p0_fantasy_cards == 0 or state.p1_fantasy_cards == 0:
            raise ValueError("M4S Fantasy row adapter received a non Fantasy/Fantasy state")
        snapshot = snapshot_episode_policy(model, episode)
        _frozen, targets = exact_selfplay_targets(model, episode)
        errors = [
            abs(model.predict(example) - example.target)
            for example in targets.p0_examples + targets.p1_examples
        ]
        source_row = report_rows.get((state.as_key(), cached.world_index), {})
        gaps = [
            float(value)
            for value in (
                source_row.get("p0_sampled_exact_support_gap"),
                source_row.get("p1_sampled_exact_support_gap"),
            )
            if value is not None
        ]
        grouped.setdefault(state, []).append(
            {
                "value": float(snapshot.diagnostic.profile_p0_value),
                "support_deviation": float(
                    snapshot.diagnostic.total_support_deviation_gain
                ),
                "q_mae": _mean(errors),
                "q_max": max(errors),
                "support_gaps": gaps,
            }
        )

    rows = []
    for state in sorted(grouped):
        observations = grouped[state]
        values = [row["value"] for row in observations]
        deviations = [row["support_deviation"] for row in observations]
        q_maes = [row["q_mae"] for row in observations]
        q_maxes = [row["q_max"] for row in observations]
        support_gaps = [
            gap for row in observations for gap in row["support_gaps"]
        ]
        rows.append(
            BellmanRowArtifact(
                state=state,
                input_continuation_fingerprint=continuation_sha,
                value_p0=_mean(values),
                kernel_kind=KERNEL_FANTASY_FANTASY,
                solver_kind=SOLVER_KIND,
                authority=AUTHORITY,
                evidence_sha256=str(report["sha256"]),
                certified=False,
                error_bound_abs=None,
                samples=len(values),
                diagnostics={
                    "chance_sample_standard_error_descriptive_only": _stderr(values),
                    "mean_support_restricted_deviation": _mean(deviations),
                    "max_support_restricted_deviation": max(deviations),
                    "mean_action_value_mae": _mean(q_maes),
                    "max_action_value_abs_error": max(q_maxes),
                    "mean_sampled_exact_support_gap": (
                        _mean(support_gaps) if support_gaps else None
                    ),
                    "support_gap_observations": len(support_gaps),
                    "certification_blocker": (
                        "descriptive chance stderr and strategic diagnostics are not a "
                        "rigorous absolute Bellman-row error bound"
                    ),
                },
            )
        )
    return BellmanRowBundle(
        input_continuation_fingerprint=continuation_sha,
        rows=tuple(rows),
        source=f"M4S:{output_dir}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build provisional Fantasy/Fantasy Bellman rows from M4S held-out evidence"
    )
    parser.add_argument("--m4s-output-dir", type=Path, required=True)
    parser.add_argument("--continuation-values", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    continuation = load_continuation_values(args.continuation_values)
    bundle = build_fantasy_rows_from_m4s(
        args.m4s_output_dir, continuation_values=continuation
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(bundle.payload(), sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"M4U_FF_ROWS={len(bundle.rows)} certified=0 "
        f"continuation={bundle.input_continuation_fingerprint}"
    )


if __name__ == "__main__":
    main()
