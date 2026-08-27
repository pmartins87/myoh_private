from __future__ import annotations

import random
import tempfile
from pathlib import Path

from engine import Board
from fantasy_fantasy_kernel import (
    FantasyFantasyWorld,
    arrangement_from_board,
    sample_fantasy_fantasy_plan,
)
from fantasy_fantasy_payoff import build_exact_support_payoff_matrix
from fantasy_fantasy_policy_model import SparseFantasyActionValueModel
from fantasy_fantasy_proposals import FantasyProposalSet
from fantasy_fantasy_selfplay import SealedSupportEpisode
from hu_continuation import HUContinuationState, zero_continuation_values
from run_m4s_multiseed import (
    CachedEpisode,
    _parse_buttons,
    _parse_pairs,
    cached_episode_payload,
    generator_fingerprint,
    heldout_row,
    load_cached_episode,
    save_cached_episode,
)


def meta() -> HUContinuationState:
    return HUContinuationState(button=0, p0_fantasy_cards=14, p1_fantasy_cards=14)


def two_arrangements(packet):
    cards = list(packet)
    a = arrangement_from_board(
        packet,
        Board(
            top=tuple(cards[0:3]),
            middle=tuple(cards[3:8]),
            bottom=tuple(cards[8:13]),
        ),
    )
    cards[2], cards[10] = cards[10], cards[2]
    b = arrangement_from_board(
        packet,
        Board(
            top=tuple(cards[0:3]),
            middle=tuple(cards[3:8]),
            bottom=tuple(cards[8:13]),
        ),
    )
    return a, b


def fixture() -> CachedEpisode:
    current = meta()
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(4401), current)
    )
    support0 = two_arrangements(world.plan.packet_for(0))
    support1 = two_arrangements(world.plan.packet_for(1))
    matrix = build_exact_support_payoff_matrix(
        world, support0, support1, zero_continuation_values()
    )
    proposal0 = FantasyProposalSet(
        player=0,
        current_meta=current,
        own_packet=world.plan.packet_for(0),
        candidates=support0,
        canonical_action_keys=("p0a", "p0b"),
        synthetic_worlds=1,
        exact_teacher_calls=1,
        max_candidates=2,
        visible_fingerprint="visible-p0",
        continuation_fingerprint=matrix.continuation_fingerprint,
    )
    proposal1 = FantasyProposalSet(
        player=1,
        current_meta=current,
        own_packet=world.plan.packet_for(1),
        candidates=support1,
        canonical_action_keys=("p1a", "p1b"),
        synthetic_worlds=1,
        exact_teacher_calls=1,
        max_candidates=2,
        visible_fingerprint="visible-p1",
        continuation_fingerprint=matrix.continuation_fingerprint,
    )
    generator_sha = generator_fingerprint(
        base_seed=10,
        synthetic_worlds=1,
        max_candidates=2,
        continuation_sha=matrix.continuation_fingerprint,
    )
    return CachedEpisode(
        split="heldout",
        world_index=0,
        world_seed=4401,
        generator_fingerprint=generator_sha,
        episode=SealedSupportEpisode(world, support0, support1, matrix),
        proposal0=proposal0,
        proposal1=proposal1,
    )


def test_cached_episode_roundtrip_is_sha_bound_and_lossless() -> None:
    cached = fixture()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "episode.json"
        save_cached_episode(path, cached)
        loaded = load_cached_episode(path)
        assert cached_episode_payload(loaded) == cached_episode_payload(cached)
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('"world_seed": 4401', '"world_seed": 4402'), encoding="utf-8")
        try:
            load_cached_episode(path)
        except ValueError as exc:
            assert "SHA" in str(exc)
        else:
            raise AssertionError("tampered episode cache was accepted")


def test_generator_fingerprint_and_state_catalog_parsing_are_deterministic() -> None:
    a = generator_fingerprint(
        base_seed=1, synthetic_worlds=2, max_candidates=8, continuation_sha="abc"
    )
    b = generator_fingerprint(
        base_seed=1, synthetic_worlds=2, max_candidates=8, continuation_sha="abc"
    )
    c = generator_fingerprint(
        base_seed=1, synthetic_worlds=3, max_candidates=8, continuation_sha="abc"
    )
    assert a == b and a != c
    assert _parse_pairs(("14:17", "16:15"), False) == ((14, 17), (16, 15))
    assert len(_parse_pairs(None, True)) == 16
    assert _parse_buttons("1,0,1") == (1, 0)


def test_heldout_row_reports_three_budgets_without_exact_support_resolve() -> None:
    cached = fixture()
    model = SparseFantasyActionValueModel(buckets=1024, seed=5)
    row = heldout_row(
        model,
        cached,
        zero_continuation_values(),
        temperature=1.0,
        support_gap_samples=0,
        diagnostic_seed=99,
    )
    assert row["support_restricted_deviation"] >= 0.0
    assert row["action_value_mae"] >= 0.0
    assert row["action_value_max_abs_error"] >= row["action_value_mae"]
    assert row["p0_sampled_exact_support_gap"] is None
    assert row["p1_sampled_exact_support_gap"] is None
    assert row["support_gap_samples_per_player"] == 0


def main() -> None:
    test_cached_episode_roundtrip_is_sha_bound_and_lossless()
    test_generator_fingerprint_and_state_catalog_parsing_are_deterministic()
    test_heldout_row_reports_three_budgets_without_exact_support_resolve()
    print(
        "OPENOFC_M4S_MULTISEED_RUNNER=PASS cache=SHA_BOUND_NO_REGEN "
        "splits=TRAIN_HELDOUT budgets=THREE_PART pilot=F14_F14_DEFAULT"
    )


if __name__ == "__main__":
    main()
