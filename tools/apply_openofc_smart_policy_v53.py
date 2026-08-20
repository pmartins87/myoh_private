from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(rel: str, old: str, new: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one target, got {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_rules_aware_scoring():
    rel = "OpenHoldem/COFCBaselinePolicy.cpp"

    old = '''long long PartialRowScore(const vector<PolicyCard> &cards, int row) {
  map<int, int> rank_count;
  int suits[4] = {0, 0, 0, 0};
  int high_sum = 0;
  int jokers = 0;
  for (size_t i = 0; i < cards.size(); ++i) {
    if (cards[i].joker) { ++jokers; continue; }
    ++rank_count[cards[i].rank];
    ++suits[cards[i].suit];
    high_sum += cards[i].rank;
  }
  long long score = high_sum;
  for (map<int, int>::const_iterator it = rank_count.begin(); it != rank_count.end(); ++it) {
    if (it->second == 2) score += row == 0 ? 180 + it->first * 8 : 100;
    if (it->second == 3) score += row == 0 ? 500 + it->first * 10 : 260;
    if (it->second == 4) score += 900;
  }
  int best_suit = 0;
  for (int suit = 0; suit < 4; ++suit) best_suit = max(best_suit, suits[suit]);
  if (row != 0) score += best_suit * best_suit * 9;
  score += jokers * (row == 0 ? 120 : 350);
  if (row == 0) score -= high_sum / 2;
  return score;
}
'''

    new = r'''// OPENOFC_SMART_BASELINE_V53
// Rules-aware deterministic evaluator. This is deliberately still a baseline,
// not the final trained/search policy. Its job is to make field-test play
// coherent: respect row hierarchy, preserve live 5-card structures, value
// Fantasy entry/refantasy explicitly and stop the old 1/2/2 shape rule from
// dominating every opening decision.

int StraightWindowHits(const map<int, int> &rank_count, int jokers, int high) {
  int hits = 0;
  for (int offset = 0; offset < 5; ++offset) {
    int rank = high - offset;
    if (high == 5 && offset == 0) rank = 5;
    if (high == 5 && offset == 1) rank = 4;
    if (high == 5 && offset == 2) rank = 3;
    if (high == 5 && offset == 3) rank = 2;
    if (high == 5 && offset == 4) rank = 14;
    if (rank_count.find(rank) != rank_count.end()) ++hits;
  }
  return min(5, hits + jokers);
}

long long FiveCardPotential(
    const vector<PolicyCard> &cards,
    const map<int, int> &rank_count,
    const int suits[4],
    int jokers,
    int row) {
  const int slots_left = 5 - static_cast<int>(cards.size());
  long long score = 0;

  int pair_count = 0;
  int trip_count = 0;
  int quad_count = 0;
  for (map<int, int>::const_iterator it = rank_count.begin(); it != rank_count.end(); ++it) {
    if (it->second == 2) { ++pair_count; score += 180 + it->first * 3; }
    if (it->second == 3) { ++trip_count; score += 430 + it->first * 5; }
    if (it->second == 4) { ++quad_count; score += 1150 + it->first * 7; }
  }
  if (pair_count >= 2) score += 330;
  if (trip_count >= 1 && pair_count >= 1) score += 650;

  int best_suit = 0;
  for (int suit = 0; suit < 4; ++suit) best_suit = max(best_suit, suits[suit]);
  const int suited_with_jokers = min(5, best_suit + jokers);
  score += suited_with_jokers * suited_with_jokers * 24;
  if (suited_with_jokers + slots_left >= 5) {
    score += 90 * suited_with_jokers;
  }

  int best_straight_hits = 0;
  for (int high = 5; high <= 14; ++high)
    best_straight_hits = max(best_straight_hits,
      StraightWindowHits(rank_count, jokers, high));
  score += best_straight_hits * best_straight_hits * 26;
  if (best_straight_hits + slots_left >= 5)
    score += 80 * best_straight_hits;

  // Bottom has to carry the hierarchy, so premium made/draw structure belongs
  // there slightly more often; middle retains a higher royalty schedule and is
  // still rewarded strongly for straights/flushes/full houses.
  if (row == 2) score = score * 108 / 100;
  if (row == 1 && (best_straight_hits >= 4 || suited_with_jokers >= 4)) score += 120;
  score += jokers * (row == 2 ? 850 : 760);
  return score;
}

long long TopPotential(
    const vector<PolicyCard> &cards,
    const map<int, int> &rank_count,
    int jokers) {
  long long score = 0;
  int high_sum = 0;
  int high_cards = 0;
  bool paired = false;
  bool trips = false;
  for (size_t i = 0; i < cards.size(); ++i) {
    if (cards[i].joker) continue;
    high_sum += cards[i].rank;
    if (cards[i].rank >= 12) ++high_cards;
  }
  for (map<int, int>::const_iterator it = rank_count.begin(); it != rank_count.end(); ++it) {
    if (it->second == 2) {
      paired = true;
      score += 420 + it->first * 18;
      // QQ+ is not just a royalty: in this KKPoker Ultimate contract it enters
      // Fantasy, with QQ/KK/AA yielding 14/15/16 cards respectively.
      if (it->first >= 12) score += 850 + (it->first - 12) * 180;
    }
    if (it->second == 3) {
      trips = true;
      // Trips top is the strongest normal Fantasy gateway and yields 17 cards.
      score += 2100 + it->first * 28;
    }
  }

  if (!paired && !trips) {
    // A single premium anchor is useful; filling top with unrelated low cards
    // early is expensive because those slots cannot build straight/flush EV.
    for (map<int, int>::const_iterator it = rank_count.begin(); it != rank_count.end(); ++it) {
      if (it->first == 14) score += 190;
      else if (it->first == 13) score += 155;
      else if (it->first == 12) score += 130;
      else if (it->first == 11) score += 55;
      else score += max(0, it->first - 7) * 8;
    }
    if (cards.size() >= 2 && high_cards == 0) score -= 170;
    if (cards.size() == 3) score -= 80;
  }

  score += jokers * 1050;
  // The old evaluator inadvertently rewarded raw top high-card sum. Remove
  // that pressure; top value should come from pair/trips/Fantasy structure.
  score -= high_sum / 5;
  return score;
}

long long PartialRowScore(const vector<PolicyCard> &cards, int row) {
  map<int, int> rank_count;
  int suits[4] = {0, 0, 0, 0};
  int jokers = 0;
  for (size_t i = 0; i < cards.size(); ++i) {
    if (cards[i].joker) { ++jokers; continue; }
    ++rank_count[cards[i].rank];
    ++suits[cards[i].suit];
  }
  if (row == 0) return TopPotential(cards, rank_count, jokers);
  return FiveCardPotential(cards, rank_count, suits, jokers, row);
}

int NormalFantasyEntryValue(const array<HandRank, 3> &ranks) {
  const HandRank &top = ranks[0];
  if (top.category == kTrips) return 20;  // 17-card Fantasy
  if (top.category == kPair && top.tie[0] == 14) return 16;  // 16 cards
  if (top.category == kPair && top.tie[0] == 13) return 13;  // 15 cards
  if (top.category == kPair && top.tie[0] == 12) return 10;  // 14 cards
  return 0;
}

int FantasyContinuationValue(
    const array<HandRank, 3> &ranks,
    int fantasy_count) {
  const bool top_trips = ranks[0].category == kTrips;
  const bool bottom_quads_plus = ranks[2].category >= kQuads;
  if (!top_trips && !bottom_quads_plus) return 0;
  // Ultimate re-fantasy keeps the same number of cards as the current Fantasy.
  // This is an intentionally conservative continuation value; later self-play
  // will learn the actual EV rather than freezing these constants forever.
  return 18 + max(0, fantasy_count - 14) * 3;
}

long long OpeningStructureAdjustment(vector<PolicyCard> rows[3]) {
  long long score = 0;
  const int top = static_cast<int>(rows[0].size());
  const int middle = static_cast<int>(rows[1].size());
  const int bottom = static_cast<int>(rows[2].size());
  if (bottom == 0) score -= 380;
  if (middle == 0) score -= 180;
  if (bottom >= 2) score += 110;
  if (middle >= 1) score += 70;
  if (top == 1) score += 90;
  if (top == 2) score -= 35;
  if (top == 3) score -= 220;
  return score;
}
'''
    replace_once(rel, old, new)

    old_terminal = '''    score += static_cast<long long>(Royalties(resolved)) * 1000000LL;
    score += RankScalar(resolved[2]) * 1000LL;
'''
    new_terminal = '''    const int own_points = Royalties(resolved) + NormalFantasyEntryValue(resolved);
    score += static_cast<long long>(own_points) * 1000000LL;
    score += RankScalar(resolved[2]) * 1000LL;
'''
    # Two copies exist after v4.3: strict score and unavoidable-foul legal score.
    path, text, eol, bom = read_source(rel)
    count = text.count(old_terminal)
    if count != 2:
        raise RuntimeError(f"{rel}: expected two terminal scoring sites, got {count}")
    text = text.replace(old_terminal, new_terminal)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: terminal Fantasy-entry value at {count} sites")

    old_open = '''    if (opening && score >= 0) {
      // A conservative 1/2/2 opening prevents the integration policy from
      // accepting KKPoker's initial all-bottom visual layout as strategy.
      // The trained policy may later choose more nuanced opening shapes.
      const int target[3] = {1, 2, 2};
      int deviation = 0;
      for (int row = 0; row < 3; ++row)
        deviation += abs(static_cast<int>(rows[row].size()) - target[row]);
      score -= static_cast<long long>(deviation) * 1000000LL;
    }
'''
    new_open = '''    if (opening && score >= 0) {
      score += OpeningStructureAdjustment(rows);
    }
'''
    replace_once(rel, old_open, new_open)

    old_open_foul = '''    if (opening) {
      const int target[3] = {1, 2, 2};
      int deviation = 0;
      for (int row = 0; row < 3; ++row)
        deviation += abs(static_cast<int>(rows[row].size()) - target[row]);
      score -= static_cast<long long>(deviation) * 1000000LL;
    }
'''
    new_open_foul = '''    if (opening) {
      score += OpeningStructureAdjustment(rows);
    }
'''
    replace_once(rel, old_open_foul, new_open_foul)

    old_fantasy = '''      const long long score = static_cast<long long>(Royalties(ranks)) * 1000000000LL
        + RankScalar(bottom) * 10000LL
'''
    new_fantasy = '''      const int fantasy_points = Royalties(ranks)
        + FantasyContinuationValue(ranks, fantasy_count);
      const long long score = static_cast<long long>(fantasy_points) * 1000000000LL
        + RankScalar(bottom) * 10000LL
'''
    replace_once(rel, old_fantasy, new_fantasy)


def patch_policy_header_and_runtime_marker():
    rel = "OpenHoldem/COFCBaselinePolicy.h"
    replace_once(
        rel,
        '''  // Produces a deterministic physical-card action. Fantasy15 is solved by an
  // exhaustive valid-board search. Normal play enumerates every legal current
  // placement/discard action and uses an exact completed-board foul gate plus
  // a conservative partial-board heuristic.
''',
        '''  // OPENOFC_SMART_BASELINE_V53. Fantasy 14..17 is solved by exhaustive
  // valid-board search with explicit Ultimate re-fantasy value. Normal play
  // still enumerates every legal current placement/discard action, but now uses
  // rules-aware top/Fantasy, straight/flush/full-house potential instead of the
  // old rigid 1/2/2 opening shape. Final self-play/search will replace this.
''')

    rel = "OpenHoldem/COFCRuntimeController.cpp"
    replace_once(
        rel,
        '''  COFCStrategyAction action;
  string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
''',
        '''  COFCStrategyAction action;
  string error;
  write_log(true,
    "[OpenOFC POLICY] engine=SMART_BASELINE_V53 round=%d fantasy=%d incoming=%d\\n",
    state.round_index,
    state.players[state.hero_chair].fantasy ? 1 : 0,
    state.hero_incoming_count);
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
''')


def main():
    patch_rules_aware_scoring()
    patch_policy_header_and_runtime_marker()
    print("OpenOFC smart baseline v5.3 policy patch applied")


if __name__ == "__main__":
    main()
