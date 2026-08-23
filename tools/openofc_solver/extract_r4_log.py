from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine import Board, card_from_runtime_value
from teacher_search import solve_r4_exact

PREFIX = "[DeepOFC SNAPSHOT v1] "


def board_from_player(p: dict) -> Board:
    return Board(
        tuple(card_from_runtime_value(v) for v in p["top"]),
        tuple(card_from_runtime_value(v) for v in p["middle"]),
        tuple(card_from_runtime_value(v) for v in p["bottom"]),
    )


def action_json(v):
    return {
        "placements": [[idx, row] for idx, row in v.action.placements],
        "discard_index": v.action.discard_index,
        "points": v.points,
        "fantasy_cards": v.fantasy_cards,
        "foul": v.foul,
    }


def extract(path: Path) -> list[dict]:
    out = []
    seen = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if PREFIX not in line:
            continue
        raw = line.split(PREFIX, 1)[1]
        try:
            s = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not s.get("valid") or s.get("player_count") != 2 or s.get("round_index") != 4:
            continue
        hero = int(s["hero_chair"])
        opp = 1 - hero
        incoming_values = tuple(s.get("hero_incoming", []))
        if len(incoming_values) != 3 or any(not (0 <= int(v) <= 53) for v in incoming_values):
            continue
        hb = board_from_player(s["players"][hero])
        ob = board_from_player(s["players"][opp])
        if hb.count() != 11 or not ob.complete():
            continue
        signature = (
            tuple(sorted(map(str, hb.top))),
            tuple(sorted(map(str, hb.middle))),
            tuple(sorted(map(str, hb.bottom))),
            tuple(sorted(map(str, ob.top))),
            tuple(sorted(map(str, ob.middle))),
            tuple(sorted(map(str, ob.bottom))),
            incoming_values,
        )
        if signature in seen:
            continue
        seen.add(signature)
        incoming = tuple(card_from_runtime_value(int(v)) for v in incoming_values)
        result = solve_r4_exact(hb, ob, incoming)
        out.append({
            "source": str(path),
            "runtime_incoming": list(incoming_values),
            "incoming": [str(c) for c in incoming],
            "hero": {
                "top": [str(c) for c in hb.top],
                "middle": [str(c) for c in hb.middle],
                "bottom": [str(c) for c in hb.bottom],
            },
            "opponent": {
                "top": [str(c) for c in ob.top],
                "middle": [str(c) for c in ob.middle],
                "bottom": [str(c) for c in ob.bottom],
            },
            "best_points": result.best_points,
            "optimal_actions": [action_json(v) for v in result.optimal_actions],
            "n_legal_actions": len(result.all_actions),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    rows = extract(args.log)
    text = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)
    if text:
        text += "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(f"OPENOFC_R4_EXACT_LABELS={len(rows)}")
    if rows:
        print(json.dumps(rows[0], ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
