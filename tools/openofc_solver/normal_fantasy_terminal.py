from __future__ import annotations

"""Safe terminal evaluators for the asymmetric normal-vs-hidden-Fantasy kernel.

The normal-player policy never receives the hidden Fantasy packet.  Exact and
learned terminal evaluators are oracle-side components invoked only after a full
chance world has been sampled and the normal board is complete.

Approximation is fail-closed: an MLP may be used only with a SHA-bound external
certificate defining its exact held-out envelope.  Any model mismatch,
out-of-envelope stratum, uncertain reachability prediction, or continuation
delta outside the certified range falls back to the exact M4H one-pass oracle.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from fantasy_frontier_cache import canonical_frontier_key
from fantasy_frontier_cache_onepass import OnePassExactFantasyFrontierCache
from fantasy_frontier_features import FEATURE_DIMENSION, encode_canonical_world_key
from fantasy_frontier_mlp import TerminalFrontierMLP
from fantasy_transition import VARIANT_ULTIMATE, transition_from_board
from hu_continuation import HUContinuationState, default_next_button
from normal_fantasy_kernel import NormalFantasyState

CERTIFICATE_SCHEMA = "openofc-m4l-terminal-model-certificate-v1"
AUTHORITY_EXACT = "EXACT_M4H_ONEPASS_NORMAL_FANTASY_TERMINAL"
AUTHORITY_CERTIFIED = "CERTIFIED_HELDOUT_MLP_WITH_EXACT_FALLBACK"


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True)
class TerminalModelCertificate:
    model_sha256: str
    allowed_fantasy_counts: tuple[int, ...]
    allowed_joker_counts: tuple[int, ...]
    confidence_low: float
    confidence_high: float
    continuation_delta_min: float
    continuation_delta_max: float
    max_utility_abs_error: float
    heldout_worlds: int
    evidence_sha256: str
    schema: str = CERTIFICATE_SCHEMA

    def __post_init__(self) -> None:
        if len(self.model_sha256) != 64 or len(self.evidence_sha256) != 64:
            raise ValueError("certificate SHA-256 fields must contain 64 hex characters")
        try:
            int(self.model_sha256, 16)
            int(self.evidence_sha256, 16)
        except ValueError as exc:
            raise ValueError("certificate SHA-256 fields must be hexadecimal") from exc
        counts = tuple(sorted(set(int(x) for x in self.allowed_fantasy_counts)))
        jokers = tuple(sorted(set(int(x) for x in self.allowed_joker_counts)))
        if not counts or any(x not in (14, 15, 16, 17) for x in counts):
            raise ValueError("certificate Fantasy envelope must be a nonempty subset of 14..17")
        if not jokers or any(x not in (0, 1, 2) for x in jokers):
            raise ValueError("certificate Joker envelope must be a nonempty subset of 0..2")
        if not 0.0 <= self.confidence_low < 0.5 < self.confidence_high <= 1.0:
            raise ValueError("certificate reachability confidence thresholds are invalid")
        if self.continuation_delta_min > self.continuation_delta_max:
            raise ValueError("certificate continuation delta range is inverted")
        if self.max_utility_abs_error < 0.0 or self.heldout_worlds <= 0:
            raise ValueError("certificate held-out error/world count is invalid")
        object.__setattr__(self, "allowed_fantasy_counts", counts)
        object.__setattr__(self, "allowed_joker_counts", jokers)

    def unsigned_payload(self) -> dict:
        return {
            "schema": self.schema,
            "model_sha256": self.model_sha256,
            "allowed_fantasy_counts": list(self.allowed_fantasy_counts),
            "allowed_joker_counts": list(self.allowed_joker_counts),
            "confidence_low": self.confidence_low,
            "confidence_high": self.confidence_high,
            "continuation_delta_min": self.continuation_delta_min,
            "continuation_delta_max": self.continuation_delta_max,
            "max_utility_abs_error": self.max_utility_abs_error,
            "heldout_worlds": self.heldout_worlds,
            "evidence_sha256": self.evidence_sha256,
        }

    def payload(self) -> dict:
        base = self.unsigned_payload()
        base["sha256"] = hashlib.sha256(_canonical_bytes(base)).hexdigest()
        return base

    @property
    def fingerprint(self) -> str:
        return str(self.payload()["sha256"])

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "TerminalModelCertificate":
        raw = dict(payload)
        expected = str(raw.pop("sha256", ""))
        actual = hashlib.sha256(_canonical_bytes(raw)).hexdigest()
        if expected != actual:
            raise ValueError("terminal model certificate SHA-256 mismatch")
        if raw.get("schema") != CERTIFICATE_SCHEMA:
            raise ValueError("unsupported terminal model certificate schema")
        return cls(
            model_sha256=str(raw["model_sha256"]),
            allowed_fantasy_counts=tuple(int(x) for x in raw["allowed_fantasy_counts"]),
            allowed_joker_counts=tuple(int(x) for x in raw["allowed_joker_counts"]),
            confidence_low=float(raw["confidence_low"]),
            confidence_high=float(raw["confidence_high"]),
            continuation_delta_min=float(raw["continuation_delta_min"]),
            continuation_delta_max=float(raw["continuation_delta_max"]),
            max_utility_abs_error=float(raw["max_utility_abs_error"]),
            heldout_worlds=int(raw["heldout_worlds"]),
            evidence_sha256=str(raw["evidence_sha256"]),
        )


@dataclass(frozen=True)
class TerminalEvaluation:
    utility_for_normal: float
    source: str
    used_exact: bool
    abstention_reason: str | None
    certified_error_bound: float
    reach_probabilities: tuple[float, float] | None = None


class ExactOnePassNormalFantasyTerminalEvaluator:
    authority = AUTHORITY_EXACT

    def __init__(self) -> None:
        self.cache = OnePassExactFantasyFrontierCache()
        self.evaluations = 0

    @property
    def exact_hits(self) -> int:
        return self.cache.hits

    @property
    def exact_misses(self) -> int:
        return self.cache.misses

    def evaluate(
        self,
        state: NormalFantasyState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> TerminalEvaluation:
        if not state.terminal():
            raise ValueError("terminal evaluator requires a completed normal/Fantasy state")
        record = self.cache.get_or_build(
            state.plan.fantasy_packet,
            state.normal_board,
            variant=VARIANT_ULTIMATE,
        )
        result = self.cache.evaluate(
            record,
            state.normal_board,
            current_meta=state.current_meta,
            fantasy_player=state.fantasy_player,
            continuation_values=continuation_values,
            variant=VARIANT_ULTIMATE,
        )
        self.evaluations += 1
        return TerminalEvaluation(
            utility_for_normal=-float(result.utility),
            source=self.authority,
            used_exact=True,
            abstention_reason=None,
            certified_error_bound=0.0,
        )


def _next_state_for_branch(
    state: NormalFantasyState,
    *,
    qualifies_refantasy: bool,
) -> HUContinuationState:
    normal_transition = transition_from_board(
        state.normal_board,
        current_fantasy_cards=0,
        variant=VARIANT_ULTIMATE,
    )
    modes = [0, 0]
    modes[state.normal_player] = normal_transition.next_cards
    fantasy_mode = state.current_meta.mode_for(state.fantasy_player)
    modes[state.fantasy_player] = fantasy_mode if qualifies_refantasy else 0
    return HUContinuationState(
        default_next_button(state.current_meta.button),
        modes[0],
        modes[1],
    )


def _hero_continuation(
    state: NormalFantasyState,
    next_state: HUContinuationState,
    continuation_values: Mapping[HUContinuationState, float],
) -> float:
    if next_state not in continuation_values:
        raise KeyError(f"continuation value missing for {next_state.as_key()}")
    p0 = float(continuation_values[next_state])
    return p0 if state.fantasy_player == 0 else -p0


class CertifiedMLPNormalFantasyTerminalEvaluator:
    """Use a certified M4K model inside its envelope, exact M4H otherwise."""

    authority = AUTHORITY_CERTIFIED

    def __init__(
        self,
        model_path: Path,
        certificate: TerminalModelCertificate,
        *,
        exact_fallback: ExactOnePassNormalFantasyTerminalEvaluator | None = None,
    ) -> None:
        digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if digest != certificate.model_sha256:
            raise ValueError("M4K model SHA-256 does not match terminal certificate")
        self.model = TerminalFrontierMLP.load(model_path)
        self.certificate = certificate
        self.exact = exact_fallback or ExactOnePassNormalFantasyTerminalEvaluator()
        self.approx_evaluations = 0
        self.fallback_evaluations = 0
        self.fallback_reasons: dict[str, int] = {}

    def _fallback(
        self,
        reason: str,
        state: NormalFantasyState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> TerminalEvaluation:
        self.fallback_evaluations += 1
        self.fallback_reasons[reason] = self.fallback_reasons.get(reason, 0) + 1
        exact = self.exact.evaluate(state, continuation_values)
        return TerminalEvaluation(
            utility_for_normal=exact.utility_for_normal,
            source=exact.source,
            used_exact=True,
            abstention_reason=reason,
            certified_error_bound=0.0,
        )

    def evaluate(
        self,
        state: NormalFantasyState,
        continuation_values: Mapping[HUContinuationState, float],
    ) -> TerminalEvaluation:
        if not state.terminal():
            raise ValueError("terminal evaluator requires a completed normal/Fantasy state")
        count = len(state.plan.fantasy_packet)
        jokers = sum(1 for card in state.plan.fantasy_packet if card.joker)
        cert = self.certificate
        if count not in cert.allowed_fantasy_counts:
            return self._fallback("FANTASY_COUNT_OUTSIDE_CERTIFICATE", state, continuation_values)
        if jokers not in cert.allowed_joker_counts:
            return self._fallback("JOKER_COUNT_OUTSIDE_CERTIFICATE", state, continuation_values)

        key = canonical_frontier_key(
            state.plan.fantasy_packet,
            state.normal_board,
            variant=VARIANT_ULTIMATE,
        )
        indices = encode_canonical_world_key(key)
        x = np.zeros((1, FEATURE_DIMENSION), dtype=np.float32)
        x[0, list(indices)] = 1.0
        reach_prob, points = self.model.predict(x)
        probabilities = (float(reach_prob[0, 0]), float(reach_prob[0, 1]))

        present: list[bool] = []
        for probability in probabilities:
            if probability <= cert.confidence_low:
                present.append(False)
            elif probability >= cert.confidence_high:
                present.append(True)
            else:
                return self._fallback(
                    "REACHABILITY_UNCERTAIN", state, continuation_values
                )
        if not any(present):
            return self._fallback("MODEL_PREDICTED_NO_REACHABLE_BRANCH", state, continuation_values)

        next_states = (
            _next_state_for_branch(state, qualifies_refantasy=False),
            _next_state_for_branch(state, qualifies_refantasy=True),
        )
        if present[0] and present[1]:
            delta = (
                _hero_continuation(state, next_states[1], continuation_values)
                - _hero_continuation(state, next_states[0], continuation_values)
            )
            if not cert.continuation_delta_min <= delta <= cert.continuation_delta_max:
                return self._fallback(
                    "CONTINUATION_DELTA_OUTSIDE_CERTIFICATE", state, continuation_values
                )

        fantasy_options = []
        for branch in (0, 1):
            if not present[branch]:
                continue
            fantasy_options.append(
                float(points[0, branch])
                + _hero_continuation(state, next_states[branch], continuation_values)
            )
        fantasy_utility = max(fantasy_options)
        self.approx_evaluations += 1
        return TerminalEvaluation(
            utility_for_normal=-fantasy_utility,
            source=self.authority,
            used_exact=False,
            abstention_reason=None,
            certified_error_bound=float(cert.max_utility_abs_error),
            reach_probabilities=probabilities,
        )
