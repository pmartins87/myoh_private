from __future__ import annotations

import argparse
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable

from engine import Action, Board, Card, apply_action, full_deck, legal_actions, resolve_board
from teacher_search_r3_dealer import BELIEF, solve_r3_dealer_sampled_backup


ROW_NAMES = ("top", "middle", "bottom")
CORPUS_VERSION = "openofc-r3-dealer-sampled-backup-v1"
SAMPLER = "UNIFORM_LEGAL_REACHABILITY_ONLY_NOT_TEACHER"


def canonical_board(board: Board) -> Board:
    return Board(
        tuple(sorted(board.top)),
        tuple(sorted(board.middle)),
        tuple(sorted(board.bottom)),
    )


def card_list(cards: Iterable[Card]) -> list[str]:
    return [str(card) for card in cards]


def board_payload(board: Board) -> dict[str, list[str]]:
    board = canonical_board(board)
    return {
        "top": card_list(board.top),
        "middle": card_list(board.middle),
        "bottom": card_list(board.bottom),
    }


def action_payload(action: Action, incoming: tuple[Card, ...]) -> dict:
    return {
        "placements": [
            {
                "incoming_index": index,
                "card": str(incoming[index]),
                "row": ROW_NAMES[row],
            }
            for index, row in action.placements
        ],
        "discard": None if action.discard_index is None else {
            "incoming_index": action.discard_index,
            "card": str(incoming[action.discard_index]),
        },
    }


def _choose_uniform(
    board: Board,
    incoming: tuple[Card, ...],
    round_index: int,
    rng: random.Random,
) -> Action:
    actions = legal_actions(board, incoming, round_index)
    if not actions:
        raise RuntimeError("reachable state has no legal action")
    return actions[rng.randrange(len(actions))]


def _deal_seed(base_seed: int, deal_id: int) -> int:
    x = (base_seed & ((1 << 64) - 1)) ^ (
        (deal_id + 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
    )
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & ((1 << 64) - 1)
    x ^= x >> 31
    return x


def _world_seed(base_seed: int, deal_id: int) -> int:
    return _deal_seed(base_seed ^ 0xD3A1E4B7C925680F, deal_id)


def _draw(
    deck: list[Card], cursor: int, count: int
) -> tuple[tuple[Card, ...], int]:
    end = cursor + count
    if end > len(deck):
        raise RuntimeError("deck exhausted")
    return tuple(deck[cursor:end]), end


def _require_m1b_materialized() -> None:
    if "row-local semantics" not in (resolve_board.__doc__ or ""):
        raise RuntimeError(
            "M1b Joker semantics are not materialized. Run "
            "`python tools/openofc_solver/apply_m1b_joker_semantics.py` first."
        )


def generate_dealer_r3_state(
    base_seed: int,
    deal_id: int,
    sample_count: int,
    confidence_delta: float,
) -> dict:
    """Generate one dealer/button R3 information set and sampled R4 backup.

    The particular shuffled-world opponent discards and R4 packets are never
    supplied to the label.  Once the 25-card legal information set is frozen,
    the teacher draws fresh uniform hidden worlds from that information set.
    """
    _require_m1b_materialized()
    seed = _deal_seed(base_seed, deal_id)
    rng = random.Random(seed)
    deck = list(full_deck(2))
    rng.shuffle(deck)
    cursor = 0

    nondealer = Board()
    dealer = Board()
    dealer_discards: list[Card] = []

    nondealer_in, cursor = _draw(deck, cursor, 5)
    dealer_in, cursor = _draw(deck, cursor, 5)
    nondealer = apply_action(
        nondealer,
        nondealer_in,
        _choose_uniform(nondealer, nondealer_in, 0, rng),
    )
    dealer = apply_action(
        dealer,
        dealer_in,
        _choose_uniform(dealer, dealer_in, 0, rng),
    )

    # R1-R2 are used only for card-blind reachability.  Hero/dealer remembers
    # only their own two discards, exactly as in live play.
    for round_index in (1, 2):
        nondealer_in, cursor = _draw(deck, cursor, 3)
        dealer_in, cursor = _draw(deck, cursor, 3)
        nondealer_action = _choose_uniform(
            nondealer, nondealer_in, round_index, rng
        )
        dealer_action = _choose_uniform(dealer, dealer_in, round_index, rng)
        if dealer_action.discard_index is None:
            raise AssertionError("dealer later-round action has no discard")
        dealer_discards.append(dealer_in[dealer_action.discard_index])
        nondealer = apply_action(nondealer, nondealer_in, nondealer_action)
        dealer = apply_action(dealer, dealer_in, dealer_action)

    if nondealer.count() != 9 or dealer.count() != 9:
        raise AssertionError("dealer R3 pre-round reachability invariant failed")

    # On R3 the non-dealer acts first and their 11-card board becomes public.
    # Their packet and discarded identity are deliberately discarded from the
    # generator state after the public board has been produced.
    nondealer_r3, cursor = _draw(deck, cursor, 3)
    dealer_r3, cursor = _draw(deck, cursor, 3)
    nondealer = apply_action(
        nondealer,
        nondealer_r3,
        _choose_uniform(nondealer, nondealer_r3, 3, rng),
    )

    dealer_before = canonical_board(dealer)
    opponent_after = canonical_board(nondealer)
    incoming = tuple(sorted(dealer_r3))
    known_discards = tuple(sorted(dealer_discards))
    worlds_seed = _world_seed(base_seed, deal_id)
    result = solve_r3_dealer_sampled_backup(
        dealer_before,
        opponent_after,
        incoming,
        known_discards,
        sample_count=sample_count,
        seed=worlds_seed,
        confidence_delta=confidence_delta,
    )

    action_values = [
        {
            "action": action_payload(value.action, incoming),
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
    empirical = [
        action_payload(value.action, incoming)
        for value in result.empirical_robust_best
    ]
    certified = None
    if result.certified_unique_best is not None:
        certified = action_payload(result.certified_unique_best.action, incoming)

    known = (
        dealer_before.top + dealer_before.middle + dealer_before.bottom
        + opponent_after.top + opponent_after.middle + opponent_after.bottom
        + incoming + known_discards
    )
    return {
        "schema": CORPUS_VERSION,
        "base_seed": base_seed,
        "deal_id": deal_id,
        "deal_seed": seed,
        "world_seed": worlds_seed,
        "position": "dealer_button_acts_second",
        "round": 3,
        "information_set": "opponent_r3_public_hidden_history_and_r4_chance",
        "reachability_sampler": SAMPLER,
        "belief_model": BELIEF,
        "dealer_before": board_payload(dealer_before),
        "opponent_after_r3": board_payload(opponent_after),
        "incoming": card_list(incoming),
        "dealer_known_discards": card_list(known_discards),
        "known_card_count": result.known_count,
        "unseen_count": result.unseen_count,
        "sample_count": result.samples,
        "confidence_delta": result.confidence_delta,
        "hoeffding_margin": result.hoeffding_margin,
        "action_values": action_values,
        "legal_action_count": len(result.all_actions),
        "empirical_robust_best_actions": empirical,
        "certified_unique_best_action": certified,
        "certified_unique_best": certified is not None,
        "contains_known_joker": any(card.joker for card in known),
        "hidden_world_persisted": False,
        "teacher_authority": (
            "SAMPLED_R3_BACKUP_WITH_EXACT_R4_LEAVES_AND_CONSERVATIVE_"
            "OPPONENT_TIE_INTERVAL"
        ),
        "training_note": (
            "The Q interval uses common random hidden worlds and both R4 "
            "teachers. It is not promoted to an exact class unless one action "
            "strictly separates under the simultaneous Hoeffding bounds. "
            "Fantasy continuation remains metadata outside current-hand points."
        ),
    }


def _worker(args: tuple[int, int, int, float]) -> dict:
    return generate_dealer_r3_state(*args)


def generate_corpus(
    base_seed: int,
    start_deal: int,
    attempts: int,
    workers: int,
    sample_count: int,
    confidence_delta: float,
) -> list[dict]:
    if attempts <= 0 or workers <= 0 or sample_count <= 0:
        raise ValueError("attempts, workers and sample_count must be positive")
    args = (
        (base_seed, deal_id, sample_count, confidence_delta)
        for deal_id in range(start_deal, start_deal + attempts)
    )
    executor = None
    if workers <= 1:
        rows = map(_worker, args)
    else:
        executor = ProcessPoolExecutor(max_workers=workers)
        rows = executor.map(_worker, args, chunksize=1)
    try:
        return list(rows)
    finally:
        if executor is not None:
            executor.shutdown(wait=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate sampled dealer/button R3 backups through exact R4 leaves"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--start-deal", type=int, default=0)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--confidence-delta", type=float, default=0.01)
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, (os.cpu_count() or 2) - 1)),
    )
    args = parser.parse_args()

    rows = generate_corpus(
        args.seed,
        args.start_deal,
        args.attempts,
        args.workers,
        args.samples,
        args.confidence_delta,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    stats = {
        "schema": CORPUS_VERSION,
        "belief_model": BELIEF,
        "seed": args.seed,
        "start_deal": args.start_deal,
        "attempts": args.attempts,
        "emitted": len(rows),
        "samples_per_action": args.samples,
        "workers": args.workers,
        "certified_unique_best": sum(
            1 for row in rows if row["certified_unique_best"]
        ),
    }
    print("OPENOFC_R3_DEALER_CORPUS=" + json.dumps(stats, sort_keys=True))


if __name__ == "__main__":
    main()
