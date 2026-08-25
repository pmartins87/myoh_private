//******************************************************************************
// OpenOFC v5.6.0 exact terminal oracle and R4 teacher selftest.
//******************************************************************************

#include <iostream>
#include <string>

#include "COFCDecisionPolicy.h"
#include "COFCExactEvaluator.h"
#include "COFCR4ExactTeacher.h"

namespace {

int Card(int rank, int suit) {
  return (rank - 2) * 4 + suit;
}

bool Require(bool condition, const std::string &message) {
  if (!condition) std::cerr << "FAIL: " << message << "\n";
  return condition;
}

void FillBoard(
    COFCPlayerBoard *board,
    const int top[3],
    const int middle[5],
    const int bottom[5]) {
  board->Reset();
  for (int i = 0; i < 3; ++i) board->top[i].value = top[i];
  for (int i = 0; i < 5; ++i) board->middle[i].value = middle[i];
  for (int i = 0; i < 5; ++i) board->bottom[i].value = bottom[i];
}

COFCPlayerBoard RoyaltyBoard() {
  COFCPlayerBoard board;
  const int top[3] = {Card(12, 3), Card(12, 2), Card(2, 0)};
  const int middle[5] = {
    Card(13, 1), Card(13, 2), Card(11, 1), Card(11, 2), Card(3, 0)};
  const int bottom[5] = {
    Card(9, 0), Card(10, 1), Card(11, 3), Card(12, 1), Card(13, 0)};
  FillBoard(&board, top, middle, bottom);
  return board;
}

bool TestRoyaltyFantasyAndFoul() {
  std::string error;
  COFCExactBoardResult result;
  const bool royalty_ok = COFCExactEvaluator::EvaluateBoard(
    RoyaltyBoard(), &result, &error);
  if (!Require(royalty_ok, "evaluate valid royalty board: " + error))
    return false;
  if (!Require(result.complete && !result.foul, "royalty board must be valid"))
    return false;
  if (!Require(result.royalties == 9, "QQ top + bottom straight must pay 9"))
    return false;
  if (!Require(result.fantasy_cards == 14, "QQ top must enter Fantasy 14"))
    return false;

  COFCPlayerBoard foul;
  const int top[3] = {Card(14, 0), Card(14, 1), Card(2, 0)};
  const int middle[5] = {
    Card(13, 0), Card(13, 1), Card(11, 0), Card(9, 1), Card(3, 0)};
  const int bottom[5] = {
    Card(12, 0), Card(12, 1), Card(10, 0), Card(10, 1), Card(4, 0)};
  FillBoard(&foul, top, middle, bottom);
  const bool foul_ok = COFCExactEvaluator::EvaluateBoard(
    foul, &result, &error);
  if (!Require(foul_ok, "evaluate foul board: " + error)) return false;
  return Require(result.complete && result.foul && result.royalties == 0
      && result.fantasy_cards == 0, "foul must suppress royalties and Fantasy");
}

bool TestJokerResolutionAndRefantasy() {
  COFCPlayerBoard board;
  const int top[3] = {Card(12, 3), Card(12, 1), kOFCCardJoker1};
  const int middle[5] = {
    Card(2, 0), Card(3, 1), Card(4, 3), Card(5, 0), Card(6, 2)};
  const int bottom[5] = {
    Card(7, 2), Card(8, 2), Card(9, 2), Card(11, 2), Card(13, 2)};
  FillBoard(&board, top, middle, bottom);
  COFCExactBoardResult result;
  std::string error;
  const bool joker_ok = COFCExactEvaluator::EvaluateBoard(
    board, &result, &error);
  if (!Require(joker_ok, "evaluate Joker board: " + error)) return false;
  if (!Require(!result.foul, "Joker board must resolve without foul")) return false;
  if (!Require(result.rows[0].category == kOFCExactTrips
      && result.rows[0].tie[0] == 12, "Joker must complete three Queens on top"))
    return false;
  return Require(result.royalties == 28 && result.fantasy_cards == 17
      && result.refantasy, "Joker trips/straight/flush exact rewards drifted");
}

bool TestPairwiseScoring() {
  COFCExactBoardResult hero;
  COFCExactBoardResult opponent;
  std::string error;
  if (!COFCExactEvaluator::EvaluateBoard(RoyaltyBoard(), &hero, &error))
    return Require(false, "evaluate scoring Hero: " + error);

  COFCPlayerBoard weak;
  const int top[3] = {Card(5, 0), Card(5, 1), Card(2, 1)};
  const int middle[5] = {
    Card(10, 0), Card(10, 1), Card(9, 0), Card(9, 1), Card(3, 1)};
  const int bottom[5] = {
    Card(14, 0), Card(14, 1), Card(13, 0), Card(13, 1), Card(4, 1)};
  FillBoard(&weak, top, middle, bottom);
  if (!COFCExactEvaluator::EvaluateBoard(weak, &opponent, &error))
    return Require(false, "evaluate scoring opponent: " + error);
  COFCExactMatchResult match;
  const bool score_ok = COFCExactEvaluator::ScoreMatch(
    hero, opponent, &match, &error);
  if (!Require(score_ok, "score exact match: " + error))
    return false;
  return Require(match.valid && match.row_points == 3
      && match.scoop_bonus == 3 && match.total_points == 15,
      "scoop + royalty differential must equal 15");
}

COFCStrategyAction DeliberatelyFouledBaseline(const COFCState &state) {
  COFCStrategyAction action;
  action.placements[0].card_value = state.hero_incoming[0].value;
  action.placements[0].row = kOFCRowTop;
  action.placements[1].card_value = state.hero_incoming[2].value;
  action.placements[1].row = kOFCRowMiddle;
  action.placement_count = 2;
  action.unused_cards[0] = state.hero_incoming[1].value;
  action.unused_count = 1;
  action.valid = true;
  return action;
}

COFCState ExactR4State() {
  COFCState state;
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 0;
  state.acting_chair = 0;
  state.round_index = 4;
  state.hero_can_prepare = true;
  state.players[0].occupied = true;
  state.players[1].occupied = true;

  COFCPlayerBoard &hero = state.players[0].board;
  hero.top[0].value = Card(12, 3);
  hero.top[1].value = Card(12, 2);
  hero.middle[0].value = Card(13, 0);
  hero.middle[1].value = Card(13, 1);
  hero.middle[2].value = Card(11, 0);
  hero.middle[3].value = Card(11, 1);
  const int hero_bottom[5] = {
    Card(2, 2), Card(3, 1), Card(4, 3), Card(5, 0), Card(6, 2)};
  for (int i = 0; i < 5; ++i) hero.bottom[i].value = hero_bottom[i];

  const int opponent_top[3] = {Card(3, 0), Card(3, 2), Card(7, 0)};
  const int opponent_middle[5] = {
    Card(8, 0), Card(8, 1), Card(4, 0), Card(5, 1), Card(9, 0)};
  const int opponent_bottom[5] = {
    Card(9, 1), Card(9, 2), Card(10, 3), Card(10, 0), Card(14, 3)};
  FillBoard(&state.players[1].board,
    opponent_top, opponent_middle, opponent_bottom);

  state.hero_incoming_count = 3;
  state.hero_incoming[0].value = Card(12, 0);
  state.hero_incoming[1].value = Card(2, 0);
  state.hero_incoming[2].value = Card(14, 0);
  return state;
}

bool TestR4TeacherParetoImprovement() {
  COFCState state = ExactR4State();
  const COFCStrategyAction baseline = DeliberatelyFouledBaseline(state);
  COFCStrategyAction selected;
  COFCR4ExactTeacherReport report;
  std::string error;
  const bool improved = COFCR4ExactTeacher::Improve(
    state, baseline, &selected, &report, &error);
  if (!Require(improved,
        "R4 exact teacher rejected terminal state: " + error)) return false;
  if (!Require(report.exact_available && report.applied,
        "R4 teacher must replace the deliberately fouled baseline")) return false;
  if (!Require(report.candidates == 27 && report.legal_candidates > 0,
        "R4 teacher must enumerate all 27 assignments")) return false;
  return Require(report.selected_points > report.baseline_points
      && report.selected_fantasy_cards >= report.baseline_fantasy_cards
      && selected.valid, "R4 Pareto guarantee was violated");
}

bool TestR4TeacherFailsClosedWithoutTerminalOpponent() {
  COFCState state = ExactR4State();
  state.players[1].board.bottom[4].Clear();
  const COFCStrategyAction baseline = DeliberatelyFouledBaseline(state);
  COFCStrategyAction selected;
  COFCR4ExactTeacherReport report;
  std::string error;
  const bool ok = COFCR4ExactTeacher::Improve(
    state, baseline, &selected, &report, &error);
  return Require(!ok && !report.exact_available && !report.applied
      && selected.valid && error.find("opponent terminal board") != std::string::npos,
      "R4 teacher must leave baseline untouched when exact information is absent");
}

bool TestProductionPolicyComposition() {
  COFCState state = ExactR4State();
  COFCStrategyAction action;
  COFCDecisionPolicyReport report;
  std::string error;
  const bool chose = COFCDecisionPolicy::Choose(
    state, &action, &report, &error);
  if (!Require(chose,
        "production policy rejected exact R4 state: " + error)) return false;
  return Require(action.valid && report.exact_r4_attempted
      && report.exact_r4.exact_available
      && report.exact_r4.selected_points >= report.exact_r4.baseline_points
      && report.exact_r4.selected_fantasy_cards
         >= report.exact_r4.baseline_fantasy_cards,
      "production composition bypassed the exact R4 Pareto contract");
}

}  // namespace

int main() {
  if (!TestRoyaltyFantasyAndFoul()
      || !TestJokerResolutionAndRefantasy()
      || !TestPairwiseScoring()
      || !TestR4TeacherParetoImprovement()
      || !TestR4TeacherFailsClosedWithoutTerminalOpponent()
      || !TestProductionPolicyComposition()) return 1;
  std::cout << "PASS OpenOFC v5.6.0 exact terminal oracle + Pareto-safe R4 teacher\n";
  return 0;
}
