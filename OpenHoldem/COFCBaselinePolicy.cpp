//******************************************************************************
// DeepOFC FP0 deterministic legal policy.
//******************************************************************************

#ifndef DEEPOFC_POLICY_STANDALONE
#include "StdAfx.h"
#else
#define StdDeck_RANK(card) ((card) % 13)
#define StdDeck_SUIT(card) ((card) / 13)
#endif
#include "COFCBaselinePolicy.h"

#include <algorithm>
#include <array>
#include <map>
#include <set>
#include <sstream>
#include <vector>

using namespace std;

namespace {

enum Category {
  kHighCard = 0,
  kPair = 1,
  kTwoPair = 2,
  kTrips = 3,
  kStraight = 4,
  kFlush = 5,
  kFullHouse = 6,
  kQuads = 7,
  kStraightFlush = 8
};

struct PolicyCard {
  int value;
  int rank;
  int suit;
  int joker;
};

struct HandRank {
  int category;
  int tie[5];
  int length;

  HandRank() : category(0), length(0) {
    for (int i = 0; i < 5; ++i) tie[i] = 0;
  }
  HandRank(int c, const vector<int> &values) : category(c), length(0) {
    for (int i = 0; i < 5; ++i) tie[i] = 0;
    length = min(5, static_cast<int>(values.size()));
    for (int i = 0; i < length; ++i) tie[i] = values[i];
  }
};

bool operator<(const HandRank &left, const HandRank &right) {
  if (left.category != right.category) return left.category < right.category;
  const int count = max(left.length, right.length);
  for (int i = 0; i < count; ++i) {
    const int a = i < left.length ? left.tie[i] : 0;
    const int b = i < right.length ? right.tie[i] : 0;
    if (a != b) return a < b;
  }
  return false;
}

bool operator==(const HandRank &left, const HandRank &right) {
  return !(left < right) && !(right < left);
}

bool LessOrEqual(const HandRank &left, const HandRank &right) {
  return left < right || left == right;
}

bool Fail(COFCStrategyAction *action, string *error, const string &message) {
  if (action != NULL) action->Reset();
  if (error != NULL) *error = message;
  return false;
}

PolicyCard Convert(int value) {
  PolicyCard card;
  card.value = value;
  card.joker = value == kOFCCardJoker1 ? 1
    : (value == kOFCCardJoker2 ? 2 : 0);
  if (card.joker != 0) {
    card.rank = 0;
    card.suit = -1;
  } else {
    card.rank = StdDeck_RANK(value) + 2;
    card.suit = StdDeck_SUIT(value);
  }
  return card;
}

vector<PolicyCard> NominalDeck() {
  vector<PolicyCard> deck;
  for (int suit = 0; suit < 4; ++suit) {
    for (int rank = 2; rank <= 14; ++rank) {
      PolicyCard card;
      card.value = -1;
      card.rank = rank;
      card.suit = suit;
      card.joker = 0;
      deck.push_back(card);
    }
  }
  return deck;
}

int StraightHigh(vector<int> ranks) {
  sort(ranks.begin(), ranks.end());
  ranks.erase(unique(ranks.begin(), ranks.end()), ranks.end());
  if (ranks.size() != 5) return 0;
  const int wheel[5] = {2, 3, 4, 5, 14};
  bool is_wheel = true;
  for (int i = 0; i < 5; ++i) if (ranks[i] != wheel[i]) is_wheel = false;
  if (is_wheel) return 5;
  return ranks[4] - ranks[0] == 4 ? ranks[4] : 0;
}

HandRank RankTopStandard(const vector<PolicyCard> &cards) {
  map<int, int> counts;
  vector<int> ranks;
  for (size_t i = 0; i < cards.size(); ++i) {
    ++counts[cards[i].rank];
    ranks.push_back(cards[i].rank);
  }
  sort(ranks.rbegin(), ranks.rend());
  for (map<int, int>::reverse_iterator it = counts.rbegin(); it != counts.rend(); ++it) {
    if (it->second == 3) return HandRank(kTrips, vector<int>(1, it->first));
  }
  for (map<int, int>::reverse_iterator it = counts.rbegin(); it != counts.rend(); ++it) {
    if (it->second == 2) {
      int kicker = 0;
      for (size_t i = 0; i < ranks.size(); ++i)
        if (ranks[i] != it->first) kicker = max(kicker, ranks[i]);
      vector<int> tie;
      tie.push_back(it->first);
      tie.push_back(kicker);
      return HandRank(kPair, tie);
    }
  }
  return HandRank(kHighCard, ranks);
}

bool ValidFiveNominal(const vector<PolicyCard> &cards) {
  map<int, int> counts;
  for (size_t i = 0; i < cards.size(); ++i) ++counts[cards[i].rank];
  for (map<int, int>::const_iterator it = counts.begin(); it != counts.end(); ++it)
    if (it->second > 4) return false;
  return true;
}

HandRank RankFiveStandard(const vector<PolicyCard> &cards) {
  map<int, int> counts;
  vector<int> ranks;
  bool flush = true;
  const int first_suit = cards[0].suit;
  for (size_t i = 0; i < cards.size(); ++i) {
    ++counts[cards[i].rank];
    ranks.push_back(cards[i].rank);
    if (cards[i].suit != first_suit) flush = false;
  }
  const int straight = StraightHigh(ranks);
  if (straight && flush) return HandRank(kStraightFlush, vector<int>(1, straight));
  int quad = 0;
  int trip = 0;
  int pair_high = 0;
  int pair_low = 0;
  for (map<int, int>::const_iterator it = counts.begin(); it != counts.end(); ++it) {
    if (it->second == 4) quad = max(quad, it->first);
    if (it->second == 3) trip = max(trip, it->first);
    if (it->second == 2) {
      if (it->first > pair_high) {
        pair_low = pair_high;
        pair_high = it->first;
      } else if (it->first > pair_low) {
        pair_low = it->first;
      }
    }
  }
  sort(ranks.rbegin(), ranks.rend());
  if (quad) {
    int kicker = 0;
    for (size_t i = 0; i < ranks.size(); ++i)
      if (ranks[i] != quad) kicker = max(kicker, ranks[i]);
    vector<int> tie;
    tie.push_back(quad); tie.push_back(kicker);
    return HandRank(kQuads, tie);
  }
  if (trip && pair_high) {
    vector<int> tie;
    tie.push_back(trip); tie.push_back(pair_high);
    return HandRank(kFullHouse, tie);
  }
  if (flush) return HandRank(kFlush, ranks);
  if (straight) return HandRank(kStraight, vector<int>(1, straight));
  if (trip) {
    vector<int> tie(1, trip);
    for (size_t i = 0; i < ranks.size(); ++i)
      if (ranks[i] != trip) tie.push_back(ranks[i]);
    return HandRank(kTrips, tie);
  }
  if (pair_high && pair_low) {
    int kicker = 0;
    for (size_t i = 0; i < ranks.size(); ++i)
      if (ranks[i] != pair_high && ranks[i] != pair_low)
        kicker = max(kicker, ranks[i]);
    vector<int> tie;
    tie.push_back(pair_high); tie.push_back(pair_low); tie.push_back(kicker);
    return HandRank(kTwoPair, tie);
  }
  if (pair_high) {
    vector<int> tie(1, pair_high);
    for (size_t i = 0; i < ranks.size(); ++i)
      if (ranks[i] != pair_high) tie.push_back(ranks[i]);
    return HandRank(kPair, tie);
  }
  return HandRank(kHighCard, ranks);
}

bool SameNominalCard(const PolicyCard &left, const PolicyCard &right) {
  return left.joker == 0 && right.joker == 0
    && left.rank == right.rank && left.suit == right.suit;
}

bool ContainsNominalCard(
    const vector<PolicyCard> &cards, const PolicyCard &candidate) {
  for (size_t i = 0; i < cards.size(); ++i) {
    if (SameNominalCard(cards[i], candidate)) return true;
  }
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
      const size_t second_limit = joker_count == 2 ? deck.size() : 1;
      for (size_t second = 0; second < second_limit; ++second) {
        if (ContainsNominalCard(standard, deck[second])
            || SameNominalCard(deck[first], deck[second])) continue;
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

int TopRoyalty(const HandRank &rank) {
  if (rank.category == kPair && rank.tie[0] >= 6) return rank.tie[0] - 5;
  if (rank.category == kTrips) return rank.tie[0] + 8;
  return 0;
}

int MiddleRoyalty(const HandRank &rank) {
  if (rank.category == kStraightFlush && rank.tie[0] == 14) return 50;
  if (rank.category == kTrips) return 2;
  if (rank.category == kStraight) return 4;
  if (rank.category == kFlush) return 8;
  if (rank.category == kFullHouse) return 12;
  if (rank.category == kQuads) return 20;
  if (rank.category == kStraightFlush) return 30;
  return 0;
}

int BottomRoyalty(const HandRank &rank) {
  if (rank.category == kStraightFlush && rank.tie[0] == 14) return 25;
  if (rank.category == kStraight) return 2;
  if (rank.category == kFlush) return 4;
  if (rank.category == kFullHouse) return 6;
  if (rank.category == kQuads) return 10;
  if (rank.category == kStraightFlush) return 15;
  return 0;
}

int Royalties(const array<HandRank, 3> &ranks) {
  return TopRoyalty(ranks[0])
    + MiddleRoyalty(ranks[1]) + BottomRoyalty(ranks[2]);
}

bool ResolveBoard(
    const vector<HandRank> &top,
    const vector<HandRank> &middle,
    const vector<HandRank> &bottom,
    array<HandRank, 3> *result) {
  if (top.empty() || middle.empty() || bottom.empty()) return false;
  const HandRank bottom_rank = bottom[0];
  HandRank middle_rank;
  bool found_middle = false;
  for (size_t i = 0; i < middle.size(); ++i) {
    if (LessOrEqual(middle[i], bottom_rank)) {
      middle_rank = middle[i];
      found_middle = true;
      break;
    }
  }
  if (!found_middle) return false;
  for (size_t i = 0; i < top.size(); ++i) {
    if (LessOrEqual(top[i], middle_rank)) {
      (*result)[0] = top[i];
      (*result)[1] = middle_rank;
      (*result)[2] = bottom_rank;
      return true;
    }
  }
  return false;
}

vector<PolicyCard> CardsForMask(
    const vector<PolicyCard> &cards, unsigned int mask) {
  vector<PolicyCard> result;
  for (size_t i = 0; i < cards.size(); ++i)
    if ((mask & (1u << i)) != 0) result.push_back(cards[i]);
  return result;
}

int Popcount(unsigned int value) {
  int count = 0;
  while (value) { value &= value - 1; ++count; }
  return count;
}

long long RankScalar(const HandRank &rank) {
  long long value = rank.category;
  for (int i = 0; i < 5; ++i) value = value * 15 + rank.tie[i];
  return value;
}

bool ChooseFantasy15(
    const COFCState &state, COFCStrategyAction *action, string *error) {
  if (state.hero_incoming_count != 15) {
    return Fail(action, error,
      "operational FP0 Fantasy policy is intentionally limited to exactly 15 cards");
  }
  vector<PolicyCard> incoming;
  for (int i = 0; i < 15; ++i) {
    if (!state.hero_incoming[i].IsKnownPhysicalCard())
      return Fail(action, error, "Fantasy incoming contains unknown card");
    incoming.push_back(Convert(state.hero_incoming[i].value));
  }
  const unsigned int limit = 1u << 15;
  const unsigned int all = limit - 1;
  vector<unsigned int> masks3;
  vector<unsigned int> masks5;
  vector<vector<HandRank> > top(limit);
  vector<vector<HandRank> > five(limit);
  for (unsigned int mask = 0; mask < limit; ++mask) {
    const int count = Popcount(mask);
    if (count == 3) {
      masks3.push_back(mask);
      top[mask] = CandidateRanks(CardsForMask(incoming, mask), true);
    } else if (count == 5) {
      masks5.push_back(mask);
      five[mask] = CandidateRanks(CardsForMask(incoming, mask), false);
    }
  }

  long long best_score = -1;
  unsigned int best_top = 0;
  unsigned int best_middle = 0;
  unsigned int best_bottom = 0;
  vector<map<HandRank, unsigned int> > top_frontier(limit);
  vector<unsigned char> top_frontier_ready(limit, 0);
  for (size_t b = 0; b < masks5.size(); ++b) {
    const unsigned int bottom_mask = masks5[b];
    const HandRank bottom = five[bottom_mask][0];
    for (size_t m = 0; m < masks5.size(); ++m) {
      const unsigned int middle_mask = masks5[m];
      if ((bottom_mask & middle_mask) != 0) continue;
      HandRank middle;
      bool found_middle = false;
      for (size_t r = 0; r < five[middle_mask].size(); ++r) {
        if (LessOrEqual(five[middle_mask][r], bottom)) {
          middle = five[middle_mask][r];
          found_middle = true;
          break;
        }
      }
      if (!found_middle) continue;
      const unsigned int remaining = all ^ (bottom_mask | middle_mask);
      if (!top_frontier_ready[remaining]) {
        map<HandRank, unsigned int> &frontier = top_frontier[remaining];
        for (unsigned int top_mask = remaining; top_mask != 0;
             top_mask = (top_mask - 1) & remaining) {
          if (Popcount(top_mask) != 3) continue;
          for (size_t r = 0; r < top[top_mask].size(); ++r) {
            map<HandRank, unsigned int>::iterator old =
              frontier.find(top[top_mask][r]);
            if (old == frontier.end() || top_mask < old->second)
              frontier[top[top_mask][r]] = top_mask;
          }
        }
        top_frontier_ready[remaining] = 1;
      }
      map<HandRank, unsigned int> &frontier = top_frontier[remaining];
      map<HandRank, unsigned int>::iterator best = frontier.upper_bound(middle);
      if (best == frontier.begin()) continue;
      --best;
      const HandRank top_rank = best->first;
      const unsigned int top_mask = best->second;
      array<HandRank, 3> ranks = {{top_rank, middle, bottom}};
      const long long score = static_cast<long long>(Royalties(ranks)) * 1000000000LL
        + RankScalar(bottom) * 10000LL
        + RankScalar(middle) * 100LL
        + RankScalar(top_rank);
      if (score > best_score
          || (score == best_score
              && (top_mask < best_top
                  || (top_mask == best_top && middle_mask < best_middle)
                  || (top_mask == best_top && middle_mask == best_middle
                      && bottom_mask < best_bottom)))) {
        best_score = score;
        best_top = top_mask;
        best_middle = middle_mask;
        best_bottom = bottom_mask;
      }
    }
  }
  if (best_score < 0) return Fail(action, error, "no valid Fantasy15 board found");

  action->Reset();
  for (int i = 0; i < 15; ++i) {
    EOFCRow row = kOFCRowUndefined;
    if ((best_top & (1u << i)) != 0) row = kOFCRowTop;
    else if ((best_middle & (1u << i)) != 0) row = kOFCRowMiddle;
    else if ((best_bottom & (1u << i)) != 0) row = kOFCRowBottom;
    if (row == kOFCRowUndefined) {
      action->unused_cards[action->unused_count++] = incoming[i].value;
    } else {
      COFCStrategyPlacement &placement =
        action->placements[action->placement_count++];
      placement.card_value = incoming[i].value;
      placement.row = row;
    }
  }
  action->valid = action->placement_count == 13 && action->unused_count == 2;
  return action->valid;
}

void BoardRows(const COFCPlayerBoard &board, vector<PolicyCard> rows[3]) {
  for (int i = 0; i < kOFCTopCards; ++i)
    if (board.top[i].IsKnownPhysicalCard()) rows[0].push_back(Convert(board.top[i].value));
  for (int i = 0; i < kOFCMiddleCards; ++i)
    if (board.middle[i].IsKnownPhysicalCard()) rows[1].push_back(Convert(board.middle[i].value));
  for (int i = 0; i < kOFCBottomCards; ++i)
    if (board.bottom[i].IsKnownPhysicalCard()) rows[2].push_back(Convert(board.bottom[i].value));
}

long long PartialRowScore(const vector<PolicyCard> &cards, int row) {
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

bool CompletedRowsLegal(vector<PolicyCard> rows[3]) {
  if (rows[1].size() == 5 && rows[2].size() == 5) {
    vector<HandRank> middle = CandidateRanks(rows[1], false);
    vector<HandRank> bottom = CandidateRanks(rows[2], false);
    bool compatible = false;
    for (size_t m = 0; m < middle.size(); ++m)
      if (LessOrEqual(middle[m], bottom[0])) { compatible = true; break; }
    if (!compatible) return false;
  }
  if (rows[0].size() == 3 && rows[1].size() == 5) {
    vector<HandRank> top = CandidateRanks(rows[0], true);
    vector<HandRank> middle = CandidateRanks(rows[1], false);
    bool compatible = false;
    for (size_t t = 0; t < top.size(); ++t)
      for (size_t m = 0; m < middle.size(); ++m)
        if (LessOrEqual(top[t], middle[m])) { compatible = true; break; }
    if (!compatible) return false;
  }
  return true;
}

long long NormalScore(vector<PolicyCard> rows[3]) {
  if (!CompletedRowsLegal(rows)) return -1;
  long long score = 0;
  for (int row = 0; row < 3; ++row) score += PartialRowScore(rows[row], row) * (row + 1);
  if (rows[0].size() == 3 && rows[1].size() == 5 && rows[2].size() == 5) {
    array<HandRank, 3> resolved;
    if (!ResolveBoard(
          CandidateRanks(rows[0], true),
          CandidateRanks(rows[1], false),
          CandidateRanks(rows[2], false), &resolved)) return -1;
    score += static_cast<long long>(Royalties(resolved)) * 1000000LL;
    score += RankScalar(resolved[2]) * 1000LL;
    score += RankScalar(resolved[1]) * 10LL;
    score += RankScalar(resolved[0]);
  }
  return score;
}

void EnumerateNormal(
    const vector<PolicyCard> &incoming,
    int index,
    int unused_index,
    vector<PolicyCard> rows[3],
    int assignments[],
    bool opening,
    long long *best_score,
    int best_assignments[]) {
  if (index == static_cast<int>(incoming.size())) {
    long long score = NormalScore(rows);
    if (opening && score >= 0) {
      // A conservative 1/2/2 opening prevents the integration policy from
      // accepting KKPoker's initial all-bottom visual layout as strategy.
      // The trained policy may later choose more nuanced opening shapes.
      const int target[3] = {1, 2, 2};
      int deviation = 0;
      for (int row = 0; row < 3; ++row)
        deviation += abs(static_cast<int>(rows[row].size()) - target[row]);
      score -= static_cast<long long>(deviation) * 1000000LL;
    }
    if (score > *best_score) {
      *best_score = score;
      for (size_t i = 0; i < incoming.size(); ++i)
        best_assignments[i] = assignments[i];
    }
    return;
  }
  if (index == unused_index) {
    assignments[index] = -1;
    EnumerateNormal(incoming, index + 1, unused_index,
      rows, assignments, opening, best_score, best_assignments);
    return;
  }
  const int capacities[3] = {3, 5, 5};
  for (int row = 0; row < 3; ++row) {
    if (static_cast<int>(rows[row].size()) >= capacities[row]) continue;
    rows[row].push_back(incoming[index]);
    assignments[index] = row;
    EnumerateNormal(incoming, index + 1, unused_index,
      rows, assignments, opening, best_score, best_assignments);
    rows[row].pop_back();
  }
}

bool ChooseNormal(
    const COFCState &state, COFCStrategyAction *action, string *error) {
  const int expected = state.round_index == 0 ? 5 : 3;
  if (state.hero_incoming_count != expected) {
    return Fail(action, error, "normal incoming count disagrees with round");
  }
  vector<PolicyCard> incoming;
  for (int i = 0; i < expected; ++i) {
    if (!state.hero_incoming[i].IsKnownPhysicalCard())
      return Fail(action, error, "normal incoming contains unknown card");
    incoming.push_back(Convert(state.hero_incoming[i].value));
  }
  vector<PolicyCard> baseline[3];
  BoardRows(state.players[state.hero_chair].board, baseline);
  long long best_score = -1;
  int best_assignments[5] = {-2, -2, -2, -2, -2};
  const int first_unused = state.round_index == 0 ? -1 : 0;
  const int last_unused = state.round_index == 0 ? -1 : expected - 1;
  for (int unused = first_unused; unused <= last_unused; ++unused) {
    // The measured client keeps a substituted Joker identifiable on the board
    // with a persistent marker, while a discarded Joker has no equally strong
    // tracker calibration yet. Preserve every physical Joker at FP0 so the
    // canonical lineage remains observable and strategically sensible.
    if (unused >= 0 && incoming[unused].joker != 0) continue;
    vector<PolicyCard> rows[3] = {baseline[0], baseline[1], baseline[2]};
    int assignments[5] = {-2, -2, -2, -2, -2};
    EnumerateNormal(incoming, 0, unused, rows,
      assignments, state.round_index == 0,
      &best_score, best_assignments);
  }
  if (best_score < 0) return Fail(action, error, "no legal normal placement found");
  action->Reset();
  for (int i = 0; i < expected; ++i) {
    if (best_assignments[i] < 0) {
      action->unused_cards[action->unused_count++] = incoming[i].value;
    } else {
      COFCStrategyPlacement &placement =
        action->placements[action->placement_count++];
      placement.card_value = incoming[i].value;
      placement.row = static_cast<EOFCRow>(best_assignments[i]);
    }
  }
  action->valid = action->placement_count == (state.round_index == 0 ? 5 : 2)
    && action->unused_count == (state.round_index == 0 ? 0 : 1);
  return action->valid;
}

}  // namespace

bool COFCBaselinePolicy::Choose(
    const COFCState &state,
    COFCStrategyAction *action,
    string *error) {
  if (action == NULL) return false;
  action->Reset();
  if (error != NULL) error->clear();
  if (!state.valid) return Fail(action, error, "policy received invalid state");
  if (state.hero_chair < 0 || state.hero_chair >= state.player_count)
    return Fail(action, error, "policy received invalid Hero chair");
  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare)
    return Fail(action, error, "policy called when Hero cannot prepare");
  if (state.players[state.hero_chair].fantasy)
    return ChooseFantasy15(state, action, error);
  if (state.round_index < 0 || state.round_index > 4)
    return Fail(action, error, "policy received invalid normal round");
  return ChooseNormal(state, action, error);
}
