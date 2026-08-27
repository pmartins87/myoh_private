from __future__ import annotations

from fantasy_frontier_model import FrontierExample, SparseFrontierModel, feature_terms
from fantasy_frontier_features import FEATURE_DIMENSION
from fantasy_frontier_distillation import evaluate_model


def ex(key: str, features, branch: int, reachable: bool, points):
    return FrontierExample(key, tuple(features), branch, reachable, points)


def toy_examples():
    # Two distinct worlds with deliberately opposite branch structure. Feature 0
    # is the shared bias coordinate from the M4I world contract; the second
    # coordinate distinguishes the worlds.
    a = (0, 1, 5, 59, 120)
    b = (0, 2, 6, 60, 121)
    return [
        ex("A", a, 0, True, 12),
        ex("A", a, 1, False, None),
        ex("B", b, 0, False, None),
        ex("B", b, 1, True, -7),
    ]


def test_feature_terms_are_branch_conditioned_and_bounded() -> None:
    features = (0, 1, 5, 59, 120)
    left = feature_terms(features, 0, pair_buckets=256)
    right = feature_terms(features, 1, pair_buckets=256)
    assert left != right
    dimension = 3 + 3 * FEATURE_DIMENSION + 2 * 256
    assert min(i for i, _ in left) >= 0
    assert max(i for i, _ in left) < dimension
    assert max(i for i, _ in right) < dimension


def test_model_learns_toy_branch_reachability_and_points_deterministically() -> None:
    examples = toy_examples()
    first = SparseFrontierModel(pair_buckets=512, learning_rate=0.12, seed=77)
    second = SparseFrontierModel(pair_buckets=512, learning_rate=0.12, seed=77)
    first.fit(examples, epochs=80)
    second.fit(examples, epochs=80)
    assert first.payload() == second.payload()
    for example in examples:
        probability = first.predict_reach_probability(example)
        assert (probability >= 0.5) == example.reachable
        if example.points is not None:
            assert abs(first.predict_points(example) - example.points) < 8.0


def test_confident_terminal_utility_diagnostic_is_finite() -> None:
    examples = toy_examples()
    model = SparseFrontierModel(pair_buckets=512, learning_rate=0.12, seed=88)
    model.fit(examples, epochs=100)
    metrics = evaluate_model(
        model,
        examples,
        confidence_low=0.25,
        confidence_high=0.75,
        continuation_deltas=(-20.0, 0.0, 20.0),
    )
    assert metrics.worlds == 2
    assert metrics.branch_examples == 4
    assert 0.0 <= metrics.reach_accuracy <= 1.0
    assert metrics.reachable_point_mae >= 0.0
    assert 0.0 <= metrics.confident_coverage <= 1.0
    assert metrics.utility_mean_abs_error >= 0.0


def main() -> None:
    test_feature_terms_are_branch_conditioned_and_bounded()
    test_model_learns_toy_branch_reachability_and_points_deterministically()
    test_confident_terminal_utility_diagnostic_is_finite()
    print(
        "OPENOFC_M4J_TERMINAL_MODEL=PASS "
        "features=PAIRWISE_BRANCH_CONDITIONED model=DETERMINISTIC "
        "metrics=REACHABILITY_POINTS_AND_CONTINUATION_UTILITY"
    )


if __name__ == "__main__":
    main()
