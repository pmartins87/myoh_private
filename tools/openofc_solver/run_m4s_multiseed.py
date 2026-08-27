from __future__ import annotations

"""Deterministic resumable M4S multiseed runner for sealed Fantasy/Fantasy HU.

The expensive M4O proposal worlds are materialized once per episode into
SHA-bound JSON records. Training uses only the train split; independent held-out
records report the three explicit approximation budgets established by M4O-R.
The default CLI is an intentionally small F14/F14 pilot for Ryzen calibration.
"""

from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Mapping, Sequence

from engine import Board, Card
from fantasy_fantasy_kernel import (
    FantasyArrangement,
    FantasyFantasyDealPlan,
    FantasyFantasyWorld,
    validate_arrangement,
    sample_fantasy_fantasy_plan,
)
from fantasy_fantasy_payoff import (
    FantasySupportPayoffMatrix,
    build_exact_support_payoff_matrix,
    continuation_fingerprint,
)
from fantasy_fantasy_policy_model import (
    DeterministicFantasyReplay,
    SparseFantasyActionValueModel,
    save_checkpoint,
)
from fantasy_fantasy_proposals import (
    FantasyProposalSet,
    evaluate_proposal_support,
    generate_fantasy_proposals,
)
from fantasy_fantasy_selfplay import (
    SealedSupportEpisode,
    exact_selfplay_targets,
    snapshot_episode_policy,
    train_selfplay_iteration,
)
from hu_continuation import HUContinuationState, all_states, zero_continuation_values
from strategic_continuation_cfr import validate_continuation_values

SCHEMA = "openofc-m4s-multiseed-runner-v1"
EPISODE_SCHEMA = "openofc-m4s-cached-episode-v1"
REPORT_SCHEMA = "openofc-m4s-heldout-report-v1"
FANTASY_COUNTS = (14, 15, 16, 17)
AUTHORITY = "MULTISEED_MEASUREMENT_ONLY_NOT_POLICY_PROMOTION"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _state_payload(state: HUContinuationState) -> dict:
    return {
        "button": state.button,
        "p0_fantasy_cards": state.p0_fantasy_cards,
        "p1_fantasy_cards": state.p1_fantasy_cards,
    }


def _state_from_payload(payload: Mapping[str, object]) -> HUContinuationState:
    return HUContinuationState(
        button=int(payload["button"]),
        p0_fantasy_cards=int(payload["p0_fantasy_cards"]),
        p1_fantasy_cards=int(payload["p1_fantasy_cards"]),
    )


def _state_from_key(key: str) -> HUContinuationState:
    try:
        button, p0, p1 = key.split(":")
        if not button.startswith("B") or not p0.startswith("P0F") or not p1.startswith("P1F"):
            raise ValueError
        return HUContinuationState(int(button[1:]), int(p0[3:]), int(p1[3:]))
    except Exception as exc:
        raise ValueError(f"invalid continuation state key: {key!r}") from exc


def load_continuation_values(path: Path | None) -> dict[HUContinuationState, float]:
    if path is None:
        return zero_continuation_values()
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("values", payload) if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        raise ValueError("continuation file must be a state-key mapping or contain values={...}")
    values = {_state_from_key(str(key)): float(value) for key, value in raw.items()}
    return validate_continuation_values(values)


def _arrangement_payload(arrangement: FantasyArrangement) -> dict:
    return {
        "top": [str(card) for card in arrangement.board.top],
        "middle": [str(card) for card in arrangement.board.middle],
        "bottom": [str(card) for card in arrangement.board.bottom],
        "discarded": [str(card) for card in arrangement.discarded],
    }


def _arrangement_from_payload(payload: Mapping[str, object]) -> FantasyArrangement:
    def cards(name: str) -> tuple[Card, ...]:
        return tuple(Card.parse(str(token)) for token in payload[name])  # type: ignore[index]
    return FantasyArrangement(
        Board(top=cards("top"), middle=cards("middle"), bottom=cards("bottom")),
        cards("discarded"),
    )


def _proposal_payload(proposal: FantasyProposalSet) -> dict:
    return {
        "player": proposal.player,
        "current_meta": _state_payload(proposal.current_meta),
        "own_packet": [str(card) for card in proposal.own_packet],
        "candidates": [_arrangement_payload(x) for x in proposal.candidates],
        "canonical_action_keys": list(proposal.canonical_action_keys),
        "synthetic_worlds": proposal.synthetic_worlds,
        "exact_teacher_calls": proposal.exact_teacher_calls,
        "max_candidates": proposal.max_candidates,
        "visible_fingerprint": proposal.visible_fingerprint,
        "continuation_fingerprint": proposal.continuation_fingerprint,
        "authority": proposal.authority,
    }


def _proposal_from_payload(payload: Mapping[str, object]) -> FantasyProposalSet:
    packet = tuple(Card.parse(str(token)) for token in payload["own_packet"])  # type: ignore[index]
    candidates = tuple(
        _arrangement_from_payload(row) for row in payload["candidates"]  # type: ignore[index]
    )
    for arrangement in candidates:
        validate_arrangement(packet, arrangement)
    proposal = FantasyProposalSet(
        player=int(payload["player"]),
        current_meta=_state_from_payload(payload["current_meta"]),  # type: ignore[arg-type]
        own_packet=packet,
        candidates=candidates,
        canonical_action_keys=tuple(str(x) for x in payload["canonical_action_keys"]),  # type: ignore[index]
        synthetic_worlds=int(payload["synthetic_worlds"]),
        exact_teacher_calls=int(payload["exact_teacher_calls"]),
        max_candidates=int(payload["max_candidates"]),
        visible_fingerprint=str(payload["visible_fingerprint"]),
        continuation_fingerprint=str(payload["continuation_fingerprint"]),
        authority=str(payload["authority"]),
    )
    if len(proposal.canonical_action_keys) != proposal.candidate_count:
        raise ValueError("cached proposal key/candidate cardinality mismatch")
    return proposal


def _matrix_payload(matrix: FantasySupportPayoffMatrix) -> dict:
    return {
        "current_meta": _state_payload(matrix.current_meta),
        "p0_action_keys": list(matrix.p0_action_keys),
        "p1_action_keys": list(matrix.p1_action_keys),
        "p0_values": [list(row) for row in matrix.p0_values],
        "continuation_fingerprint": matrix.continuation_fingerprint,
        "authority": matrix.authority,
    }


def _matrix_from_payload(payload: Mapping[str, object]) -> FantasySupportPayoffMatrix:
    return FantasySupportPayoffMatrix(
        current_meta=_state_from_payload(payload["current_meta"]),  # type: ignore[arg-type]
        p0_action_keys=tuple(str(x) for x in payload["p0_action_keys"]),  # type: ignore[index]
        p1_action_keys=tuple(str(x) for x in payload["p1_action_keys"]),  # type: ignore[index]
        p0_values=tuple(
            tuple(float(x) for x in row) for row in payload["p0_values"]  # type: ignore[index]
        ),
        continuation_fingerprint=str(payload["continuation_fingerprint"]),
        authority=str(payload["authority"]),
    )


@dataclass(frozen=True)
class CachedEpisode:
    split: str
    world_index: int
    world_seed: int
    generator_fingerprint: str
    episode: SealedSupportEpisode
    proposal0: FantasyProposalSet
    proposal1: FantasyProposalSet


def cached_episode_payload(cached: CachedEpisode) -> dict:
    world = cached.episode.world
    base = {
        "schema": EPISODE_SCHEMA,
        "split": cached.split,
        "world_index": cached.world_index,
        "world_seed": cached.world_seed,
        "generator_fingerprint": cached.generator_fingerprint,
        "current_meta": _state_payload(world.current_meta),
        "packets": [
            [str(card) for card in world.plan.packet_for(0)],
            [str(card) for card in world.plan.packet_for(1)],
        ],
        "proposal0": _proposal_payload(cached.proposal0),
        "proposal1": _proposal_payload(cached.proposal1),
        "matrix": _matrix_payload(cached.episode.matrix),
    }
    base["sha256"] = _sha(base)
    return base


def cached_episode_from_payload(payload: Mapping[str, object]) -> CachedEpisode:
    raw = dict(payload)
    expected = str(raw.pop("sha256", ""))
    if raw.get("schema") != EPISODE_SCHEMA or expected != _sha(raw):
        raise ValueError("cached M4S episode schema/SHA mismatch")
    current = _state_from_payload(raw["current_meta"])  # type: ignore[arg-type]
    packet_rows = raw["packets"]  # type: ignore[assignment]
    packets = tuple(
        tuple(Card.parse(str(token)) for token in row)
        for row in packet_rows  # type: ignore[union-attr]
    )
    if len(packets) != 2:
        raise ValueError("cached M4S episode must contain two packets")
    world = FantasyFantasyWorld(current, FantasyFantasyDealPlan((packets[0], packets[1])))
    proposal0 = _proposal_from_payload(raw["proposal0"])  # type: ignore[arg-type]
    proposal1 = _proposal_from_payload(raw["proposal1"])  # type: ignore[arg-type]
    if proposal0.current_meta != current or proposal1.current_meta != current:
        raise ValueError("cached proposal meta-state mismatch")
    if proposal0.own_packet != tuple(sorted(packets[0])) or proposal1.own_packet != tuple(sorted(packets[1])):
        raise ValueError("cached proposal packet mismatch")
    matrix = _matrix_from_payload(raw["matrix"])  # type: ignore[arg-type]
    episode = SealedSupportEpisode(
        world=world,
        p0_support=proposal0.candidates,
        p1_support=proposal1.candidates,
        matrix=matrix,
    )
    return CachedEpisode(
        split=str(raw["split"]),
        world_index=int(raw["world_index"]),
        world_seed=int(raw["world_seed"]),
        generator_fingerprint=str(raw["generator_fingerprint"]),
        episode=episode,
        proposal0=proposal0,
        proposal1=proposal1,
    )


def save_cached_episode(path: Path, cached: CachedEpisode) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(
        cached_episode_payload(cached), sort_keys=True, indent=2, allow_nan=False
    ) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(path)


def load_cached_episode(path: Path) -> CachedEpisode:
    return cached_episode_from_payload(json.loads(path.read_text(encoding="utf-8")))


def _seed(base_seed: int, state: HUContinuationState, split: str, index: int, tag: str) -> int:
    payload = {
        "base_seed": int(base_seed),
        "state": state.as_key(),
        "split": split,
        "index": int(index),
        "tag": tag,
    }
    return int.from_bytes(hashlib.sha256(_canonical_bytes(payload)).digest()[:8], "big")


def generator_fingerprint(
    *,
    base_seed: int,
    synthetic_worlds: int,
    max_candidates: int,
    continuation_sha: str,
) -> str:
    return _sha(
        {
            "schema": SCHEMA,
            "base_seed": int(base_seed),
            "synthetic_worlds": int(synthetic_worlds),
            "max_candidates": int(max_candidates),
            "continuation_sha256": continuation_sha,
        }
    )


def materialize_episode(
    path: Path,
    *,
    state: HUContinuationState,
    split: str,
    world_index: int,
    base_seed: int,
    synthetic_worlds: int,
    max_candidates: int,
    continuation_values: Mapping[HUContinuationState, float],
    generator_sha: str,
) -> CachedEpisode:
    if path.exists():
        cached = load_cached_episode(path)
        if cached.generator_fingerprint != generator_sha:
            raise ValueError(
                f"existing episode {path} was built under a different generator/continuation config"
            )
        if (
            cached.split != split
            or cached.world_index != world_index
            or cached.episode.world.current_meta != state
        ):
            raise ValueError(f"existing episode {path} identity mismatch")
        return cached

    world_seed = _seed(base_seed, state, split, world_index, "world")
    world = FantasyFantasyWorld(
        state, sample_fantasy_fantasy_plan(random.Random(world_seed), state)
    )
    proposals = []
    for player in (0, 1):
        proposals.append(
            generate_fantasy_proposals(
                world.plan.packet_for(player),
                current_meta=state,
                player=player,
                continuation_values=continuation_values,
                synthetic_worlds=synthetic_worlds,
                max_candidates=max_candidates,
                base_seed=_seed(base_seed, state, split, world_index, f"proposal-p{player}"),
            )
        )
    matrix = build_exact_support_payoff_matrix(
        world, proposals[0].candidates, proposals[1].candidates, continuation_values
    )
    cached = CachedEpisode(
        split=split,
        world_index=world_index,
        world_seed=world_seed,
        generator_fingerprint=generator_sha,
        episode=SealedSupportEpisode(
            world=world,
            p0_support=proposals[0].candidates,
            p1_support=proposals[1].candidates,
            matrix=matrix,
        ),
        proposal0=proposals[0],
        proposal1=proposals[1],
    )
    save_cached_episode(path, cached)
    return cached


def _sample_index(policy: Sequence[float], rng: random.Random) -> int:
    x = rng.random()
    cumulative = 0.0
    for index, probability in enumerate(policy):
        cumulative += float(probability)
        if x < cumulative or index == len(policy) - 1:
            return index
    raise AssertionError("policy sampling fell through")


def heldout_row(
    model: SparseFantasyActionValueModel,
    cached: CachedEpisode,
    continuation_values: Mapping[HUContinuationState, float],
    *,
    temperature: float,
    support_gap_samples: int,
    diagnostic_seed: int,
) -> dict:
    episode = cached.episode
    snapshot = snapshot_episode_policy(model, episode, temperature=temperature)
    _frozen, targets = exact_selfplay_targets(model, episode, temperature=temperature)
    errors = [
        abs(model.predict(example) - example.target)
        for example in targets.p0_examples + targets.p1_examples
    ]

    gap0: list[float] = []
    gap1: list[float] = []
    rng = random.Random(diagnostic_seed)
    for _ in range(support_gap_samples):
        j = _sample_index(snapshot.p1_policy, rng)
        i = _sample_index(snapshot.p0_policy, rng)
        gap0.append(
            evaluate_proposal_support(
                cached.proposal0,
                episode.p1_support[j].board,
                continuation_values,
            ).support_gap
        )
        gap1.append(
            evaluate_proposal_support(
                cached.proposal1,
                episode.p0_support[i].board,
                continuation_values,
            ).support_gap
        )

    def mean(values: Sequence[float]) -> float | None:
        return sum(values) / len(values) if values else None

    packet0 = episode.world.plan.packet_for(0)
    packet1 = episode.world.plan.packet_for(1)
    joker0 = sum(1 for card in packet0 if card.joker)
    joker1 = sum(1 for card in packet1 if card.joker)
    return {
        "state": episode.world.current_meta.as_key(),
        "world_index": cached.world_index,
        "p0_candidates": len(episode.p0_support),
        "p1_candidates": len(episode.p1_support),
        "p0_jokers": joker0,
        "p1_jokers": joker1,
        "support_restricted_deviation": snapshot.diagnostic.total_support_deviation_gain,
        "p0_support_deviation": snapshot.diagnostic.p0_deviation_gain,
        "p1_support_deviation": snapshot.diagnostic.p1_deviation_gain,
        "action_value_mae": sum(errors) / len(errors),
        "action_value_max_abs_error": max(errors),
        "p0_sampled_exact_support_gap": mean(gap0),
        "p1_sampled_exact_support_gap": mean(gap1),
        "support_gap_samples_per_player": support_gap_samples,
    }


def _parse_pairs(raw_pairs: Sequence[str] | None, all_pairs: bool) -> tuple[tuple[int, int], ...]:
    if all_pairs:
        return tuple((a, b) for a in FANTASY_COUNTS for b in FANTASY_COUNTS)
    supplied = tuple(raw_pairs or ("14:14",))
    result = []
    for raw in supplied:
        try:
            left, right = (int(x) for x in raw.split(":"))
        except Exception as exc:
            raise ValueError(f"invalid --pair {raw!r}; expected e.g. 14:16") from exc
        if left not in FANTASY_COUNTS or right not in FANTASY_COUNTS:
            raise ValueError("Fantasy pair counts must be 14..17")
        result.append((left, right))
    return tuple(dict.fromkeys(result))


def _parse_buttons(text: str) -> tuple[int, ...]:
    values = tuple(dict.fromkeys(int(x.strip()) for x in text.split(",") if x.strip()))
    if not values or any(value not in (0, 1) for value in values):
        raise ValueError("buttons must be 0 and/or 1")
    return values


def _aggregate(rows: Sequence[dict]) -> dict:
    if not rows:
        return {"rows": 0}
    deviation = [float(row["support_restricted_deviation"]) for row in rows]
    mae = [float(row["action_value_mae"]) for row in rows]
    max_error = [float(row["action_value_max_abs_error"]) for row in rows]
    gaps = [
        float(value)
        for row in rows
        for value in (
            row["p0_sampled_exact_support_gap"],
            row["p1_sampled_exact_support_gap"],
        )
        if value is not None
    ]
    return {
        "rows": len(rows),
        "mean_support_restricted_deviation": sum(deviation) / len(deviation),
        "max_support_restricted_deviation": max(deviation),
        "mean_action_value_mae": sum(mae) / len(mae),
        "max_action_value_abs_error": max(max_error),
        "mean_sampled_exact_support_gap": (sum(gaps) / len(gaps) if gaps else None),
        "max_sampled_exact_support_gap": (max(gaps) if gaps else None),
    }


def run(args: argparse.Namespace) -> dict:
    if (
        args.train_worlds_per_state <= 0
        or args.heldout_worlds_per_state <= 0
        or args.synthetic_worlds <= 0
        or args.max_candidates <= 0
        or args.selfplay_iterations <= 0
        or args.epochs_per_iteration <= 0
        or args.support_gap_samples < 0
    ):
        raise ValueError("M4S counts/iterations must be positive (support-gap samples may be zero)")
    pairs = _parse_pairs(args.pair, args.all_pairs)
    buttons = _parse_buttons(args.buttons)
    states = tuple(
        HUContinuationState(button, p0, p1)
        for p0, p1 in pairs
        for button in buttons
    )
    continuation = load_continuation_values(args.continuation_values)
    _checked, continuation_sha = continuation_fingerprint(continuation)
    generator_sha = generator_fingerprint(
        base_seed=args.base_seed,
        synthetic_worlds=args.synthetic_worlds,
        max_candidates=args.max_candidates,
        continuation_sha=continuation_sha,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)

    train_cached: list[CachedEpisode] = []
    heldout_cached: list[CachedEpisode] = []
    for split, count, target in (
        ("train", args.train_worlds_per_state, train_cached),
        ("heldout", args.heldout_worlds_per_state, heldout_cached),
    ):
        for state in states:
            state_dir = args.output_dir / "episodes" / split / state.as_key().replace(":", "_")
            for index in range(count):
                path = state_dir / f"world_{index:05d}.json"
                target.append(
                    materialize_episode(
                        path,
                        state=state,
                        split=split,
                        world_index=index,
                        base_seed=args.base_seed,
                        synthetic_worlds=args.synthetic_worlds,
                        max_candidates=args.max_candidates,
                        continuation_values=continuation,
                        generator_sha=generator_sha,
                    )
                )

    model = SparseFantasyActionValueModel(
        buckets=args.model_buckets,
        seed=args.base_seed ^ 0x4D3451,
    )
    replay = DeterministicFantasyReplay(
        capacity=args.replay_capacity,
        seed=args.base_seed ^ 0x52504C59,
    )
    train_reports = []
    train_episodes = tuple(cached.episode for cached in train_cached)
    for iteration in range(args.selfplay_iterations):
        report = train_selfplay_iteration(
            model,
            replay,
            train_episodes,
            epochs=args.epochs_per_iteration,
            temperature=args.temperature,
        )
        row = asdict(report)
        row["iteration"] = iteration + 1
        train_reports.append(row)
        print(
            f"M4S_ITER={iteration + 1} mean_dev_before={report.mean_support_deviation_before:.6f} "
            f"mean_dev_after={report.mean_support_deviation_after:.6f} replay={report.replay_size}",
            flush=True,
        )

    checkpoint = args.output_dir / "M4S_MODEL_REPLAY.json.gz"
    save_checkpoint(checkpoint, model, replay)
    checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

    heldout_rows = []
    for cached in heldout_cached:
        state = cached.episode.world.current_meta
        heldout_rows.append(
            heldout_row(
                model,
                cached,
                continuation,
                temperature=args.temperature,
                support_gap_samples=args.support_gap_samples,
                diagnostic_seed=_seed(
                    args.base_seed, state, "heldout", cached.world_index, "diagnostic"
                ),
            )
        )
        print(
            f"M4S_HELDOUT={state.as_key()}:{cached.world_index} "
            f"dev={heldout_rows[-1]['support_restricted_deviation']:.6f} "
            f"q_mae={heldout_rows[-1]['action_value_mae']:.6f}",
            flush=True,
        )

    report = {
        "schema": REPORT_SCHEMA,
        "authority": AUTHORITY,
        "promotion_blocked": True,
        "generator_fingerprint": generator_sha,
        "continuation_fingerprint": continuation_sha,
        "states": [state.as_key() for state in states],
        "config": {
            "base_seed": args.base_seed,
            "train_worlds_per_state": args.train_worlds_per_state,
            "heldout_worlds_per_state": args.heldout_worlds_per_state,
            "synthetic_worlds": args.synthetic_worlds,
            "max_candidates": args.max_candidates,
            "selfplay_iterations": args.selfplay_iterations,
            "epochs_per_iteration": args.epochs_per_iteration,
            "temperature": args.temperature,
            "model_buckets": args.model_buckets,
            "replay_capacity": args.replay_capacity,
            "support_gap_samples": args.support_gap_samples,
        },
        "train_iterations": train_reports,
        "heldout": heldout_rows,
        "heldout_aggregate": _aggregate(heldout_rows),
        "model_checkpoint_sha256": checkpoint_sha,
        "error_budgets": {
            "support_loss": "sampled exact M4N-vs-M4O gap against held-out opponent support actions",
            "within_support_policy_loss": "exact M4P unilateral-deviation gain",
            "function_generalization_loss": "held-out M4Q action-value absolute error",
        },
        "next_action": (
            "Use the F14/F14 pilot to calibrate exact-teacher runtime, then expand states/seeds. "
            "Do not freeze promotion thresholds until independent multiseed evidence exists."
        ),
    }
    report["sha256"] = _sha(report)
    out = args.output_dir / "M4S_HELDOUT_REPORT.json"
    out.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run resumable M4S sealed Fantasy multiseed pilot")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--pair", action="append", help="Fantasy count pair such as 14:16; repeatable")
    parser.add_argument("--all-pairs", action="store_true", help="run all 16 P0/P1 Fantasy-count pairs")
    parser.add_argument("--buttons", default="0,1")
    parser.add_argument("--train-worlds-per-state", type=int, default=1)
    parser.add_argument("--heldout-worlds-per-state", type=int, default=1)
    parser.add_argument("--synthetic-worlds", type=int, default=2)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--selfplay-iterations", type=int, default=2)
    parser.add_argument("--epochs-per-iteration", type=int, default=2)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--model-buckets", type=int, default=1 << 16)
    parser.add_argument("--replay-capacity", type=int, default=100000)
    parser.add_argument("--support-gap-samples", type=int, default=1)
    parser.add_argument("--base-seed", type=int, default=20260828)
    parser.add_argument("--continuation-values", type=Path)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps(report["heldout_aggregate"], sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
