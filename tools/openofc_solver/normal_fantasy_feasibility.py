from __future__ import annotations

"""Measure whether exact delayed-Fantasy frontier misses are training-feasible.

The probe deliberately separates exact cache misses from exact suit-isomorphic
hits. Random complete worlds are expected to have little natural key reuse; the
question is therefore empirical: how many exact frontiers per second can the
current implementation build for F14..F17, and is that enough for a strategic
trainer before we invest Ryzen time?
"""

import argparse
import json
import random
import time
from pathlib import Path

from fantasy_frontier_cache import ExactFantasyFrontierCache
from fantasy_response_frontier import mask_pair_count
from hu_continuation import HUContinuationState
from normal_fantasy_kernel import (
    NormalFantasyState,
    child_normal_state,
    legal_normal_actions,
    sample_normal_fantasy_plan,
)

SCHEMA = "openofc-m4g-normal-fantasy-feasibility-v1"


def terminal_state(seed: int, fantasy_count: int) -> NormalFantasyState:
    # Alternate persistent identity/button to ensure the probe does not quietly
    # benchmark only one metadata orientation. Exact frontier build cost is
    # identity-independent, but the hand kernel itself is not allowed to assume so.
    fantasy_player = seed & 1
    button = (seed >> 1) & 1
    meta = HUContinuationState(
        button=button,
        p0_fantasy_cards=fantasy_count if fantasy_player == 0 else 0,
        p1_fantasy_cards=fantasy_count if fantasy_player == 1 else 0,
    )
    deal_rng = random.Random(seed)
    action_rng = random.Random(seed ^ 0xD1B54A32D192ED03)
    state = NormalFantasyState(
        current_meta=meta,
        plan=sample_normal_fantasy_plan(deal_rng, fantasy_count),
    )
    while not state.terminal():
        actions = legal_normal_actions(state)
        state = child_normal_state(state, actions[action_rng.randrange(len(actions))])
    return state


def run_probe(counts: tuple[int, ...], *, samples: int, base_seed: int) -> dict:
    if samples <= 0:
        raise ValueError("samples must be positive")
    if not counts or any(count not in (14, 15, 16, 17) for count in counts):
        raise ValueError("counts must be a non-empty subset of 14,15,16,17")
    rows = []
    cache = ExactFantasyFrontierCache()
    for count in counts:
        timings = []
        hit_timings = []
        for sample in range(samples):
            seed = int(base_seed) + count * 1000003 + sample * 104729
            state = terminal_state(seed, count)
            packet = state.plan.fantasy_packet
            board = state.normal_board
            before_misses = cache.misses
            start = time.perf_counter()
            _record = cache.get_or_build(packet, board)
            elapsed = time.perf_counter() - start
            if cache.misses != before_misses + 1:
                raise AssertionError("random feasibility world unexpectedly reused exact frontier")
            timings.append(elapsed)

            start_hit = time.perf_counter()
            _same = cache.get_or_build(packet, board)
            hit_timings.append(time.perf_counter() - start_hit)
        pair_count = mask_pair_count(count)
        # M4D performs two constrained exact searches per frontier.
        searched_pairs = 2 * pair_count
        mean_seconds = sum(timings) / len(timings)
        rows.append({
            "fantasy_count": count,
            "samples": samples,
            "mask_pairs_per_constrained_search": pair_count,
            "mask_pairs_per_frontier": searched_pairs,
            "mean_exact_miss_seconds": mean_seconds,
            "min_exact_miss_seconds": min(timings),
            "max_exact_miss_seconds": max(timings),
            "mean_exact_frontiers_per_second": 1.0 / mean_seconds,
            "mean_mask_pairs_per_second": searched_pairs / mean_seconds,
            "mean_cache_hit_seconds": sum(hit_timings) / len(hit_timings),
        })
    return {
        "schema": SCHEMA,
        "base_seed": int(base_seed),
        "counts": list(counts),
        "samples_per_count": samples,
        "rows": rows,
        "cache": {
            "records": len(cache.records),
            "misses": cache.misses,
            "hits": cache.hits,
        },
        "interpretation": (
            "Engineering throughput probe only. No strategic quality or "
            "exploitability claim. Use results to choose exact/C++/distilled "
            "terminal frontier path before large training."
        ),
    }


def parse_counts(text: str) -> tuple[int, ...]:
    result = tuple(int(item.strip()) for item in text.split(",") if item.strip())
    if len(set(result)) != len(result):
        raise ValueError("duplicate Fantasy count")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenOFC M4G asymmetric terminal feasibility probe")
    parser.add_argument("--counts", default="14")
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--base-seed", type=int, default=20260826)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_probe(
        parse_counts(args.counts), samples=args.samples, base_seed=args.base_seed
    )
    raw = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw, end="")


if __name__ == "__main__":
    main()
