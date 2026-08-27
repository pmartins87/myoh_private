from __future__ import annotations

"""Deterministic sparse action-conditioned model for OpenOFC strategic learning.

This dependency-free layer is a bounded function-generalization probe built on
M4C's lossless visible feature contract.  It is deliberately approximate and
must earn promotion against exact teachers and held-out strategic states.
"""

from dataclasses import dataclass
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from strategic_feature_encoder import FEATURE_DIMENSION, OFFSET_ACTION

MODEL_SCHEMA = "openofc-hu-action-advantage-v1"
CHECKPOINT_SCHEMA = "openofc-hu-action-advantage-checkpoint-v1"
REPLAY_SCHEMA = "openofc-hu-deterministic-reservoir-v1"
DEFAULT_INTERACTION_BUCKETS = 1 << 16
MASK64 = (1 << 64) - 1


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _mix64(value: int) -> int:
    """Stable SplitMix64 finalizer; independent of Python's randomized hash."""
    x = value & MASK64
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & MASK64
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & MASK64
    x ^= x >> 31
    return x & MASK64


def _require_power_of_two(value: int) -> None:
    if value <= 0 or value & (value - 1):
        raise ValueError("interaction bucket count must be a positive power of two")


def _validate_state_action_features(
    state_features: Sequence[int], action_features: Sequence[int]
) -> None:
    if not state_features or not action_features:
        raise ValueError("state and action features must both be non-empty")
    if min(state_features) < 0 or max(state_features) >= OFFSET_ACTION:
        raise ValueError("state feature escaped the state feature range")
    if min(action_features) < OFFSET_ACTION or max(action_features) >= FEATURE_DIMENSION:
        raise ValueError("action feature escaped the action feature range")


def interaction_terms(
    state_features: Sequence[int],
    action_features: Sequence[int],
    *,
    buckets: int = DEFAULT_INTERACTION_BUCKETS,
) -> tuple[tuple[int, float], ...]:
    """Sparse direct-action + signed-hashed state/action interaction terms."""
    _require_power_of_two(buckets)
    _validate_state_action_features(state_features, action_features)
    action_size = FEATURE_DIMENSION - OFFSET_ACTION
    interaction_offset = 1 + action_size
    terms: dict[int, float] = {0: 1.0}

    for action_feature in action_features:
        local_action = int(action_feature) - OFFSET_ACTION
        direct_index = 1 + local_action
        terms[direct_index] = terms.get(direct_index, 0.0) + 1.0
        for state_feature in state_features:
            seed = (
                ((int(state_feature) + 1) * 0x9E3779B185EBCA87)
                ^ ((local_action + 1) * 0xC2B2AE3D27D4EB4F)
            ) & MASK64
            mixed = _mix64(seed)
            bucket = mixed & (buckets - 1)
            sign = -1.0 if (mixed >> 63) else 1.0
            index = interaction_offset + int(bucket)
            terms[index] = terms.get(index, 0.0) + sign

    return tuple(sorted((index, value) for index, value in terms.items() if value))


@dataclass(frozen=True)
class ReplayExample:
    state_features: tuple[int, ...]
    action_features: tuple[int, ...]
    target: float
    weight: float = 1.0
    source: str = "mccfr"

    def __post_init__(self) -> None:
        _validate_state_action_features(self.state_features, self.action_features)
        if not math.isfinite(self.target):
            raise ValueError("replay target must be finite")
        if not math.isfinite(self.weight) or self.weight <= 0.0:
            raise ValueError("replay weight must be positive and finite")
        if not self.source:
            raise ValueError("replay source must be non-empty")

    def payload(self) -> dict:
        return {
            "state": list(self.state_features),
            "action": list(self.action_features),
            "target": float(self.target),
            "weight": float(self.weight),
            "source": self.source,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ReplayExample":
        return cls(
            state_features=tuple(int(x) for x in payload["state"]),  # type: ignore[index]
            action_features=tuple(int(x) for x in payload["action"]),  # type: ignore[index]
            target=float(payload["target"]),
            weight=float(payload["weight"]),
            source=str(payload["source"]),
        )


class DeterministicReservoir:
    """Bounded replay with resume-stable counter-derived reservoir sampling."""

    def __init__(self, *, capacity: int, seed: int = 20260826) -> None:
        if capacity <= 0:
            raise ValueError("replay capacity must be positive")
        self.capacity = int(capacity)
        self.seed = int(seed) & MASK64
        self.seen = 0
        self.items: list[ReplayExample] = []

    def add(self, example: ReplayExample) -> None:
        self.seen += 1
        if len(self.items) < self.capacity:
            self.items.append(example)
            return
        j = _mix64(self.seed ^ self.seen) % self.seen
        if j < self.capacity:
            self.items[int(j)] = example

    def extend(self, examples: Iterable[ReplayExample]) -> None:
        for example in examples:
            self.add(example)

    def payload(self) -> dict:
        base = {
            "schema": REPLAY_SCHEMA,
            "capacity": self.capacity,
            "seed": self.seed,
            "seen": self.seen,
            "items": [item.payload() for item in self.items],
        }
        base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
        return base

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "DeterministicReservoir":
        if payload.get("schema") != REPLAY_SCHEMA:
            raise ValueError("unsupported replay schema")
        raw = dict(payload)
        expected = str(raw.pop("sha256", ""))
        actual = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
        if expected != actual:
            raise ValueError("replay SHA-256 mismatch")
        replay = cls(capacity=int(raw["capacity"]), seed=int(raw["seed"]))
        replay.seen = int(raw["seen"])
        replay.items = [ReplayExample.from_payload(row) for row in raw["items"]]  # type: ignore[arg-type]
        if len(replay.items) > replay.capacity or replay.seen < len(replay.items):
            raise ValueError("corrupt replay cardinality")
        return replay


class SparseActionAdvantageModel:
    """Sparse AdaGrad regressor over bounded action-conditioned interactions."""

    def __init__(
        self,
        *,
        buckets: int = DEFAULT_INTERACTION_BUCKETS,
        learning_rate: float = 0.08,
        l2: float = 1e-6,
        huber_delta: float = 1.0,
        seed: int = 20260826,
    ) -> None:
        _require_power_of_two(buckets)
        if learning_rate <= 0.0 or l2 < 0.0 or huber_delta <= 0.0:
            raise ValueError("invalid model hyperparameter")
        self.buckets = int(buckets)
        self.learning_rate = float(learning_rate)
        self.l2 = float(l2)
        self.huber_delta = float(huber_delta)
        self.seed = int(seed) & MASK64
        self.weights: dict[int, float] = {}
        self.grad_sq: dict[int, float] = {}
        self.epochs_trained = 0
        self.updates = 0

    @property
    def dimension(self) -> int:
        return 1 + (FEATURE_DIMENSION - OFFSET_ACTION) + self.buckets

    def terms(self, example: ReplayExample) -> tuple[tuple[int, float], ...]:
        return interaction_terms(
            example.state_features, example.action_features, buckets=self.buckets
        )

    def predict_features(
        self, state_features: Sequence[int], action_features: Sequence[int]
    ) -> float:
        return sum(
            self.weights.get(index, 0.0) * value
            for index, value in interaction_terms(
                state_features, action_features, buckets=self.buckets
            )
        )

    def predict(self, example: ReplayExample) -> float:
        return self.predict_features(example.state_features, example.action_features)

    def _loss_gradient(self, error: float) -> float:
        if abs(error) <= self.huber_delta:
            return error
        return self.huber_delta if error > 0.0 else -self.huber_delta

    def update(self, example: ReplayExample) -> float:
        prediction = self.predict(example)
        error = prediction - example.target
        common = self._loss_gradient(error) * example.weight
        for index, value in self.terms(example):
            weight = self.weights.get(index, 0.0)
            gradient = common * value + self.l2 * weight
            accum = self.grad_sq.get(index, 0.0) + gradient * gradient
            self.grad_sq[index] = accum
            self.weights[index] = weight - (
                self.learning_rate * gradient / math.sqrt(accum + 1e-12)
            )
        self.updates += 1
        if abs(error) <= self.huber_delta:
            return 0.5 * error * error * example.weight
        return self.huber_delta * (
            abs(error) - 0.5 * self.huber_delta
        ) * example.weight

    def fit(self, replay: DeterministicReservoir, *, epochs: int = 1) -> dict[str, float]:
        if epochs <= 0 or not replay.items:
            raise ValueError("fit requires positive epochs and non-empty replay")
        total_loss = 0.0
        count = 0
        for _ in range(epochs):
            epoch = self.epochs_trained
            order = list(range(len(replay.items)))
            order.sort(key=lambda i: _mix64(self.seed ^ (epoch << 32) ^ i))
            for index in order:
                total_loss += self.update(replay.items[index])
                count += 1
            self.epochs_trained += 1
        return {
            "mean_huber_loss": total_loss / max(1, count),
            "examples": float(count),
            "epochs_trained": float(self.epochs_trained),
            "updates": float(self.updates),
            "nonzero_weights": float(len(self.weights)),
        }

    def policy(
        self,
        state_features: Sequence[int],
        action_features: Sequence[Sequence[int]],
    ) -> list[float]:
        if not action_features:
            raise ValueError("policy requires at least one legal action")
        scores = [
            max(0.0, self.predict_features(state_features, features))
            for features in action_features
        ]
        total = sum(scores)
        if total <= 0.0:
            return [1.0 / len(scores)] * len(scores)
        return [score / total for score in scores]

    def payload(self) -> dict:
        return {
            "schema": MODEL_SCHEMA,
            "buckets": self.buckets,
            "learning_rate": self.learning_rate,
            "l2": self.l2,
            "huber_delta": self.huber_delta,
            "seed": self.seed,
            "epochs_trained": self.epochs_trained,
            "updates": self.updates,
            "weights": [[index, value] for index, value in sorted(self.weights.items())],
            "grad_sq": [[index, value] for index, value in sorted(self.grad_sq.items())],
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "SparseActionAdvantageModel":
        if payload.get("schema") != MODEL_SCHEMA:
            raise ValueError("unsupported model schema")
        model = cls(
            buckets=int(payload["buckets"]),
            learning_rate=float(payload["learning_rate"]),
            l2=float(payload["l2"]),
            huber_delta=float(payload["huber_delta"]),
            seed=int(payload["seed"]),
        )
        model.epochs_trained = int(payload["epochs_trained"])
        model.updates = int(payload["updates"])
        model.weights = {int(i): float(v) for i, v in payload["weights"]}  # type: ignore[misc]
        model.grad_sq = {int(i): float(v) for i, v in payload["grad_sq"]}  # type: ignore[misc]
        if set(model.weights) - set(model.grad_sq):
            raise ValueError("model optimizer state missing for trained weight")
        if any(i < 0 or i >= model.dimension for i in model.weights):
            raise ValueError("model weight index outside declared dimension")
        return model


def checkpoint_payload(
    model: SparseActionAdvantageModel, replay: DeterministicReservoir
) -> dict:
    base = {
        "schema": CHECKPOINT_SCHEMA,
        "model": model.payload(),
        "replay": replay.payload(),
    }
    base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
    return base


def save_checkpoint(
    path: Path, model: SparseActionAdvantageModel, replay: DeterministicReservoir
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(checkpoint_payload(model, replay))
    if path.suffix == ".gz":
        # gzip.open() does not expose mtime. GzipFile does, so force mtime=0 to
        # make compressed checkpoints byte-stable for equal logical payloads.
        with path.open("wb") as raw_handle:
            with gzip.GzipFile(
                fileobj=raw_handle, mode="wb", compresslevel=6, mtime=0
            ) as handle:
                handle.write(raw)
    else:
        path.write_bytes(raw)


def load_checkpoint(path: Path) -> tuple[SparseActionAdvantageModel, DeterministicReservoir]:
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("unsupported action-advantage checkpoint schema")
    raw = dict(payload)
    expected = str(raw.pop("sha256", ""))
    actual = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
    if expected != actual:
        raise ValueError("action-advantage checkpoint SHA-256 mismatch")
    model = SparseActionAdvantageModel.from_payload(raw["model"])
    replay = DeterministicReservoir.from_payload(raw["replay"])
    return model, replay
