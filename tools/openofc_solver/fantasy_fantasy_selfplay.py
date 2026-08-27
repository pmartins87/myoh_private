from __future__ import annotations

"""Synchronous generalized self-play probe for sealed Fantasy/Fantasy HU.

The policy-facing function accepts only one player's private packet, public
meta-state and candidate support.  Complete-world M4P matrices are used solely
inside offline training/evaluation to turn the opponent's current sealed policy
into exact candidate action-value targets.

This is fitted self-play research plumbing, not an equilibrium certificate.
"""

from dataclasses import dataclass
import inspect
import math
from typing import Sequence

from engine import Card
from fantasy_fantasy_bootstrap import BootstrapTargetBatch, build_bootstrap_targets
from fantasy_fantasy_kernel import FantasyArrangement, FantasyFantasyWorld
from fantasy_fantasy_payoff import (
    FantasySupportPayoffMatrix,
    SupportDeviationDiagnostic,
    support_deviation_diagnostic,
)
from fantasy_fantasy_policy_features import encode_policy_action, encode_policy_state
from fantasy_fantasy_policy_model import (
    DeterministicFantasyReplay,
    SparseFantasyActionValueModel,
)
from hu_continuation import HUContinuationState

AUTHORITY = "GENERALIZED_SEALED_SELFPLAY_PROBE_NOT_EQUILIBRIUM"


@dataclass(frozen=True)
class SealedSupportEpisode:
    world: FantasyFantasyWorld
    p0_support: tuple[FantasyArrangement, ...]
    p1_support: tuple[FantasyArrangement, ...]
    matrix: FantasySupportPayoffMatrix

    def __post_init__(self) -> None:
        if self.matrix.current_meta != self.world.current_meta:
            raise ValueError("episode matrix/meta mismatch")
        if self.matrix.shape != (len(self.p0_support), len(self.p1_support)):
            raise ValueError("episode support/matrix shape mismatch")


@dataclass(frozen=True)
class EpisodePolicySnapshot:
    p0_policy: tuple[float, ...]
    p1_policy: tuple[float, ...]
    diagnostic: SupportDeviationDiagnostic


@dataclass(frozen=True)
class SelfPlayIterationReport:
    episodes: int
    examples_added: int
    replay_size: int
    replay_seen: int
    mean_support_deviation_before: float
    mean_support_deviation_after: float
    max_support_deviation_before: float
    max_support_deviation_after: float
    fit_mean_huber_loss: float
    authority: str = AUTHORITY


def policy_for_private_support(
    model: SparseFantasyActionValueModel,
    own_packet: Sequence[Card],
    support: Sequence[FantasyArrangement],
    *,
    current_meta: HUContinuationState,
    player: int,
    temperature: float = 1.0,
) -> tuple[float, ...]:
    """Infer a sealed support policy without any opponent-card argument."""
    candidates = tuple(support)
    if not candidates:
        raise ValueError("sealed policy requires non-empty candidate support")
    state = encode_policy_state(
        tuple(own_packet), current_meta=current_meta, player=player
    )
    actions = [
        encode_policy_action(
            tuple(own_packet),
            arrangement,
            current_meta=current_meta,
            player=player,
        )
        for arrangement in candidates
    ]
    return tuple(model.policy(state, actions, temperature=temperature))


def snapshot_episode_policy(
    model: SparseFantasyActionValueModel,
    episode: SealedSupportEpisode,
    *,
    temperature: float = 1.0,
) -> EpisodePolicySnapshot:
    sigma0 = policy_for_private_support(
        model,
        episode.world.plan.packet_for(0),
        episode.p0_support,
        current_meta=episode.world.current_meta,
        player=0,
        temperature=temperature,
    )
    sigma1 = policy_for_private_support(
        model,
        episode.world.plan.packet_for(1),
        episode.p1_support,
        current_meta=episode.world.current_meta,
        player=1,
        temperature=temperature,
    )
    diagnostic = support_deviation_diagnostic(episode.matrix, sigma0, sigma1)
    return EpisodePolicySnapshot(sigma0, sigma1, diagnostic)


def exact_selfplay_targets(
    model: SparseFantasyActionValueModel,
    episode: SealedSupportEpisode,
    *,
    temperature: float = 1.0,
) -> tuple[EpisodePolicySnapshot, BootstrapTargetBatch]:
    """Freeze current sealed policies, then compute exact synchronous Q targets."""
    snapshot = snapshot_episode_policy(model, episode, temperature=temperature)
    batch = build_bootstrap_targets(
        episode.world,
        episode.p0_support,
        episode.p1_support,
        episode.matrix,
        p0_opponent_policy=snapshot.p1_policy,
        p1_opponent_policy=snapshot.p0_policy,
        source="m4r-exact-current-policy-selfplay",
    )
    return snapshot, batch


def _mean(values: Sequence[float]) -> float:
    return sum(values) / float(len(values)) if values else 0.0


def train_selfplay_iteration(
    model: SparseFantasyActionValueModel,
    replay: DeterministicFantasyReplay,
    episodes: Sequence[SealedSupportEpisode],
    *,
    epochs: int = 1,
    temperature: float = 1.0,
) -> SelfPlayIterationReport:
    """Run one synchronous fitted self-play iteration over frozen exact matrices."""
    episode_rows = tuple(episodes)
    if not episode_rows:
        raise ValueError("self-play iteration requires at least one episode")
    if epochs <= 0 or not math.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("invalid self-play fit parameters")

    before = []
    batches = []
    for episode in episode_rows:
        snapshot, batch = exact_selfplay_targets(
            model, episode, temperature=temperature
        )
        before.append(snapshot.diagnostic.total_support_deviation_gain)
        batches.append(batch)

    examples_added = 0
    for batch in batches:
        examples = batch.p0_examples + batch.p1_examples
        replay.extend(examples)
        examples_added += len(examples)

    fit = model.fit(replay, epochs=epochs)
    after = [
        snapshot_episode_policy(
            model, episode, temperature=temperature
        ).diagnostic.total_support_deviation_gain
        for episode in episode_rows
    ]
    if any(not math.isfinite(value) or value < -1e-9 for value in before + after):
        raise AssertionError("self-play support diagnostic became invalid")

    return SelfPlayIterationReport(
        episodes=len(episode_rows),
        examples_added=examples_added,
        replay_size=len(replay.items),
        replay_seen=replay.seen,
        mean_support_deviation_before=_mean(before),
        mean_support_deviation_after=_mean(after),
        max_support_deviation_before=max(before),
        max_support_deviation_after=max(after),
        fit_mean_huber_loss=float(fit["mean_huber_loss"]),
    )


def policy_api_has_hidden_opponent_argument() -> bool:
    """Mechanical regression helper for the inference firewall."""
    names = inspect.signature(policy_for_private_support).parameters
    forbidden = ("opponent", "world", "matrix")
    return any(any(token in name for token in forbidden) for name in names)
