from __future__ import annotations

"""Deterministic, resumable runner for strategic HU MCCFR.

The v2 runner persists the *exact* PRNG state alongside the regret table, hashes
the canonical payload and writes checkpoints atomically.  It supports both the
raw full-action solver and the exact 24-way suit-isomorphic solver.

This is execution infrastructure, not an optimality certificate.  A completed
checkpoint remains `STRATEGIC_APPROX` until a separate regret/best-response
certificate establishes an epsilon bound for the declared game model.
"""

import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Type

from strategic_cfr import CHECKPOINT_SCHEMA, InfoSetNode, OutcomeSamplingMCCFR

RUNNER_SCHEMA = "openofc-hu-outcome-sampling-mccfr-runner-v2"
AUTHORITY = "STRATEGIC_APPROX_CURRENT_HAND_HU"
RAW_SOLVER_KIND = "raw-full-action"


def _solver_kind(solver: OutcomeSamplingMCCFR) -> str:
    return str(getattr(solver, "solver_kind", RAW_SOLVER_KIND))


def _solver_class(kind: str) -> Type[OutcomeSamplingMCCFR]:
    if kind == RAW_SOLVER_KIND:
        return OutcomeSamplingMCCFR
    if kind == "suit24-exact":
        from strategic_suit_symmetry import SuitCanonicalOutcomeSamplingMCCFR
        return SuitCanonicalOutcomeSamplingMCCFR
    raise ValueError(f"unsupported strategic solver kind: {kind!r}")


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def solver_state_payload(solver: OutcomeSamplingMCCFR) -> dict[str, Any]:
    core = solver.checkpoint_payload()
    if core.get("schema") != CHECKPOINT_SCHEMA:
        raise AssertionError("unexpected strategic CFR core checkpoint schema")
    return {
        "schema": RUNNER_SCHEMA,
        "authority": AUTHORITY,
        "solver_kind": _solver_kind(solver),
        "core": core,
        # repr(random.getstate()) is Python-literal data only. ast.literal_eval
        # restores nested tuples exactly without executing code.
        "rng_state_repr": repr(solver.rng.getstate()),
    }


def state_digest(solver: OutcomeSamplingMCCFR) -> str:
    return _sha256(_canonical_json_bytes(solver_state_payload(solver)))


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if path.suffix == ".gz":
        # gzip.open() has no portable `mtime` keyword. GzipFile does; pinning it
        # makes the compressed checkpoint reproducible as well as the payload.
        with tmp.open("wb") as raw_handle:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=6,
                fileobj=raw_handle,
                mtime=0,
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


def save_runner_checkpoint(solver: OutcomeSamplingMCCFR, path: Path) -> str:
    payload = solver_state_payload(solver)
    raw = _canonical_json_bytes(payload)
    digest = _sha256(raw)
    envelope = {
        "schema": RUNNER_SCHEMA + "-envelope",
        "payload_sha256": digest,
        "payload": payload,
    }
    _write_bytes(path, _canonical_json_bytes(envelope))
    return digest


def load_runner_checkpoint(path: Path) -> tuple[OutcomeSamplingMCCFR, str]:
    envelope = json.loads(_read_bytes(path).decode("utf-8"))
    if envelope.get("schema") != RUNNER_SCHEMA + "-envelope":
        raise ValueError("unsupported strategic runner checkpoint envelope")
    payload = envelope.get("payload")
    if not isinstance(payload, dict) or payload.get("schema") != RUNNER_SCHEMA:
        raise ValueError("unsupported strategic runner checkpoint payload")
    raw = _canonical_json_bytes(payload)
    actual = _sha256(raw)
    expected = str(envelope.get("payload_sha256", ""))
    if actual != expected:
        raise ValueError("strategic runner checkpoint SHA-256 mismatch")

    core = payload.get("core")
    if not isinstance(core, dict) or core.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("runner checkpoint contains incompatible CFR core")
    cls = _solver_class(str(payload.get("solver_kind", RAW_SOLVER_KIND)))
    solver = cls(
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
            raise ValueError("corrupt CFR node in runner checkpoint")
        solver.nodes[str(row["key"])] = node

    rng_state = ast.literal_eval(str(payload["rng_state_repr"]))
    if not isinstance(rng_state, tuple):
        raise ValueError("runner checkpoint RNG state is not a tuple")
    solver.rng.setstate(rng_state)
    if state_digest(solver) != actual:
        raise AssertionError("restored strategic state does not reproduce checkpoint digest")
    return solver, actual


def run_chunked(
    solver: OutcomeSamplingMCCFR,
    *,
    additional_iterations: int,
    checkpoint_every: int,
    checkpoint: Path,
) -> dict[str, Any]:
    if additional_iterations <= 0:
        raise ValueError("additional_iterations must be positive")
    if checkpoint_every <= 0:
        raise ValueError("checkpoint_every must be positive")
    remaining = int(additional_iterations)
    writes = 0
    last_digest = ""
    while remaining:
        chunk = min(remaining, checkpoint_every)
        solver.run(chunk)
        remaining -= chunk
        last_digest = save_runner_checkpoint(solver, checkpoint)
        writes += 1
    stats = solver.stats()
    return {
        "schema": RUNNER_SCHEMA,
        "authority": AUTHORITY,
        "solver_kind": _solver_kind(solver),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": last_digest,
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
        description="Deterministic resumable runner for full-action HU OFC MCCFR"
    )
    parser.add_argument("--iterations", type=int, required=True,
                        help="additional iterations to execute")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-every", type=int, default=10000)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--epsilon", type=float, default=0.6)
    parser.add_argument("--no-cfr-plus", action="store_true")
    parser.add_argument("--suit-canonical", action="store_true",
                        help="use exact 24-way suit-isomorphism reduction")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    if args.resume is not None:
        solver, _digest = load_runner_checkpoint(args.resume)
        if abs(solver.epsilon - args.epsilon) > 1e-12:
            raise SystemExit("resume epsilon does not match requested epsilon")
        if solver.cfr_plus == bool(args.no_cfr_plus):
            raise SystemExit("resume CFR+ mode does not match requested mode")
        if args.suit_canonical and _solver_kind(solver) != "suit24-exact":
            raise SystemExit("--suit-canonical conflicts with raw resume checkpoint")
    else:
        if args.suit_canonical:
            from strategic_suit_symmetry import SuitCanonicalOutcomeSamplingMCCFR
            cls = SuitCanonicalOutcomeSamplingMCCFR
        else:
            cls = OutcomeSamplingMCCFR
        solver = cls(
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
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("OPENOFC_STRATEGIC_RUNNER=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
