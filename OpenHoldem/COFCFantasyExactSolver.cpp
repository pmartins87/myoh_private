//******************************************************************************
// OpenOFC v5.7.0 exact Fantasy 14..17 search kernel.
//******************************************************************************

#ifndef DEEPOFC_POLICY_STANDALONE
#include "StdAfx.h"
#endif

#include "COFCFantasyExactSolver.h"

#include <algorithm>
#include <map>
#include <set>
#include <vector>

using namespace std;

namespace {

struct RankLess {
  bool operator()(
      const COFCExactHandRank &left,
      const COFCExactHandRank &right) const {
    return COFCExactEvaluator::CompareHands(left, right) < 0;
  }
};

struct RowCache {
  vector<COFCExactHandRank> ranks;
};

struct Candidate {
  unsigned int top;
  unsigned int middle;
  unsigned int bottom;
  COFCExactBoardResult board;

  Candidate() : top(0), middle(0), bottom(0) {}
};

bool Fail(
    COFCStrategyAction *selected,
    string *error,
    const string &message) {
  if (selected != NULL) selected->Reset();
  if (error != NULL) *error = message;
  return false;
}

int Popcount(unsigned int value) {
  int count = 0;
  while (value) {
    value &= value - 1;
    ++count;
  }
  return count;
}

vector<int> ValuesForMask(
    const vector<int> &incoming,
    unsigned int mask) {
  vector<int> result;
  for (size_t i = 0; i < incoming.size(); ++i) {
    if ((mask & (1u << i)) != 0) result.push_back(incoming[i]);
  }
  return result;
}

bool BuildBoardFromAction(
    const vector<int> &incoming,
    const COFCStrategyAction &action,
    COFCPlayerBoard *board,
    string *error) {
  if (!action.valid || action.placement_count != kOFCCardsPerBoard
      || action.unused_count
         != static_cast<int>(incoming.size()) - kOFCCardsPerBoard) {
    if (error != NULL) *error = "Fantasy action has wrong placement/unused counts";
    return false;
  }
  map<int, int> available;
  for (size_t i = 0; i < incoming.size(); ++i) ++available[incoming[i]];
  int row_count[3] = {0, 0, 0};
  board->Reset();
  for (int i = 0; i < action.placement_count; ++i) {
    const COFCStrategyPlacement &placement = action.placements[i];
    map<int, int>::iterator found = available.find(placement.card_value);
    if (found == available.end() || found->second != 1
        || placement.row < kOFCRowTop || placement.row > kOFCRowBottom) {
      if (error != NULL) *error = "Fantasy action placement violates incoming set";
      return false;
    }
    found->second = 0;
    const int index = row_count[placement.row]++;
    if ((placement.row == kOFCRowTop && index >= kOFCTopCards)
        || (placement.row != kOFCRowTop && index >= kOFCMiddleCards)) {
      if (error != NULL) *error = "Fantasy action exceeds row capacity";
      return false;
    }
    if (placement.row == kOFCRowTop)
      board->top[index].value = placement.card_value;
    else if (placement.row == kOFCRowMiddle)
      board->middle[index].value = placement.card_value;
    else
      board->bottom[index].value = placement.card_value;
  }
  for (int i = 0; i < action.unused_count; ++i) {
    map<int, int>::iterator found = available.find(action.unused_cards[i]);
    if (found == available.end() || found->second != 1) {
      if (error != NULL) *error = "Fantasy unused card violates incoming set";
      return false;
    }
    found->second = 0;
  }
  if (row_count[0] != 3 || row_count[1] != 5 || row_count[2] != 5) {
    if (error != NULL) *error = "Fantasy action is not a 3/5/5 board";
    return false;
  }
  for (map<int, int>::const_iterator it = available.begin();
       it != available.end(); ++it) {
    if (it->second != 0) {
      if (error != NULL) *error = "Fantasy action does not cover incoming exactly";
      return false;
    }
  }
  return true;
}

bool Dominates(
    const COFCExactBoardResult &left,
    const COFCExactBoardResult &right,
    bool require_strict) {
  if (left.foul || right.foul) return !left.foul && right.foul;
  bool strict = false;
  for (int row = 0; row < 3; ++row) {
    const int cmp = COFCExactEvaluator::CompareHands(
      left.rows[row], right.rows[row]);
    if (cmp < 0) return false;
    if (cmp > 0) strict = true;
  }
  if (left.royalties < right.royalties) return false;
  if (left.royalties > right.royalties) strict = true;
  if (!left.refantasy && right.refantasy) return false;
  if (left.refantasy && !right.refantasy) strict = true;
  return !require_strict || strict;
}

bool CandidateLess(const Candidate &left, const Candidate &right) {
  if (left.board.refantasy != right.board.refantasy)
    return left.board.refantasy < right.board.refantasy;
  if (left.board.royalties != right.board.royalties)
    return left.board.royalties < right.board.royalties;
  for (int row = 0; row < 3; ++row) {
    const int cmp = COFCExactEvaluator::CompareHands(
      left.board.rows[row], right.board.rows[row]);
    if (cmp != 0) return cmp < 0;
  }
  if (left.top != right.top) return left.top > right.top;
  if (left.middle != right.middle) return left.middle > right.middle;
  return left.bottom > right.bottom;
}

COFCStrategyAction ActionForMasks(
    const vector<int> &incoming,
    const Candidate &candidate) {
  COFCStrategyAction action;
  for (size_t i = 0; i < incoming.size(); ++i) {
    const unsigned int bit = 1u << i;
    EOFCRow row = kOFCRowUndefined;
    if ((candidate.top & bit) != 0) row = kOFCRowTop;
    else if ((candidate.middle & bit) != 0) row = kOFCRowMiddle;
    else if ((candidate.bottom & bit) != 0) row = kOFCRowBottom;
    if (row == kOFCRowUndefined) {
      action.unused_cards[action.unused_count++] = incoming[i];
    } else {
      COFCStrategyPlacement &placement =
        action.placements[action.placement_count++];
      placement.card_value = incoming[i];
      placement.row = row;
    }
  }
  action.valid = action.placement_count == kOFCCardsPerBoard
    && action.unused_count
       == static_cast<int>(incoming.size()) - kOFCCardsPerBoard;
  return action;
}

}  // namespace

COFCFantasyExactReport::COFCFantasyExactReport()
    : exact_available(false), applied(false), incoming_count(0), mask_pairs(0),
      legal_boards(0), universal_improvements(0), baseline_royalties(0),
      selected_royalties(0), baseline_refantasy(false),
      selected_refantasy(false) {}

bool COFCFantasyExactSolver::ImproveUniversally(
    const COFCState &state,
    const COFCStrategyAction &baseline,
    COFCStrategyAction *selected,
    COFCFantasyExactReport *report,
    string *error) {
  if (selected == NULL || report == NULL) return false;
  *selected = baseline;
  *report = COFCFantasyExactReport();
  if (error != NULL) error->clear();
  if (!state.valid || state.hero_chair < 0
      || state.hero_chair >= state.player_count
      || !state.players[state.hero_chair].fantasy)
    return Fail(selected, error, "exact Fantasy solver requires valid Hero Fantasy state");
  const int count = state.hero_incoming_count;
  if (count < 14 || count > 17)
    return Fail(selected, error, "exact Fantasy solver requires 14..17 incoming cards");

  vector<int> incoming;
  set<int> unique;
  for (int i = 0; i < count; ++i) {
    const int value = state.hero_incoming[i].value;
    if (!state.hero_incoming[i].IsKnownPhysicalCard()
        || !unique.insert(value).second)
      return Fail(selected, error, "exact Fantasy incoming is unknown or duplicated");
    incoming.push_back(value);
  }

  COFCPlayerBoard baseline_board;
  if (!BuildBoardFromAction(incoming, baseline, &baseline_board, error)) {
    selected->Reset();
    return false;
  }
  COFCExactBoardResult baseline_result;
  if (!COFCExactEvaluator::EvaluateBoard(
        baseline_board, &baseline_result, error)) {
    selected->Reset();
    return false;
  }

  report->exact_available = true;
  report->incoming_count = count;
  report->baseline_royalties = baseline_result.royalties;
  report->selected_royalties = baseline_result.royalties;
  report->baseline_refantasy = baseline_result.refantasy;
  report->selected_refantasy = baseline_result.refantasy;
  for (int row = 0; row < 3; ++row) {
    report->baseline_rows[row] = baseline_result.rows[row];
    report->selected_rows[row] = baseline_result.rows[row];
  }

  const unsigned int limit = 1u << count;
  const unsigned int all = limit - 1;
  vector<RowCache> top(limit);
  vector<RowCache> five(limit);
  vector<unsigned int> masks5;
  for (unsigned int mask = 0; mask < limit; ++mask) {
    const int cards = Popcount(mask);
    string row_error;
    if (cards == 3) {
      if (!COFCExactEvaluator::EvaluateRowCandidates(
            ValuesForMask(incoming, mask), true, &top[mask].ranks, &row_error))
        return Fail(selected, error, row_error);
    } else if (cards == 5) {
      masks5.push_back(mask);
      if (!COFCExactEvaluator::EvaluateRowCandidates(
            ValuesForMask(incoming, mask), false, &five[mask].ranks, &row_error))
        return Fail(selected, error, row_error);
    }
  }

  vector<map<COFCExactHandRank, unsigned int, RankLess> >
    top_frontier(limit);
  vector<unsigned char> top_frontier_ready(limit, 0);
  Candidate chosen;
  chosen.board = baseline_result;
  bool have_improvement = false;

  for (size_t b = 0; b < masks5.size(); ++b) {
    const unsigned int bottom_mask = masks5[b];
    const COFCExactHandRank bottom_rank = five[bottom_mask].ranks[0];
    for (size_t m = 0; m < masks5.size(); ++m) {
      const unsigned int middle_mask = masks5[m];
      if ((bottom_mask & middle_mask) != 0) continue;
      ++report->mask_pairs;

      COFCExactHandRank middle_rank;
      bool have_middle = false;
      for (size_t r = 0; r < five[middle_mask].ranks.size(); ++r) {
        if (COFCExactEvaluator::CompareHands(
              five[middle_mask].ranks[r], bottom_rank) <= 0) {
          middle_rank = five[middle_mask].ranks[r];
          have_middle = true;
          break;
        }
      }
      if (!have_middle) continue;

      const unsigned int remaining = all ^ (bottom_mask | middle_mask);
      if (!top_frontier_ready[remaining]) {
        map<COFCExactHandRank, unsigned int, RankLess> &frontier =
          top_frontier[remaining];
        for (unsigned int top_mask = remaining; top_mask != 0;
             top_mask = (top_mask - 1) & remaining) {
          if (Popcount(top_mask) != 3) continue;
          for (size_t r = 0; r < top[top_mask].ranks.size(); ++r) {
            map<COFCExactHandRank, unsigned int, RankLess>::iterator old =
              frontier.find(top[top_mask].ranks[r]);
            if (old == frontier.end() || top_mask < old->second)
              frontier[top[top_mask].ranks[r]] = top_mask;
          }
        }
        top_frontier_ready[remaining] = 1;
      }

      map<COFCExactHandRank, unsigned int, RankLess> &frontier =
        top_frontier[remaining];
      map<COFCExactHandRank, unsigned int, RankLess>::iterator best_top =
        frontier.upper_bound(middle_rank);
      if (best_top == frontier.begin()) continue;
      --best_top;

      vector<COFCExactHandRank> one_top(1, best_top->first);
      vector<COFCExactHandRank> one_middle(1, middle_rank);
      vector<COFCExactHandRank> one_bottom(1, bottom_rank);
      Candidate candidate;
      candidate.top = best_top->second;
      candidate.middle = middle_mask;
      candidate.bottom = bottom_mask;
      string resolve_error;
      if (!COFCExactEvaluator::ResolveBoardCandidates(
            one_top, one_middle, one_bottom,
            &candidate.board, &resolve_error)
          || candidate.board.foul) continue;
      ++report->legal_boards;

      if (!Dominates(candidate.board, baseline_result, true)) continue;
      ++report->universal_improvements;
      if (!have_improvement || CandidateLess(chosen, candidate)) {
        chosen = candidate;
        have_improvement = true;
      }
    }
  }

  if (!have_improvement) return true;
  *selected = ActionForMasks(incoming, chosen);
  if (!selected->valid)
    return Fail(selected, error, "exact Fantasy solver produced invalid action");
  report->applied = true;
  report->selected_royalties = chosen.board.royalties;
  report->selected_refantasy = chosen.board.refantasy;
  for (int row = 0; row < 3; ++row)
    report->selected_rows[row] = chosen.board.rows[row];
  return true;
}
