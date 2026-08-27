from __future__ import annotations

import argparse
import json
from pathlib import Path

from fantasy_frontier_mlp import TerminalFrontierMLP, load_worlds
from fantasy_frontier_mlp_eval import evaluate, stratified_metrics

REPORT_SCHEMA = "openofc-m4k-terminal-frontier-mlp-report-v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the M4K terminal-frontier MLP")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--hidden1", type=int, default=128)
    parser.add_argument("--hidden2", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(args.input_dir.rglob("*.jsonl"))
    if not paths:
        raise SystemExit("no M4I exact frontier shards found")
    train = load_worlds(paths, holdout=False)
    holdout = load_worlds(paths, holdout=True)
    if not train or not holdout:
        raise SystemExit(
            f"M4K split is empty: train_worlds={len(train)} holdout_worlds={len(holdout)}"
        )

    model = TerminalFrontierMLP(
        hidden1=args.hidden1,
        hidden2=args.hidden2,
        seed=args.seed,
    )
    fit = model.fit(train, epochs=args.epochs, batch_size=args.batch_size)
    model_sha = model.save(args.model_output)
    train_metrics = evaluate(model, train).payload()
    holdout_metrics = evaluate(model, holdout).payload()
    report = {
        "schema": REPORT_SCHEMA,
        "authority": "APPROXIMATION_PROBE_NOT_PRODUCTION",
        "promotion_blocked": True,
        "source_shards": [str(path.relative_to(args.input_dir)) for path in paths],
        "train_worlds": len(train),
        "holdout_worlds": len(holdout),
        "fit": fit,
        "train_metrics": train_metrics,
        "holdout_metrics": holdout_metrics,
        "holdout_strata": stratified_metrics(model, holdout),
        "model_sha256": model_sha,
        "model_bytes": args.model_output.stat().st_size,
        "promotion_note": (
            "Smoke metrics validate mechanics only. Promotion requires a Ryzen-scale "
            "multiseed exact corpus across F14-F17 and explicit error thresholds."
        ),
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
