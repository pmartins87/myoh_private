from __future__ import annotations

import hashlib
import json
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
from fantasy_fantasy_policy_model import (
    DeterministicFantasyReplay,
    SparseFantasyActionValueModel,
    save_checkpoint,
)
from fantasy_fantasy_proposals import FantasyProposalSet
from fantasy_fantasy_selfplay import SealedSupportEpisode, snapshot_episode_policy
from hu_bellman_iteration import continuation_sha256
from hu_bellman_rows import (
    BellmanRowArtifact,
    BellmanRowBundle,
    EXPECTED_KERNEL_COUNTS,
    assemble_bellman_image,
    coverage_report,
    merge_bundles,
)
from hu_continuation import (
    HUContinuationState,
    all_states,
    hand_kernel_kind,
    zero_continuation_values,
)
from m4s_fantasy_bellman_adapter import build_fantasy_rows_from_m4s
from run_m4s_multiseed import (
    CachedEpisode,
    cached_episode_payload,
    generator_fingerprint,
    save_cached_episode,
)


def certified_rows(values):
    fingerprint = continuation_sha256(values)
    return tuple(
        BellmanRowArtifact(
            state=state,
            input_continuation_fingerprint=fingerprint,
            value_p0=0.0,
            kernel_kind=hand_kernel_kind(state),
            solver_kind="unit-test",
            authority="UNIT_TEST_CERTIFIED",
            evidence_sha256="a" * 64,
            certified=True,
            error_bound_abs=0.1,
            samples=100,
        )
        for state in all_states()
    )


def test_exact_50_state_coverage_counts_and_certified_assembly() -> None:
    values = zero_continuation_values()
    rows = certified_rows(values)
    report = coverage_report(rows)
    assert report.total_rows == 50
    assert report.certified_rows == 50
    assert report.rows_by_kernel == EXPECTED_KERNEL_COUNTS
    assert report.certified_by_kernel == EXPECTED_KERNEL_COUNTS
    assert report.complete and report.fully_certified
    image = assemble_bellman_image(values, rows, iteration=4)
    assert len(image.estimates) == 50
    assert image.input_fingerprint == continuation_sha256(values)


def test_provisional_row_blocks_fail_closed_assembly() -> None:
    values = zero_continuation_values()
    rows = list(certified_rows(values))
    old = rows[0]
    rows[0] = BellmanRowArtifact(
        state=old.state,
        input_continuation_fingerprint=old.input_continuation_fingerprint,
        value_p0=old.value_p0,
        kernel_kind=old.kernel_kind,
        solver_kind="provisional-test",
        authority="PROVISIONAL",
        evidence_sha256="b" * 64,
        certified=False,
        error_bound_abs=None,
        samples=2,
    )
    try:
        assemble_bellman_image(values, rows, iteration=0)
    except ValueError as exc:
        assert "certified" in str(exc)
    else:
        raise AssertionError("provisional row entered certified Bellman image")
    exploratory = assemble_bellman_image(
        values, rows, iteration=0, require_certified=False
    )
    assert exploratory.estimates[old.state].error_bound_abs is None


def test_partial_bundle_merge_and_sha_roundtrip() -> None:
    values = zero_continuation_values()
    rows = certified_rows(values)
    fingerprint = continuation_sha256(values)
    left = BellmanRowBundle(fingerprint, rows[:17], "left")
    right = BellmanRowBundle(fingerprint, rows[17:], "right")
    merged = merge_bundles((left, right))
    assert coverage_report(merged.rows).complete
    payload = merged.payload()
    restored = BellmanRowBundle.from_payload(payload)
    assert restored.payload() == payload
    tampered = dict(payload)
    tampered["source"] = "tampered"
    try:
        BellmanRowBundle.from_payload(tampered)
    except ValueError as exc:
        assert "SHA" in str(exc)
    else:
        raise AssertionError("tampered Bellman row bundle was accepted")


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
    cards[0], cards[8] = cards[8], cards[0]
    b = arrangement_from_board(
        packet,
        Board(
            top=tuple(cards[0:3]),
            middle=tuple(cards[3:8]),
            bottom=tuple(cards[8:13]),
        ),
    )
    return a, b


def make_cached(seed: int, index: int, continuation_sha: str) -> CachedEpisode:
    current = HUContinuationState(0, 14, 14)
    world = FantasyFantasyWorld(
        current, sample_fantasy_fantasy_plan(random.Random(seed), current)
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
        canonical_action_keys=(f"p0-{index}-a", f"p0-{index}-b"),
        synthetic_worlds=1,
        exact_teacher_calls=1,
        max_candidates=2,
        visible_fingerprint=f"v0-{index}",
        continuation_fingerprint=continuation_sha,
    )
    proposal1 = FantasyProposalSet(
        player=1,
        current_meta=current,
        own_packet=world.plan.packet_for(1),
        candidates=support1,
        canonical_action_keys=(f"p1-{index}-a", f"p1-{index}-b"),
        synthetic_worlds=1,
        exact_teacher_calls=1,
        max_candidates=2,
        visible_fingerprint=f"v1-{index}",
        continuation_fingerprint=continuation_sha,
    )
    return CachedEpisode(
        split="heldout",
        world_index=index,
        world_seed=seed,
        generator_fingerprint=generator_fingerprint(
            base_seed=7,
            synthetic_worlds=1,
            max_candidates=2,
            continuation_sha=continuation_sha,
        ),
        episode=SealedSupportEpisode(world, support0, support1, matrix),
        proposal0=proposal0,
        proposal1=proposal1,
    )


def test_m4s_adapter_emits_provisional_ff_row_with_descriptive_evidence() -> None:
    values = zero_continuation_values()
    continuation_sha = continuation_sha256(values)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cache_dir = root / "episodes" / "heldout" / "B0_P0F14_P1F14"
        cached_rows = [make_cached(8801, 0, continuation_sha), make_cached(8802, 1, continuation_sha)]
        for cached in cached_rows:
            save_cached_episode(
                cache_dir / f"world_{cached.world_index:05d}.json", cached
            )

        model = SparseFantasyActionValueModel(buckets=1024, seed=3)
        replay = DeterministicFantasyReplay(capacity=16, seed=4)
        checkpoint = root / "M4S_MODEL_REPLAY.json.gz"
        save_checkpoint(checkpoint, model, replay)
        checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

        heldout = []
        for cached in cached_rows:
            snapshot = snapshot_episode_policy(model, cached.episode)
            heldout.append(
                {
                    "state": cached.episode.world.current_meta.as_key(),
                    "world_index": cached.world_index,
                    "p0_sampled_exact_support_gap": 0.25,
                    "p1_sampled_exact_support_gap": 0.75,
                    "profile_reference": snapshot.diagnostic.profile_p0_value,
                }
            )
        report = {
            "schema": "openofc-m4s-heldout-report-v1",
            "continuation_fingerprint": continuation_sha,
            "model_checkpoint_sha256": checkpoint_sha,
            "heldout": heldout,
        }
        report["sha256"] = hashlib.sha256(
            json.dumps(
                report, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        ).hexdigest()
        (root / "M4S_HELDOUT_REPORT.json").write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )

        bundle = build_fantasy_rows_from_m4s(root, continuation_values=values)
        assert len(bundle.rows) == 1
        row = bundle.rows[0]
        assert row.state == HUContinuationState(0, 14, 14)
        assert row.samples == 2
        assert not row.certified
        assert row.error_bound_abs is None
        assert row.diagnostics["support_gap_observations"] == 4
        assert abs(float(row.diagnostics["mean_sampled_exact_support_gap"]) - 0.5) <= 1e-12
        try:
            assemble_bellman_image(values, bundle.rows, iteration=0)
        except ValueError as exc:
            assert "incomplete" in str(exc)
        else:
            raise AssertionError("partial M4S bundle unexpectedly assembled a 50-state image")


def main() -> None:
    test_exact_50_state_coverage_counts_and_certified_assembly()
    test_provisional_row_blocks_fail_closed_assembly()
    test_partial_bundle_merge_and_sha_roundtrip()
    test_m4s_adapter_emits_provisional_ff_row_with_descriptive_evidence()
    print(
        "OPENOFC_M4U_BELLMAN_ROWS=PASS coverage=2_16_32 fail_closed=CERTIFIED_DEFAULT "
        "m4s_adapter=PROVISIONAL_FF evidence=SHA_BOUND"
    )


if __name__ == "__main__":
    main()
