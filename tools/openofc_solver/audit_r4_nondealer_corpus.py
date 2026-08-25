from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine import Board, Card, parse_cards
from generate_r4_nondealer_corpus import BELIEF, CORPUS_VERSION, action_payload
from teacher_search_nondealer import solve_r4_nondealer_uniform_belief


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
        raise RuntimeError("non-dealer row schema mismatch")
    if row.get("belief_model") != BELIEF:
        raise RuntimeError("non-dealer belief contract mismatch")
    if row.get("position") != "nondealer_acts_first":
        raise RuntimeError("non-dealer position contract mismatch")
    if row.get("information_set") != "opponent_r4_packet_hidden":
        raise RuntimeError("non-dealer information-set contract mismatch")
    if row.get("opponent_hidden_packet_persisted") is not False:
        raise RuntimeError("hidden opponent packet leakage guard is not false")
    forbidden = {
        "opponent_r4_packet",
        "actual_opponent_packet",
        "hidden_opponent_packet",
        "opponent_incoming",
    }
    leaked = forbidden.intersection(row)
    if leaked:
        raise RuntimeError(f"future-information key leaked into training row: {sorted(leaked)}")

    hero = parse_board(row["hero_before"])
    opponent = parse_board(row["opponent_before"])
    incoming = parse_cards(" ".join(row["incoming"]))
    discards = parse_cards(" ".join(row["hero_known_discards"]))
    result = solve_r4_nondealer_uniform_belief(hero, opponent, incoming, discards)

    if int(row.get("known_card_count", -1)) != 28:
        raise RuntimeError("known-card count is not 28")
    if int(row.get("unseen_count", -1)) != result.unseen_count:
        raise RuntimeError("unseen-card count mismatch")
    if int(row.get("opponent_packet_count", -1)) != result.opponent_packet_count:
        raise RuntimeError("opponent packet count mismatch")
    if result.opponent_packet_count != 2600:
        raise RuntimeError("non-dealer chance tree is not exact 26 choose 3")
    if int(row.get("best_expected_points_num")) != result.best_expected_points_num:
        raise RuntimeError("best expected-point numerator mismatch")
    if int(row.get("best_expected_points_den")) != result.best_expected_points_den:
        raise RuntimeError("best expected-point denominator mismatch")

    expected_values = []
    for value in result.all_actions:
        expected_values.append({
            "action": action_payload(value.action, tuple(incoming)),
            "expected_points_num": value.expected_points_num,
            "expected_points_den": value.expected_points_den,
            "packet_min_points": value.packet_min_points,
            "packet_max_points": value.packet_max_points,
            "fantasy_cards": value.fantasy_cards,
            "foul": value.foul,
        })
    if canonical(row.get("action_values")) != canonical(expected_values):
        raise RuntimeError("stored non-dealer Q vector does not match independent recomputation")

    expected_optimal = [
        action_payload(value.action, tuple(incoming))
        for value in result.optimal_actions
    ]
    if {canonical(x) for x in row.get("point_optimal_actions", [])} != {
        canonical(x) for x in expected_optimal
    }:
        raise RuntimeError("stored non-dealer optimal action set mismatch")
    if int(row.get("legal_action_count", -1)) != len(result.all_actions):
        raise RuntimeError("non-dealer legal action count mismatch")
    if bool(row.get("all_hero_actions_foul")) != all(v.foul for v in result.all_actions):
        raise RuntimeError("all-Hero-actions-foul flag mismatch")

    return {
        "deal_id": int(row["deal_id"]),
        "legal_actions": len(result.all_actions),
        "optimal_actions": len(result.optimal_actions),
        "best_expected_points_num": result.best_expected_points_num,
        "best_expected_points_den": result.best_expected_points_den,
        "unseen_count": result.unseen_count,
        "opponent_packet_count": result.opponent_packet_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Independently recompute non-dealer R4 information-set labels"
    )
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    seen: set[tuple[int, int]] = set()
    rows = []
    with args.corpus.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            raw = json.loads(line)
            key = (int(raw["base_seed"]), int(raw["deal_id"]))
            if key in seen:
                raise RuntimeError(f"duplicate corpus key: {key}")
            seen.add(key)
            rows.append(audit_row(raw))
    if not rows:
        raise RuntimeError("non-dealer corpus is empty")

    report = {
        "schema": CORPUS_VERSION,
        "status": "PASS",
        "records_audited": len(rows),
        "unique_keys": len(seen),
        "all_packets_exact_2600": all(x["opponent_packet_count"] == 2600 for x in rows),
        "legal_action_histogram": {
            str(n): sum(1 for x in rows if x["legal_actions"] == n)
            for n in sorted({x["legal_actions"] for x in rows})
        },
        "point_tie_states": sum(1 for x in rows if x["optimal_actions"] > 1),
        "best_expected_points_num_min": min(x["best_expected_points_num"] for x in rows),
        "best_expected_points_num_max": max(x["best_expected_points_num"] for x in rows),
        "common_denominator": 2600,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("OPENOFC_R4_NONDEALER_AUDIT=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
