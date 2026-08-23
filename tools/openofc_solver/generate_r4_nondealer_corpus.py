from __future__ import annotations

import argparse
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterable

from engine import Action, Board, Card, apply_action, full_deck, legal_actions
from teacher_search_nondealer import solve_r4_nondealer_uniform_belief

ROW_NAMES = ("top", "middle", "bottom")
CORPUS_VERSION = "openofc-r4-nondealer-uniform-belief-v1"
SAMPLER = "UNIFORM_LEGAL_REACHABILITY_ONLY_NOT_TEACHER"
BELIEF = "UNIFORM_3CARD_SUBSET_OF_26_UNSEEN_EXACT_UNDER_UNIFORM_LEGAL_REACHABILITY_V1"


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


def _draw(deck: list[Card], cursor: int, n: int) -> tuple[tuple[Card, ...], int]:
    end = cursor + n
    if end > len(deck):
        raise RuntimeError("deck exhausted")
    return tuple(deck[cursor:end]), end


def generate_nondealer_r4_state(base_seed: int, deal_id: int) -> dict:
    """Generate one reachable non-dealer R4 information set and exact Q vector.

    The hidden opponent R4 packet is deliberately never drawn into or persisted
    in the training record. The teacher integrates over all 2,600 packets that
    are compatible with Hero's information. Earlier rounds use uniform legal
    actions only to create reachable states; those actions are not demonstrations.
    """
    seed = _deal_seed(base_seed, deal_id)
    rng = random.Random(seed)
    deck = list(full_deck(2))
    rng.shuffle(deck)
    cursor = 0

    # Hero is the non-dealer and acts first in every round. Opponent/dealer acts
    # second. Only Hero's own past discards are private information Hero knows.
    hero = Board()
    opponent = Board()
    hero_discards: list[Card] = []

    hero_in, cursor = _draw(deck, cursor, 5)
    opp_in, cursor = _draw(deck, cursor, 5)
    hero = apply_action(hero, hero_in, _choose_uniform(hero, hero_in, 0, rng))
    opponent = apply_action(opponent, opp_in, _choose_uniform(opponent, opp_in, 0, rng))

    for round_index in range(1, 4):
        hero_in, cursor = _draw(deck, cursor, 3)
        opp_in, cursor = _draw(deck, cursor, 3)

        hero_action = _choose_uniform(hero, hero_in, round_index, rng)
        if hero_action.discard_index is None:
            raise AssertionError("later-round Hero action unexpectedly has no discard")
        hero_discards.append(hero_in[hero_action.discard_index])
        hero = apply_action(hero, hero_in, hero_action)

        opp_action = _choose_uniform(opponent, opp_in, round_index, rng)
        opponent = apply_action(opponent, opp_in, opp_action)

    if hero.count() != 11 or opponent.count() != 11 or len(hero_discards) != 3:
        raise AssertionError("R3 non-dealer reachability invariant failed")

    # R4 Hero packet is known. The next three physical cards would be the
    # opponent packet in this particular shuffled world, but reading/storing
    # them here would create a future-information leakage hazard. Stop drawing.
    hero_r4, cursor = _draw(deck, cursor, 3)
    hero_before = canonical_board(hero)
    opponent_before = canonical_board(opponent)
    incoming = tuple(sorted(hero_r4))
    known_discards = tuple(sorted(hero_discards))

    result = solve_r4_nondealer_uniform_belief(
        hero_before,
        opponent_before,
        incoming,
        known_discards,
    )

    action_values = [
        {
            "action": action_payload(value.action, incoming),
            "expected_points_num": value.expected_points_num,
            "expected_points_den": value.expected_points_den,
            "packet_min_points": value.packet_min_points,
            "packet_max_points": value.packet_max_points,
            "fantasy_cards": value.fantasy_cards,
            "foul": value.foul,
        }
        for value in result.all_actions
    ]
    optimal = [action_payload(value.action, incoming) for value in result.optimal_actions]

    known_cards = (
        hero_before.top + hero_before.middle + hero_before.bottom
        + opponent_before.top + opponent_before.middle + opponent_before.bottom
        + incoming + known_discards
    )
    known_jokers = sum(1 for c in known_cards if c.joker)

    return {
        "schema": CORPUS_VERSION,
        "base_seed": base_seed,
        "deal_id": deal_id,
        "deal_seed": seed,
        "position": "nondealer_acts_first",
        "round": 4,
        "information_set": "opponent_r4_packet_hidden",
        "reachability_sampler": SAMPLER,
        "belief_model": BELIEF,
        "hero_before": board_payload(hero_before),
        "opponent_before": board_payload(opponent_before),
        "incoming": card_list(incoming),
        "hero_known_discards": card_list(known_discards),
        "known_card_count": 28,
        "unseen_count": result.unseen_count,
        "unseen_joker_count": 2 - known_jokers,
        "opponent_packet_count": result.opponent_packet_count,
        "best_expected_points_num": result.best_expected_points_num,
        "best_expected_points_den": result.best_expected_points_den,
        "point_optimal_actions": optimal,
        "action_values": action_values,
        "legal_action_count": len(result.all_actions),
        "all_hero_actions_foul": all(value.foul for value in result.all_actions),
        "opponent_hidden_packet_persisted": False,
        "training_note": (
            "Exact current-hand expectimax under the explicit uniform-unseen "
            "belief induced by the M2 uniform-legal reachability sampler. The "
            "actual opponent R4 packet is never used as a label input. Fantasy "
            "continuation EV is metadata only and strategic self-play must later "
            "replace this reachability belief."
        ),
    }


def _worker(args: tuple[int, int]) -> dict:
    return generate_nondealer_r4_state(*args)


def generate_corpus(
    base_seed: int,
    start_deal: int,
    attempts: int,
    workers: int,
) -> list[dict]:
    ids = range(start_deal, start_deal + attempts)
    args = ((base_seed, i) for i in ids)
    executor = None
    if workers <= 1:
        rows = map(_worker, args)
    else:
        executor = ProcessPoolExecutor(max_workers=workers)
        rows = executor.map(_worker, args, chunksize=1)
    out: list[dict] = []
    try:
        out.extend(rows)
    finally:
        if executor is not None:
            executor.shutdown(wait=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate exact-current-hand non-dealer R4 information-set teachers"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260823)
    parser.add_argument("--start-deal", type=int, default=0)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--workers", type=int, default=max(1, min(4, (os.cpu_count() or 2) - 1)))
    args = parser.parse_args()
    if args.attempts <= 0 or args.workers <= 0:
        raise SystemExit("attempts/workers must be positive")

    rows = generate_corpus(args.seed, args.start_deal, args.attempts, args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    stats = {
        "schema": CORPUS_VERSION,
        "belief_model": BELIEF,
        "seed": args.seed,
        "start_deal": args.start_deal,
        "attempts": args.attempts,
        "emitted": len(rows),
        "workers": args.workers,
        "all_hero_actions_foul": sum(1 for row in rows if row["all_hero_actions_foul"]),
        "point_tie_states": sum(1 for row in rows if len(row["point_optimal_actions"]) > 1),
    }
    print("OPENOFC_R4_NONDEALER_CORPUS=" + json.dumps(stats, sort_keys=True))


if __name__ == "__main__":
    main()
