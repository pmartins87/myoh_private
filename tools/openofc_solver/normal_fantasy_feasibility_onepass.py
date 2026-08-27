from __future__ import annotations

"""M4H throughput probe for the exact one-pass Fantasy frontier."""

import argparse
import json
import time
from pathlib import Path

from fantasy_frontier_cache_onepass import OnePassExactFantasyFrontierCache
from fantasy_response_frontier import mask_pair_count
from normal_fantasy_feasibility import parse_counts, terminal_state

SCHEMA = "openofc-m4h-onepass-frontier-feasibility-v1"


def run_probe(counts: tuple[int, ...], *, samples: int, base_seed: int) -> dict:
    if samples <= 0:
        raise ValueError("samples must be positive")
    if not counts or any(count not in (14, 15, 16, 17) for count in counts):
        raise ValueError("counts must be a non-empty subset of 14,15,16,17")
    rows = []
    cache = OnePassExactFantasyFrontierCache()
    for count in counts:
        misses = []
        hits = []
        for sample in range(samples):
            seed = int(base_seed) + count * 1000003 + sample * 104729
            state = terminal_state(seed, count)
            before = cache.misses
            start = time.perf_counter()
            record = cache.get_or_build(state.plan.fantasy_packet, state.normal_board)
            miss_elapsed = time.perf_counter() - start
            if cache.misses != before + 1:
                raise AssertionError("random M4H world unexpectedly reused exact frontier")
            if record.incoming_count != count:
                raise AssertionError("one-pass record count mismatch")
            misses.append(miss_elapsed)

            start = time.perf_counter()
            same = cache.get_or_build(state.plan.fantasy_packet, state.normal_board)
            hit_elapsed = time.perf_counter() - start
            if same != record:
                raise AssertionError("one-pass cache hit changed exact record")
            hits.append(hit_elapsed)

        onepass_pairs = mask_pair_count(count)
        mean_miss = sum(misses) / len(misses)
        rows.append({
            "fantasy_count": count,
            "samples": samples,
            "mask_pairs_single_bottom_middle_traversal": onepass_pairs,
            "mean_exact_miss_seconds": mean_miss,
            "min_exact_miss_seconds": min(misses),
            "max_exact_miss_seconds": max(misses),
            "mean_exact_frontiers_per_second": 1.0 / mean_miss,
            "mean_mask_pairs_per_second": onepass_pairs / mean_miss,
            "mean_cache_hit_seconds": sum(hits) / len(hits),
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
            "Exact one-pass engineering throughput only. Compare F14 against the "
            "M4G two-pass baseline and use F14..F17 costs to choose the terminal "
            "teacher/runtime architecture."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenOFC M4H one-pass frontier probe")
    parser.add_argument("--counts", default="14,15,16,17")
    parser.add_argument("--samples", type=int, default=1)
    parser.add_argument("--base-seed", type=int, default=20260826)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_probe(parse_counts(args.counts), samples=args.samples, base_seed=args.base_seed)
    raw = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw, end="")


if __name__ == "__main__":
    main()
