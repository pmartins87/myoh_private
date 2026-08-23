from __future__ import annotations

import argparse
import json
import random
import subprocess
from dataclasses import asdict
from pathlib import Path

from engine import (
    Board,
    Card,
    RANKS,
    SUITS,
    _eval_regular,
    card_from_runtime_value,
    fantasy_award_from_top,
    resolve_board,
    royalty,
)

CPP_SUIT_TO_CHAR = "hdcs"
CHAR_TO_CPP_SUIT = {c: i for i, c in enumerate(CPP_SUIT_TO_CHAR)}


def runtime_value(text: str) -> int:
    t = text.strip()
    if t.upper() in {"JK", "JK1", "X"}:
        return 52
    if t.upper() in {"JK2", "Y"}:
        return 53
    rank = RANKS.index(t[0].upper())
    suit = CHAR_TO_CPP_SUIT[t[1].lower()]
    return suit * 13 + rank


def board_from_values(values: list[int]) -> Board:
    if len(values) != 13:
        raise ValueError("board requires 13 values")
    cards = [card_from_runtime_value(v) for v in values]
    return Board(tuple(cards[:3]), tuple(cards[3:8]), tuple(cards[8:13]))


def rank_key(rank) -> tuple[int, int, int, int, int, int, int]:
    ties = list(rank.tie) + [0] * (5 - len(rank.tie))
    return (rank.category, len(rank.tie), *ties[:5])


def parse_rank(text: str) -> tuple[int, int, int, int, int, int, int]:
    fields = tuple(int(x) for x in text.split(","))
    if len(fields) != 7:
        raise ValueError(f"invalid C++ rank payload: {text!r}")
    return fields  # category, length, tie0..tie4


def run_probe(exe: Path, commands: list[str]) -> list[str]:
    proc = subprocess.run(
        [str(exe)],
        input="\n".join(commands) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"C++ parity probe failed rc={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) != len(commands):
        raise RuntimeError(
            f"C++ parity probe response count mismatch: commands={len(commands)} lines={len(lines)}\n"
            f"stderr={proc.stderr}"
        )
    for line in lines:
        if line.startswith("ERR|"):
            raise RuntimeError(f"C++ parity probe protocol error: {line}")
    return lines


def explicit_row_vectors() -> list[tuple[int, list[int]]]:
    def rv(cards: str) -> list[int]:
        return [runtime_value(x) for x in cards.split()]

    return [
        (0, rv("Ac Kd 7s")),
        (0, rv("Qc Qd As")),
        (0, rv("7c 7d 7h")),
        (1, rv("Ac Kd Qh Js Tc")),
        (1, rv("Ah Kh Qh Jh Th")),
        (1, rv("9c 9d 9h 9s 2c")),
        (1, rv("Tc Td Th 7c 7d")),
        (1, rv("Ac Jc 9c 6c 3c")),
        (1, rv("5c 4d 3h 2s Ah")),
        (2, rv("Ah Kh Qh Jh Th")),
        (2, rv("8c 8d 8h 7c 7d")),
        (2, rv("Ac Ad 7h 7s 2c")),
    ]


def check_nonjoker(exe: Path, seed: int) -> dict:
    rng = random.Random(seed)
    commands: list[str] = []
    expectations: list[tuple[str, object]] = []

    # Full 0..53 mapping. This is the regression that catches the historical
    # rank-major standalone shim: production OpenHoldem is suit*13 + rank.
    for value in range(54):
        commands.append(f"MAP {value}")
        if value < 52:
            expectations.append(("MAP", (value % 13 + 2, value // 13, 0)))
        else:
            expectations.append(("MAP", (0, -1, value - 51)))

    rows = explicit_row_vectors()
    for _ in range(512):
        rows.append((0, rng.sample(range(52), 3)))
    for row in (1, 2):
        for _ in range(768):
            rows.append((row, rng.sample(range(52), 5)))

    for row, values in rows:
        commands.append("ROW %d %d %s" % (row, len(values), " ".join(map(str, values))))
        cards = [card_from_runtime_value(v) for v in values]
        rank = _eval_regular(cards)
        expectations.append(("ROW", (rank_key(rank), royalty(rank, row))))

    boards: list[list[int]] = []
    for _ in range(1536):
        boards.append(rng.sample(range(52), 13))
    # Explicit valid/foul/royalty-sensitive boards.
    for text in (
        "Qc Qd 2h 2c 3c 4c 5c 6c 9h Th Jh Qh Kh",
        "Ac Ad 2h Kc Kd 9h 7s 3c 2c 3d 4h 5s 6c",
        "6c 6d Ah 2c 3d 4h 5s 6c 7c 8c 9c Tc Jc",
    ):
        boards.append([runtime_value(x) for x in text.split()])

    for values in boards:
        commands.append("BOARD " + " ".join(map(str, values)))
        resolved = resolve_board(board_from_values(values))
        expectations.append(("BOARD", resolved))

    outputs = run_probe(exe, commands)
    failures: list[dict] = []
    checked = {"map": 0, "row": 0, "board": 0}

    for index, (line, expected) in enumerate(zip(outputs, expectations)):
        parts = line.split("|")
        kind = parts[0]
        if kind == "MAP":
            checked["map"] += 1
            got = (int(parts[2]), int(parts[3]), int(parts[4]))
            if got != expected:
                failures.append({"index": index, "kind": kind, "got": got, "expected": expected})
            value = int(parts[1])
            # Also assert the pure solver's human label is consistent with the
            # production suit order h,d,c,s.
            if value < 52:
                expected_label = RANKS[value % 13] + CPP_SUIT_TO_CHAR[value // 13]
                actual_label = str(card_from_runtime_value(value))
                if actual_label != expected_label:
                    failures.append({
                        "index": index,
                        "kind": "PY_MAP",
                        "value": value,
                        "got": actual_label,
                        "expected": expected_label,
                    })
        elif kind == "ROW":
            checked["row"] += 1
            expected_rank, expected_royalty = expected
            if parts[1] != "1":
                failures.append({"index": index, "kind": kind, "got": line, "expected": "valid row"})
                continue
            got_rank = parse_rank(parts[2])
            got_royalty = int(parts[3])
            if got_rank != expected_rank or got_royalty != expected_royalty:
                failures.append({
                    "index": index,
                    "kind": kind,
                    "got_rank": got_rank,
                    "expected_rank": expected_rank,
                    "got_royalty": got_royalty,
                    "expected_royalty": expected_royalty,
                })
        elif kind == "BOARD":
            checked["board"] += 1
            if expected is None:
                if parts[1] != "0":
                    failures.append({"index": index, "kind": kind, "got": line, "expected": "foul"})
                continue
            if parts[1] != "1":
                failures.append({"index": index, "kind": kind, "got": line, "expected": "valid"})
                continue
            got_ranks = tuple(parse_rank(parts[i]) for i in (2, 3, 4))
            expected_ranks = tuple(rank_key(r) for r in expected.ranks)
            got_royalties = int(parts[5])
            got_fantasy = int(parts[6])
            if (
                got_ranks != expected_ranks
                or got_royalties != expected.royalties
                or got_fantasy != expected.fantasy_cards
            ):
                failures.append({
                    "index": index,
                    "kind": kind,
                    "got_ranks": got_ranks,
                    "expected_ranks": expected_ranks,
                    "got_royalties": got_royalties,
                    "expected_royalties": expected.royalties,
                    "got_fantasy": got_fantasy,
                    "expected_fantasy": expected.fantasy_cards,
                })
        else:
            failures.append({"index": index, "kind": "PROTOCOL", "got": line})

    if failures:
        preview = json.dumps(failures[:10], indent=2, default=str)
        raise AssertionError(
            f"non-Joker C++/Python parity failed: {len(failures)} mismatches\n{preview}"
        )

    result = {"seed": seed, "checked": checked, "status": "PASS"}
    print("NONJOKER_CPP_PARITY=PASS " + json.dumps(result, sort_keys=True))
    return result


def check_joker_diagnostic(exe: Path, seed: int, report: Path) -> dict:
    rng = random.Random(seed ^ 0x5A17)
    samples: list[list[int]] = []

    # One live-rule-shaped example: Joker completes the bottom straight.
    samples.append([
        runtime_value(x)
        for x in "Kc Jh Jc Qs Qd Ts 9h 6s 8h 7d JK1 5s 4c".split()
    ])
    # Top Joker creating trips/Fantasy.
    samples.append([
        runtime_value(x)
        for x in "Ac Ad JK1 2c 3c 4c 5c 6c 9h Th Jh Qh Kh".split()
    ])

    for _ in range(96):
        regular = rng.sample(range(52), 12)
        pos = rng.randrange(13)
        sample = regular[:]
        sample.insert(pos, 52)
        samples.append(sample)
    for _ in range(48):
        regular = rng.sample(range(52), 11)
        positions = sorted(rng.sample(range(13), 2))
        sample = regular[:]
        sample.insert(positions[0], 52)
        sample.insert(positions[1], 53)
        samples.append(sample)

    commands = ["BOARD " + " ".join(map(str, values)) for values in samples]
    outputs = run_probe(exe, commands)
    mismatches: list[dict] = []

    for values, line in zip(samples, outputs):
        parts = line.split("|")
        py = resolve_board(board_from_values(values))
        cpp_valid = len(parts) >= 2 and parts[0] == "BOARD" and parts[1] == "1"
        mismatch = False
        payload: dict = {"values": values, "cpp": line}
        if py is None:
            mismatch = cpp_valid
            payload["python"] = None
        else:
            payload["python"] = {
                "ranks": [rank_key(r) for r in py.ranks],
                "royalties": py.royalties,
                "fantasy_cards": py.fantasy_cards,
            }
            if not cpp_valid:
                mismatch = True
            else:
                cpp_ranks = tuple(parse_rank(parts[i]) for i in (2, 3, 4))
                cpp_royalties = int(parts[5])
                cpp_fantasy = int(parts[6])
                mismatch = (
                    cpp_ranks != tuple(rank_key(r) for r in py.ranks)
                    or cpp_royalties != py.royalties
                    or cpp_fantasy != py.fantasy_cards
                )
        if mismatch:
            mismatches.append(payload)

    result = {
        "seed": seed,
        "samples": len(samples),
        "mismatches": len(mismatches),
        "status": "PASS" if not mismatches else "UNRESOLVED",
        "note": (
            "A mismatch is diagnostic, not automatically a Python bug: KKPoker's exact wildcard substitution "
            "objective must decide which implementation is authoritative."
        ),
        "first_mismatches": mismatches[:20],
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(
        f"JOKER_CPP_PARITY={result['status']} samples={result['samples']} mismatches={result['mismatches']} "
        f"report={report}"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("probe", type=Path)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--joker-report", type=Path, default=Path("joker_parity_report.json"))
    parser.add_argument("--strict-jokers", action="store_true")
    args = parser.parse_args()

    check_nonjoker(args.probe, args.seed)
    joker = check_joker_diagnostic(args.probe, args.seed, args.joker_report)
    if args.strict_jokers and joker["status"] != "PASS":
        raise SystemExit("strict Joker parity requested but wildcard semantics are unresolved")


if __name__ == "__main__":
    main()
