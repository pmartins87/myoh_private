from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine import Board, parse_cards
from generate_r3_dealer_corpus import (
    BELIEF,
    CORPUS_VERSION,
    action_payload,
)
from teacher_search_r3_dealer import solve_r3_dealer_sampled_backup


def parse_board(payload: dict) -> Board:
    return Board(
        parse_cards(" ".join(payload["top"])),
        parse_cards(" ".join(payload["middle"])),
        parse_cards(" ".join(payload["bottom"])),
    )


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def audit_row(row: dict) -> dict:
    if row.get("schema") != CORPUS_VERSION:
        raise RuntimeError("dealer R3 corpus schema mismatch")
    if row.get("belief_model") != BELIEF:
        raise RuntimeError("dealer R3 belief model mismatch")
    if row.get("position") != "dealer_button_acts_second":
        raise RuntimeError("dealer R3 position mismatch")
    if row.get("round") != 3:
        raise RuntimeError("dealer R3 round mismatch")
    if row.get("hidden_world_persisted") is not False:
        raise RuntimeError("dealer R3 hidden-world leakage guard is not false")
    forbidden = {
        "opponent_hidden_discards",
        "opponent_r3_packet",
        "opponent_r4_packet",
        "dealer_r4_packet",
        "actual_hidden_worlds",
        "sampled_hidden_worlds",
    }
    leaked = forbidden.intersection(row)
    if leaked:
        raise RuntimeError(f"dealer R3 hidden information leaked: {sorted(leaked)}")

    dealer = parse_board(row["dealer_before"])
    opponent = parse_board(row["opponent_after_r3"])
    incoming = parse_cards(" ".join(row["incoming"]))
    discards = parse_cards(" ".join(row["dealer_known_discards"]))
    result = solve_r3_dealer_sampled_backup(
        dealer,
        opponent,
        incoming,
        discards,
        sample_count=int(row["sample_count"]),
        seed=int(row["world_seed"]),
        confidence_delta=float(row["confidence_delta"]),
    )
    if int(row.get("known_card_count", -1)) != 25 or result.known_count != 25:
        raise RuntimeError("dealer R3 known-card count mismatch")
    if int(row.get("unseen_count", -1)) != 29 or result.unseen_count != 29:
        raise RuntimeError("dealer R3 unseen-card count mismatch")
    if int(row.get("legal_action_count", -1)) != len(result.all_actions):
        raise RuntimeError("dealer R3 legal-action count mismatch")

    expected_values = [
        {
            "action": action_payload(value.action, tuple(incoming)),
            "samples": value.samples,
            "lower_points_sum": value.lower_points_sum,
            "upper_points_sum": value.upper_points_sum,
            "lower_mean": value.lower_mean,
            "upper_mean": value.upper_mean,
            "observed_min": value.observed_min,
            "observed_max": value.observed_max,
            "confidence_lower": value.confidence_lower,
            "confidence_upper": value.confidence_upper,
            "opponent_r4_tie_worlds": value.opponent_r4_tie_worlds,
        }
        for value in result.all_actions
    ]
    if canonical(row.get("action_values")) != canonical(expected_values):
        raise RuntimeError("dealer R3 sampled Q intervals do not recompute")
    expected_empirical = [
        action_payload(value.action, tuple(incoming))
        for value in result.empirical_robust_best
    ]
    if canonical(row.get("empirical_robust_best_actions")) != canonical(
        expected_empirical
    ):
        raise RuntimeError("dealer R3 empirical robust-best set mismatch")
    expected_certified = None
    if result.certified_unique_best is not None:
        expected_certified = action_payload(
            result.certified_unique_best.action, tuple(incoming)
        )
    if canonical(row.get("certified_unique_best_action")) != canonical(
        expected_certified
    ):
        raise RuntimeError("dealer R3 confidence certificate mismatch")

    return {
        "deal_id": int(row["deal_id"]),
        "samples": result.samples,
        "legal_actions": len(result.all_actions),
        "certified": result.certified_unique_best is not None,
        "opponent_tie_worlds": max(
            value.opponent_r4_tie_worlds for value in result.all_actions
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recompute sampled dealer/button R3 action intervals"
    )
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    seen: set[tuple[int, int]] = set()
    audited = []
    with args.corpus.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (int(row["base_seed"]), int(row["deal_id"]))
            if key in seen:
                raise RuntimeError(f"duplicate dealer R3 corpus key: {key}")
            seen.add(key)
            audited.append(audit_row(row))
    if not audited:
        raise RuntimeError("dealer R3 corpus is empty")

    report = {
        "schema": CORPUS_VERSION,
        "status": "PASS",
        "records_audited": len(audited),
        "unique_keys": len(seen),
        "samples_per_action": sorted({row["samples"] for row in audited}),
        "certified_unique_best": sum(row["certified"] for row in audited),
        "legal_action_histogram": {
            str(count): sum(
                1 for row in audited if row["legal_actions"] == count
            )
            for count in sorted({row["legal_actions"] for row in audited})
        },
        "opponent_tie_interval_exercised": any(
            row["opponent_tie_worlds"] > 0 for row in audited
        ),
    }
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("OPENOFC_R3_DEALER_AUDIT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
