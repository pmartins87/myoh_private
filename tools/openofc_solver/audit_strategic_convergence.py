from __future__ import annotations

"""Policy-stability audit for two strategic MCCFR checkpoints.

This deliberately does *not* call policy stability exploitability.  It measures
what can be observed directly: overlap of information states, visit-weighted
average-policy total-variation drift and greedy-action agreement.  These are
necessary scaling diagnostics, not a Nash-equilibrium certificate.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from strategic_cfr_runner import load_runner_checkpoint

AUDIT_SCHEMA = "openofc-hu-strategic-convergence-audit-v1"


def _tv(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("TV vectors differ in length")
    return 0.5 * sum(abs(x - y) for x, y in zip(a, b))


def _greedy_set(policy: list[float], tol: float = 1e-15) -> set[int]:
    best = max(policy)
    return {i for i, p in enumerate(policy) if best - p <= tol}


def audit(a_path: Path, b_path: Path) -> dict[str, Any]:
    a, a_sha = load_runner_checkpoint(a_path)
    b, b_sha = load_runner_checkpoint(b_path)
    if abs(a.epsilon - b.epsilon) > 1e-12 or a.cfr_plus != b.cfr_plus:
        raise ValueError("cannot compare checkpoints with different solver modes")

    keys_a = set(a.nodes)
    keys_b = set(b.nodes)
    common = sorted(keys_a & keys_b)
    rows = []
    weighted_tv_num = 0.0
    weighted_agree_num = 0.0
    weight_den = 0.0
    common_b_visits = 0
    for key in common:
        na = a.nodes[key]
        nb = b.nodes[key]
        if na.action_keys != nb.action_keys:
            raise ValueError("common information state changed legal action set")
        pa = na.average_policy()
        pb = nb.average_policy()
        distance = _tv(pa, pb)
        agree = bool(_greedy_set(pa) & _greedy_set(pb))
        weight = float(max(1, nb.visits))
        weighted_tv_num += weight * distance
        weighted_agree_num += weight * float(agree)
        weight_den += weight
        common_b_visits += nb.visits
        rows.append((distance, agree, nb.visits))

    total_b_visits = sum(node.visits for node in b.nodes.values())
    distances = sorted(row[0] for row in rows)
    p95 = distances[min(len(distances) - 1, int(0.95 * len(distances)))] if distances else 0.0
    report = {
        "schema": AUDIT_SCHEMA,
        "authority": "STABILITY_ONLY_NOT_EXPLOITABILITY",
        "a": {
            "path": str(a_path),
            "sha256": a_sha,
            "iterations": a.iterations,
            "infosets": len(a.nodes),
        },
        "b": {
            "path": str(b_path),
            "sha256": b_sha,
            "iterations": b.iterations,
            "infosets": len(b.nodes),
        },
        "common_infosets": len(common),
        "new_infosets_in_b": len(keys_b - keys_a),
        "lost_infosets_from_a": len(keys_a - keys_b),
        "b_visit_coverage_in_common": (
            common_b_visits / total_b_visits if total_b_visits else 0.0
        ),
        "weighted_mean_tv": (
            weighted_tv_num / weight_den if weight_den else 0.0
        ),
        "p95_tv": p95,
        "max_tv": max(distances, default=0.0),
        "weighted_greedy_overlap": (
            weighted_agree_num / weight_den if weight_den else 0.0
        ),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit MCCFR checkpoint policy stability")
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--max-weighted-tv", type=float)
    parser.add_argument("--min-weighted-greedy-overlap", type=float)
    args = parser.parse_args()
    report = audit(args.a, args.b)
    failures = []
    if args.max_weighted_tv is not None and report["weighted_mean_tv"] > args.max_weighted_tv:
        failures.append("weighted_mean_tv")
    if (args.min_weighted_greedy_overlap is not None
            and report["weighted_greedy_overlap"] < args.min_weighted_greedy_overlap):
        failures.append("weighted_greedy_overlap")
    report["threshold_status"] = "PASS" if not failures else "FAIL"
    report["threshold_failures"] = failures
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("OPENOFC_STRATEGIC_CONVERGENCE=" + json.dumps(report, sort_keys=True))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
