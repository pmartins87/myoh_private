//******************************************************************************
// OpenOFC v5.4.3G Fantasy/Joker execution-state selftest.
// No real mouse input is possible: the CI seam replaces only external I/O.
//******************************************************************************

#include <Windows.h>

#include <algorithm>
#include <iostream>
#include <string>
#include <vector>

#include "COFCFantasyBatchExecutor.h"

namespace {

std::vector<std::vector<RECT> > g_batches;
std::vector<RECT> g_single_clicks;
bool g_allow_batch = true;
bool g_allow_single = true;

const int kDeal[15] = {
  kOFCCardJoker1, kOFCCardJoker2,
  0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
};

RECT SourceRectForIndex(int index) {
  RECT rect;
  rect.left = 20 + index * 24;
  rect.top = 640;
  rect.right = rect.left + 18;
  rect.bottom = 704;
  return rect;
}

RECT RowActionRect(EOFCRow row) {
  RECT rect;
  rect.left = 500 + static_cast<int>(row) * 30;
  rect.top = 420 + static_cast<int>(row) * 70;
  rect.right = rect.left + 22;
  rect.bottom = rect.top + 22;
  return rect;
}

bool SameRect(const RECT &a, const RECT &b) {
  return a.left == b.left && a.top == b.top
    && a.right == b.right && a.bottom == b.bottom;
}

void ResetHooks() {
  g_batches.clear();
  g_single_clicks.clear();
  g_allow_batch = true;
  g_allow_single = true;
}

void Require(bool condition, const std::string &message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << std::endl;
    std::exit(2);
  }
}

EOFCRow TargetRowForOrdinal(int ordinal) {
  if (ordinal < 3) return kOFCRowTop;
  if (ordinal < 8) return kOFCRowMiddle;
  return kOFCRowBottom;
}

COFCState MakeState(int committed_targets) {
  COFCState state;
  state.Reset();
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 1;
  state.dealer_chair = 0;
  state.acting_chair = 1;
  state.round_index = -1;
  state.players[0].occupied = true;
  state.players[0].source_chair = 0;
  state.players[1].occupied = true;
  state.players[1].source_chair = 1;
  state.players[1].fantasy = true;
  state.hero_incoming_count = 15;
  for (int i = 0; i < 15; ++i) state.hero_incoming[i].value = kDeal[i];

  for (int i = 0; i < committed_targets; ++i) {
    state.pending[i].active = true;
    state.pending[i].incoming_index = i;
    state.pending[i].row = TargetRowForOrdinal(i);
  }
  return state;
}

COFCVisualObservation MakeObservation(int committed_targets) {
  COFCVisualObservation observation;
  observation.Reset();
  observation.valid = true;
  observation.player_count = 2;
  observation.hero_chair = 1;
  observation.dealer_chair = 0;
  observation.acting_chair = 1;
  observation.round_index = -1;
  observation.players[0].occupied = true;
  observation.players[0].source_chair = 0;
  observation.players[1].occupied = true;
  observation.players[1].source_chair = 1;
  observation.players[1].fantasy = true;

  int loose = 0;
  for (int i = committed_targets; i < 15; ++i) {
    observation.hero_loose_cards[loose].value = kDeal[i];
    observation.hero_loose_sources[loose].valid = true;
    observation.hero_loose_sources[loose].card_value = kDeal[i];
    observation.hero_loose_sources[loose].rect = SourceRectForIndex(i);
    ++loose;
  }
  observation.hero_loose_count = loose;
  return observation;
}

COFCTurnPlan MakePlan() {
  COFCTurnPlan plan;
  plan.Reset();
  plan.valid = true;
  plan.decision_state = MakeState(0);
  plan.decision_state.valid = true;
  plan.target_count = 13;
  plan.to_add_count = 13;
  for (int i = 0; i < 13; ++i) {
    plan.target[i].card_value = kDeal[i];
    plan.target[i].row = TargetRowForOrdinal(i);
    plan.to_add[i] = plan.target[i];
  }
  plan.unused_count = 2;
  plan.unused_cards[0] = kDeal[13];
  plan.unused_cards[1] = kDeal[14];
  return plan;
}

void TestExactJokerRowBatches() {
  ResetHooks();
  COFCFantasyBatchExecutor executor;
  const COFCTurnPlan plan = MakePlan();
  bool complete = false;
  std::string error;

  COFCState state0 = MakeState(0);
  COFCVisualObservation obs0 = MakeObservation(0);
  Require(executor.Start(state0, obs0, plan, &complete, &error),
    "initial Fantasy execution did not start: " + error);
  Require(!complete, "initial empty arrangement was incorrectly complete");
  Require(g_batches.size() == 1, "top row was not dispatched exactly once");
  Require(g_batches[0].size() == 4, "top row must be 3 card selections + 1 row action");

  // Target top is JK1, JK2, card 0. Sorting is right-to-left, so the physical
  // source rectangles must appear as card0, JK2, JK1, followed by row check.
  Require(SameRect(g_batches[0][0], SourceRectForIndex(2)),
    "top click[0] is not the expected exact standard-card source");
  Require(SameRect(g_batches[0][1], SourceRectForIndex(1)),
    "top click[1] did not retain exact JK2 source identity");
  Require(SameRect(g_batches[0][2], SourceRectForIndex(0)),
    "top click[2] did not retain exact JK1 source identity");
  Require(SameRect(g_batches[0][3], RowActionRect(kOFCRowTop)),
    "top row action is not last in the atomic batch");

  COFCState state3 = MakeState(3);
  COFCVisualObservation obs3 = MakeObservation(3);
  Require(executor.AdvanceAfterFreshScrape(state3, obs3, &complete, &error),
    "top verification/middle dispatch failed: " + error);
  Require(!complete && g_batches.size() == 2 && g_batches[1].size() == 6,
    "middle row must be one 5+1 atomic batch after fresh top verification");
  Require(SameRect(g_batches[1].back(), RowActionRect(kOFCRowMiddle)),
    "middle row action is not last in batch");

  COFCState state8 = MakeState(8);
  COFCVisualObservation obs8 = MakeObservation(8);
  Require(executor.AdvanceAfterFreshScrape(state8, obs8, &complete, &error),
    "middle verification/bottom dispatch failed: " + error);
  Require(!complete && g_batches.size() == 3 && g_batches[2].size() == 6,
    "bottom row must be one 5+1 atomic batch after fresh middle verification");
  Require(SameRect(g_batches[2].back(), RowActionRect(kOFCRowBottom)),
    "bottom row action is not last in batch");

  COFCState state13 = MakeState(13);
  COFCVisualObservation obs13 = MakeObservation(13);
  Require(executor.AdvanceAfterFreshScrape(state13, obs13, &complete, &error),
    "final 13-card arrangement verification failed: " + error);
  Require(complete, "13-card 3/5/5 target was not marked complete");
  Require(g_batches.size() == 3, "executor clicked after final board verification");
  Require(g_single_clicks.empty(), "unexpected clear-row click in clean 3/5/5 path");

  int selected_cards = 0;
  for (size_t i = 0; i < g_batches.size(); ++i)
    selected_cards += static_cast<int>(g_batches[i].size()) - 1;
  Require(selected_cards == 13, "execution did not select exactly 13 physical cards");

  std::cout << "FANTASY_JOKER_ACTION_GATE=PASS" << std::endl;
  std::cout << "FANTASY_13_SELECTIONS_3_ROW_CHECKS=PASS" << std::endl;
}

void TestSourceIdentityMismatchFailsClosed() {
  ResetHooks();
  COFCFantasyBatchExecutor executor;
  COFCVisualObservation observation = MakeObservation(0);
  // Deliberately cross-wire JK1's fresh rectangle metadata to JK2. The visible
  // card array remains JK1, so only the source-identity tuple check can catch it.
  observation.hero_loose_sources[0].card_value = kOFCCardJoker2;

  bool complete = false;
  std::string error;
  const bool ok = executor.Start(
    MakeState(0), observation, MakePlan(), &complete, &error);
  Require(!ok, "cross-wired JK1/JK2 source metadata was accepted");
  Require(error.find("identity metadata mismatch") != std::string::npos,
    "source-identity failure did not report the structural reason: " + error);
  Require(g_batches.empty(), "a click batch escaped after source-identity mismatch");
  Require(!executor.active(), "failed source identity left a stale active executor");

  std::cout << "FANTASY_JOKER_SOURCE_IDENTITY_GATE=PASS" << std::endl;
}

void TestTransactionFailureResetsForFreshPlan() {
  ResetHooks();
  COFCFantasyBatchExecutor executor;
  bool complete = false;
  std::string error;

  g_allow_batch = false;
  Require(!executor.Start(MakeState(0), MakeObservation(0), MakePlan(),
      &complete, &error),
    "refused atomic row batch did not fail");
  Require(!executor.active(),
    "transaction failure retained stale Fantasy plan/phase instead of reset");

  g_allow_batch = true;
  g_batches.clear();
  error.clear();
  Require(executor.Start(MakeState(0), MakeObservation(0), MakePlan(),
      &complete, &error),
    "fresh plan could not restart after transaction failure: " + error);
  Require(g_batches.size() == 1,
    "fresh restart did not dispatch exactly one top-row batch");

  std::cout << "FANTASY_TRANSACTION_RESTART_GATE=PASS" << std::endl;
}

void TestBoundedNoopRetryThenReset() {
  ResetHooks();
  COFCFantasyBatchExecutor executor;
  bool complete = false;
  std::string error;
  const COFCState unchanged = MakeState(0);
  const COFCVisualObservation unchanged_obs = MakeObservation(0);

  Require(executor.Start(unchanged, unchanged_obs, MakePlan(),
      &complete, &error), "bounded-retry test failed to start: " + error);
  Require(g_batches.size() == 1, "bounded-retry initial dispatch missing");

  for (int i = 0; i < 9; ++i) {
    Require(executor.AdvanceAfterFreshScrape(
        unchanged, unchanged_obs, &complete, &error),
      "executor failed before first verification timeout");
  }
  Require(executor.AdvanceAfterFreshScrape(
      unchanged, unchanged_obs, &complete, &error),
    "single permitted no-op retry was not dispatched");
  Require(g_batches.size() == 2,
    "no-op verification did not produce exactly one bounded retry");

  for (int i = 0; i < 9; ++i) {
    Require(executor.AdvanceAfterFreshScrape(
        unchanged, unchanged_obs, &complete, &error),
      "executor failed before second verification timeout");
  }
  Require(!executor.AdvanceAfterFreshScrape(
      unchanged, unchanged_obs, &complete, &error),
    "executor exceeded the one-retry bound");
  Require(error.find("bounded retry") != std::string::npos,
    "retry exhaustion did not report bounded-retry failure: " + error);
  Require(g_batches.size() == 2,
    "retry exhaustion dispatched an unbounded third batch");
  Require(!executor.active(),
    "retry exhaustion retained stale active state instead of fresh-plan reset");

  g_batches.clear();
  error.clear();
  Require(executor.Start(MakeState(0), MakeObservation(0), MakePlan(),
      &complete, &error),
    "executor could not bind a fresh plan after bounded retry exhaustion: " + error);
  Require(g_batches.size() == 1,
    "post-exhaustion fresh plan did not restart from one top-row batch");

  std::cout << "FANTASY_BOUNDED_RETRY_GATE=PASS" << std::endl;
}

}  // namespace

bool DeepOFCTestFantasyResolveRowActionRect(EOFCRow row, RECT *out) {
  if (out == NULL || row < kOFCRowTop || row > kOFCRowBottom) return false;
  *out = RowActionRect(row);
  return true;
}

bool DeepOFCTestFantasyClickRect(RECT rect) {
  g_single_clicks.push_back(rect);
  return g_allow_single;
}

bool DeepOFCTestFantasyClickRects(
    const std::vector<RECT> &rects, int gap_ms) {
  if (gap_ms < 60) return false;
  g_batches.push_back(rects);
  return g_allow_batch;
}

int DeepOFCTestFantasySelectGapMs() {
  return 110;
}

int main() {
  TestExactJokerRowBatches();
  TestSourceIdentityMismatchFailsClosed();
  TestTransactionFailureResetsForFreshPlan();
  TestBoundedNoopRetryThenReset();
  std::cout << "FANTASY_JOKER_EXECUTION_GATE=PASS" << std::endl;
  std::cout << "FANTASY_CONFIRM_GATE=NOT_YET_CERTIFIED" << std::endl;
  std::cout << "FIELD_PACKAGE_AUTHORIZED=0" << std::endl;
  return 0;
}
