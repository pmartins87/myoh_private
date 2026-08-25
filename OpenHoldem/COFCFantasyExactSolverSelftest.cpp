//******************************************************************************
// OpenOFC v5.7.0 exact Fantasy 14..17 search selftest.
//******************************************************************************

#include <chrono>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "COFCFantasyExactSolver.h"

namespace {

int Card(int rank, int suit) {
  return suit * 13 + (rank - 2);
}

bool Require(bool condition, const std::string &message) {
  if (!condition) std::cerr << "FAIL: " << message << "\n";
  return condition;
}

std::vector<int> BaseCards() {
  const int values[] = {
    Card(12, 3), Card(12, 2), Card(2, 0),
    Card(13, 1), Card(13, 2), Card(11, 1), Card(11, 2), Card(3, 0),
    Card(9, 0), Card(10, 1), Card(11, 3), Card(12, 1), Card(13, 0),
    Card(4, 0), Card(5, 0), Card(6, 0), Card(7, 0)
  };
  return std::vector<int>(values, values + 17);
}

COFCState FantasyState(const std::vector<int> &cards, int count) {
  COFCState state;
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 1;
  state.acting_chair = 1;
  state.round_index = -1;
  state.hero_can_prepare = true;
  state.players[0].occupied = true;
  state.players[1].occupied = true;
  state.players[1].fantasy = true;
  state.hero_incoming_count = count;
  for (int i = 0; i < count; ++i)
    state.hero_incoming[i].value = cards[i];
  return state;
}

COFCStrategyAction FouledBaseline(
    const std::vector<int> &cards, int count) {
  // KK top over QQ middle is intentionally foul.  The bottom is a straight.
  const int top_indices[3] = {3, 4, 5};
  const int middle_indices[5] = {0, 1, 2, 6, 7};
  const int bottom_indices[5] = {8, 9, 10, 11, 12};
  bool used[17] = {false};
  COFCStrategyAction action;
  for (int i = 0; i < 3; ++i) {
    used[top_indices[i]] = true;
    action.placements[action.placement_count].card_value =
      cards[top_indices[i]];
    action.placements[action.placement_count++].row = kOFCRowTop;
  }
  for (int i = 0; i < 5; ++i) {
    used[middle_indices[i]] = true;
    action.placements[action.placement_count].card_value =
      cards[middle_indices[i]];
    action.placements[action.placement_count++].row = kOFCRowMiddle;
  }
  for (int i = 0; i < 5; ++i) {
    used[bottom_indices[i]] = true;
    action.placements[action.placement_count].card_value =
      cards[bottom_indices[i]];
    action.placements[action.placement_count++].row = kOFCRowBottom;
  }
  for (int i = 0; i < count; ++i)
    if (!used[i]) action.unused_cards[action.unused_count++] = cards[i];
  action.valid = true;
  return action;
}

bool ActionBoard(
    const COFCStrategyAction &action,
    COFCPlayerBoard *board) {
  board->Reset();
  int counts[3] = {0, 0, 0};
  for (int i = 0; i < action.placement_count; ++i) {
    const COFCStrategyPlacement &p = action.placements[i];
    const int index = counts[p.row]++;
    if (p.row == kOFCRowTop) board->top[index].value = p.card_value;
    else if (p.row == kOFCRowMiddle) board->middle[index].value = p.card_value;
    else if (p.row == kOFCRowBottom) board->bottom[index].value = p.card_value;
    else return false;
  }
  return counts[0] == 3 && counts[1] == 5 && counts[2] == 5;
}

bool CoversExactly(
    const COFCStrategyAction &action,
    const std::vector<int> &cards,
    int count) {
  std::multiset<int> expected(cards.begin(), cards.begin() + count);
  std::multiset<int> actual;
  for (int i = 0; i < action.placement_count; ++i)
    actual.insert(action.placements[i].card_value);
  for (int i = 0; i < action.unused_count; ++i)
    actual.insert(action.unused_cards[i]);
  return expected == actual;
}

unsigned long long ExpectedMaskPairs(int count) {
  const unsigned long long choose5[] = {
    0, 0, 0, 0, 0, 1, 6, 21, 56, 126, 252, 462, 792,
    1287, 2002, 3003, 4368, 6188
  };
  return choose5[count] * choose5[count - 5];
}

bool TestCounts14To17() {
  const std::vector<int> cards = BaseCards();
  for (int count = 14; count <= 17; ++count) {
    const COFCState state = FantasyState(cards, count);
    const COFCStrategyAction baseline = FouledBaseline(cards, count);
    COFCStrategyAction selected;
    COFCFantasyExactReport report;
    std::string error;
    const std::chrono::steady_clock::time_point started =
      std::chrono::steady_clock::now();
    const bool ok = COFCFantasyExactSolver::ImproveUniversally(
      state, baseline, &selected, &report, &error);
    const long long elapsed =
      std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - started).count();
    if (!Require(ok, "solve Fantasy count " + std::to_string(count)
        + ": " + error)) return false;
    if (!Require(report.exact_available && report.applied,
          "valid board must replace fouled Fantasy baseline")) return false;
    if (!Require(report.mask_pairs == ExpectedMaskPairs(count),
          "search did not enumerate every ordered 5/5 mask pair")) return false;
    if (!Require(report.legal_boards > 0
          && report.universal_improvements == report.legal_boards,
          "every valid board must dominate the fouled baseline")) return false;
    if (!Require(selected.valid && selected.placement_count == 13
          && selected.unused_count == count - 13
          && CoversExactly(selected, cards, count),
          "exact Fantasy action does not cover physical deal")) return false;
    COFCPlayerBoard board;
    COFCExactBoardResult result;
    if (!Require(ActionBoard(selected, &board)
          && COFCExactEvaluator::EvaluateBoard(board, &result, &error)
          && !result.foul,
          "exact Fantasy selection is not a legal terminal board")) return false;
    std::cout << "EXACT_FANTASY count=" << count
              << " mask_pairs=" << report.mask_pairs
              << " legal=" << report.legal_boards
              << " royalties=" << result.royalties
              << " refantasy=" << (result.refantasy ? 1 : 0)
              << " elapsed_ms=" << elapsed << " PASS\n";
  }
  return true;
}

bool TestTwoPhysicalJokersAndIdempotence() {
  std::vector<int> cards = BaseCards();
  cards[13] = kOFCCardJoker1;
  cards[14] = kOFCCardJoker2;
  const int count = 15;
  const COFCState state = FantasyState(cards, count);
  const COFCStrategyAction baseline = FouledBaseline(cards, count);
  COFCStrategyAction selected;
  COFCFantasyExactReport first;
  std::string error;
  if (!Require(COFCFantasyExactSolver::ImproveUniversally(
        state, baseline, &selected, &first, &error),
        "two-Joker Fantasy solve failed: " + error)) return false;
  if (!Require(first.applied && CoversExactly(selected, cards, count),
        "two physical Jokers were not preserved exactly")) return false;

  COFCStrategyAction repeated;
  COFCFantasyExactReport second;
  if (!Require(COFCFantasyExactSolver::ImproveUniversally(
        state, selected, &repeated, &second, &error),
        "idempotent exact Fantasy solve failed: " + error)) return false;
  return Require(!second.applied && repeated.valid,
    "exactly maximal Fantasy layout must not be replaced again");
}

bool TestDuplicateFailsClosed() {
  std::vector<int> cards = BaseCards();
  cards[13] = cards[0];
  const COFCState state = FantasyState(cards, 14);
  const COFCStrategyAction baseline = FouledBaseline(cards, 14);
  COFCStrategyAction selected;
  COFCFantasyExactReport report;
  std::string error;
  const bool ok = COFCFantasyExactSolver::ImproveUniversally(
    state, baseline, &selected, &report, &error);
  return Require(!ok && !selected.valid && !report.exact_available
      && error.find("duplicated") != std::string::npos,
      "duplicate Fantasy physical card must fail closed");
}

}  // namespace

int main() {
  if (!TestCounts14To17()
      || !TestTwoPhysicalJokersAndIdempotence()
      || !TestDuplicateFailsClosed()) return 1;
  std::cout << "PASS OpenOFC v5.7.0 exact Fantasy 14..17 exhaustive kernel\n";
  return 0;
}
