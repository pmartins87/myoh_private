from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Iterable

from audit_r3_dealer_corpus import audit_row, canonical, parse_board
from engine import parse_cards
from generate_r3_dealer_corpus import CORPUS_VERSION, action_payload
from teacher_search_r3_dealer import solve_r3_dealer_sampled_backup


MANIFEST_VERSION = "openofc-r3-dealer-shards-v1"
REPORT_VERSION = "openofc-r3-dealer-convergence-v1"


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1))
    return ordered[index]


def iter_rows(source: Path) -> Iterable[dict]:
    if source.name == "manifest.json" or source.suffix.lower() == ".json":
        manifest = json.loads(source.read_text(encoding="utf-8"))
        if manifest.get("schema") != MANIFEST_VERSION or manifest.get("status") != "PASS":
            raise RuntimeError("convergence source manifest is not certified")
        for meta in sorted(
            manifest.get("shards", []),
            key=lambda item: int(item["shard_index"]),
        ):
            path = source.parent / meta["file"]
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)
        return
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _best_actions_from_row(row: dict) -> set[str]:
    return {
        canonical(action)
        for action in row.get("empirical_robust_best_actions", [])
    }


def _best_actions_from_result(result, incoming) -> set[str]:
    return {
        canonical(action_payload(value.action, incoming))
        for value in result.empirical_robust_best
    }


def compare_row(row: dict, multiplier: int) -> dict:
    if row.get("schema") != CORPUS_VERSION:
        raise RuntimeError("dealer R3 convergence row schema mismatch")
    # First prove that the stored N-world vector still recomputes exactly.
    audited = audit_row(row)
    base_samples = int(row["sample_count"])
    expanded_samples = base_samples * multiplier
    dealer = parse_board(row["dealer_before"])
    opponent = parse_board(row["opponent_after_r3"])
    incoming = parse_cards(" ".join(row["incoming"]))
    discards = parse_cards(" ".join(row["dealer_known_discards"]))
    expanded = solve_r3_dealer_sampled_backup(
        dealer,
        opponent,
        incoming,
        discards,
        sample_count=expanded_samples,
        seed=int(row["world_seed"]),
        confidence_delta=float(row["confidence_delta"]),
    )
    base_by_action = {
        canonical(value["action"]): value for value in row["action_values"]
    }
    expanded_by_action = {
        canonical(action_payload(value.action, incoming)): value
        for value in expanded.all_actions
    }
    if base_by_action.keys() != expanded_by_action.keys():
        raise RuntimeError("dealer R3 action set changed between N and multiplier*N")

    mean_drifts: list[float] = []
    base_widths: list[float] = []
    expanded_widths: list[float] = []
    for key, base in base_by_action.items():
        extension = expanded_by_action[key]
        mean_drifts.extend((
            abs(float(base["lower_mean"]) - extension.lower_mean),
            abs(float(base["upper_mean"]) - extension.upper_mean),
        ))
        base_widths.append(
            float(base["confidence_upper"]) - float(base["confidence_lower"])
        )
        expanded_widths.append(
            extension.confidence_upper - extension.confidence_lower
        )

    base_best = _best_actions_from_row(row)
    expanded_best = _best_actions_from_result(expanded, incoming)
    if not base_best or not expanded_best:
        raise RuntimeError("dealer R3 robust-best set is empty")
    expanded_lower = {
        key: value.lower_mean for key, value in expanded_by_action.items()
    }
    expanded_optimum = max(expanded_lower.values())
    selected_best_value = max(expanded_lower[key] for key in base_best)
    selected_worst_value = min(expanded_lower[key] for key in base_best)
    # The corpus deliberately keeps set-valued targets.  Until distillation
    # defines a tie breaker, convergence must protect against *any* member of
    # the N-sample best set being chosen, not only its most convenient member.
    optimistic_regret = expanded_optimum - selected_best_value
    conservative_regret = expanded_optimum - selected_worst_value

    base_certified = row.get("certified_unique_best_action")
    expanded_certified = None
    if expanded.certified_unique_best is not None:
        expanded_certified = action_payload(
            expanded.certified_unique_best.action,
            incoming,
        )
    base_margin = float(row["hoeffding_margin"])
    expected_margin = base_margin / math.sqrt(multiplier)
    if not math.isclose(
        expanded.hoeffding_margin,
        expected_margin,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise RuntimeError("dealer R3 Hoeffding margin did not shrink as 1/sqrt(N)")

    return {
        "base_seed": int(row["base_seed"]),
        "deal_id": int(row["deal_id"]),
        "base_samples": base_samples,
        "expanded_samples": expanded_samples,
        "legal_actions": audited["legal_actions"],
        "base_informative": bool(row["informative_action_values"]),
        "expanded_informative": len({
            (value.lower_points_sum, value.upper_points_sum)
            for value in expanded.all_actions
        }) > 1,
        "best_set_exactly_stable": base_best == expanded_best,
        "best_set_overlap": bool(base_best.intersection(expanded_best)),
        "selection_regret_at_expanded_n": conservative_regret,
        "selection_regret_best_case_at_expanded_n": optimistic_regret,
        "selection_regret_worst_case_at_expanded_n": conservative_regret,
        "max_lower_or_upper_mean_drift": max(mean_drifts),
        "mean_lower_or_upper_mean_drift": statistics.fmean(mean_drifts),
        "base_max_confidence_width": max(base_widths),
        "expanded_max_confidence_width": max(expanded_widths),
        "base_hoeffding_margin": base_margin,
        "expanded_hoeffding_margin": expanded.hoeffding_margin,
        "base_certified": base_certified is not None,
        "expanded_certified": expanded_certified is not None,
        "certificate_same": (
            base_certified is not None
            and expanded_certified is not None
            and canonical(base_certified) == canonical(expanded_certified)
        ),
    }


def audit_convergence(
    source: Path,
    multiplier: int,
    max_records: int | None,
    max_selection_regret: float | None,
    max_mean_drift: float | None,
    min_best_overlap_rate: float | None,
) -> dict:
    if multiplier <= 1:
        raise ValueError("sample multiplier must be greater than one")
    selected = []
    for row in iter_rows(source):
        selected.append(row)
        if max_records is not None and len(selected) >= max_records:
            break
    if not selected:
        raise RuntimeError("convergence audit source contains no rows")
    comparisons = [compare_row(row, multiplier) for row in selected]
    regrets = [row["selection_regret_at_expanded_n"] for row in comparisons]
    drifts = [row["max_lower_or_upper_mean_drift"] for row in comparisons]
    overlap_rate = sum(row["best_set_overlap"] for row in comparisons) / len(comparisons)
    exact_rate = sum(row["best_set_exactly_stable"] for row in comparisons) / len(comparisons)
    failures: list[str] = []
    if max_selection_regret is not None and max(regrets) > max_selection_regret:
        failures.append(
            f"max selection regret {max(regrets):.6g} > {max_selection_regret:.6g}"
        )
    if max_mean_drift is not None and max(drifts) > max_mean_drift:
        failures.append(f"max mean drift {max(drifts):.6g} > {max_mean_drift:.6g}")
    if min_best_overlap_rate is not None and overlap_rate < min_best_overlap_rate:
        failures.append(
            f"best-set overlap rate {overlap_rate:.6g} < {min_best_overlap_rate:.6g}"
        )

    base_certified = sum(row["base_certified"] for row in comparisons)
    expanded_certified = sum(row["expanded_certified"] for row in comparisons)
    return {
        "schema": REPORT_VERSION,
        "status": "PASS" if not failures else "FAIL",
        "source": str(source),
        "records_compared": len(comparisons),
        "sample_multiplier": multiplier,
        "base_samples": sorted({row["base_samples"] for row in comparisons}),
        "expanded_samples": sorted({row["expanded_samples"] for row in comparisons}),
        "informative_base": sum(row["base_informative"] for row in comparisons),
        "informative_expanded": sum(
            row["expanded_informative"] for row in comparisons
        ),
        "best_set_exact_stability_rate": exact_rate,
        "best_set_overlap_rate": overlap_rate,
        "selection_regret_mean": statistics.fmean(regrets),
        "selection_regret_p95": percentile(regrets, 0.95),
        "selection_regret_max": max(regrets),
        "mean_drift_mean": statistics.fmean(drifts),
        "mean_drift_p95": percentile(drifts, 0.95),
        "mean_drift_max": max(drifts),
        "base_certified": base_certified,
        "expanded_certified": expanded_certified,
        "retained_certificates": sum(
            row["certificate_same"] for row in comparisons
        ),
        "hoeffding_margin_ratio": 1.0 / math.sqrt(multiplier),
        "thresholds": {
            "max_selection_regret": max_selection_regret,
            "max_mean_drift": max_mean_drift,
            "min_best_overlap_rate": min_best_overlap_rate,
        },
        "failures": failures,
        "comparisons": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute identical dealer-R3 information sets at N and k*N "
            "nested worlds and report policy/value convergence"
        )
    )
    parser.add_argument("source", type=Path,
                        help="certified shard manifest or JSONL corpus")
    parser.add_argument("--multiplier", type=int, default=2)
    parser.add_argument("--max-records", type=int)
    parser.add_argument("--max-selection-regret", type=float)
    parser.add_argument("--max-mean-drift", type=float)
    parser.add_argument("--min-best-overlap-rate", type=float)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.max_records is not None and args.max_records <= 0:
        raise SystemExit("max-records must be positive")
    if (
        args.min_best_overlap_rate is not None
        and not 0.0 <= args.min_best_overlap_rate <= 1.0
    ):
        raise SystemExit("min-best-overlap-rate must be between zero and one")
    report = audit_convergence(
        args.source.resolve(),
        args.multiplier,
        args.max_records,
        args.max_selection_regret,
        args.max_mean_drift,
        args.min_best_overlap_rate,
    )
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("OPENOFC_R3_CONVERGENCE=" + json.dumps(report, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
