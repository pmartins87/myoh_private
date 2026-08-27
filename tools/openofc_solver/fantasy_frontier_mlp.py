from __future__ import annotations

"""Compact CPU MLP for M4K terminal Fantasy-frontier distillation.

The M4J sparse linear/pairwise probe established the data/evaluation plumbing,
but its tiny smoke corpus also showed that a low-capacity regressor should not
be treated as a likely final model.  M4K adds a small dense neural model that is
still practical on a Ryzen CPU and trivial to export to C++ later.

This module is oracle-only: its input contains the sampled hidden Fantasy packet
and must never be reused as a normal-player information-set policy encoder.
"""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from fantasy_frontier_corpus import POINT_LIMIT, iter_rows
from fantasy_frontier_features import FEATURE_DIMENSION, encode_canonical_world_key

MODEL_SCHEMA = "openofc-m4k-terminal-frontier-mlp-v1"
ARTIFACT_SCHEMA = "openofc-m4k-terminal-frontier-mlp-artifact-v1"


@dataclass(frozen=True)
class DenseWorld:
    key: str
    world_id: int
    fantasy_count: int
    joker_count: int
    x: np.ndarray
    reachable: np.ndarray  # shape (2,), float32 0/1
    points: np.ndarray  # shape (2,), normalized; ignored where unreachable


def _joker_count_from_key(key: str) -> int:
    payload = json.loads(key)
    return sum(1 for token in payload["packet"] if str(token).startswith("X"))


def row_to_world(row: dict) -> DenseWorld:
    key = str(row["canonical_world_key"])
    indices = encode_canonical_world_key(key)
    x = np.zeros(FEATURE_DIMENSION, dtype=np.float32)
    x[list(indices)] = 1.0
    no = row.get("no_refantasy_points")
    ref = row.get("refantasy_points")
    reachable = np.asarray([no is not None, ref is not None], dtype=np.float32)
    points = np.zeros(2, dtype=np.float32)
    if no is not None:
        points[0] = float(no) / POINT_LIMIT
    if ref is not None:
        points[1] = float(ref) / POINT_LIMIT
    return DenseWorld(
        key=key,
        world_id=int(row["world_id"]),
        fantasy_count=int(row["fantasy_count"]),
        joker_count=_joker_count_from_key(key),
        x=x,
        reachable=reachable,
        points=points,
    )


def load_worlds(paths: Iterable[Path], *, holdout: bool) -> list[DenseWorld]:
    worlds: list[DenseWorld] = []
    for path in paths:
        for row in iter_rows(path):
            is_holdout = int(row["world_id"]) % 5 == 0
            if is_holdout == holdout:
                worlds.append(row_to_world(row))
    return worlds


def stack_worlds(worlds: Sequence[DenseWorld]):
    if not worlds:
        raise ValueError("cannot stack an empty world set")
    x = np.stack([world.x for world in worlds]).astype(np.float32, copy=False)
    reach = np.stack([world.reachable for world in worlds]).astype(np.float32, copy=False)
    points = np.stack([world.points for world in worlds]).astype(np.float32, copy=False)
    return x, reach, points


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)


class TerminalFrontierMLP:
    def __init__(
        self,
        *,
        hidden1: int = 128,
        hidden2: int = 64,
        seed: int = 20260826,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        huber_delta: float = 0.20,
    ) -> None:
        if hidden1 <= 0 or hidden2 <= 0:
            raise ValueError("hidden dimensions must be positive")
        if learning_rate <= 0 or weight_decay < 0 or huber_delta <= 0:
            raise ValueError("invalid MLP hyperparameter")
        self.hidden1 = int(hidden1)
        self.hidden2 = int(hidden2)
        self.seed = int(seed)
        self.learning_rate = float(learning_rate)
        self.weight_decay = float(weight_decay)
        self.huber_delta = float(huber_delta)
        rng = np.random.default_rng(self.seed)
        self.params = {
            "w1": (rng.normal(0.0, math.sqrt(2.0 / FEATURE_DIMENSION),
                              (FEATURE_DIMENSION, self.hidden1))).astype(np.float32),
            "b1": np.zeros(self.hidden1, dtype=np.float32),
            "w2": (rng.normal(0.0, math.sqrt(2.0 / self.hidden1),
                              (self.hidden1, self.hidden2))).astype(np.float32),
            "b2": np.zeros(self.hidden2, dtype=np.float32),
            "w3": (rng.normal(0.0, math.sqrt(1.0 / self.hidden2),
                              (self.hidden2, 4))).astype(np.float32),
            "b3": np.zeros(4, dtype=np.float32),
        }
        self.m = {name: np.zeros_like(value) for name, value in self.params.items()}
        self.v = {name: np.zeros_like(value) for name, value in self.params.items()}
        self.step = 0
        self.epochs = 0

    def _forward(self, x: np.ndarray):
        z1 = x @ self.params["w1"] + self.params["b1"]
        h1 = _relu(z1)
        z2 = h1 @ self.params["w2"] + self.params["b2"]
        h2 = _relu(z2)
        out = h2 @ self.params["w3"] + self.params["b3"]
        reach_logits = out[:, :2]
        point_raw = out[:, 2:]
        point_pred = np.tanh(point_raw)
        cache = (x, z1, h1, z2, h2, reach_logits, point_raw, point_pred)
        return reach_logits, point_pred, cache

    def predict(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        reach_logits, points, _cache = self._forward(x.astype(np.float32, copy=False))
        return _sigmoid(reach_logits), points * POINT_LIMIT

    def _loss_and_grads(
        self,
        x: np.ndarray,
        reach_target: np.ndarray,
        point_target: np.ndarray,
    ):
        reach_logits, point_pred, cache = self._forward(x)
        _, z1, h1, z2, h2, _, _, _ = cache
        batch = float(x.shape[0])
        reach_prob = _sigmoid(reach_logits)
        eps = 1e-7
        reach_loss = -np.mean(
            reach_target * np.log(reach_prob + eps)
            + (1.0 - reach_target) * np.log(1.0 - reach_prob + eps)
        )
        d_reach = (reach_prob - reach_target) / (batch * 2.0)

        mask = reach_target
        point_error = point_pred - point_target
        abs_error = np.abs(point_error)
        delta = self.huber_delta
        quadratic = np.minimum(abs_error, delta)
        linear = abs_error - quadratic
        point_loss_matrix = 0.5 * quadratic * quadratic + delta * linear
        denom = max(1.0, float(mask.sum()))
        point_loss = float((point_loss_matrix * mask).sum() / denom)
        d_point_pred = np.where(abs_error <= delta, point_error, delta * np.sign(point_error))
        d_point_pred = d_point_pred * mask / denom
        d_point_raw = d_point_pred * (1.0 - point_pred * point_pred)

        d_out = np.concatenate([d_reach, d_point_raw], axis=1).astype(np.float32)
        grads: dict[str, np.ndarray] = {}
        grads["w3"] = h2.T @ d_out + self.weight_decay * self.params["w3"]
        grads["b3"] = d_out.sum(axis=0)
        d_h2 = d_out @ self.params["w3"].T
        d_z2 = d_h2 * (z2 > 0.0)
        grads["w2"] = h1.T @ d_z2 + self.weight_decay * self.params["w2"]
        grads["b2"] = d_z2.sum(axis=0)
        d_h1 = d_z2 @ self.params["w2"].T
        d_z1 = d_h1 * (z1 > 0.0)
        grads["w1"] = x.T @ d_z1 + self.weight_decay * self.params["w1"]
        grads["b1"] = d_z1.sum(axis=0)
        return float(reach_loss), float(point_loss), grads

    def _adam(self, grads: dict[str, np.ndarray]) -> None:
        self.step += 1
        beta1, beta2 = 0.9, 0.999
        for name, grad in grads.items():
            self.m[name] = beta1 * self.m[name] + (1.0 - beta1) * grad
            self.v[name] = beta2 * self.v[name] + (1.0 - beta2) * (grad * grad)
            mhat = self.m[name] / (1.0 - beta1 ** self.step)
            vhat = self.v[name] / (1.0 - beta2 ** self.step)
            self.params[name] -= self.learning_rate * mhat / (np.sqrt(vhat) + 1e-8)

    def fit(
        self,
        worlds: Sequence[DenseWorld],
        *,
        epochs: int = 10,
        batch_size: int = 256,
    ) -> dict[str, float]:
        if not worlds or epochs <= 0 or batch_size <= 0:
            raise ValueError("fit requires worlds, positive epochs and batch size")
        x, reach, points = stack_worlds(worlds)
        total_reach = 0.0
        total_point = 0.0
        batches = 0
        for _ in range(epochs):
            epoch = self.epochs
            rng = np.random.default_rng(self.seed ^ (epoch * 0x9E3779B1))
            order = rng.permutation(len(worlds))
            for start in range(0, len(order), batch_size):
                idx = order[start:start + batch_size]
                rl, pl, grads = self._loss_and_grads(x[idx], reach[idx], points[idx])
                self._adam(grads)
                total_reach += rl
                total_point += pl
                batches += 1
            self.epochs += 1
        return {
            "epochs": float(self.epochs),
            "optimizer_steps": float(self.step),
            "mean_reach_loss": total_reach / max(1, batches),
            "mean_point_huber_normalized": total_point / max(1, batches),
            "parameter_count": float(sum(value.size for value in self.params.values())),
        }

    def save(self, path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "schema": MODEL_SCHEMA,
            "hidden1": self.hidden1,
            "hidden2": self.hidden2,
            "seed": self.seed,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "huber_delta": self.huber_delta,
            "step": self.step,
            "epochs": self.epochs,
        }
        arrays = {**self.params, **{f"m_{k}": v for k, v in self.m.items()},
                  **{f"v_{k}": v for k, v in self.v.items()}}
        arrays["metadata"] = np.asarray(json.dumps(metadata, sort_keys=True))
        np.savez_compressed(path, **arrays)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest

    @classmethod
    def load(cls, path: Path) -> "TerminalFrontierMLP":
        with np.load(path, allow_pickle=False) as data:
            metadata = json.loads(str(data["metadata"].item()))
            if metadata.get("schema") != MODEL_SCHEMA:
                raise ValueError("unsupported M4K model schema")
            model = cls(
                hidden1=int(metadata["hidden1"]),
                hidden2=int(metadata["hidden2"]),
                seed=int(metadata["seed"]),
                learning_rate=float(metadata["learning_rate"]),
                weight_decay=float(metadata["weight_decay"]),
                huber_delta=float(metadata["huber_delta"]),
            )
            for name in model.params:
                model.params[name] = data[name].astype(np.float32, copy=True)
                model.m[name] = data[f"m_{name}"].astype(np.float32, copy=True)
                model.v[name] = data[f"v_{name}"].astype(np.float32, copy=True)
            model.step = int(metadata["step"])
            model.epochs = int(metadata["epochs"])
        return model
