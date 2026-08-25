//******************************************************************************
// OpenOFC v5.6.0 exact terminal rules oracle.
//******************************************************************************

#ifndef DEEPOFC_POLICY_STANDALONE
#include "StdAfx.h"
#endif

#include "COFCExactEvaluator.h"

#include <algorithm>
#include <map>
#include <set>
#include <vector>

using namespace std;

namespace {

struct ExactCard {
  int rank;
  int suit;
  bool joker;
};

bool Fail(string *error, const string &message) {
  if (error != NULL) *error = message;
  return false;
}

ExactCard ConvertCard(int value) {
  ExactCard card;
  card.joker = value == kOFCCardJoker1 || value == kOFCCardJoker2;
  card.rank = card.joker ? 0 : value / 4 + 2;
  card.suit = card.joker ? -1 : value & 0x03;
  return card;
}

COFCExactHandRank MakeRank(int category, const vector<int> &tie) {
  COFCExactHandRank rank;
  rank.category = category;
  rank.length = min(5, static_cast<int>(tie.size()));
  for (int i = 0; i < rank.length; ++i) rank.tie[i] = tie[i];
  return rank;
}

struct RankLess {
  bool operator()(
      const COFCExactHandRank &left,
      const COFCExactHandRank &right) const {
    return COFCExactEvaluator::CompareHands(left, right) < 0;
  }
};

int StraightHigh(vector<int> ranks) {
  sort(ranks.begin(), ranks.end());
  ranks.erase(unique(ranks.begin(), ranks.end()), ranks.end());
  if (ranks.size() != 5) return 0;
  const int wheel[5] = {2, 3, 4, 5, 14};
  bool is_wheel = true;
  for (int i = 0; i < 5; ++i) {
    if (ranks[i] != wheel[i]) is_wheel = false;
  }
  if (is_wheel) return 5;
  return ranks[4] - ranks[0] == 4 ? ranks[4] : 0;
}

COFCExactHandRank RankTopStandard(const vector<ExactCard> &cards) {
  map<int, int> counts;
  vector<int> ranks;
  for (size_t i = 0; i < cards.size(); ++i) {
    ++counts[cards[i].rank];
    ranks.push_back(cards[i].rank);
  }
  sort(ranks.rbegin(), ranks.rend());
  for (map<int, int>::reverse_iterator it = counts.rbegin();
       it != counts.rend(); ++it) {
    if (it->second == 3)
      return MakeRank(kOFCExactTrips, vector<int>(1, it->first));
  }
  for (map<int, int>::reverse_iterator it = counts.rbegin();
       it != counts.rend(); ++it) {
    if (it->second == 2) {
      int kicker = 0;
      for (size_t i = 0; i < ranks.size(); ++i) {
        if (ranks[i] != it->first) kicker = max(kicker, ranks[i]);
      }
      vector<int> tie;
      tie.push_back(it->first);
      tie.push_back(kicker);
      return MakeRank(kOFCExactPair, tie);
    }
  }
  return MakeRank(kOFCExactHighCard, ranks);
}

bool ValidFiveNominal(const vector<ExactCard> &cards) {
  map<int, int> counts;
  for (size_t i = 0; i < cards.size(); ++i) ++counts[cards[i].rank];
  for (map<int, int>::const_iterator it = counts.begin();
       it != counts.end(); ++it) {
    if (it->second > 4) return false;
  }
  return true;
}

COFCExactHandRank RankFiveStandard(const vector<ExactCard> &cards) {
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
  if (straight && flush)
    return MakeRank(kOFCExactStraightFlush, vector<int>(1, straight));

  int quad = 0;
  int trip = 0;
  int pair_high = 0;
  int pair_low = 0;
  for (map<int, int>::const_iterator it = counts.begin();
       it != counts.end(); ++it) {
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
    for (size_t i = 0; i < ranks.size(); ++i) {
      if (ranks[i] != quad) kicker = max(kicker, ranks[i]);
    }
    vector<int> tie;
    tie.push_back(quad);
    tie.push_back(kicker);
    return MakeRank(kOFCExactQuads, tie);
  }
  if (trip && pair_high) {
    vector<int> tie;
    tie.push_back(trip);
    tie.push_back(pair_high);
    return MakeRank(kOFCExactFullHouse, tie);
  }
  if (flush) return MakeRank(kOFCExactFlush, ranks);
  if (straight)
    return MakeRank(kOFCExactStraight, vector<int>(1, straight));
  if (trip) {
    vector<int> tie(1, trip);
    for (size_t i = 0; i < ranks.size(); ++i) {
      if (ranks[i] != trip) tie.push_back(ranks[i]);
    }
    return MakeRank(kOFCExactTrips, tie);
  }
  if (pair_high && pair_low) {
    int kicker = 0;
    for (size_t i = 0; i < ranks.size(); ++i) {
      if (ranks[i] != pair_high && ranks[i] != pair_low)
        kicker = max(kicker, ranks[i]);
    }
    vector<int> tie;
    tie.push_back(pair_high);
    tie.push_back(pair_low);
    tie.push_back(kicker);
    return MakeRank(kOFCExactTwoPair, tie);
  }
  if (pair_high) {
    vector<int> tie(1, pair_high);
    for (size_t i = 0; i < ranks.size(); ++i) {
      if (ranks[i] != pair_high) tie.push_back(ranks[i]);
    }
    return MakeRank(kOFCExactPair, tie);
  }
  return MakeRank(kOFCExactHighCard, ranks);
}

vector<ExactCard> NominalDeck() {
  vector<ExactCard> deck;
  for (int suit = 0; suit < 4; ++suit) {
    for (int rank = 2; rank <= 14; ++rank) {
      ExactCard card;
      card.rank = rank;
      card.suit = suit;
      card.joker = false;
      deck.push_back(card);
    }
  }
  return deck;
}

vector<COFCExactHandRank> CandidateRanks(
    const vector<int> &values, bool top) {
  vector<ExactCard> standard;
  int jokers = 0;
  for (size_t i = 0; i < values.size(); ++i) {
    ExactCard card = ConvertCard(values[i]);
    if (card.joker) ++jokers;
    else standard.push_back(card);
  }

  set<COFCExactHandRank, RankLess> unique;
  if (jokers == 0) {
    unique.insert(top ? RankTopStandard(standard)
                      : RankFiveStandard(standard));
  } else {
    const vector<ExactCard> deck = NominalDeck();
    for (size_t first = 0; first < deck.size(); ++first) {
      const size_t second_limit = jokers == 2 ? deck.size() : 1;
      for (size_t second = 0; second < second_limit; ++second) {
        vector<ExactCard> nominal = standard;
        nominal.push_back(deck[first]);
        if (jokers == 2) nominal.push_back(deck[second]);
        if (!top && !ValidFiveNominal(nominal)) continue;
        unique.insert(top ? RankTopStandard(nominal)
                          : RankFiveStandard(nominal));
      }
    }
  }
  vector<COFCExactHandRank> result(unique.begin(), unique.end());
  reverse(result.begin(), result.end());
  return result;
}

int TopRoyalty(const COFCExactHandRank &rank) {
  if (rank.category == kOFCExactPair && rank.tie[0] >= 6)
    return rank.tie[0] - 5;
  if (rank.category == kOFCExactTrips) return rank.tie[0] + 8;
  return 0;
}

int MiddleRoyalty(const COFCExactHandRank &rank) {
  if (rank.category == kOFCExactStraightFlush && rank.tie[0] == 14)
    return 50;
  if (rank.category == kOFCExactTrips) return 2;
  if (rank.category == kOFCExactStraight) return 4;
  if (rank.category == kOFCExactFlush) return 8;
  if (rank.category == kOFCExactFullHouse) return 12;
  if (rank.category == kOFCExactQuads) return 20;
  if (rank.category == kOFCExactStraightFlush) return 30;
  return 0;
}

int BottomRoyalty(const COFCExactHandRank &rank) {
  if (rank.category == kOFCExactStraightFlush && rank.tie[0] == 14)
    return 25;
  if (rank.category == kOFCExactStraight) return 2;
  if (rank.category == kOFCExactFlush) return 4;
  if (rank.category == kOFCExactFullHouse) return 6;
  if (rank.category == kOFCExactQuads) return 10;
  if (rank.category == kOFCExactStraightFlush) return 15;
  return 0;
}

bool ResolveBoard(
    const vector<COFCExactHandRank> &top,
    const vector<COFCExactHandRank> &middle,
    const vector<COFCExactHandRank> &bottom,
    COFCExactHandRank rows[3]) {
  if (top.empty() || middle.empty() || bottom.empty()) return false;
  const COFCExactHandRank bottom_rank = bottom[0];
  COFCExactHandRank middle_rank;
  bool found_middle = false;
  for (size_t i = 0; i < middle.size(); ++i) {
    if (COFCExactEvaluator::CompareHands(middle[i], bottom_rank) <= 0) {
      middle_rank = middle[i];
      found_middle = true;
      break;
    }
  }
  if (!found_middle) return false;
  for (size_t i = 0; i < top.size(); ++i) {
    if (COFCExactEvaluator::CompareHands(top[i], middle_rank) <= 0) {
      rows[0] = top[i];
      rows[1] = middle_rank;
      rows[2] = bottom_rank;
      return true;
    }
  }
  return false;
}

vector<int> RowValues(const COFCCard *cards, int count) {
  vector<int> result;
  for (int i = 0; i < count; ++i) result.push_back(cards[i].value);
  return result;
}

bool KnownPhysical(int value) {
  return (value >= 0 && value <= 51)
    || value == kOFCCardJoker1 || value == kOFCCardJoker2;
}

}  // namespace

COFCExactHandRank::COFCExactHandRank()
    : category(kOFCExactHighCard), length(0) {
  for (int i = 0; i < 5; ++i) tie[i] = 0;
}

COFCExactBoardResult::COFCExactBoardResult()
    : complete(false), foul(false), royalties(0), fantasy_cards(0),
      refantasy(false) {}

COFCExactMatchResult::COFCExactMatchResult()
    : valid(false), row_points(0), scoop_bonus(0), base_points(0),
      hero_royalties(0), opponent_royalties(0), total_points(0) {}

int COFCExactEvaluator::CompareHands(
    const COFCExactHandRank &left,
    const COFCExactHandRank &right) {
  if (left.category != right.category)
    return left.category < right.category ? -1 : 1;
  const int count = max(left.length, right.length);
  for (int i = 0; i < count; ++i) {
    const int a = i < left.length ? left.tie[i] : 0;
    const int b = i < right.length ? right.tie[i] : 0;
    if (a != b) return a < b ? -1 : 1;
  }
  return 0;
}

bool COFCExactEvaluator::EvaluateBoard(
    const COFCPlayerBoard &board,
    COFCExactBoardResult *result,
    string *error) {
  if (result == NULL) return false;
  *result = COFCExactBoardResult();
  if (error != NULL) error->clear();

  set<int> physical;
  const COFCCard *row_cards[3] = {board.top, board.middle, board.bottom};
  const int row_sizes[3] = {kOFCTopCards, kOFCMiddleCards, kOFCBottomCards};
  for (int row = 0; row < 3; ++row) {
    for (int i = 0; i < row_sizes[row]; ++i) {
      const int value = row_cards[row][i].value;
      if (!KnownPhysical(value))
        return Fail(error, "terminal board is incomplete or unknown");
      if (!physical.insert(value).second)
        return Fail(error, "terminal board contains duplicate physical card");
    }
  }

  const vector<COFCExactHandRank> top =
    CandidateRanks(RowValues(board.top, kOFCTopCards), true);
  const vector<COFCExactHandRank> middle =
    CandidateRanks(RowValues(board.middle, kOFCMiddleCards), false);
  const vector<COFCExactHandRank> bottom =
    CandidateRanks(RowValues(board.bottom, kOFCBottomCards), false);

  result->complete = true;
  if (!ResolveBoard(top, middle, bottom, result->rows)) {
    result->foul = true;
    if (!top.empty()) result->rows[0] = top[0];
    if (!middle.empty()) result->rows[1] = middle[0];
    if (!bottom.empty()) result->rows[2] = bottom[0];
    return true;
  }

  result->foul = false;
  result->royalties = TopRoyalty(result->rows[0])
    + MiddleRoyalty(result->rows[1])
    + BottomRoyalty(result->rows[2]);

  const COFCExactHandRank &top_rank = result->rows[0];
  if (top_rank.category == kOFCExactTrips) {
    result->fantasy_cards = 17;
  } else if (top_rank.category == kOFCExactPair) {
    if (top_rank.tie[0] == 14) result->fantasy_cards = 16;
    else if (top_rank.tie[0] == 13) result->fantasy_cards = 15;
    else if (top_rank.tie[0] == 12) result->fantasy_cards = 14;
  }
  result->refantasy = top_rank.category == kOFCExactTrips
    || result->rows[2].category >= kOFCExactQuads;
  return true;
}

bool COFCExactEvaluator::ScoreMatch(
    const COFCExactBoardResult &hero,
    const COFCExactBoardResult &opponent,
    COFCExactMatchResult *result,
    string *error) {
  if (result == NULL) return false;
  *result = COFCExactMatchResult();
  if (error != NULL) error->clear();
  if (!hero.complete || !opponent.complete)
    return Fail(error, "match scoring requires two complete board evaluations");

  result->hero_royalties = hero.foul ? 0 : hero.royalties;
  result->opponent_royalties = opponent.foul ? 0 : opponent.royalties;
  if (hero.foul && opponent.foul) {
    result->base_points = 0;
  } else if (hero.foul) {
    result->base_points = -6;
  } else if (opponent.foul) {
    result->base_points = 6;
  } else {
    for (int row = 0; row < 3; ++row) {
      result->row_points += CompareHands(hero.rows[row], opponent.rows[row]);
    }
    if (result->row_points == 3) result->scoop_bonus = 3;
    else if (result->row_points == -3) result->scoop_bonus = -3;
    result->base_points = result->row_points + result->scoop_bonus;
  }
  result->total_points = result->base_points
    + result->hero_royalties - result->opponent_royalties;
  result->valid = true;
  return true;
}
