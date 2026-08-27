from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random

from engine import Board
from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
)
from hu_continuation import HUContinuationState, zero_continuation_values
from m4w_outcome_model import SparseFantasyOutcomeModel
from m4x_robust_support import freeze_continuation_family
from m5a_fantasy_fantasy_oracle import model_fingerprint
from m5b_fantasy_selfplay import ContinuationAwareEpisode
from m5f_fantasy_heldout_evidence import (
    FantasyEvidenceBudgets,
    HeldoutFantasyEpisode,
    collect_fantasy_route_evidence,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def three_arrangements(packet):
    cards = list(packet)
    out = []
    for left, right in ((0, 9), (1, 10), (2, 11)):
        x = list(cards)
        x[left], x[right] = x[right], x[left]
        out.append(
            arrangement_from_board(
                packet,
                Board(
                    top=tuple(x[0:3]),
                    middle=tuple(x[3:8]),
                    bottom=tuple(x[8:13]),
                ),
            )
        )
    return tuple(out)


@dataclass(frozen=True)
class FixtureRobustSupport:
    player: int
    current_meta: HUContinuationState
    candidates: tuple
    family_sha256: str


@dataclass(frozen=True)
class FixtureSnapshot:
    model_sha256: str
    family_sha256: str


class FixtureOracle:
    def __init__(self, model, family) -> None:
        self.model = model
        self.family = family
        self.snapshot = FixtureSnapshot(
            model_sha256=model_fingerprint(model),
            family_sha256=family.sha256,
        )
        self.oracle_id = "m5f-heldout-fixture-oracle"


def _family():
    return freeze_continuation_family(
        {"zero-anchor": zero_continuation_values()},
        radius_linf=0.0,
        provenance="M5F deterministic held-out fixture family",
        source_sha256=_sha("m5f-family-source"),
    )


def _heldout_rows(meta, family):
    rows = []
    for seed in (20260911, 20260912):
        world = FantasyFantasyWorld(
            meta,
            sample_fantasy_fantasy_plan(random.Random(seed), meta),
        )
        support0 = three_arrangements(world.plan.packet_for(0))
        support1 = three_arrangements(world.plan.packet_for(1))
        episode = ContinuationAwareEpisode.build(world, support0, support1)
        rows.append(
            HeldoutFantasyEpisode(
                seed=seed,
                episode=episode,
                p0_support=FixtureRobustSupport(
                    player=0,
                    current_meta=meta,
                    candidates=support0,
                    family_sha256=family.sha256,
                ),
                p1_support=FixtureRobustSupport(
                    player=1,
                    current_meta=meta,
                    candidates=support1,
                    family_sha256=family.sha256,
                ),
            )
        )
    return tuple(rows)


def _wide_budgets(*, max_support_gap: float = 0.02):
    return FantasyEvidenceBudgets(
        max_support_gap=max_support_gap,
        max_support_deviation_gain=100.0,
        max_model_q_mae=100.0,
        max_model_q_error=100.0,
        max_standard_error=100.0,
    )


def fixture_support_gap(_support, _opponent_board, _values):
    return 0.01


def test_real_metric_pipeline_is_deterministic_with_fixture_m4n_hook() -> None:
    meta = HUContinuationState(1, 14, 15)
    family = _family()
    values = zero_continuation_values()
    heldout = _heldout_rows(meta, family)

    model_a = SparseFantasyOutcomeModel(buckets=1024, seed=717)
    model_b = SparseFantasyOutcomeModel(buckets=1024, seed=717)
    oracle_a = FixtureOracle(model_a, family)
    oracle_b = FixtureOracle(model_b, family)

    kwargs = dict(
        state=meta,
        continuation_values=values,
        heldout=heldout,
        budgets=_wide_budgets(),
        implementation_sha256=_sha("m5f-implementation"),
        reference_authority="M4N_EXACT_INTERFACE_CI_FIXTURE_HOOK",
        provenance="M5F deterministic pipeline regression",
        support_gap_evaluator=fixture_support_gap,
    )
    a = collect_fantasy_route_evidence(oracle_a, **kwargs)
    b = collect_fantasy_route_evidence(oracle_b, **kwargs)

    assert a.report.sha256 == b.report.sha256
    assert a.route_evidence["sha256"] == b.route_evidence["sha256"]
    assert a.report.worlds == 2
    assert a.report.distinct_seeds == 2
    assert a.report.q_targets == 12
    assert abs(a.report.max_support_gap - 0.01) <= 1e-12
    assert a.report.max_support_deviation_gain >= 0.0
    assert a.report.model_q_mae >= 0.0
    assert a.report.model_q_max_error >= a.report.model_q_mae
    assert a.report.standard_error >= 0.0
    assert a.route_evidence["passed"] is True
    assert a.route_evidence["promotion_blocked"] is True
    assert a.report.promotion_blocked is True


def test_explicit_support_gap_budget_can_fail_same_evidence() -> None:
    meta = HUContinuationState(0, 14, 14)
    family = _family()
    oracle = FixtureOracle(
        SparseFantasyOutcomeModel(buckets=1024, seed=818), family
    )
    result = collect_fantasy_route_evidence(
        oracle,
        meta,
        zero_continuation_values(),
        _heldout_rows(meta, family),
        _wide_budgets(max_support_gap=0.005),
        implementation_sha256=_sha("m5f-budget-fail-implementation"),
        reference_authority="M4N_EXACT_INTERFACE_CI_FIXTURE_HOOK",
        provenance="M5F threshold separation regression",
        support_gap_evaluator=fixture_support_gap,
    )
    assert result.report.max_support_gap == 0.01
    assert result.route_evidence["passed"] is False
    assert result.route_evidence["thresholds"]["max_support_gap"] == 0.005


def test_wrong_state_and_family_fail_closed() -> None:
    meta = HUContinuationState(1, 14, 15)
    family = _family()
    oracle = FixtureOracle(
        SparseFantasyOutcomeModel(buckets=1024, seed=919), family
    )
    heldout = _heldout_rows(meta, family)

    try:
        collect_fantasy_route_evidence(
            oracle,
            HUContinuationState(0, 14, 15),
            zero_continuation_values(),
            heldout,
            _wide_budgets(),
            implementation_sha256=_sha("wrong-state"),
            reference_authority="fixture",
            provenance="wrong state should fail",
            support_gap_evaluator=fixture_support_gap,
        )
    except ValueError as exc:
        assert "another route state" in str(exc)
    else:
        raise AssertionError("M5F accepted held-out worlds from another route")

    other_family = freeze_continuation_family(
        {"zero-anchor": zero_continuation_values()},
        radius_linf=0.0,
        provenance="different family",
        source_sha256=_sha("different-family-source"),
    )
    other_oracle = FixtureOracle(
        SparseFantasyOutcomeModel(buckets=1024, seed=920), other_family
    )
    try:
        collect_fantasy_route_evidence(
            other_oracle,
            meta,
            zero_continuation_values(),
            heldout,
            _wide_budgets(),
            implementation_sha256=_sha("wrong-family"),
            reference_authority="fixture",
            provenance="wrong family should fail",
            support_gap_evaluator=fixture_support_gap,
        )
    except ValueError as exc:
        assert "another M4X family" in str(exc)
    else:
        raise AssertionError("M5F accepted held-out supports from another family")


def main() -> None:
    test_real_metric_pipeline_is_deterministic_with_fixture_m4n_hook()
    test_explicit_support_gap_budget_can_fail_same_evidence()
    test_wrong_state_and_family_fail_closed()
    print("OPENOFC_M5F_FANTASY_HELDOUT_EVIDENCE_GATE=PASS")


if __name__ == "__main__":
    main()
