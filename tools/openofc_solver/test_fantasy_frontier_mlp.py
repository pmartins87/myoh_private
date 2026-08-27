from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from fantasy_frontier_features import FEATURE_DIMENSION
from fantasy_frontier_mlp import DenseWorld, TerminalFrontierMLP, stack_worlds
from fantasy_frontier_mlp_eval import evaluate


def toy_world(world_id: int, kind: int) -> DenseWorld:
    x = np.zeros(FEATURE_DIMENSION, dtype=np.float32)
    x[0] = 1.0
    x[1 + (world_id % 4)] = 1.0
    x[10 + kind] = 1.0
    x[60 + (world_id % 13)] = 1.0
    if kind == 0:
        reachable = np.asarray([1.0, 0.0], dtype=np.float32)
        points = np.asarray([0.50, 0.0], dtype=np.float32)
    else:
        reachable = np.asarray([1.0, 1.0], dtype=np.float32)
        points = np.asarray([-0.20, 0.70], dtype=np.float32)
    return DenseWorld(
        key=f"toy-{world_id}-{kind}",
        world_id=world_id,
        fantasy_count=14 + (world_id % 4),
        joker_count=world_id % 3,
        x=x,
        reachable=reachable,
        points=points,
    )


def dataset() -> list[DenseWorld]:
    return [toy_world(i, i % 2) for i in range(40)]


def test_shape_and_deterministic_training() -> None:
    worlds = dataset()
    a = TerminalFrontierMLP(hidden1=24, hidden2=12, seed=77, learning_rate=0.01)
    b = TerminalFrontierMLP(hidden1=24, hidden2=12, seed=77, learning_rate=0.01)
    a.fit(worlds, epochs=25, batch_size=8)
    b.fit(worlds, epochs=25, batch_size=8)
    xa, _, _ = stack_worlds(worlds)
    pa = a.predict(xa)
    pb = b.predict(xa)
    assert np.array_equal(pa[0], pb[0])
    assert np.array_equal(pa[1], pb[1])
    assert pa[0].shape == (40, 2)
    assert pa[1].shape == (40, 2)


def test_model_learns_toy_reachability_and_scores() -> None:
    worlds = dataset()
    model = TerminalFrontierMLP(hidden1=32, hidden2=16, seed=88, learning_rate=0.01)
    model.fit(worlds, epochs=60, batch_size=10)
    metrics = evaluate(
        model,
        worlds,
        confidence_low=0.25,
        confidence_high=0.75,
        continuation_deltas=(-20.0, 0.0, 20.0),
    )
    assert metrics.reach_accuracy >= 0.95
    assert metrics.reachable_point_mae < 12.0
    assert metrics.confident_coverage >= 0.90
    assert metrics.utility_cases > 0


def test_save_load_preserves_predictions_and_optimizer_state() -> None:
    worlds = dataset()
    model = TerminalFrontierMLP(hidden1=20, hidden2=10, seed=99, learning_rate=0.005)
    model.fit(worlds, epochs=5, batch_size=8)
    x, _, _ = stack_worlds(worlds)
    before = model.predict(x)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "m4k_model.npz"
        digest = model.save(path)
        assert len(digest) == 64
        restored = TerminalFrontierMLP.load(path)
        after = restored.predict(x)
        assert np.array_equal(before[0], after[0])
        assert np.array_equal(before[1], after[1])
        # Resume both for one epoch and require identical continued training.
        model.fit(worlds, epochs=1, batch_size=8)
        restored.fit(worlds, epochs=1, batch_size=8)
        final_a = model.predict(x)
        final_b = restored.predict(x)
        assert np.array_equal(final_a[0], final_b[0])
        assert np.array_equal(final_a[1], final_b[1])


def main() -> None:
    test_shape_and_deterministic_training()
    test_model_learns_toy_reachability_and_scores()
    test_save_load_preserves_predictions_and_optimizer_state()
    print(
        "OPENOFC_M4K_TERMINAL_MLP=PASS "
        "cpu=NUMPY deterministic=YES resume=OPTIMIZER_EXACT "
        "outputs=BRANCH_REACHABILITY_AND_POINTS authority=PROBE_ONLY"
    )


if __name__ == "__main__":
    main()
