//******************************************************************************
// OpenOFC v5.4.4 UNKNOWN_OCCUPIED regression.
// Compiled only after the v5.4.4 materialization patch is applied.
//******************************************************************************

#include "COFCBaselinePolicy.h"
#include "COFCReconstructor.h"
#include "COFCTurnPlan.h"

#include <iostream>
#include <string>

namespace {

void Put(COFCCard *card, int value) { card->value = value; }

bool Require(bool condition, const char *message) {
  if (condition) return true;
  std::cerr << "FAIL: " << message << "\n";
  return false;
}

void InitPlayers(COFCVisualObservation *obs, int round) {
  obs->Reset();
  obs->valid = true;
  obs->player_count = 2;
  obs->hero_chair = 1;
  obs->dealer_chair = 0;
  obs->dealer_known = true;
  obs->acting_chair = 1;
  obs->round_index = round;
  obs->hero_can_prepare = true;
  obs->confirm_visible = false;
  for (int p = 0; p < 2; ++p) {
    obs->players[p].occupied = true;
    obs->players[p].source_chair = p;
    obs->players[p].fantasy = false;
  }
}

void PutOpeningBoard(COFCPlayerBoard *board) {
  // A deterministic 1/2/2 legal-capacity opening shape.
  Put(&board->top[0], 0);
  Put(&board->middle[0], 1);
  Put(&board->middle[1], 2);
  Put(&board->bottom[0], 3);
  Put(&board->bottom[1], 4);
}

void PutLoose(COFCVisualObservation *obs, int index, int value) {
  Put(&obs->hero_loose_cards[index], value);
  obs->hero_loose_sources[index].valid = true;
  obs->hero_loose_sources[index].card_value = value;
  obs->hero_loose_sources[index].rect.left = 20 + index * 30;
  obs->hero_loose_sources[index].rect.top = 650;
  obs->hero_loose_sources[index].rect.right = 40 + index * 30;
  obs->hero_loose_sources[index].rect.bottom = 710;
}

int UnknownIncoming(const COFCState &state) {
  int count = 0;
  for (int i = 0; i < state.hero_incoming_count; ++i)
    if (state.hero_incoming[i].value == kOFCCardUnknown) ++count;
  return count;
}

COFCState PreviousRound0() {
  COFCState state;
  state.Reset();
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 1;
  state.dealer_chair = 0;
  state.dealer_known = true;
  state.acting_chair = 1;
  state.round_index = 0;
  state.hero_can_prepare = true;
  for (int p = 0; p < 2; ++p) {
    state.players[p].occupied = true;
    state.players[p].source_chair = p;
  }
  state.hero_incoming_count = 5;
  for (int i = 0; i < 5; ++i) state.hero_incoming[i].value = i;
  return state;
}

bool NewLaterRoundUnknownIsActionable(COFCState *round1_out) {
  COFCState previous = PreviousRound0();
  COFCVisualObservation obs;
  InitPlayers(&obs, 1);
  PutOpeningBoard(&obs.players[1].visual_board);
  PutLoose(&obs, 0, 5);
  PutLoose(&obs, 1, 6);
  PutLoose(&obs, 2, kOFCCardUnknown);
  obs.hero_loose_count = 3;

  std::string error;
  COFCState state;
  if (!Require(COFCReconstructor::Reconstruct(obs, &previous, &state, &error),
        "R1 with two known + one UNKNOWN must reconstruct")) {
    std::cerr << error << "\n";
    return false;
  }
  if (!Require(state.valid && state.round_index == 1
        && state.hero_incoming_count == 3 && UnknownIncoming(state) == 1,
        "R1 canonical state retains UNKNOWN as occupied incoming")) return false;

  COFCStrategyAction action;
  error.clear();
  if (!Require(COFCBaselinePolicy::Choose(state, &action, &error),
        "R1 UNKNOWN policy must choose the two readable cards")) {
    std::cerr << error << "\n";
    return false;
  }
  if (!Require(action.valid && action.placement_count == 2
        && action.unused_count == 1
        && action.unused_cards[0] == kOFCCardUnknown,
        "R1 UNKNOWN is the sole safe unused card")) return false;

  COFCTurnPlan plan;
  error.clear();
  if (!Require(COFCTurnPlanBuilder::Build(state, action, &plan, &error),
        "turn plan must accept UNKNOWN only as unused")) {
    std::cerr << error << "\n";
    return false;
  }
  if (!Require(plan.valid && plan.target_count == 2 && plan.unused_count == 1
        && plan.unused_cards[0] == kOFCCardUnknown,
        "turn plan preserves two targets + UNKNOWN unused partition")) return false;

  if (round1_out != NULL) *round1_out = state;
  return true;
}

bool TransientSameRoundUnknownRecoversIdentity() {
  COFCState previous;
  previous.Reset();
  previous.valid = true;
  previous.player_count = 2;
  previous.hero_chair = 1;
  previous.dealer_chair = 0;
  previous.dealer_known = true;
  previous.acting_chair = 1;
  previous.round_index = 1;
  previous.hero_can_prepare = true;
  for (int p = 0; p < 2; ++p) {
    previous.players[p].occupied = true;
    previous.players[p].source_chair = p;
  }
  PutOpeningBoard(&previous.players[1].board);
  previous.hero_incoming_count = 3;
  previous.hero_incoming[0].value = 5;
  previous.hero_incoming[1].value = 6;
  previous.hero_incoming[2].value = 7;

  COFCVisualObservation obs;
  InitPlayers(&obs, 1);
  PutOpeningBoard(&obs.players[1].visual_board);
  PutLoose(&obs, 0, 5);
  PutLoose(&obs, 1, 6);
  PutLoose(&obs, 2, kOFCCardUnknown);
  obs.hero_loose_count = 3;

  COFCState repaired;
  std::string error;
  if (!Require(COFCReconstructor::Reconstruct(obs, &previous, &repaired, &error),
        "same-round transient UNKNOWN must reconstruct from lineage")) {
    std::cerr << error << "\n";
    return false;
  }
  if (!Require(UnknownIncoming(repaired) == 0,
        "same-round transient UNKNOWN must recover prior identity")) return false;
  bool found7 = false;
  for (int i = 0; i < repaired.hero_incoming_count; ++i)
    if (repaired.hero_incoming[i].value == 7) found7 = true;
  return Require(found7, "lineage repair restores the missing physical card identity");
}

bool UnknownUnusedDoesNotBlockNextRound(const COFCState &round1) {
  COFCVisualObservation obs;
  InitPlayers(&obs, 2);
  PutOpeningBoard(&obs.players[1].visual_board);
  // The two readable R1 cards are now committed.  The UNKNOWN physical card was
  // intentionally left loose and was discarded by Confirm; its rank/suit is
  // never invented and therefore does not appear in canonical discard identity.
  Put(&obs.players[1].visual_board.middle[2], 5);
  Put(&obs.players[1].visual_board.bottom[2], 6);
  PutLoose(&obs, 0, 7);
  PutLoose(&obs, 1, 8);
  PutLoose(&obs, 2, 9);
  obs.hero_loose_count = 3;

  COFCState next;
  std::string error;
  if (!Require(COFCReconstructor::Reconstruct(obs, &round1, &next, &error),
        "R1 UNKNOWN unused must not block transition to R2")) {
    std::cerr << error << "\n";
    return false;
  }
  return Require(next.valid && next.round_index == 2
      && next.hero_incoming_count == 3 && UnknownIncoming(next) == 0
      && next.players[next.hero_chair].board.CountKnownCards() == 7,
      "R2 commits both readable R1 cards and continues with three new cards");
}

bool OpeningUnknownStaysValidButPolicyWaits() {
  COFCState state;
  state.Reset();
  state.valid = true;
  state.player_count = 2;
  state.hero_chair = 1;
  state.dealer_chair = 0;
  state.dealer_known = true;
  state.acting_chair = 1;
  state.round_index = 0;
  state.hero_can_prepare = true;
  state.players[0].occupied = state.players[1].occupied = true;
  state.players[0].source_chair = 0;
  state.players[1].source_chair = 1;
  state.hero_incoming_count = 5;
  state.hero_incoming[0].value = 10;
  state.hero_incoming[1].value = 11;
  state.hero_incoming[2].value = 12;
  state.hero_incoming[3].value = 13;
  state.hero_incoming[4].value = kOFCCardUnknown;

  COFCStrategyAction action;
  std::string error;
  const bool chose = COFCBaselinePolicy::Choose(state, &action, &error);
  return Require(!chose && error == "WAIT_TRANSIENT_UNKNOWN_OPENING",
    "R0 UNKNOWN must wait for identity instead of inventing rank/suit");
}

}  // namespace

int main() {
  COFCState r1;
  if (!NewLaterRoundUnknownIsActionable(&r1)) return 1;
  if (!TransientSameRoundUnknownRecoversIdentity()) return 1;
  if (!UnknownUnusedDoesNotBlockNextRound(r1)) return 1;
  if (!OpeningUnknownStaysValidButPolicyWaits()) return 1;
  std::cout
    << "PASS OpenOFC v5.4.4 UNKNOWN_OCCUPIED: transient lineage repair, "
    << "later-round safe unused, next-round continuation, opening wait\n";
  return 0;
}
