from __future__ import annotations

"""Strategically correct imperfect-information HU OFC training core.

The earlier backward teachers are exact at their certified leaves, but their
uniform hidden-card belief is only a bootstrap belief while earlier play is
card-blind.  Once R1-R3 policies depend on cards, those public actions change
posterior beliefs.  A globally strategic policy must therefore learn all
information sets jointly instead of pretending that every hidden packet remains
uniform after strategic signalling.

This module starts that joint solver.  It implements outcome-sampling MCCFR for
the complete *normal-hand* heads-up KKPoker OFC Joker Ultimate action tree with:

- all 232 legal opening placements (no action abstraction);
- all legal place-2/discard-1 actions on R1-R4;
- two physical Jokers and the certified exact terminal evaluator from engine.py;
- alternating non-dealer/dealer action order;
- private own discards and private current packets;
- full public placement history, preserving signalling and perfect recall;
- information-state keys that never expose the opponent packet/discards;
- epsilon exploration only for the player whose regrets are being updated;
- regret-matching+, average-policy accumulation, deterministic checkpoints.

The current terminal utility is exact current-hand points.  Fantasy is carried
by the engine as an observable terminal transition and is intentionally *not*
converted into heuristic points here.  Long-horizon Fantasy continuation is a
separate value layer built on fantasy_transition.py.

Outcome-sampling equations follow the standard baseline-zero MCCFR estimator
used by OpenSpiel.  One trajectory is sampled per update player, so runtime is
linear in hand depth rather than branching through 232 x 27^4 own actions.
"""

from dataclasses import dataclass, field
import argparse
import gzip
import json
import math
from pathlib import Path
import random
from typing import Iterable, Sequence

from engine import Action, Board, Card, apply_action, full_deck, legal_actions, resolve_board, score_heads_up

PLAYER_NONDEALER = 0
PLAYER_DEALER = 1
PLAYERS = (PLAYER_NONDEALER, PLAYER_DEALER)
ROUND_TERMINAL = 5
CHECKPOINT_SCHEMA = "openofc-hu-outcome-sampling-mccfr-v1"


@dataclass(frozen=True)
class DealPlan:
    opening: tuple[tuple[Card, ...], tuple[Card, ...]]
    rounds: tuple[
        tuple[tuple[Card, ...], tuple[Card, ...]],
        tuple[tuple[Card, ...], tuple[Card, ...]],
        tuple[tuple[Card, ...], tuple[Card, ...]],
        tuple[tuple[Card, ...], tuple[Card, ...]],
    ]

    def incoming(self, round_index: int, player: int) -> tuple[Card, ...]:
        if player not in PLAYERS:
            raise ValueError("invalid HU player")
        if round_index == 0:
            return self.opening[player]
        if 1 <= round_index <= 4:
            return self.rounds[round_index - 1][player]
        raise ValueError("normal OFC round must be 0..4")

    def dealt_cards(self) -> tuple[Card, ...]:
        out: list[Card] = []
        out.extend(self.opening[0])
        out.extend(self.opening[1])
        for packets in self.rounds:
            out.extend(packets[0])
            out.extend(packets[1])
        return tuple(out)


@dataclass(frozen=True)
class PublicActionEvent:
    round_index: int
    player: int
    placements: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class HUState:
    plan: DealPlan
    round_index: int = 0
    actor: int = PLAYER_NONDEALER
    boards: tuple[Board, Board] = (Board(), Board())
    discards: tuple[tuple[Card, ...], tuple[Card, ...]] = ((), ())
    public_history: tuple[PublicActionEvent, ...] = ()

    def terminal(self) -> bool:
        return self.round_index == ROUND_TERMINAL


@dataclass
class InfoSetNode:
    action_keys: tuple[str, ...]
    cumulative_regrets: list[float]
    cumulative_policy: list[float]
    visits: int = 0

    @staticmethod
    def create(action_keys: Sequence[str]) -> "InfoSetNode":
        keys = tuple(action_keys)
        if not keys:
            raise ValueError("information set must contain legal actions")
        return InfoSetNode(keys, [0.0] * len(keys), [0.0] * len(keys), 0)

    def current_policy(self) -> list[float]:
        positive = [max(0.0, x) for x in self.cumulative_regrets]
        total = sum(positive)
        if total > 0.0:
            return [x / total for x in positive]
        p = 1.0 / len(positive)
        return [p] * len(positive)

    def average_policy(self) -> list[float]:
        total = sum(self.cumulative_policy)
        if total > 0.0:
            return [x / total for x in self.cumulative_policy]
        return self.current_policy()


@dataclass(frozen=True)
class SolverStats:
    iterations: int
    episodes: int
    infosets: int
    total_visits: int
    max_actions: int
    mean_actions: float
    epsilon: float
    cfr_plus: bool


def _require_m1b_materialized() -> None:
    if "row-local semantics" not in (resolve_board.__doc__ or ""):
        raise RuntimeError(
            "M1b Joker semantics are not materialized. Run "
            "`python tools/openofc_solver/apply_m1b_joker_semantics.py` first."
        )


def _sorted_packet(cards: Iterable[Card]) -> tuple[Card, ...]:
    return tuple(sorted(cards))


def sample_deal_plan(rng: random.Random) -> DealPlan:
    """Sample one complete 34-card HU normal-hand deal without replacement."""
    deck = list(full_deck(2))
    rng.shuffle(deck)
    cursor = 0

    def draw(n: int) -> tuple[Card, ...]:
        nonlocal cursor
        result = _sorted_packet(deck[cursor:cursor + n])
        cursor += n
        return result

    opening = (draw(5), draw(5))
    rounds = tuple((draw(3), draw(3)) for _ in range(4))
    assert len(rounds) == 4
    plan = DealPlan(opening=opening, rounds=rounds)  # type: ignore[arg-type]
    dealt = plan.dealt_cards()
    if len(dealt) != 34 or len(set(dealt)) != 34:
        raise AssertionError("HU deal plan must contain 34 unique physical cards")
    return plan


def _card_token(card: Card) -> str:
    return str(card)


def _canonical_board(board: Board) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(sorted(_card_token(card) for card in row))
        for row in board.rows()
    )


def _action_key(action: Action, incoming: Sequence[Card]) -> str:
    placements = sorted(
        (_card_token(incoming[index]), int(row))
        for index, row in action.placements
    )
    discard = None
    if action.discard_index is not None:
        discard = _card_token(incoming[action.discard_index])
    return json.dumps(
        {"p": placements, "d": discard},
        sort_keys=True,
        separators=(",", ":"),
    )


def _public_event(
    round_index: int,
    player: int,
    action: Action,
    incoming: Sequence[Card],
) -> PublicActionEvent:
    # The discarded identity is intentionally absent: only placed cards/rows
    # become public.  The owner still remembers the discard through state.discards.
    placements = tuple(sorted(
        (_card_token(incoming[index]), int(row))
        for index, row in action.placements
    ))
    return PublicActionEvent(round_index, player, placements)


def _history_payload(history: Sequence[PublicActionEvent]) -> tuple:
    return tuple(
        (event.round_index, event.player, event.placements)
        for event in history
    )


def information_state_key(state: HUState) -> str:
    """Return the exact acting-player information state, with no hidden leakage."""
    if state.terminal():
        raise ValueError("terminal state has no information state")
    player = state.actor
    opponent = 1 - player
    incoming = state.plan.incoming(state.round_index, player)
    payload = {
        "v": 1,
        "player": player,
        "position": "nondealer_first" if player == 0 else "dealer_button_second",
        "round": state.round_index,
        "self_board": _canonical_board(state.boards[player]),
        "opp_board": _canonical_board(state.boards[opponent]),
        "own_discards": tuple(sorted(_card_token(c) for c in state.discards[player])),
        "incoming": tuple(_card_token(c) for c in incoming),
        "public_history": _history_payload(state.public_history),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def legal_action_pairs(state: HUState) -> list[tuple[str, Action]]:
    if state.terminal():
        return []
    incoming = state.plan.incoming(state.round_index, state.actor)
    pairs = [(_action_key(action, incoming), action)
             for action in legal_actions(state.boards[state.actor], incoming, state.round_index)]
    pairs.sort(key=lambda item: item[0])
    if len({key for key, _ in pairs}) != len(pairs):
        raise AssertionError("canonical legal action keys are not unique")
    return pairs


def child_state(state: HUState, action: Action) -> HUState:
    if state.terminal():
        raise ValueError("cannot act in terminal state")
    player = state.actor
    incoming = state.plan.incoming(state.round_index, player)
    boards = [state.boards[0], state.boards[1]]
    boards[player] = apply_action(boards[player], incoming, action)
    discards = [state.discards[0], state.discards[1]]
    if action.discard_index is not None:
        discards[player] = discards[player] + (incoming[action.discard_index],)
    history = state.public_history + (
        _public_event(state.round_index, player, action, incoming),
    )

    if player == PLAYER_NONDEALER:
        next_round = state.round_index
        next_actor = PLAYER_DEALER
    elif state.round_index < 4:
        next_round = state.round_index + 1
        next_actor = PLAYER_NONDEALER
    else:
        next_round = ROUND_TERMINAL
        next_actor = PLAYER_NONDEALER

    result = HUState(
        plan=state.plan,
        round_index=next_round,
        actor=next_actor,
        boards=(boards[0], boards[1]),
        discards=(discards[0], discards[1]),
        public_history=history,
    )
    if result.terminal():
        if not result.boards[0].complete() or not result.boards[1].complete():
            raise AssertionError("terminal HU state must contain two complete boards")
        if len(result.discards[0]) != 4 or len(result.discards[1]) != 4:
            raise AssertionError("terminal HU state must contain four private discards per player")
    return result


def terminal_utility(state: HUState, update_player: int) -> float:
    """Exact current-hand zero-sum utility for the requested player."""
    if not state.terminal():
        raise ValueError("terminal utility requires a terminal state")
    if update_player not in PLAYERS:
        raise ValueError("invalid update player")
    score = score_heads_up(state.boards[0], state.boards[1]).points
    return float(score if update_player == PLAYER_NONDEALER else -score)


def _sample_index(probabilities: Sequence[float], rng: random.Random) -> int:
    if not probabilities:
        raise ValueError("cannot sample empty probability vector")
    x = rng.random()
    cumulative = 0.0
    for i, p in enumerate(probabilities):
        if p < 0.0 or not math.isfinite(p):
            raise ValueError("invalid policy probability")
        cumulative += p
        if x < cumulative or i == len(probabilities) - 1:
            return i
    raise AssertionError("probability sampling fell through")


class OutcomeSamplingMCCFR:
    def __init__(
        self,
        *,
        epsilon: float = 0.6,
        seed: int = 20260825,
        cfr_plus: bool = True,
    ) -> None:
        _require_m1b_materialized()
        if not 0.0 < epsilon <= 1.0:
            raise ValueError("epsilon must be in (0, 1]")
        self.epsilon = float(epsilon)
        self.seed = int(seed)
        self.cfr_plus = bool(cfr_plus)
        self.rng = random.Random(self.seed)
        self.nodes: dict[str, InfoSetNode] = {}
        self.iterations = 0
        self.episodes = 0

    def _node(self, key: str, action_keys: Sequence[str]) -> InfoSetNode:
        keys = tuple(action_keys)
        node = self.nodes.get(key)
        if node is None:
            node = InfoSetNode.create(keys)
            self.nodes[key] = node
        elif node.action_keys != keys:
            raise AssertionError(
                "same information state produced a different legal action set"
            )
        return node

    def _episode(
        self,
        state: HUState,
        update_player: int,
        *,
        my_reach: float,
        opp_reach: float,
        sample_reach: float,
    ) -> float:
        if state.terminal():
            return terminal_utility(state, update_player)

        current = state.actor
        pairs = legal_action_pairs(state)
        action_keys = [key for key, _ in pairs]
        actions = [action for _, action in pairs]
        key = information_state_key(state)
        node = self._node(key, action_keys)
        policy = node.current_policy()

        if current == update_player:
            uniform = 1.0 / len(policy)
            sample_policy = [
                self.epsilon * uniform + (1.0 - self.epsilon) * p
                for p in policy
            ]
        else:
            sample_policy = list(policy)

        sampled = _sample_index(sample_policy, self.rng)
        if current == update_player:
            new_my_reach = my_reach * policy[sampled]
            new_opp_reach = opp_reach
        else:
            new_my_reach = my_reach
            new_opp_reach = opp_reach * policy[sampled]
        new_sample_reach = sample_reach * sample_policy[sampled]
        child_value = self._episode(
            child_state(state, actions[sampled]),
            update_player,
            my_reach=new_my_reach,
            opp_reach=new_opp_reach,
            sample_reach=new_sample_reach,
        )

        # Baseline-zero outcome-sampling estimator.  Only the sampled action has
        # a non-zero child estimate; dividing by its sampling probability makes
        # the estimate unbiased under the exploration policy.
        child_values = [0.0] * len(policy)
        child_values[sampled] = child_value / sample_policy[sampled]
        value_estimate = sum(
            policy[i] * child_values[i] for i in range(len(policy))
        )

        if current == update_player:
            if sample_reach <= 0.0:
                raise AssertionError("sample reach became non-positive")
            scale = opp_reach / sample_reach
            cf_value = value_estimate * scale
            for i in range(len(policy)):
                delta = child_values[i] * scale - cf_value
                updated = node.cumulative_regrets[i] + delta
                node.cumulative_regrets[i] = max(0.0, updated) if self.cfr_plus else updated

            # Match the standard outcome-sampling average-strategy estimator.
            # Chance is sampled as one uniformly random full permutation at the
            # episode root and its constant probability is omitted from both
            # opponent and sampling reach, so no astronomical chance factor is
            # introduced here.
            for i in range(len(policy)):
                node.cumulative_policy[i] += (
                    my_reach * policy[i] / sample_reach
                )
            node.visits += 1

        return value_estimate

    def run_iteration(self) -> None:
        """Run one alternating MCCFR iteration (one episode per player)."""
        for update_player in PLAYERS:
            plan = sample_deal_plan(self.rng)
            state = HUState(plan=plan)
            self._episode(
                state,
                update_player,
                my_reach=1.0,
                opp_reach=1.0,
                sample_reach=1.0,
            )
            self.episodes += 1
        self.iterations += 1

    def run(self, iterations: int) -> SolverStats:
        if iterations <= 0:
            raise ValueError("iterations must be positive")
        for _ in range(iterations):
            self.run_iteration()
        return self.stats()

    def stats(self) -> SolverStats:
        action_counts = [len(node.action_keys) for node in self.nodes.values()]
        return SolverStats(
            iterations=self.iterations,
            episodes=self.episodes,
            infosets=len(self.nodes),
            total_visits=sum(node.visits for node in self.nodes.values()),
            max_actions=max(action_counts, default=0),
            mean_actions=(sum(action_counts) / len(action_counts)) if action_counts else 0.0,
            epsilon=self.epsilon,
            cfr_plus=self.cfr_plus,
        )

    def policy_for_key(self, key: str, *, average: bool = True) -> dict[str, float]:
        node = self.nodes[key]
        probabilities = node.average_policy() if average else node.current_policy()
        return dict(zip(node.action_keys, probabilities))

    def checkpoint_payload(self) -> dict:
        return {
            "schema": CHECKPOINT_SCHEMA,
            "seed": self.seed,
            "epsilon": self.epsilon,
            "cfr_plus": self.cfr_plus,
            "iterations": self.iterations,
            "episodes": self.episodes,
            "nodes": [
                {
                    "key": key,
                    "action_keys": list(node.action_keys),
                    "cumulative_regrets": node.cumulative_regrets,
                    "cumulative_policy": node.cumulative_policy,
                    "visits": node.visits,
                }
                for key, node in sorted(self.nodes.items())
            ],
        }

    def save_checkpoint(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(
            self.checkpoint_payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if path.suffix == ".gz":
            with gzip.open(path, "wb", compresslevel=6) as handle:
                handle.write(raw)
        else:
            path.write_bytes(raw)

    @classmethod
    def load_checkpoint(cls, path: Path) -> "OutcomeSamplingMCCFR":
        if path.suffix == ".gz":
            with gzip.open(path, "rb") as handle:
                payload = json.loads(handle.read().decode("utf-8"))
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != CHECKPOINT_SCHEMA:
            raise ValueError("unsupported strategic CFR checkpoint schema")
        solver = cls(
            epsilon=float(payload["epsilon"]),
            seed=int(payload["seed"]),
            cfr_plus=bool(payload["cfr_plus"]),
        )
        solver.iterations = int(payload["iterations"])
        solver.episodes = int(payload["episodes"])
        for row in payload["nodes"]:
            node = InfoSetNode(
                action_keys=tuple(row["action_keys"]),
                cumulative_regrets=[float(x) for x in row["cumulative_regrets"]],
                cumulative_policy=[float(x) for x in row["cumulative_policy"]],
                visits=int(row["visits"]),
            )
            if not (
                len(node.action_keys)
                == len(node.cumulative_regrets)
                == len(node.cumulative_policy)
            ):
                raise ValueError("corrupt strategic CFR checkpoint node")
            solver.nodes[str(row["key"])] = node
        # RNG state is intentionally not serialized in v1.  Resumed training is
        # statistically valid but not byte-identical to uninterrupted training.
        # A deterministic RNG-state checkpoint is a scaling milestone, not a
        # reason to fake determinism here.
        return solver


def _stats_payload(stats: SolverStats) -> dict:
    return {
        "iterations": stats.iterations,
        "episodes": stats.episodes,
        "infosets": stats.infosets,
        "total_visits": stats.total_visits,
        "max_actions": stats.max_actions,
        "mean_actions": stats.mean_actions,
        "epsilon": stats.epsilon,
        "cfr_plus": stats.cfr_plus,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train the full-action HU OFC outcome-sampling MCCFR core"
    )
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--epsilon", type=float, default=0.6)
    parser.add_argument("--no-cfr-plus", action="store_true")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    if args.resume is not None:
        solver = OutcomeSamplingMCCFR.load_checkpoint(args.resume)
        if abs(solver.epsilon - args.epsilon) > 1e-12:
            raise SystemExit("resume epsilon does not match requested epsilon")
        if solver.cfr_plus == bool(args.no_cfr_plus):
            raise SystemExit("resume CFR+ mode does not match requested mode")
    else:
        solver = OutcomeSamplingMCCFR(
            epsilon=args.epsilon,
            seed=args.seed,
            cfr_plus=not args.no_cfr_plus,
        )

    stats = solver.run(args.iterations)
    payload = {
        "schema": CHECKPOINT_SCHEMA,
        "authority": "STRATEGIC_CURRENT_HAND_HU_MCCFR_NOT_YET_ZERO_EXPLOITABILITY",
        "fantasy_continuation": "EXACT_TRANSITION_AVAILABLE_VALUE_NOT_YET_COUPLED",
        "stats": _stats_payload(stats),
    }
    if args.checkpoint is not None:
        solver.save_checkpoint(args.checkpoint)
        payload["checkpoint"] = str(args.checkpoint)
    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print("OPENOFC_STRATEGIC_CFR=" + json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
