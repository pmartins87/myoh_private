from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from engine import Board, parse_cards
from generate_r4_dealer_corpus import (
    CORPUS_VERSION,
    action_payload,
    canonical_board,
)
from teacher_search import solve_r4_exact

FORBIDDEN_TOP_LEVEL = {
    "opponent_incoming",
    "opponent_discard",
    "deck",
    "undealt",
    "hidden_cards",
}


def parse_board(payload: dict) -> Board:
    return canonical_board(Board(
        parse_cards(" ".join(payload["top"])),
        parse_cards(" ".join(payload["middle"])),
        parse_cards(" ".join(payload["bottom"])),
    ))


def audit_row(row: dict) -> None:
    if row.get("schema") != CORPUS_VERSION:
        raise AssertionError(f"unexpected schema: {row.get('schema')!r}")
    leaked = FORBIDDEN_TOP_LEVEL.intersection(row)
    if leaked:
        raise AssertionError(f"hidden-information fields leaked into corpus: {sorted(leaked)}")
    if row.get("position") != "dealer_button_acts_second":
        raise AssertionError("corpus row is not dealer/button R4")
    if row.get("information_set") != "opponent_r4_final_public":
        raise AssertionError("incorrect information-set tag")

    hero = parse_board(row["hero_before"])
    opponent = parse_board(row["opponent_final"])
    incoming = tuple(sorted(parse_cards(" ".join(row["incoming"]))))
    if hero.count() != 11 or opponent.count() != 13 or len(incoming) != 3:
        raise AssertionError("R4 cardinality invariant failed")

    exact = solve_r4_exact(hero, opponent, incoming)
    expected_values = [
        {
            "action": action_payload(v.action, incoming),
            "points": v.points,
            "fantasy_cards": v.fantasy_cards,
            "foul": v.foul,
        }
        for v in exact.all_actions
    ]
    expected_optimal = [action_payload(v.action, incoming) for v in exact.optimal_actions]
    if row["best_current_hand_points"] != exact.best_points:
        raise AssertionError("stored best-points label differs from exact oracle")
    if row["action_values"] != expected_values:
        raise AssertionError("stored action-value vector differs from exact oracle")
    if row["point_optimal_actions"] != expected_optimal:
        raise AssertionError("stored point-optimal action set differs from exact oracle")
    if row["legal_action_count"] != len(exact.all_actions):
        raise AssertionError("stored legal-action count differs from exact oracle")
    nonfoul = sum(1 for v in exact.all_actions if not v.foul)
    if row["nonfoul_action_count"] != nonfoul:
        raise AssertionError("stored non-foul count differs from exact oracle")
    if row["all_actions_foul"] != (nonfoul == 0):
        raise AssertionError("stored all-actions-foul flag is inconsistent")


def audit_file(path: Path, limit: int | None = None) -> dict:
    records = 0
    seen: set[tuple[int, int]] = set()
    legal_counts: Counter[int] = Counter()
    ties = 0
    jokers = 0
    all_foul = 0
    min_points = None
    max_points = None

    with path.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            key = (int(row["base_seed"]), int(row["deal_id"]))
            if key in seen:
                raise AssertionError(f"duplicate state key at line {line_number}: {key}")
            seen.add(key)
            audit_row(row)
            records += 1
            legal_counts[int(row["legal_action_count"])] += 1
            ties += int(len(row["point_optimal_actions"]) > 1)
            jokers += int(bool(row["contains_joker"]))
            all_foul += int(bool(row["all_actions_foul"]))
            points = int(row["best_current_hand_points"])
            min_points = points if min_points is None else min(min_points, points)
            max_points = points if max_points is None else max(max_points, points)
            if limit is not None and records >= limit:
                break

    if records == 0:
        raise AssertionError("empty corpus")
    return {
        "schema": CORPUS_VERSION,
        "records_audited": records,
        "unique_keys": len(seen),
        "joker_states": jokers,
        "point_tie_states": ties,
        "all_actions_foul": all_foul,
        "legal_action_histogram": dict(sorted(legal_counts.items())),
        "best_points_min": min_points,
        "best_points_max": max_points,
        "status": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute and audit exact dealer R4 corpus labels")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = audit_file(args.corpus, args.limit)
    print("OPENOFC_R4_DEALER_AUDIT=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
