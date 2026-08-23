from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations, product
from typing import Iterable, Sequence

RANKS = "23456789TJQKA"
SUITS = "cdhs"
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}
VALUE_RANK = {v: r for r, v in RANK_VALUE.items()}

ROW_TOP = 0
ROW_MIDDLE = 1
ROW_BOTTOM = 2
ROW_CAPACITY = (3, 5, 5)

CAT_HIGH = 0
CAT_PAIR = 1
CAT_TWO_PAIR = 2
CAT_TRIPS = 3
CAT_STRAIGHT = 4
CAT_FLUSH = 5
CAT_FULL_HOUSE = 6
CAT_QUADS = 7
CAT_STRAIGHT_FLUSH = 8


@dataclass(frozen=True, order=True)
class Card:
    rank: int = 0
    suit: int = -1
    joker: int = 0

    @staticmethod
    def parse(text: str) -> "Card":
        t = text.strip().upper()
        if t in {"JK", "JK1", "JOKER", "X"}:
            return Card(joker=1)
        if t in {"JK2", "JOKER2", "Y"}:
            return Card(joker=2)
        if len(t) != 2 or t[0] not in RANKS or t[1].lower() not in SUITS:
            raise ValueError(f"invalid card: {text!r}")
        return Card(rank=RANK_VALUE[t[0]], suit=SUITS.index(t[1].lower()))

    def __str__(self) -> str:
        if self.joker:
            return f"JK{self.joker}"
        return VALUE_RANK[self.rank] + SUITS[self.suit]


REGULAR_DECK: tuple[Card, ...] = tuple(
    Card(rank=r, suit=s)
    for r in range(2, 15)
    for s in range(4)
)


def full_deck(jokers: int = 2) -> tuple[Card, ...]:
    if jokers not in (0, 1, 2):
        raise ValueError("jokers must be 0, 1, or 2")
    return REGULAR_DECK + tuple(Card(joker=i + 1) for i in range(jokers))


@dataclass(frozen=True, order=True)
class HandRank:
    category: int
    tie: tuple[int, ...]
    royal: bool = False


@dataclass(frozen=True)
class Board:
    top: tuple[Card, ...] = ()
    middle: tuple[Card, ...] = ()
    bottom: tuple[Card, ...] = ()

    def rows(self) -> tuple[tuple[Card, ...], tuple[Card, ...], tuple[Card, ...]]:
        return self.top, self.middle, self.bottom

    def complete(self) -> bool:
        return tuple(map(len, self.rows())) == ROW_CAPACITY

    def count(self) -> int:
        return sum(map(len, self.rows()))

    def with_card(self, row: int, card: Card) -> "Board":
        if row not in (ROW_TOP, ROW_MIDDLE, ROW_BOTTOM):
            raise ValueError("invalid row")
        rows = [list(x) for x in self.rows()]
        if len(rows[row]) >= ROW_CAPACITY[row]:
            raise ValueError("row capacity exceeded")
        rows[row].append(card)
        return Board(tuple(rows[0]), tuple(rows[1]), tuple(rows[2]))


@dataclass(frozen=True)
class Action:
    placements: tuple[tuple[int, int], ...]
    discard_index: int | None


@dataclass(frozen=True)
class ResolvedBoard:
    board: Board
    ranks: tuple[HandRank, HandRank, HandRank]
    royalties: int
    fantasy_cards: int


@dataclass(frozen=True)
class ScoreResult:
    points: int
    row_points: tuple[int, int, int]
    scoop: int
    royalty_diff: int
    hero_foul: bool
    opponent_foul: bool
    hero_fantasy_cards: int
    opponent_fantasy_cards: int


def _straight_high(ranks: Iterable[int]) -> int:
    uniq = set(ranks)
    if 14 in uniq:
        uniq.add(1)
    for high in range(14, 4, -1):
        if all((high - d) in uniq for d in range(5)):
            return high
    return 0


def _eval_regular(cards: Sequence[Card]) -> HandRank:
    n = len(cards)
    if n not in (3, 5):
        raise ValueError("row evaluator requires 3 or 5 cards")
    if any(c.joker for c in cards):
        raise ValueError("regular evaluator received joker")
    counts: dict[int, int] = {}
    for c in cards:
        counts[c.rank] = counts.get(c.rank, 0) + 1
    groups = sorted(((cnt, rank) for rank, cnt in counts.items()), reverse=True)
    desc = sorted((c.rank for c in cards), reverse=True)

    if n == 3:
        if groups[0][0] == 3:
            return HandRank(CAT_TRIPS, (groups[0][1],))
        if groups[0][0] == 2:
            pair = groups[0][1]
            kicker = max(r for r in desc if r != pair)
            return HandRank(CAT_PAIR, (pair, kicker))
        return HandRank(CAT_HIGH, tuple(desc))

    flush = len({c.suit for c in cards}) == 1
    shigh = _straight_high(desc)
    if flush and shigh:
        return HandRank(CAT_STRAIGHT_FLUSH, (shigh,), royal=(shigh == 14))
    if groups[0][0] == 4:
        quad = groups[0][1]
        kicker = max(r for r in desc if r != quad)
        return HandRank(CAT_QUADS, (quad, kicker))
    if groups[0][0] == 3 and groups[1][0] == 2:
        return HandRank(CAT_FULL_HOUSE, (groups[0][1], groups[1][1]))
    if flush:
        return HandRank(CAT_FLUSH, tuple(desc))
    if shigh:
        return HandRank(CAT_STRAIGHT, (shigh,))
    if groups[0][0] == 3:
        trip = groups[0][1]
        kickers = tuple(sorted((r for r in desc if r != trip), reverse=True))
        return HandRank(CAT_TRIPS, (trip,) + kickers)
    pairs = sorted((rank for rank, cnt in counts.items() if cnt == 2), reverse=True)
    if len(pairs) == 2:
        kicker = max(r for r in desc if r not in pairs)
        return HandRank(CAT_TWO_PAIR, (pairs[0], pairs[1], kicker))
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = tuple(sorted((r for r in desc if r != pair), reverse=True))
        return HandRank(CAT_PAIR, (pair,) + kickers)
    return HandRank(CAT_HIGH, tuple(desc))


def royalty(rank: HandRank, row: int) -> int:
    if row == ROW_TOP:
        if rank.category == CAT_PAIR and rank.tie[0] >= 6:
            return rank.tie[0] - 5
        if rank.category == CAT_TRIPS:
            return rank.tie[0] + 8
        return 0
    if row == ROW_MIDDLE:
        if rank.category == CAT_TRIPS:
            return 2
        if rank.category == CAT_STRAIGHT:
            return 4
        if rank.category == CAT_FLUSH:
            return 8
        if rank.category == CAT_FULL_HOUSE:
            return 12
        if rank.category == CAT_QUADS:
            return 20
        if rank.category == CAT_STRAIGHT_FLUSH:
            return 50 if rank.royal else 30
        return 0
    if row == ROW_BOTTOM:
        if rank.category == CAT_STRAIGHT:
            return 2
        if rank.category == CAT_FLUSH:
            return 4
        if rank.category == CAT_FULL_HOUSE:
            return 6
        if rank.category == CAT_QUADS:
            return 10
        if rank.category == CAT_STRAIGHT_FLUSH:
            return 25 if rank.royal else 15
        return 0
    raise ValueError("invalid row")


def fantasy_award_from_top(top: HandRank, *, ultimate_with_jokers: bool = True) -> int:
    if top.category == CAT_TRIPS and ultimate_with_jokers:
        return 17
    if top.category == CAT_PAIR:
        pair = top.tie[0]
        if pair == 12:
            return 14
        if pair == 13:
            return 15
        if pair == 14:
            return 16
    return 0


def _board_rank_key(ranks: tuple[HandRank, HandRank, HandRank]) -> tuple:
    return ranks[2], ranks[1], ranks[0]


def _is_valid_ranks(ranks: tuple[HandRank, HandRank, HandRank]) -> bool:
    top, middle, bottom = ranks
    return bottom >= middle and middle >= top


def _substitute_board(board: Board, replacements: Sequence[Card]) -> Board:
    it = iter(replacements)
    rows: list[tuple[Card, ...]] = []
    for row in board.rows():
        out = []
        for c in row:
            out.append(next(it) if c.joker else c)
        rows.append(tuple(out))
    return Board(rows[0], rows[1], rows[2])


def resolve_board(board: Board) -> ResolvedBoard | None:
    """Resolve up to two Jokers exhaustively.

    Joker contract v1 is isolated behind a parity gate: substitutions are
    distinct regular cards not already in this 13-card board. Among non-fouled
    substitutions, choose maximum total royalty, then bottom/middle/top rank.
    """
    if not board.complete():
        raise ValueError("resolve_board requires 3/5/5 complete board")
    all_cards = [c for row in board.rows() for c in row]
    joker_count = sum(1 for c in all_cards if c.joker)
    if joker_count > 2:
        raise ValueError("Joker OFC supports at most two jokers")
    nonjokers = [c for c in all_cards if not c.joker]
    if len(set(nonjokers)) != len(nonjokers):
        raise ValueError("duplicate physical regular card in board")

    if joker_count == 0:
        ranks = tuple(_eval_regular(row) for row in board.rows())
        if not _is_valid_ranks(ranks):
            return None
        rs = sum(royalty(ranks[i], i) for i in range(3))
        return ResolvedBoard(board, ranks, rs, fantasy_award_from_top(ranks[0]))

    used = set(nonjokers)
    available = [c for c in REGULAR_DECK if c not in used]
    best: tuple | None = None
    best_resolved: ResolvedBoard | None = None
    for repl in permutations(available, joker_count):
        resolved = _substitute_board(board, repl)
        ranks = tuple(_eval_regular(row) for row in resolved.rows())
        if not _is_valid_ranks(ranks):
            continue
        rs = sum(royalty(ranks[i], i) for i in range(3))
        fantasy = fantasy_award_from_top(ranks[0])
        key = (rs, _board_rank_key(ranks), fantasy)
        if best is None or key > best:
            best = key
            best_resolved = ResolvedBoard(resolved, ranks, rs, fantasy)
    return best_resolved


def score_heads_up(hero: Board, opponent: Board) -> ScoreResult:
    if not hero.complete() or not opponent.complete():
        raise ValueError("heads-up scoring requires complete boards")
    hr = resolve_board(hero)
    vr = resolve_board(opponent)
    hero_foul = hr is None
    opp_foul = vr is None

    if hero_foul and opp_foul:
        return ScoreResult(0, (0, 0, 0), 0, 0, True, True, 0, 0)
    if hero_foul:
        assert vr is not None
        royalty_diff = -vr.royalties
        return ScoreResult(-6 + royalty_diff, (-1, -1, -1), -3,
                           royalty_diff, True, False, 0, vr.fantasy_cards)
    if opp_foul:
        assert hr is not None
        royalty_diff = hr.royalties
        return ScoreResult(6 + royalty_diff, (1, 1, 1), 3,
                           royalty_diff, False, True, hr.fantasy_cards, 0)

    assert hr is not None and vr is not None
    row_points = tuple(
        1 if hr.ranks[i] > vr.ranks[i] else -1 if hr.ranks[i] < vr.ranks[i] else 0
        for i in range(3)
    )
    scoop = 3 if row_points == (1, 1, 1) else -3 if row_points == (-1, -1, -1) else 0
    royalty_diff = hr.royalties - vr.royalties
    points = sum(row_points) + scoop + royalty_diff
    return ScoreResult(points, row_points, scoop, royalty_diff, False, False,
                       hr.fantasy_cards, vr.fantasy_cards)


def legal_actions(board: Board, incoming: Sequence[Card], round_index: int) -> list[Action]:
    expected = 5 if round_index == 0 else 3
    if len(incoming) != expected:
        raise ValueError(f"round {round_index} requires {expected} incoming cards")
    if round_index < 0 or round_index > 4:
        raise ValueError("normal OFC round must be 0..4")
    capacities = [ROW_CAPACITY[i] - len(board.rows()[i]) for i in range(3)]
    if any(x < 0 for x in capacities):
        raise ValueError("board already exceeds row capacity")

    actions: list[Action] = []
    discards: Iterable[int | None] = (None,) if round_index == 0 else range(len(incoming))
    for discard in discards:
        keep = [i for i in range(len(incoming)) if i != discard]
        for rows in product((ROW_TOP, ROW_MIDDLE, ROW_BOTTOM), repeat=len(keep)):
            need = [0, 0, 0]
            for row in rows:
                need[row] += 1
            if any(need[r] > capacities[r] for r in range(3)):
                continue
            placements = tuple((keep[j], rows[j]) for j in range(len(keep)))
            actions.append(Action(placements, discard))
    return actions


def apply_action(board: Board, incoming: Sequence[Card], action: Action) -> Board:
    placed = set()
    out = board
    for idx, row in action.placements:
        if idx in placed:
            raise ValueError("incoming card placed more than once")
        if idx < 0 or idx >= len(incoming):
            raise ValueError("incoming index out of range")
        placed.add(idx)
        out = out.with_card(row, incoming[idx])
    expected_placed = len(incoming) if action.discard_index is None else len(incoming) - 1
    if len(placed) != expected_placed:
        raise ValueError("action does not place expected number of cards")
    if action.discard_index is not None and action.discard_index in placed:
        raise ValueError("discarded card was also placed")
    return out


def parse_cards(text: str) -> tuple[Card, ...]:
    return tuple(Card.parse(x) for x in text.split() if x.strip())


def card_from_runtime_value(value: int) -> Card:
    """Map OpenOFC canonical values 0..53 to the pure solver card model."""
    if 0 <= value <= 51:
        suit_block, rank_offset = divmod(value, 13)
        runtime_to_solver_suit = (
            SUITS.index("h"), SUITS.index("d"), SUITS.index("c"), SUITS.index("s"))
        return Card(rank=rank_offset + 2, suit=runtime_to_solver_suit[suit_block])
    if value == 52:
        return Card(joker=1)
    if value == 53:
        return Card(joker=2)
    raise ValueError(f"invalid OpenOFC runtime card value: {value}")
