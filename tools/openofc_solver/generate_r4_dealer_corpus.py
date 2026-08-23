from __future__ import annotations

import argparse
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from engine import Action, Board, Card, apply_action, full_deck, legal_actions, resolve_board
from teacher_search import solve_r4_exact

ROW_NAMES = ("top", "middle", "bottom")
CORPUS_VERSION = "openofc-r4-dealer-exact-v1"
SAMPLER = "UNIFORM_LEGAL_REACHABILITY_ONLY_NOT_TEACHER"


def canonical_board(board: Board) -> Board:
    return Board(
        tuple(sorted(board.top)),
        tuple(sorted(board.middle)),
        tuple(sorted(board.bottom)),
    )


def card_list(cards: Iterable[Card]) -> list[str]:
    return [str(c) for c in cards]


def board_payload(board: Board) -> dict[str, list[str]]:
    b = canonical_board(board)
    return {
        "top": card_list(b.top),
        "middle": card_list(b.middle),
        "bottom": card_list(b.bottom),
    }


def action_payload(action: Action, incoming: tuple[Card, ...]) -> dict:
    placements = [
        {
            "incoming_index": idx,
            "card": str(incoming[idx]),
            "row": ROW_NAMES[row],
        }
        for idx, row in action.placements
    ]
    discard = None if action.discard_index is None else {
        "incoming_index": action.discard_index,
        "card": str(incoming[action.discard_index]),
    }
    return {"placements": placements, "discard": discard}


def _choose_uniform(board: Board, incoming: tuple[Card, ...], round_index: int,
                    rng: random.Random) -> Action:
    actions = legal_actions(board, incoming, round_index)
    if not actions:
        raise RuntimeError("reachable state has no legal action")
    return actions[rng.randrange(len(actions))]


def _deal_seed(base_seed: int, deal_id: int) -> int:
    # SplitMix-like integer mixing. Every deal is independently reproducible,
    # so corpus shards can be generated on many workers/machines and merged.
    x = (base_seed & ((1 << 64) - 1)) ^ ((deal_id + 0x9E3779B97F4A7C15) & ((1 << 64) - 1))
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & ((1 << 64) - 1)
    x ^= x >> 31
    return x


def _draw(deck: list[Card], cursor: int, n: int) -> tuple[tuple[Card, ...], int]:
    end = cursor + n
    if end > len(deck):
        raise RuntimeError("deck exhausted")
    return tuple(deck[cursor:end]), end


def generate_dealer_r4_state(base_seed: int, deal_id: int) -> dict:
    """Generate one *reachable* HU dealer/button R4 information state.

    Earlier actions are sampled uniformly from legal actions only to cover the
    reachable state space. They are NOT teacher labels and must never be used
    as demonstrations of good strategy.

    In HU the non-dealer acts first. At R4 we let the non-dealer complete the
    round, then freeze the dealer's decision: Hero has 11 placed cards + 3
    incoming cards and can observe the opponent's complete 13-card board.
    Therefore the terminal action values are exact with no future-opponent
    information leak.
    """
    seed = _deal_seed(base_seed, deal_id)
    rng = random.Random(seed)
    deck = list(full_deck(2))
    rng.shuffle(deck)
    cursor = 0

    nondealer = Board()
    dealer = Board()

    # Round 0: five cards each, place all five.
    nd_in, cursor = _draw(deck, cursor, 5)
    d_in, cursor = _draw(deck, cursor, 5)
    nondealer = apply_action(nondealer, nd_in, _choose_uniform(nondealer, nd_in, 0, rng))
    dealer = apply_action(dealer, d_in, _choose_uniform(dealer, d_in, 0, rng))

    # Rounds 1-3: each receives three, places two, discards one.
    for round_index in range(1, 4):
        nd_in, cursor = _draw(deck, cursor, 3)
        d_in, cursor = _draw(deck, cursor, 3)
        nondealer = apply_action(
            nondealer, nd_in, _choose_uniform(nondealer, nd_in, round_index, rng)
        )
        dealer = apply_action(
            dealer, d_in, _choose_uniform(dealer, d_in, round_index, rng)
        )

    if nondealer.count() != 11 or dealer.count() != 11:
        raise AssertionError("R3 reachability invariant failed")

    # R4: opponent/non-dealer acts first and becomes fully public.
    nd_r4, cursor = _draw(deck, cursor, 3)
    d_r4, cursor = _draw(deck, cursor, 3)
    nondealer_final = apply_action(
        nondealer, nd_r4, _choose_uniform(nondealer, nd_r4, 4, rng)
    )
    dealer_before = canonical_board(dealer)
    opponent_final = canonical_board(nondealer_final)
    incoming = tuple(sorted(d_r4))

    result = solve_r4_exact(dealer_before, opponent_final, incoming)
    action_values = []
    for value in result.all_actions:
        action_values.append({
            "action": action_payload(value.action, incoming),
            "points": value.points,
            "fantasy_cards": value.fantasy_cards,
            "foul": value.foul,
        })
    point_optimal = [
        action_payload(value.action, incoming)
        for value in result.optimal_actions
    ]
    nonfoul_count = sum(1 for value in result.all_actions if not value.foul)

    return {
        "schema": CORPUS_VERSION,
        "base_seed": base_seed,
        "deal_id": deal_id,
        "deal_seed": seed,
        "position": "dealer_button_acts_second",
        "round": 4,
        "information_set": "opponent_r4_final_public",
        "reachability_sampler": SAMPLER,
        "hero_before": board_payload(dealer_before),
        "opponent_final": board_payload(opponent_final),
        "incoming": card_list(incoming),
        "best_current_hand_points": result.best_points,
        "point_optimal_actions": point_optimal,
        "action_values": action_values,
        "legal_action_count": len(result.all_actions),
        "nonfoul_action_count": nonfoul_count,
        "all_actions_foul": nonfoul_count == 0,
        "contains_joker": any(c.joker for c in (
            dealer_before.top + dealer_before.middle + dealer_before.bottom
            + opponent_final.top + opponent_final.middle + opponent_final.bottom
            + incoming
        )),
        "training_note": (
            "Exact for current-hand points only. If point-optimal actions tie, "
            "Fantasy continuation EV must break the tie later; reachability actions "
            "from rounds 0-3 are random legal sampling, not strategy labels."
        ),
    }


def _worker(args: tuple[int, int]) -> dict:
    return generate_dealer_r4_state(*args)


def generate_corpus(base_seed: int, start_deal: int, attempts: int,
                    workers: int, require_nonfoul_option: bool) -> list[dict]:
    ids = range(start_deal, start_deal + attempts)
    args = ((base_seed, i) for i in ids)
    if workers <= 1:
        rows = map(_worker, args)
    else:
        executor = ProcessPoolExecutor(max_workers=workers)
        rows = executor.map(_worker, args, chunksize=max(1, attempts // (workers * 8)))
    out: list[dict] = []
    try:
        for row in rows:
            if require_nonfoul_option and row["all_actions_foul"]:
                continue
            out.append(row)
    finally:
        if workers > 1:
            executor.shutdown(wait=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate exact dealer/button R4 OFC teacher states")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--start-deal", type=int, default=0)
    parser.add_argument("--attempts", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--include-all-foul", action="store_true")
    args = parser.parse_args()

    rows = generate_corpus(
        args.seed,
        args.start_deal,
        args.attempts,
        args.workers,
        require_nonfoul_option=not args.include_all_foul,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    stats = {
        "schema": CORPUS_VERSION,
        "seed": args.seed,
        "start_deal": args.start_deal,
        "attempts": args.attempts,
        "emitted": len(rows),
        "workers": args.workers,
        "require_nonfoul_option": not args.include_all_foul,
        "joker_states": sum(1 for row in rows if row["contains_joker"]),
    }
    print("OPENOFC_R4_DEALER_CORPUS=" + json.dumps(stats, sort_keys=True))


if __name__ == "__main__":
    main()
