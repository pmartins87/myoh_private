from __future__ import annotations

import argparse
import json
from pathlib import Path

from fantasy_frontier_distillation import evaluate_model, load_examples
from fantasy_frontier_model import SparseFrontierModel, model_sha256

REPORT_SCHEMA = "openofc-m4j-terminal-frontier-training-report-v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train M4J terminal frontier approximation probe")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--pair-buckets", type=int, default=32768)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.input_dir.glob("*.jsonl"))
    if not paths:
        raise SystemExit("no M4I JSONL shards found")
    train = load_examples(paths, holdout=False)
    holdout = load_examples(paths, holdout=True)
    if not train or not holdout:
        raise SystemExit(
            f"exact corpus split is empty: train={len(train)} holdout={len(holdout)}"
        )

    model = SparseFrontierModel(
        pair_buckets=args.pair_buckets,
        seed=args.seed,
    )
    fit = model.fit(train, epochs=args.epochs)
    train_metrics = evaluate_model(model, train).payload()
    holdout_metrics = evaluate_model(model, holdout).payload()
    model_payload = model.payload()
    fingerprint = model_sha256(model)
    model_doc = {
        "schema": "openofc-m4j-terminal-frontier-model-artifact-v1",
        "sha256": fingerprint,
        "model": model_payload,
    }
    report = {
        "schema": REPORT_SCHEMA,
        "source_shards": [path.name for path in paths],
        "train_branch_examples": len(train),
        "holdout_branch_examples": len(holdout),
        "fit": fit,
        "train_metrics": train_metrics,
        "holdout_metrics": holdout_metrics,
        "model_sha256": fingerprint,
        "authority": "APPROXIMATION_PROBE_NOT_PRODUCTION",
        "promotion_blocked": True,
        "promotion_note": (
            "No quality threshold is frozen from this smoke corpus. Ryzen-scale "
            "multiseed exact held-out results are required before terminal-model use."
        ),
    }
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.model_output.write_text(
        json.dumps(model_doc, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    args.report_output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
