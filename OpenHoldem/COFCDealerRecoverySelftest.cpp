//******************************************************************************
// OpenOFC v5.4.2C dealer-marker continuity self-test.
// Built only by the dedicated v5.4.2C CI workflow.
//******************************************************************************

#include "COFCReconstructor.h"

#include <iostream>
#include <string>

namespace {

void Put(COFCCard *card, int value) {
  card->value = value;
}

void InitPlayers(COFCVisualObservation *obs) {
  obs->player_count = 2;
  obs->hero_chair = 1;
  obs->acting_chair = 1;  // v4.4 compatibility placeholder, not turn authority.
  for (int p = 0; p < 2; ++p) {
    obs->players[p].occupied = true;
    obs->players[p].source_chair = p;
    obs->players[p].fantasy = false;
  }
}

COFCVisualObservation Round1AllLoose() {
  COFCVisualObservation obs;
  obs.Reset();
  InitPlayers(&obs);
  obs.round_index = 1;
  obs.hero_can_prepare = true;
  obs.confirm_visible = true;
  obs.hero_timer_active = false;

  Put(&obs.players[1].visual_board.top[0], 0);
  Put(&obs.players[1].visual_board.middle[0], 1);
  Put(&obs.players[1].visual_board.middle[1], 2);
  Put(&obs.players[1].visual_board.bottom[0], 3);
  Put(&obs.players[1].visual_board.bottom[1], 4);

  Put(&obs.hero_loose_cards[0], 5);
  Put(&obs.hero_loose_cards[1], 6);
  Put(&obs.hero_loose_cards[2], 7);
  obs.hero_loose_count = 3;
  obs.valid = true;
  return obs;
}

void UnknownDealer(COFCVisualObservation *obs) {
  obs->dealer_chair = -1;
  obs->dealer_known = false;
}

void KnownDealer(COFCVisualObservation *obs, int chair) {
  obs->dealer_chair = chair;
  obs->dealer_known = true;
}

bool Require(bool condition, const char *message) {
  if (condition) return true;
  std::cerr << "FAIL: " << message << "\n";
  return false;
}

}  // namespace

int main() {
  std::string error;

  // 1) Fresh process + missing/ambiguous dealer marker: card state is still
  // canonical and arrangement may proceed, but Confirm is held unless another
  // independent finalization proof (the Hero timer) appears.
  COFCVisualObservation unknown = Round1AllLoose();
  UnknownDealer(&unknown);
  COFCState s_unknown;
  if (!Require(COFCReconstructor::ReconstructCurrentScreen(
        unknown, &s_unknown, &error),
        "fresh unknown-dealer current-screen bootstrap")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s_unknown.valid && !s_unknown.dealer_known,
        "unknown dealer remains explicit canonical uncertainty")) return 1;
  if (!Require(!s_unknown.dealer_carried,
        "fresh unknown dealer is never fabricated from history")) return 1;
  if (!Require(s_unknown.hero_can_prepare,
        "unknown dealer does not block safe card arrangement")) return 1;
  if (!Require(!s_unknown.decision_finalizable
        && !s_unknown.hero_can_confirm
        && !s_unknown.action_required,
        "unknown dealer without timer holds Confirm")) return 1;

  // 2) Exact opponent dealer marker arrives on a later heartbeat. Unknown ->
  // exact is a confidence upgrade, not an in-hand metadata contradiction.
  COFCVisualObservation opponent = unknown;
  KnownDealer(&opponent, 0);
  COFCState s_opponent;
  error.clear();
  if (!Require(COFCReconstructor::Reconstruct(
        opponent, &s_unknown, &s_opponent, &error),
        "unknown dealer upgrades to exact opponent dealer")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s_opponent.valid && s_opponent.dealer_known
        && s_opponent.dealer_chair == 0 && !s_opponent.dealer_carried,
        "visible opponent dealer is exact, not carried")) return 1;
  if (!Require(s_opponent.decision_finalizable
        && s_opponent.hero_can_confirm
        && s_opponent.action_required,
        "opponent dealer makes visible Confirm finalizable")) return 1;

  // 3) Hero is the exact dealer and timer has not started: prepare is allowed,
  // submission remains provisional.
  COFCVisualObservation hero_dealer = Round1AllLoose();
  KnownDealer(&hero_dealer, 1);
  hero_dealer.hero_timer_active = false;
  COFCState s_hero_wait;
  error.clear();
  if (!Require(COFCReconstructor::ReconstructCurrentScreen(
        hero_dealer, &s_hero_wait, &error),
        "Hero-dealer provisional bootstrap")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s_hero_wait.dealer_known && s_hero_wait.dealer_chair == 1,
        "Hero dealer identity is retained")) return 1;
  if (!Require(s_hero_wait.hero_can_prepare
        && !s_hero_wait.decision_finalizable
        && !s_hero_wait.hero_can_confirm,
        "Hero dealer waits for timer before Confirm")) return 1;

  // 4) Timer is an independent finalization proof. Even Hero dealer may submit
  // when the timer becomes active.
  COFCVisualObservation hero_timer = hero_dealer;
  hero_timer.hero_timer_active = true;
  COFCState s_timer;
  error.clear();
  if (!Require(COFCReconstructor::Reconstruct(
        hero_timer, &s_hero_wait, &s_timer, &error),
        "Hero timer upgrades provisional state")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s_timer.decision_finalizable
        && s_timer.hero_can_confirm && s_timer.action_required,
        "Hero timer authorizes finalization")) return 1;

  // 5) Once an exact dealer was certified in this hand, a one-frame marker
  // dropout carries that exact identity forward. This is temporal memory, not a
  // guess, and is explicitly tagged for logs/diagnostics.
  COFCVisualObservation dropout = opponent;
  UnknownDealer(&dropout);
  COFCState s_carried;
  error.clear();
  if (!Require(COFCReconstructor::Reconstruct(
        dropout, &s_opponent, &s_carried, &error),
        "same-hand exact dealer survives marker dropout")) {
    std::cerr << error << "\n";
    return 1;
  }
  if (!Require(s_carried.valid && s_carried.dealer_known
        && s_carried.dealer_chair == 0 && s_carried.dealer_carried,
        "dropout uses only prior certified exact dealer")) return 1;
  if (!Require(s_carried.decision_finalizable && s_carried.hero_can_confirm,
        "carried opponent dealer preserves safe finalization")) return 1;

  // 6) Contradictory exact identities remain fail-closed. Continuity must not
  // turn a real dealer change inside one hand into permissive guessing.
  COFCVisualObservation contradiction = opponent;
  KnownDealer(&contradiction, 1);
  COFCState rejected;
  error.clear();
  if (!Require(!COFCReconstructor::Reconstruct(
        contradiction, &s_opponent, &rejected, &error),
        "contradictory exact dealer identity rejects")) return 1;
  if (!Require(error.find("dealer chair changed inside hand")
        != std::string::npos,
        "dealer contradiction reason remains explicit")) return 1;

  std::cout
    << "PASS OpenOFC v5.4.2C dealer continuity: fresh unknown -> provisional, "
    << "unknown->exact upgrade, Hero-dealer timer gate, prior-exact carry-forward, "
    << "contradictory exact identity fail-closed\n";
  return 0;
}
