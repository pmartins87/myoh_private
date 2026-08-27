from __future__ import annotations

"""Bounded generalizing action-value model for sealed Fantasy/Fantasy policy work.

This model consumes only M4P own-information state/action features.  Training
labels may come from offline complete-world evaluators, but hidden opponent cards
are never present in inference features.  M4Q is a bootstrap/generalization
milestone, not equilibrium authority.
"""

from dataclasses import dataclass
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from fantasy_fantasy_policy_features import FEATURE_DIMENSION, STATE_FEATURE_LIMIT

MODEL_SCHEMA = "openofc-m4q-fantasy-action-value-v1"
REPLAY_SCHEMA = "openofc-m4q-fantasy-replay-v1"
CHECKPOINT_SCHEMA = "openofc-m4q-fantasy-checkpoint-v1"
DEFAULT_INTERACTION_BUCKETS = 1 << 16
MASK64 = (1 << 64) - 1
AUTHORITY = "STRATEGIC_BOOTSTRAP_GENERALIZATION_NOT_EQUILIBRIUM"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _mix64(value: int) -> int:
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


def _validate_features(
    state_features: Sequence[int], action_features: Sequence[int]
) -> None:
    if not state_features or not action_features:
        raise ValueError("state and action features must be non-empty")
    if min(state_features) < 0 or max(state_features) >= STATE_FEATURE_LIMIT:
        raise ValueError("Fantasy state feature escaped declared state range")
    if min(action_features) < STATE_FEATURE_LIMIT or max(action_features) >= FEATURE_DIMENSION:
        raise ValueError("Fantasy action feature escaped declared action range")


def interaction_terms(
    state_features: Sequence[int],
    action_features: Sequence[int],
    *,
    buckets: int = DEFAULT_INTERACTION_BUCKETS,
) -> tuple[tuple[int, float], ...]:
    _require_power_of_two(buckets)
    _validate_features(state_features, action_features)
    action_span = FEATURE_DIMENSION - STATE_FEATURE_LIMIT
    interaction_offset = 1 + action_span
    terms: dict[int, float] = {0: 1.0}
    for action_feature in action_features:
        local_action = int(action_feature) - STATE_FEATURE_LIMIT
        direct = 1 + local_action
        terms[direct] = terms.get(direct, 0.0) + 1.0
        for state_feature in state_features:
            seed = (
                ((int(state_feature) + 1) * 0x9E3779B185EBCA87)
                ^ ((local_action + 1) * 0xC2B2AE3D27D4EB4F)
            ) & MASK64
            mixed = _mix64(seed)
            bucket = int(mixed & (buckets - 1))
            sign = -1.0 if (mixed >> 63) else 1.0
            index = interaction_offset + bucket
            terms[index] = terms.get(index, 0.0) + sign
    return tuple(sorted((i, v) for i, v in terms.items() if v))


@dataclass(frozen=True)
class FantasyPolicyExample:
    state_features: tuple[int, ...]
    action_features: tuple[int, ...]
    target: float
    weight: float = 1.0
    source: str = "m4p-support-matrix"

    def __post_init__(self) -> None:
        _validate_features(self.state_features, self.action_features)
        if not math.isfinite(self.target):
            raise ValueError("Fantasy action-value target must be finite")
        if not math.isfinite(self.weight) or self.weight <= 0.0:
            raise ValueError("Fantasy action-value weight must be positive and finite")
        if not self.source:
            raise ValueError("Fantasy action-value source must be non-empty")

    def payload(self) -> dict:
        return {
            "state": list(self.state_features),
            "action": list(self.action_features),
            "target": float(self.target),
            "weight": float(self.weight),
            "source": self.source,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "FantasyPolicyExample":
        return cls(
            state_features=tuple(int(x) for x in payload["state"]),  # type: ignore[index]
            action_features=tuple(int(x) for x in payload["action"]),  # type: ignore[index]
            target=float(payload["target"]),
            weight=float(payload["weight"]),
            source=str(payload["source"]),
        )


class DeterministicFantasyReplay:
    def __init__(self, *, capacity: int, seed: int = 20260828) -> None:
        if capacity <= 0:
            raise ValueError("replay capacity must be positive")
        self.capacity = int(capacity)
        self.seed = int(seed) & MASK64
        self.seen = 0
        self.items: list[FantasyPolicyExample] = []

    def add(self, example: FantasyPolicyExample) -> None:
        self.seen += 1
        if len(self.items) < self.capacity:
            self.items.append(example)
            return
        j = _mix64(self.seed ^ self.seen) % self.seen
        if j < self.capacity:
            self.items[int(j)] = example

    def extend(self, examples: Iterable[FantasyPolicyExample]) -> None:
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
    def from_payload(cls, payload: Mapping[str, object]) -> "DeterministicFantasyReplay":
        if payload.get("schema") != REPLAY_SCHEMA:
            raise ValueError("unsupported Fantasy replay schema")
        raw = dict(payload)
        expected = str(raw.pop("sha256", ""))
        actual = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
        if expected != actual:
            raise ValueError("Fantasy replay SHA-256 mismatch")
        replay = cls(capacity=int(raw["capacity"]), seed=int(raw["seed"]))
        replay.seen = int(raw["seen"])
        replay.items = [FantasyPolicyExample.from_payload(x) for x in raw["items"]]  # type: ignore[arg-type]
        if len(replay.items) > replay.capacity or replay.seen < len(replay.items):
            raise ValueError("corrupt Fantasy replay cardinality")
        return replay


class SparseFantasyActionValueModel:
    def __init__(
        self,
        *,
        buckets: int = DEFAULT_INTERACTION_BUCKETS,
        learning_rate: float = 0.08,
        l2: float = 1e-6,
        huber_delta: float = 1.0,
        seed: int = 20260828,
    ) -> None:
        _require_power_of_two(buckets)
        if learning_rate <= 0.0 or l2 < 0.0 or huber_delta <= 0.0:
            raise ValueError("invalid Fantasy model hyperparameter")
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
        return 1 + (FEATURE_DIMENSION - STATE_FEATURE_LIMIT) + self.buckets

    def predict_features(
        self, state_features: Sequence[int], action_features: Sequence[int]
    ) -> float:
        return sum(
            self.weights.get(index, 0.0) * value
            for index, value in interaction_terms(
                state_features, action_features, buckets=self.buckets
            )
        )

    def predict(self, example: FantasyPolicyExample) -> float:
        return self.predict_features(example.state_features, example.action_features)

    def update(self, example: FantasyPolicyExample) -> float:
        prediction = self.predict(example)
        error = prediction - example.target
        if abs(error) <= self.huber_delta:
            loss = 0.5 * error * error
            common = error
        else:
            loss = self.huber_delta * (abs(error) - 0.5 * self.huber_delta)
            common = self.huber_delta if error > 0.0 else -self.huber_delta
        common *= example.weight
        for index, value in interaction_terms(
            example.state_features, example.action_features, buckets=self.buckets
        ):
            old = self.weights.get(index, 0.0)
            gradient = common * value + self.l2 * old
            accum = self.grad_sq.get(index, 0.0) + gradient * gradient
            self.grad_sq[index] = accum
            self.weights[index] = old - (
                self.learning_rate * gradient / math.sqrt(accum + 1e-12)
            )
        self.updates += 1
        return float(loss * example.weight)

    def fit(
        self, replay: DeterministicFantasyReplay, *, epochs: int = 1
    ) -> dict[str, float]:
        if epochs <= 0 or not replay.items:
            raise ValueError("fit requires positive epochs and non-empty Fantasy replay")
        total_loss = 0.0
        updates = 0
        for _ in range(epochs):
            epoch = self.epochs_trained
            order = list(range(len(replay.items)))
            order.sort(key=lambda i: _mix64(self.seed ^ (epoch << 32) ^ i))
            for index in order:
                total_loss += self.update(replay.items[index])
                updates += 1
            self.epochs_trained += 1
        return {
            "mean_huber_loss": total_loss / max(1, updates),
            "examples": float(updates),
            "epochs_trained": float(self.epochs_trained),
            "updates": float(self.updates),
            "nonzero_weights": float(len(self.weights)),
        }

    def policy(
        self,
        state_features: Sequence[int],
        action_features: Sequence[Sequence[int]],
        *,
        temperature: float = 1.0,
    ) -> list[float]:
        if not action_features or not math.isfinite(temperature) or temperature <= 0.0:
            raise ValueError("policy requires actions and positive finite temperature")
        scores = [
            self.predict_features(state_features, action) / temperature
            for action in action_features
        ]
        peak = max(scores)
        weights = [math.exp(score - peak) for score in scores]
        total = sum(weights)
        return [weight / total for weight in weights]

    def payload(self) -> dict:
        return {
            "schema": MODEL_SCHEMA,
            "authority": AUTHORITY,
            "buckets": self.buckets,
            "learning_rate": self.learning_rate,
            "l2": self.l2,
            "huber_delta": self.huber_delta,
            "seed": self.seed,
            "epochs_trained": self.epochs_trained,
            "updates": self.updates,
            "weights": [[i, v] for i, v in sorted(self.weights.items())],
            "grad_sq": [[i, v] for i, v in sorted(self.grad_sq.items())],
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "SparseFantasyActionValueModel":
        if payload.get("schema") != MODEL_SCHEMA or payload.get("authority") != AUTHORITY:
            raise ValueError("unsupported Fantasy action-value model schema/authority")
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
            raise ValueError("Fantasy model optimizer state missing")
        if any(index < 0 or index >= model.dimension for index in model.weights):
            raise ValueError("Fantasy model weight outside declared dimension")
        return model


def checkpoint_payload(
    model: SparseFantasyActionValueModel,
    replay: DeterministicFantasyReplay,
) -> dict:
    base = {
        "schema": CHECKPOINT_SCHEMA,
        "model": model.payload(),
        "replay": replay.payload(),
    }
    base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
    return base


def save_checkpoint(
    path: Path,
    model: SparseFantasyActionValueModel,
    replay: DeterministicFantasyReplay,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canonical_bytes(checkpoint_payload(model, replay))
    if path.suffix == ".gz":
        with path.open("wb") as raw_handle:
            with gzip.GzipFile(fileobj=raw_handle, mode="wb", compresslevel=6, mtime=0) as handle:
                handle.write(raw)
    else:
        path.write_bytes(raw)


def load_checkpoint(
    path: Path,
) -> tuple[SparseFantasyActionValueModel, DeterministicFantasyReplay]:
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as handle:
            payload = json.loads(handle.read().decode("utf-8"))
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("unsupported Fantasy checkpoint schema")
    raw = dict(payload)
    expected = str(raw.pop("sha256", ""))
    actual = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
    if expected != actual:
        raise ValueError("Fantasy checkpoint SHA-256 mismatch")
    return (
        SparseFantasyActionValueModel.from_payload(raw["model"]),
        DeterministicFantasyReplay.from_payload(raw["replay"]),
    )
