//******************************************************************************
// OpenOFC v5.4.2B partial normal-round reconnect self-test.
// Built only by the dedicated v5.4.2B CI workflow.
//******************************************************************************

#include "COFCBaselinePolicy.h"
#include "COFCReconstructor.h"
#include "COFCTurnPlan.h"

#include <iostream>
#include <string>

namespace {

void Put(COFCCard *card, int value) {
  card->value = value;
}

void InitPlayers(COFCVisualObservation *obs) {
  obs->player_count = 2;
  obs->hero_chair = 1;
  obs->dealer_chair = 0;
  obs->acting_chair = 1;
  for (int p = 0; p < 2; ++p) {
    obs->players[p].occupied = true;
    obs->players[p].source_chair = p;
    obs->players[p].fantasy = false;
  }
}

void PutFirstFree(COFCPlayerBoard *board, EOFCRow row, int value) {
  if (row == kOFCRowTop) {
    for (int i = 0; i < kOFCTopCards; ++i) {
      if (!board->top[i].IsKnownPhysicalCard()) {
        Put(&board->top[i], value);
        return;
      }
    }
  } else if (row == kOFCRowMiddle) {
    for (int i = 0; i < kOFCMiddleCards; ++i) {
      if (!board->middle[i].IsKnownPhysicalCard()) {
        Put(&board->middle[i], value);
        return;
      }
    }
  } else if (row == kOFCRowBottom) {
    for (int i = 0; i < kOFCBottomCards; ++i) {
      if (!board->bottom[i].IsKnownPhysicalCard()) {
        Put(&board->bottom[i], value);
        return;
      }
    }
  }
}

int PendingCount(const COFCState &state) {
  int count = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i)
    if (state.pending[i].active) ++count;
  return count;
}

COFCVisualObservation Round3Loose2() {
  COFCVisualObservation obs;
  obs.Reset();
  InitPlayers(&obs);
  obs.round_index = 3;
  obs.hero_can_prepare = true;
  obs.confirm_visible = true;

  // Round 3 begins with 9 committed cards. This frame models a reconnect after
  // one of the current three cards was already placed manually: 10 cards are
  // visible on Hero's board and exactly two current cards remain loose.
  Put(&obs.players[1].visual_board.top[0], 0);
  Put(&obs.players[1].visual_board.top[1], 1);
  Put(&obs.players[1].visual_board.top[2], 2);  // pre-attach current placement
  Put(&obs.players[1].visual_board.middle[0], 3);
  Put(&obs.players[1].visual_board.middle[1], 4);
  Put(&obs.players[1].visual_board.bottom[0], 5);
  Put(&obs.players[1].visual_board.bottom[1], 6);
  Put(&obs.players[1].visual_board.bottom[2], 7);
  Put(&obs.players[1].visual_board.bottom[3], 8);
  Put(&obs.players[1].visual_board.bottom[4], 9);

  Put(&obs.hero_loose_cards[0], 20);
  Put(&obs.hero_loose_cards[1], 21);
  obs.hero_loose_count = 2;

  // Two prior-round discards are already known before round 3.
  Put(&obs.hero_discard_tracker[0], 30);
  Put(&obs.hero_discard_tracker[1], 31);
  obs.hero_discard_tracker_count = 2;
  obs.valid = true;
  return obs;
}

COFCVisualObservation Round3Loose1() {
  COFCVisualObservation obs = Round3Loose2();
  // Add a second pre-attach current placement to make 11 visible board cards.
  Put(&obs.players[1].visual_board.middle[2], 20);
  Put(&obs.hero_loose_cards[0], 21);
  obs.hero_loose_cards[1].Clear();
  obs.hero_loose_count = 1;
  return obs;
}

bool Require(bool condition, const char *message) {
  if (condition) return true;
  std::cerr << "FAIL: " << message << "\n";
  return false;
}

}  // namespace

int main() {
  std::string error;

  // 1) Fresh process attaches after exactly one current card was already placed.
  COFCVisualObservation partial2 = Round3Loose2();
  COFCState s2;
  if (!Require(COFCReconstructor::ReconstructCurrentScreen(
        partial2, &s2, &error), "loose=2 current-screen bootstrap")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s2.valid && s2.partial_turn_recovery,
        "loose=2 state is marked partial recovery")) return 1;
  if (!Require(s2.round_index == 3 && s2.hero_incoming_count == 2,
        "loose=2 preserves reduced live incoming set")) return 1;
  if (!Require(s2.players[s2.hero_chair].board.CountKnownCards() == 10,
        "loose=2 fixes the visible board as continuation baseline")) return 1;
  if (!Require(PendingCount(s2) == 0,
        "pre-attach tentative history is not invented as pending state")) return 1;

  COFCStrategyAction a2;
  error.clear();
  if (!Require(COFCBaselinePolicy::Choose(s2, &a2, &error),
        "partial loose=2 policy chooses one finishing placement")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(a2.valid && a2.placement_count == 1 && a2.unused_count == 1,
        "loose=2 action shape is one placement plus one unused discard")) return 1;

  COFCTurnPlan p2;
  error.clear();
  if (!Require(COFCTurnPlanBuilder::Build(s2, a2, &p2, &error),
        "partial loose=2 turn plan")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(p2.valid && p2.target_count == 1 && p2.unused_count == 1,
        "loose=2 turn plan preserves reduced action shape")) return 1;

  // 2) Simulate the one runtime drag. Stateful lineage now knows exactly which
  // card moved after this process attached, so ordinary pending verification can
  // resume without guessing the pre-attach placement.
  const int moved = a2.placements[0].card_value;
  const int unused = a2.unused_cards[0];
  COFCVisualObservation after_drag = partial2;
  PutFirstFree(&after_drag.players[1].visual_board,
    a2.placements[0].row, moved);
  Put(&after_drag.hero_loose_cards[0], unused);
  after_drag.hero_loose_cards[1].Clear();
  after_drag.hero_loose_count = 1;

  COFCState s_after;
  error.clear();
  if (!Require(COFCReconstructor::Reconstruct(
        after_drag, &s2, &s_after, &error),
        "same-round continuation after recovery drag")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s_after.valid && s_after.partial_turn_recovery,
        "partial marker survives only inside the recovered same round")) return 1;
  if (!Require(s_after.hero_incoming_count == 2 && PendingCount(s_after) == 1,
        "post-drag lineage retains two-card decision and one certified pending card")) return 1;

  // 3) Simulate Confirm and next deal. The pre-attach placement was already in
  // the fixed board baseline; only the one post-attach pending card is promoted.
  COFCVisualObservation next_round = after_drag;
  next_round.round_index = 4;
  next_round.confirm_visible = false;
  Put(&next_round.hero_discard_tracker[2], unused);
  next_round.hero_discard_tracker_count = 3;
  Put(&next_round.hero_loose_cards[0], 22);
  Put(&next_round.hero_loose_cards[1], 23);
  Put(&next_round.hero_loose_cards[2], 24);
  next_round.hero_loose_count = 3;

  COFCState s4;
  error.clear();
  if (!Require(COFCReconstructor::Reconstruct(
        next_round, &s_after, &s4, &error),
        "partial recovery exits cleanly on next normal round")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s4.valid && !s4.partial_turn_recovery,
        "partial mode is cleared after round transition")) return 1;
  if (!Require(s4.round_index == 4 && s4.hero_incoming_count == 3,
        "next round returns to ordinary three-card semantics")) return 1;
  if (!Require(s4.players[s4.hero_chair].board.CountKnownCards() == 11,
        "round transition commits exactly the post-attach pending placement")) return 1;

  // 4) Fresh process attaches with two current placements already complete.
  // No strategic reconstruction of those two cards is needed: the only safe
  // physical continuation is Confirm, leaving the final loose card unused.
  COFCVisualObservation partial1 = Round3Loose1();
  COFCState s1;
  error.clear();
  if (!Require(COFCReconstructor::ReconstructCurrentScreen(
        partial1, &s1, &error), "loose=1 current-screen bootstrap")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s1.valid && s1.partial_turn_recovery
        && s1.hero_incoming_count == 1,
        "loose=1 recovery exposes exactly one remaining card")) return 1;

  COFCStrategyAction a1;
  error.clear();
  if (!Require(COFCBaselinePolicy::Choose(s1, &a1, &error),
        "loose=1 policy produces confirm-only partition")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(a1.valid && a1.placement_count == 0 && a1.unused_count == 1,
        "loose=1 action has no drag and one unused discard")) return 1;

  COFCTurnPlan p1;
  error.clear();
  if (!Require(COFCTurnPlanBuilder::Build(s1, a1, &p1, &error),
        "loose=1 confirm-only turn plan")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(p1.valid && p1.target_count == 0 && p1.unused_count == 1,
        "loose=1 turn plan is immediately placement-complete")) return 1;

  std::cout
    << "PASS OpenOFC v5.4.2B partial reconnect: loose=2 bootstrap -> one drag -> "
    << "verified lineage -> next-round exit; loose=1 confirm-only bootstrap\n";
  return 0;
}
