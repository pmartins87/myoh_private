from __future__ import annotations

"""Deterministic resumable runner for continuation-coupled HU normal MCCFR."""

import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from hu_continuation import HUContinuationState, all_states, zero_continuation_values
from strategic_cfr import CHECKPOINT_SCHEMA, InfoSetNode
from strategic_continuation_cfr import (
    AUTHORITY,
    SOLVER_KIND,
    ContinuationObjective,
    SuitCanonicalContinuationMCCFR,
    _state_from_key,
)

RUNNER_SCHEMA = "openofc-hu-continuation-mccfr-runner-v1"
VALUES_SCHEMA = "openofc-hu-continuation-values-v1"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if path.suffix == ".gz":
        with tmp.open("wb") as raw:
            with gzip.GzipFile(
                filename="", mode="wb", compresslevel=6, fileobj=raw, mtime=0
            ) as handle:
                handle.write(data)
    else:
        tmp.write_bytes(data)
    os.replace(tmp, path)


def _read_bytes(path: Path) -> bytes:
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as handle:
            return handle.read()
    return path.read_bytes()


def load_values_file(path: Path) -> dict[HUContinuationState, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != VALUES_SCHEMA:
        raise ValueError("unsupported continuation-values file schema")
    values = payload.get("values")
    if not isinstance(values, dict):
        raise ValueError("continuation-values file has no values mapping")
    parsed = {_state_from_key(str(k)): float(v) for k, v in values.items()}
    if set(parsed) != set(all_states()):
        raise ValueError("continuation-values file must contain exactly 50 HU states")
    return parsed


def write_values_file(
    path: Path, values: dict[HUContinuationState, float]
) -> None:
    payload = {
        "schema": VALUES_SCHEMA,
        "values": {
            state.as_key(): float(values[state])
            for state in sorted(all_states())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def state_payload(solver: SuitCanonicalContinuationMCCFR) -> dict[str, Any]:
    core = solver.checkpoint_payload()
    if core.get("schema") != CHECKPOINT_SCHEMA:
        raise AssertionError("unexpected strategic CFR checkpoint schema")
    return {
        "schema": RUNNER_SCHEMA,
        "authority": AUTHORITY,
        "solver_kind": SOLVER_KIND,
        "core": core,
        "rng_state_repr": repr(solver.rng.getstate()),
    }


def state_digest(solver: SuitCanonicalContinuationMCCFR) -> str:
    return _sha256(_canonical_bytes(state_payload(solver)))


def save_checkpoint(
    solver: SuitCanonicalContinuationMCCFR, path: Path
) -> str:
    payload = state_payload(solver)
    raw = _canonical_bytes(payload)
    digest = _sha256(raw)
    envelope = {
        "schema": RUNNER_SCHEMA + "-envelope",
        "payload_sha256": digest,
        "payload": payload,
    }
    _write_bytes(path, _canonical_bytes(envelope))
    return digest


def load_checkpoint(
    path: Path,
) -> tuple[SuitCanonicalContinuationMCCFR, str]:
    envelope = json.loads(_read_bytes(path).decode("utf-8"))
    if envelope.get("schema") != RUNNER_SCHEMA + "-envelope":
        raise ValueError("unsupported continuation runner envelope")
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or payload.get("schema") != RUNNER_SCHEMA:
        raise ValueError("unsupported continuation runner payload")
    raw = _canonical_bytes(payload)
    actual = _sha256(raw)
    if actual != str(envelope.get("payload_sha256", "")):
        raise ValueError("continuation runner checkpoint SHA-256 mismatch")
    if payload.get("solver_kind") != SOLVER_KIND:
        raise ValueError("checkpoint is not continuation-coupled suit24 solver")

    core = payload.get("core")
    if not isinstance(core, dict) or core.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("checkpoint contains incompatible CFR core")
    objective_payload = core.get("continuation_objective")
    if not isinstance(objective_payload, dict):
        raise ValueError("checkpoint is missing continuation objective")
    objective = ContinuationObjective.from_payload(objective_payload)
    solver = SuitCanonicalContinuationMCCFR(
        objective=objective,
        epsilon=float(core["epsilon"]),
        seed=int(core["seed"]),
        cfr_plus=bool(core["cfr_plus"]),
    )
    solver.iterations = int(core["iterations"])
    solver.episodes = int(core["episodes"])
    for row in core["nodes"]:
        node = InfoSetNode(
            action_keys=tuple(row["action_keys"]),
            cumulative_regrets=[float(x) for x in row["cumulative_regrets"]],
            cumulative_policy=[float(x) for x in row["cumulative_policy"]],
            visits=int(row["visits"]),
        )
        if not (
            len(node.action_keys)
            == len(node.cumulative_regrets)
            == len(node.cumulative_policy)
        ):
            raise ValueError("corrupt CFR node in continuation checkpoint")
        solver.nodes[str(row["key"])] = node
    rng_state = ast.literal_eval(str(payload["rng_state_repr"]))
    if not isinstance(rng_state, tuple):
        raise ValueError("continuation checkpoint RNG state is not a tuple")
    solver.rng.setstate(rng_state)
    if state_digest(solver) != actual:
        raise AssertionError("restored continuation state digest mismatch")
    return solver, actual


def run_chunked(
    solver: SuitCanonicalContinuationMCCFR,
    *,
    additional_iterations: int,
    checkpoint_every: int,
    checkpoint: Path,
) -> dict[str, Any]:
    if additional_iterations <= 0 or checkpoint_every <= 0:
        raise ValueError("iterations and checkpoint cadence must be positive")
    remaining = int(additional_iterations)
    writes = 0
    digest = ""
    while remaining:
        chunk = min(remaining, checkpoint_every)
        solver.run(chunk)
        remaining -= chunk
        digest = save_checkpoint(solver, checkpoint)
        writes += 1
    stats = solver.stats()
    return {
        "schema": RUNNER_SCHEMA,
        "authority": AUTHORITY,
        "solver_kind": SOLVER_KIND,
        "objective_sha256": solver.objective.fingerprint,
        "current_state": solver.objective.current_state.as_key(),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": digest,
        "checkpoint_writes": writes,
        "iterations": stats.iterations,
        "episodes": stats.episodes,
        "infosets": stats.infosets,
        "total_visits": stats.total_visits,
        "max_actions": stats.max_actions,
        "mean_actions": stats.mean_actions,
        "epsilon": stats.epsilon,
        "cfr_plus": stats.cfr_plus,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Continuation-coupled full-action HU normal/normal MCCFR"
    )
    parser.add_argument("--iterations", type=int, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-every", type=int, default=10000)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--continuation-values", type=Path)
    parser.add_argument("--zero-continuation", action="store_true")
    parser.add_argument("--button", type=int, choices=(0, 1), default=1)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--epsilon", type=float, default=0.6)
    parser.add_argument("--no-cfr-plus", action="store_true")
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--write-zero-values", type=Path)
    args = parser.parse_args()

    if args.write_zero_values is not None:
        write_values_file(args.write_zero_values, zero_continuation_values())

    if args.resume is not None:
        if args.continuation_values is not None or args.zero_continuation:
            raise SystemExit("resume restores its pinned continuation objective; do not replace it")
        solver, _ = load_checkpoint(args.resume)
        if abs(solver.epsilon - args.epsilon) > 1e-12:
            raise SystemExit("resume epsilon does not match requested epsilon")
        if solver.cfr_plus == bool(args.no_cfr_plus):
            raise SystemExit("resume CFR+ mode does not match requested mode")
    else:
        if bool(args.continuation_values) == bool(args.zero_continuation):
            raise SystemExit(
                "new run requires exactly one of --continuation-values or --zero-continuation"
            )
        values = (
            zero_continuation_values()
            if args.zero_continuation
            else load_values_file(args.continuation_values)
        )
        objective = ContinuationObjective(
            HUContinuationState(args.button, 0, 0), values
        )
        solver = SuitCanonicalContinuationMCCFR(
            objective=objective,
            epsilon=args.epsilon,
            seed=args.seed,
            cfr_plus=not args.no_cfr_plus,
        )

    report = run_chunked(
        solver,
        additional_iterations=args.iterations,
        checkpoint_every=args.checkpoint_every,
        checkpoint=args.checkpoint,
    )
    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print("OPENOFC_STRATEGIC_CONTINUATION_RUNNER=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
