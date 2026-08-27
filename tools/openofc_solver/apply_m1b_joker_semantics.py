from __future__ import annotations

from pathlib import Path


ENGINE = Path("tools/openofc_solver/engine.py")
CPP = Path("OpenHoldem/COFCBaselinePolicy.cpp")
CHECK = Path("tools/openofc_solver/check_cpp_parity.py")


PY_REPLACEMENT = r'''def _substitute_row(row: Sequence[Card], replacements: Sequence[Card]) -> tuple[Card, ...]:
    it = iter(replacements)
    return tuple(next(it) if c.joker else c for c in row)


def _candidate_row_resolutions(row: Sequence[Card]) -> list[tuple[HandRank, tuple[Card, ...]]]:
    """Enumerate legal row-local Joker interpretations.

    KKPoker scores each row separately. A Joker may therefore represent a
    regular card that physically appears in another row. Within this row,
    however, the represented playing cards must form a legal traditional poker
    hand: a Joker cannot duplicate an exact card already present in this row,
    and two Jokers cannot both represent the same exact card.
    """
    joker_count = sum(1 for c in row if c.joker)
    if joker_count > 2:
        raise ValueError("Joker OFC supports at most two jokers in a row")
    regular = [c for c in row if not c.joker]
    if len(set(regular)) != len(regular):
        raise ValueError("duplicate physical regular card in row")
    if joker_count == 0:
        resolved = tuple(row)
        return [(_eval_regular(resolved), resolved)]

    available = [c for c in REGULAR_DECK if c not in set(regular)]
    best_row_for_rank: dict[HandRank, tuple[Card, ...]] = {}
    for repl in permutations(available, joker_count):
        resolved = _substitute_row(row, repl)
        rank = _eval_regular(resolved)
        old = best_row_for_rank.get(rank)
        if old is None or resolved < old:
            best_row_for_rank[rank] = resolved
    return sorted(best_row_for_rank.items(), key=lambda item: item[0], reverse=True)


def resolve_board(board: Board) -> ResolvedBoard | None:
    """Resolve Jokers with KKPoker row-local semantics.

    Physical regular cards in the 13-card board must be unique. Joker
    substitution identity is row-local because KKPoker scores the three rows
    separately. The strongest legal Bottom is selected first, then the
    strongest Middle not exceeding Bottom, then the strongest Top not
    exceeding Middle. This is the strongest non-fouled board under the normal
    OFC ranking requirement.
    """
    if not board.complete():
        raise ValueError("resolve_board requires 3/5/5 complete board")
    all_cards = [c for row in board.rows() for c in row]
    nonjokers = [c for c in all_cards if not c.joker]
    if len(set(nonjokers)) != len(nonjokers):
        raise ValueError("duplicate physical regular card in board")
    if sum(1 for c in all_cards if c.joker) > 2:
        raise ValueError("Joker OFC supports at most two jokers")

    candidates = [_candidate_row_resolutions(row) for row in board.rows()]
    if any(not row for row in candidates):
        return None

    bottom_rank, bottom_row = candidates[ROW_BOTTOM][0]
    middle_choice = next(
        ((rank, row) for rank, row in candidates[ROW_MIDDLE] if rank <= bottom_rank),
        None,
    )
    if middle_choice is None:
        return None
    middle_rank, middle_row = middle_choice

    top_choice = next(
        ((rank, row) for rank, row in candidates[ROW_TOP] if rank <= middle_rank),
        None,
    )
    if top_choice is None:
        return None
    top_rank, top_row = top_choice

    ranks = (top_rank, middle_rank, bottom_rank)
    resolved_board = Board(top_row, middle_row, bottom_row)
    rs = sum(royalty(ranks[i], i) for i in range(3))
    return ResolvedBoard(
        resolved_board,
        ranks,
        rs,
        fantasy_award_from_top(top_rank),
    )


'''


CPP_REPLACEMENT = r'''bool SameNominalCard(const PolicyCard &left, const PolicyCard &right) {
  return left.joker == 0 && right.joker == 0
    && left.rank == right.rank && left.suit == right.suit;
}

bool ContainsNominalCard(
    const vector<PolicyCard> &cards, const PolicyCard &candidate) {
  for (size_t i = 0; i < cards.size(); ++i)
    if (SameNominalCard(cards[i], candidate)) return true;
  return false;
}

vector<HandRank> CandidateRanks(const vector<PolicyCard> &cards, bool top) {
  int joker_count = 0;
  vector<PolicyCard> standard;
  for (size_t i = 0; i < cards.size(); ++i) {
    if (cards[i].joker) ++joker_count;
    else standard.push_back(cards[i]);
  }
  set<HandRank> unique;
  if (joker_count == 0) {
    unique.insert(top ? RankTopStandard(cards) : RankFiveStandard(cards));
  } else {
    const vector<PolicyCard> deck = NominalDeck();
    for (size_t first = 0; first < deck.size(); ++first) {
      if (ContainsNominalCard(standard, deck[first])) continue;
      vector<PolicyCard> nominal = standard;
      nominal.push_back(deck[first]);
      if (joker_count == 1) {
        if (!top && !ValidFiveNominal(nominal)) continue;
        unique.insert(top ? RankTopStandard(nominal) : RankFiveStandard(nominal));
        continue;
      }
      for (size_t second = 0; second < deck.size(); ++second) {
        if (ContainsNominalCard(standard, deck[second])) continue;
        if (SameNominalCard(deck[first], deck[second])) continue;
        vector<PolicyCard> two = nominal;
        two.push_back(deck[second]);
        if (!top && !ValidFiveNominal(two)) continue;
        unique.insert(top ? RankTopStandard(two) : RankFiveStandard(two));
      }
    }
  }
  vector<HandRank> result(unique.begin(), unique.end());
  reverse(result.begin(), result.end());
  return result;
}

'''


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    a = text.find(start)
    if a < 0:
        raise SystemExit(f"{label}: start marker not found")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"{label}: end marker not found")
    return text[:a] + replacement + text[b:]


def patch_engine() -> None:
    text = ENGINE.read_text(encoding="utf-8")
    if "KKPoker row-local semantics" in text:
        print("engine.py: M1b Joker semantics already materialized")
        return
    text = replace_between(
        text,
        "def _substitute_board(",
        "def score_heads_up(",
        PY_REPLACEMENT,
        "engine.py",
    )
    ENGINE.write_text(text, encoding="utf-8")
    print("engine.py: materialized row-local Joker semantics")


def patch_cpp() -> None:
    text = CPP.read_text(encoding="utf-8")
    if "SameNominalCard" in text:
        print("COFCBaselinePolicy.cpp: M1b Joker semantics already materialized")
        return
    text = replace_between(
        text,
        "vector<HandRank> CandidateRanks(",
        "int TopRoyalty(",
        CPP_REPLACEMENT,
        "COFCBaselinePolicy.cpp",
    )
    CPP.write_text(text, encoding="utf-8")
    print("COFCBaselinePolicy.cpp: materialized same-row physical-card uniqueness")


def patch_stress() -> None:
    text = CHECK.read_text(encoding="utf-8")
    if "M1B_STRESS_512_256" in text:
        print("check_cpp_parity.py: M1b stress already materialized")
        return
    text = text.replace(
        "    for _ in range(96):\n",
        "    # M1B_STRESS_512_256: deterministic broader Joker parity corpus.\n    for _ in range(512):\n",
        1,
    )
    text = text.replace("    for _ in range(48):\n", "    for _ in range(256):\n", 1)
    CHECK.write_text(text, encoding="utf-8")
    print("check_cpp_parity.py: expanded Joker corpus to 770 boards")


def main() -> None:
    patch_engine()
    patch_cpp()
    patch_stress()
    print("OPENOFC_SOLVER_M1B_MATERIALIZATION=PASS")


if __name__ == "__main__":
    main()
