from __future__ import annotations

"""Bounded sparse terminal-frontier approximator for M4J.

This model is a probe, not an authority.  It receives the oracle-only lossless
terminal world features from M4I and predicts, separately for each branch,
(1) reachability and (2) exact immediate points conditional on reachability.

The feature map keeps exact direct coordinates and adds deterministic signed
pairwise interactions.  With at most 32 active world features, pairwise terms
are cheap while allowing the model to represent card-combination structure that
a purely additive linear model cannot learn.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping, Sequence

from fantasy_frontier_corpus import POINT_LIMIT
from fantasy_frontier_features import FEATURE_DIMENSION

MODEL_SCHEMA = "openofc-m4j-terminal-frontier-sparse-v1"
DEFAULT_PAIR_BUCKETS = 1 << 15
MASK64 = (1 << 64) - 1


def _mix64(value: int) -> int:
    x = value & MASK64
    x ^= x >> 30
    x = (x * 0xBF58476D1CE4E5B9) & MASK64
    x ^= x >> 27
    x = (x * 0x94D049BB133111EB) & MASK64
    x ^= x >> 31
    return x & MASK64


def _power_of_two(value: int) -> None:
    if value <= 0 or value & (value - 1):
        raise ValueError("pair bucket count must be a positive power of two")


@dataclass(frozen=True)
class FrontierExample:
    world_key: str
    world_features: tuple[int, ...]
    branch: int  # 0=no-refantasy, 1=refantasy
    reachable: bool
    points: int | None

    def __post_init__(self) -> None:
        if self.branch not in (0, 1):
            raise ValueError("frontier branch must be 0 or 1")
        if not self.world_key or not self.world_features:
            raise ValueError("frontier example requires key and features")
        if min(self.world_features) < 0 or max(self.world_features) >= FEATURE_DIMENSION:
            raise ValueError("frontier world feature outside declared dimension")
        if self.reachable != (self.points is not None):
            raise ValueError("reachability and exact point label disagree")
        if self.points is not None and not -POINT_LIMIT <= int(self.points) <= POINT_LIMIT:
            raise ValueError("frontier exact point outside proven HU bound")


def feature_terms(
    world_features: Sequence[int],
    branch: int,
    *,
    pair_buckets: int = DEFAULT_PAIR_BUCKETS,
) -> tuple[tuple[int, float], ...]:
    _power_of_two(pair_buckets)
    if branch not in (0, 1):
        raise ValueError("branch must be 0 or 1")
    features = tuple(sorted(set(int(x) for x in world_features)))
    if not features or features[0] < 0 or features[-1] >= FEATURE_DIMENSION:
        raise ValueError("invalid world feature vector")

    # Layout: bias | branch bias(2) | shared direct(F) | branch direct(2F)
    # | branch-specific signed pair hash(2B).
    branch_bias = 1 + branch
    shared_offset = 3
    branch_direct_offset = shared_offset + FEATURE_DIMENSION + branch * FEATURE_DIMENSION
    pair_offset = shared_offset + 3 * FEATURE_DIMENSION + branch * pair_buckets
    terms: dict[int, float] = {0: 1.0, branch_bias: 1.0}
    for feature in features:
        terms[shared_offset + feature] = 1.0
        terms[branch_direct_offset + feature] = 1.0
    for i, left in enumerate(features):
        for right in features[i + 1:]:
            seed = (
                ((left + 1) * 0x9E3779B185EBCA87)
                ^ ((right + 1) * 0xC2B2AE3D27D4EB4F)
                ^ ((branch + 1) * 0x165667B19E3779F9)
            ) & MASK64
            mixed = _mix64(seed)
            index = pair_offset + int(mixed & (pair_buckets - 1))
            sign = -1.0 if (mixed >> 63) else 1.0
            terms[index] = terms.get(index, 0.0) + sign
    return tuple(sorted((index, value) for index, value in terms.items() if value))


class SparseFrontierModel:
    def __init__(
        self,
        *,
        pair_buckets: int = DEFAULT_PAIR_BUCKETS,
        learning_rate: float = 0.06,
        l2: float = 1e-6,
        huber_delta: float = 0.25,
        seed: int = 20260826,
    ) -> None:
        _power_of_two(pair_buckets)
        if learning_rate <= 0 or l2 < 0 or huber_delta <= 0:
            raise ValueError("invalid frontier model hyperparameter")
        self.pair_buckets = int(pair_buckets)
        self.learning_rate = float(learning_rate)
        self.l2 = float(l2)
        self.huber_delta = float(huber_delta)
        self.seed = int(seed) & MASK64
        self.reach_w: dict[int, float] = {}
        self.reach_g2: dict[int, float] = {}
        self.point_w: dict[int, float] = {}
        self.point_g2: dict[int, float] = {}
        self.epochs = 0
        self.updates = 0

    @property
    def dimension(self) -> int:
        return 3 + 3 * FEATURE_DIMENSION + 2 * self.pair_buckets

    def _terms(self, example: FrontierExample):
        return feature_terms(
            example.world_features,
            example.branch,
            pair_buckets=self.pair_buckets,
        )

    @staticmethod
    def _dot(weights: Mapping[int, float], terms: Sequence[tuple[int, float]]) -> float:
        return sum(float(weights.get(i, 0.0)) * value for i, value in terms)

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            z = math.exp(-min(value, 60.0))
            return 1.0 / (1.0 + z)
        z = math.exp(max(value, -60.0))
        return z / (1.0 + z)

    def predict_reach_probability(self, example: FrontierExample) -> float:
        return self._sigmoid(self._dot(self.reach_w, self._terms(example)))

    def predict_points(self, example: FrontierExample) -> float:
        normalized = self._dot(self.point_w, self._terms(example))
        return max(-POINT_LIMIT, min(POINT_LIMIT, normalized * POINT_LIMIT))

    def _adagrad_update(
        self,
        weights: dict[int, float],
        accum: dict[int, float],
        terms: Sequence[tuple[int, float]],
        common_gradient: float,
    ) -> None:
        for index, value in terms:
            old = weights.get(index, 0.0)
            gradient = common_gradient * value + self.l2 * old
            g2 = accum.get(index, 0.0) + gradient * gradient
            accum[index] = g2
            weights[index] = old - self.learning_rate * gradient / math.sqrt(g2 + 1e-12)

    def update(self, example: FrontierExample) -> tuple[float, float | None]:
        terms = self._terms(example)
        reach_target = 1.0 if example.reachable else 0.0
        reach_logit = self._dot(self.reach_w, terms)
        reach_prob = self._sigmoid(reach_logit)
        self._adagrad_update(
            self.reach_w,
            self.reach_g2,
            terms,
            reach_prob - reach_target,
        )
        reach_loss = -(
            reach_target * math.log(max(reach_prob, 1e-12))
            + (1.0 - reach_target) * math.log(max(1.0 - reach_prob, 1e-12))
        )

        point_loss = None
        if example.points is not None:
            target = float(example.points) / POINT_LIMIT
            prediction = self._dot(self.point_w, terms)
            error = prediction - target
            if abs(error) <= self.huber_delta:
                gradient = error
                point_loss = 0.5 * error * error
            else:
                gradient = self.huber_delta if error > 0 else -self.huber_delta
                point_loss = self.huber_delta * (abs(error) - 0.5 * self.huber_delta)
            self._adagrad_update(self.point_w, self.point_g2, terms, gradient)
        self.updates += 1
        return reach_loss, point_loss

    def fit(self, examples: Sequence[FrontierExample], *, epochs: int = 1) -> dict[str, float]:
        if epochs <= 0 or not examples:
            raise ValueError("fit requires examples and positive epochs")
        reach_loss = 0.0
        point_loss = 0.0
        point_count = 0
        updates = 0
        for _ in range(epochs):
            epoch = self.epochs
            order = list(range(len(examples)))
            order.sort(
                key=lambda i: _mix64(
                    self.seed
                    ^ (epoch << 32)
                    ^ int.from_bytes(
                        hashlib.sha256(
                            (examples[i].world_key + f":{examples[i].branch}").encode("utf-8")
                        ).digest()[:8],
                        "big",
                    )
                )
            )
            for index in order:
                rl, pl = self.update(examples[index])
                reach_loss += rl
                if pl is not None:
                    point_loss += pl
                    point_count += 1
                updates += 1
            self.epochs += 1
        return {
            "mean_reach_logloss": reach_loss / updates,
            "mean_point_huber_normalized": point_loss / max(1, point_count),
            "examples": float(len(examples)),
            "epochs": float(self.epochs),
            "updates": float(self.updates),
            "reach_nonzero": float(len(self.reach_w)),
            "point_nonzero": float(len(self.point_w)),
        }

    def payload(self) -> dict:
        return {
            "schema": MODEL_SCHEMA,
            "pair_buckets": self.pair_buckets,
            "learning_rate": self.learning_rate,
            "l2": self.l2,
            "huber_delta": self.huber_delta,
            "seed": self.seed,
            "epochs": self.epochs,
            "updates": self.updates,
            "reach_w": [[i, v] for i, v in sorted(self.reach_w.items())],
            "reach_g2": [[i, v] for i, v in sorted(self.reach_g2.items())],
            "point_w": [[i, v] for i, v in sorted(self.point_w.items())],
            "point_g2": [[i, v] for i, v in sorted(self.point_g2.items())],
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "SparseFrontierModel":
        if payload.get("schema") != MODEL_SCHEMA:
            raise ValueError("unsupported M4J model schema")
        model = cls(
            pair_buckets=int(payload["pair_buckets"]),
            learning_rate=float(payload["learning_rate"]),
            l2=float(payload["l2"]),
            huber_delta=float(payload["huber_delta"]),
            seed=int(payload["seed"]),
        )
        model.epochs = int(payload["epochs"])
        model.updates = int(payload["updates"])
        for name in ("reach_w", "reach_g2", "point_w", "point_g2"):
            setattr(model, name, {int(i): float(v) for i, v in payload[name]})
        return model


def model_sha256(model: SparseFrontierModel) -> str:
    raw = json.dumps(model.payload(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
