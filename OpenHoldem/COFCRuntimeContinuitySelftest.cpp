//******************************************************************************
// OpenOFC v5.4.2B runtime-continuity current-screen reconstruction self-test.
// Built only by the dedicated v5.4.2B CI workflow.
//******************************************************************************

#include "COFCReconstructor.h"

#include <iostream>
#include <string>

namespace {

void Put(COFCCard *card, int value) {
  card->value = value;
}

void InitPlayers(COFCVisualObservation *obs, bool fantasy) {
  obs->player_count = 2;
  obs->hero_chair = 1;
  obs->dealer_chair = 0;
  obs->acting_chair = 1;
  for (int p = 0; p < 2; ++p) {
    obs->players[p].occupied = true;
    obs->players[p].source_chair = p;
    obs->players[p].fantasy = fantasy && p == 1;
  }
}

COFCVisualObservation NormalRound1AllLoose() {
  COFCVisualObservation obs;
  obs.Reset();
  InitPlayers(&obs, false);
  obs.round_index = 1;
  obs.hero_can_prepare = true;
  obs.confirm_visible = false;

  // Five already-committed Hero cards.
  Put(&obs.players[1].visual_board.top[0], 0);
  Put(&obs.players[1].visual_board.middle[0], 1);
  Put(&obs.players[1].visual_board.middle[1], 2);
  Put(&obs.players[1].visual_board.bottom[0], 3);
  Put(&obs.players[1].visual_board.bottom[1], 4);

  // Current R1 trio is completely loose, so the screen is self-describing.
  Put(&obs.hero_loose_cards[0], 5);
  Put(&obs.hero_loose_cards[1], 6);
  Put(&obs.hero_loose_cards[2], 7);
  obs.hero_loose_count = 3;
  obs.valid = true;
  return obs;
}

COFCVisualObservation FantasyLoose(int count) {
  COFCVisualObservation obs;
  obs.Reset();
  InitPlayers(&obs, true);
  obs.round_index = -1;
  obs.hero_can_prepare = true;
  obs.confirm_visible = false;
  for (int i = 0; i < count; ++i) {
    Put(&obs.hero_loose_cards[i], i);
  }
  obs.hero_loose_count = count;
  obs.valid = true;
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
  COFCState state;

  COFCVisualObservation r1 = NormalRound1AllLoose();
  if (!Require(COFCReconstructor::ReconstructCurrentScreen(
        r1, &state, &error), "R1 all-loose current-screen bootstrap")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(state.valid && state.round_index == 1,
        "R1 recovery produced canonical round 1")) return 1;
  if (!Require(!state.partial_turn_recovery,
        "all-loose recovery remains ordinary normal semantics")) return 1;
  if (!Require(state.players[state.hero_chair].board.CountKnownCards() == 5,
        "R1 recovery preserved five committed Hero cards")) return 1;
  if (!Require(state.hero_incoming_count == 3,
        "R1 recovery exposed exactly three current incoming cards")) return 1;

  // Reproduce the field-failure class: lineage says one trio, the stable
  // current screen says another trio in the same round. Lineage reconstruction
  // must reject; the independent current-screen candidate remains available.
  COFCState stale = state;
  COFCVisualObservation drift = r1;
  Put(&drift.hero_loose_cards[2], 8);
  COFCState rejected;
  error.clear();
  if (!Require(!COFCReconstructor::Reconstruct(
        drift, &stale, &rejected, &error),
        "same-round identity drift must reject stale lineage")) return 1;
  // v5.4.4E narrows the wording because UNKNOWN->known is now a permitted
  // monotonic refinement, while known->different-known remains a hard drift.
  // Keep this older continuity regression valid on both sides of that upgrade.
  const bool drift_reason_observable =
    error.find("identities changed within the same round") != std::string::npos
    || error.find("same-round incoming physical set changed outside monotonic identity refinement")
        != std::string::npos;
  if (!Require(drift_reason_observable,
        "field identity-drift reason remains observable")) return 1;
  error.clear();
  if (!Require(COFCReconstructor::ReconstructCurrentScreen(
        drift, &state, &error),
        "same-round drift has a safe all-loose current-screen candidate")) {
    std::cerr << error << "\n";
    return 1;
  }

  // v5.4.2B extends the current-screen contract: once one card has already
  // been placed before process attachment, the whole visible Hero board is the
  // fixed continuation baseline and the remaining two loose cards are the only
  // live decision set. No historical tentative-card identity is guessed.
  COFCVisualObservation partial = r1;
  Put(&partial.players[1].visual_board.top[1], 5);
  Put(&partial.hero_loose_cards[0], 6);
  Put(&partial.hero_loose_cards[1], 7);
  partial.hero_loose_cards[2].Clear();
  partial.hero_loose_count = 2;
  error.clear();
  if (!Require(COFCReconstructor::ReconstructCurrentScreen(
        partial, &state, &error),
        "partial later-round screen is recoverable without history guessing")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(state.valid && state.partial_turn_recovery,
        "partial-screen recovery is explicitly marked")) return 1;
  if (!Require(state.players[state.hero_chair].board.CountKnownCards() == 6,
        "partial-screen visible Hero board becomes fixed baseline")) return 1;
  if (!Require(state.hero_incoming_count == 2,
        "partial-screen recovery exposes only remaining live cards")) return 1;

  // Fantasy remains one generic runtime mode. Canonical recovery is count-
  // agnostic across every legal 14..17-card deal size.
  for (int count = 14; count <= 17; ++count) {
    COFCVisualObservation fantasy = FantasyLoose(count);
    error.clear();
    if (!Require(COFCReconstructor::ReconstructCurrentScreen(
          fantasy, &state, &error),
          "generic Fantasy current-screen bootstrap")) {
      std::cerr << "Fantasy count=" << count << " error=" << error << "\n";
      return 1;
    }
    if (!Require(state.valid && state.round_index == -1,
          "Fantasy recovery produced one-shot canonical state")) return 1;
    if (!Require(!state.partial_turn_recovery,
          "Fantasy never inherits normal partial-reconnect semantics")) return 1;
    if (!Require(state.hero_incoming_count == count,
          "Fantasy recovery preserved dynamic card count")) return 1;
  }

  std::cout
    << "PASS OpenOFC v5.4.2B current-screen continuity: "
    << "all-loose bootstrap, identity-drift reacquire, partial loose=2 baseline, "
    << "Fantasy 14..17\n";
  return 0;
}
