//******************************************************************************
// OpenOFC v5.6.0 exact normal-R4 teacher.
//******************************************************************************

#ifndef DEEPOFC_POLICY_STANDALONE
#include "StdAfx.h"
#endif

#include "COFCR4ExactTeacher.h"

#include <algorithm>
#include <set>
#include <vector>

#include "COFCExactEvaluator.h"

using namespace std;

namespace {

struct ExactCandidate {
  COFCStrategyAction action;
  COFCExactBoardResult board;
  int points;
};

bool Fail(string *error, const string &message) {
  if (error != NULL) *error = message;
  return false;
}

bool KnownPhysical(int value) {
  return (value >= 0 && value <= 51)
    || value == kOFCCardJoker1 || value == kOFCCardJoker2;
}

COFCCard *FirstEmpty(COFCPlayerBoard *board, EOFCRow row) {
  if (row == kOFCRowTop) {
    for (int i = 0; i < kOFCTopCards; ++i)
      if (!board->top[i].IsKnownPhysicalCard()) return &board->top[i];
  } else if (row == kOFCRowMiddle) {
    for (int i = 0; i < kOFCMiddleCards; ++i)
      if (!board->middle[i].IsKnownPhysicalCard()) return &board->middle[i];
  } else if (row == kOFCRowBottom) {
    for (int i = 0; i < kOFCBottomCards; ++i)
      if (!board->bottom[i].IsKnownPhysicalCard()) return &board->bottom[i];
  }
  return NULL;
}

bool ApplyAction(
    const COFCState &state,
    const COFCStrategyAction &action,
    COFCPlayerBoard *board,
    string *error) {
  if (!action.valid || action.placement_count != 2 || action.unused_count != 1)
    return Fail(error, "R4 action must contain two placements and one discard");

  set<int> incoming;
  for (int i = 0; i < 3; ++i) {
    const int value = state.hero_incoming[i].value;
    if (!KnownPhysical(value) || !incoming.insert(value).second)
      return Fail(error, "R4 incoming set is unknown or duplicated");
  }
  set<int> covered;
  for (int i = 0; i < action.placement_count; ++i) {
    const COFCStrategyPlacement &placement = action.placements[i];
    if (incoming.find(placement.card_value) == incoming.end()
        || !covered.insert(placement.card_value).second)
      return Fail(error, "R4 action placement is outside incoming set");
    COFCCard *slot = FirstEmpty(board, placement.row);
    if (slot == NULL) return Fail(error, "R4 action exceeds row capacity");
    slot->value = placement.card_value;
  }
  const int unused = action.unused_cards[0];
  if (incoming.find(unused) == incoming.end() || !covered.insert(unused).second)
    return Fail(error, "R4 discard is outside incoming set");
  if (covered != incoming)
    return Fail(error, "R4 action does not cover the incoming set exactly");
  return true;
}

bool GlobalPhysicalCardsUnique(
    const COFCState &state,
    const COFCPlayerBoard &hero_board) {
  set<int> seen;
  const COFCPlayerBoard *boards[kOFCMaxPlayers];
  for (int p = 0; p < state.player_count; ++p) {
    if (p == state.hero_chair) boards[p] = &hero_board;
    else boards[p] = &state.players[p].board;
    if (!state.players[p].occupied || state.players[p].sitting_out) continue;
    const COFCCard *rows[3] = {
      boards[p]->top, boards[p]->middle, boards[p]->bottom};
    const int counts[3] = {kOFCTopCards, kOFCMiddleCards, kOFCBottomCards};
    for (int row = 0; row < 3; ++row) {
      for (int i = 0; i < counts[row]; ++i) {
        const int value = rows[row][i].value;
        if (!KnownPhysical(value) || !seen.insert(value).second) return false;
      }
    }
  }
  return true;
}

bool VisibleDecisionCardsUnique(const COFCState &state) {
  set<int> seen;
  for (int p = 0; p < state.player_count; ++p) {
    if (!state.players[p].occupied || state.players[p].sitting_out) continue;
    const COFCPlayerBoard &board = state.players[p].board;
    const COFCCard *rows[3] = {board.top, board.middle, board.bottom};
    const int counts[3] = {kOFCTopCards, kOFCMiddleCards, kOFCBottomCards};
    for (int row = 0; row < 3; ++row) {
      for (int i = 0; i < counts[row]; ++i) {
        const int value = rows[row][i].value;
        if (!KnownPhysical(value)) continue;
        if (!seen.insert(value).second) return false;
      }
    }
  }
  for (int i = 0; i < state.hero_incoming_count; ++i) {
    const int value = state.hero_incoming[i].value;
    if (!KnownPhysical(value) || !seen.insert(value).second) return false;
  }
  for (int i = 0; i < state.hero_discard_count; ++i) {
    const int value = state.hero_discards[i].value;
    if (!KnownPhysical(value) || !seen.insert(value).second) return false;
  }
  return true;
}

bool ScoreCandidate(
    const COFCState &state,
    const COFCStrategyAction &action,
    const vector<COFCExactBoardResult> &opponents,
    ExactCandidate *candidate,
    string *error) {
  candidate->action = action;
  COFCPlayerBoard board = state.players[state.hero_chair].board;
  if (!ApplyAction(state, action, &board, error)) return false;
  if (!GlobalPhysicalCardsUnique(state, board))
    return Fail(error, "R4 exact state contains duplicate/unknown physical card");
  if (!COFCExactEvaluator::EvaluateBoard(board, &candidate->board, error))
    return false;
  candidate->points = 0;
  for (size_t i = 0; i < opponents.size(); ++i) {
    COFCExactMatchResult match;
    if (!COFCExactEvaluator::ScoreMatch(
          candidate->board, opponents[i], &match, error)) return false;
    candidate->points += match.total_points;
  }
  return true;
}

COFCStrategyAction MakeAction(
    const COFCState &state, int discard, EOFCRow first, EOFCRow second) {
  COFCStrategyAction action;
  int kept_index = 0;
  for (int i = 0; i < 3; ++i) {
    const int value = state.hero_incoming[i].value;
    if (i == discard) {
      action.unused_cards[action.unused_count++] = value;
      continue;
    }
    COFCStrategyPlacement &placement =
      action.placements[action.placement_count++];
    placement.card_value = value;
    placement.row = kept_index++ == 0 ? first : second;
  }
  action.valid = action.placement_count == 2 && action.unused_count == 1;
  return action;
}

bool ActionLess(
    const COFCStrategyAction &left,
    const COFCStrategyAction &right) {
  if (left.unused_cards[0] != right.unused_cards[0])
    return left.unused_cards[0] < right.unused_cards[0];
  for (int i = 0; i < 2; ++i) {
    if (left.placements[i].card_value != right.placements[i].card_value)
      return left.placements[i].card_value < right.placements[i].card_value;
    if (left.placements[i].row != right.placements[i].row)
      return left.placements[i].row < right.placements[i].row;
  }
  return false;
}

bool BetterDominatingCandidate(
    const ExactCandidate &left,
    const ExactCandidate &right) {
  if (left.points != right.points) return left.points > right.points;
  if (left.board.fantasy_cards != right.board.fantasy_cards)
    return left.board.fantasy_cards > right.board.fantasy_cards;
  if (left.board.royalties != right.board.royalties)
    return left.board.royalties > right.board.royalties;
  return ActionLess(left.action, right.action);
}

}  // namespace

COFCR4ExactTeacherReport::COFCR4ExactTeacherReport()
    : exact_available(false), applied(false), candidates(0), legal_candidates(0),
      baseline_points(0), selected_points(0), baseline_fantasy_cards(0),
      selected_fantasy_cards(0), baseline_royalties(0), selected_royalties(0) {}

bool COFCR4ExactTeacher::Improve(
    const COFCState &state,
    const COFCStrategyAction &baseline,
    COFCStrategyAction *selected,
    COFCR4ExactTeacherReport *report,
    string *error) {
  if (selected == NULL || report == NULL) return false;
  *selected = baseline;
  *report = COFCR4ExactTeacherReport();
  if (error != NULL) error->clear();
  if (!state.valid || state.round_index != 4)
    return Fail(error, "exact R4 teacher requires a valid normal round 4");
  if (state.hero_chair < 0 || state.hero_chair >= state.player_count)
    return Fail(error, "exact R4 teacher received invalid Hero chair");
  if (state.players[state.hero_chair].fantasy)
    return Fail(error, "exact R4 teacher does not evaluate Fantasy layout");
  if (state.hero_incoming_count != 3
      || state.players[state.hero_chair].board.CountKnownCards() != 11)
    return Fail(error, "exact R4 teacher requires 11 known board cards plus 3 incoming");
  if (!VisibleDecisionCardsUnique(state))
    return Fail(error, "exact R4 visible decision cards are unknown or duplicated");

  vector<COFCExactBoardResult> opponents;
  for (int p = 0; p < state.player_count; ++p) {
    if (p == state.hero_chair || !state.players[p].occupied
        || state.players[p].sitting_out) continue;
    if (state.players[p].board.CountKnownCards() != 13)
      return Fail(error, "exact R4 opponent terminal board is unavailable");
    COFCExactBoardResult opponent;
    if (!COFCExactEvaluator::EvaluateBoard(
          state.players[p].board, &opponent, error)) return false;
    opponents.push_back(opponent);
  }
  if (opponents.empty())
    return Fail(error, "exact R4 teacher requires at least one opponent");

  ExactCandidate baseline_candidate;
  if (!ScoreCandidate(state, baseline, opponents, &baseline_candidate, error))
    return false;
  report->exact_available = true;
  report->baseline_points = baseline_candidate.points;
  report->selected_points = baseline_candidate.points;
  report->baseline_fantasy_cards = baseline_candidate.board.fantasy_cards;
  report->selected_fantasy_cards = baseline_candidate.board.fantasy_cards;
  report->baseline_royalties = baseline_candidate.board.royalties;
  report->selected_royalties = baseline_candidate.board.royalties;

  vector<ExactCandidate> improving;
  const EOFCRow rows[3] = {kOFCRowTop, kOFCRowMiddle, kOFCRowBottom};
  for (int discard = 0; discard < 3; ++discard) {
    for (int first = 0; first < 3; ++first) {
      for (int second = 0; second < 3; ++second) {
        ++report->candidates;
        const COFCStrategyAction action =
          MakeAction(state, discard, rows[first], rows[second]);
        ExactCandidate candidate;
        string candidate_error;
        if (!ScoreCandidate(
              state, action, opponents, &candidate, &candidate_error)) continue;
        ++report->legal_candidates;
        const bool no_worse = candidate.points >= baseline_candidate.points
          && candidate.board.fantasy_cards
             >= baseline_candidate.board.fantasy_cards;
        const bool strict = candidate.points > baseline_candidate.points
          || candidate.board.fantasy_cards
             > baseline_candidate.board.fantasy_cards;
        if (no_worse && strict) improving.push_back(candidate);
      }
    }
  }
  if (improving.empty()) return true;
  sort(improving.begin(), improving.end(), BetterDominatingCandidate);
  *selected = improving[0].action;
  report->applied = true;
  report->selected_points = improving[0].points;
  report->selected_fantasy_cards = improving[0].board.fantasy_cards;
  report->selected_royalties = improving[0].board.royalties;
  return true;
}
