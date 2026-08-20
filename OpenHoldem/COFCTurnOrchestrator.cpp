//******************************************************************************
//
// DeepOFC R10 multi-placement turn orchestrator.
//
//******************************************************************************

#include "StdAfx.h"
#include "COFCTurnOrchestrator.h"

#include <sstream>

using namespace std;

namespace {

bool SameBoard(const COFCPlayerBoard &a, const COFCPlayerBoard &b) {
  for (int i = 0; i < kOFCTopCards; ++i)
    if (a.top[i].value != b.top[i].value) return false;
  for (int i = 0; i < kOFCMiddleCards; ++i)
    if (a.middle[i].value != b.middle[i].value) return false;
  for (int i = 0; i < kOFCBottomCards; ++i)
    if (a.bottom[i].value != b.bottom[i].value) return false;
  return true;
}

bool KnownPhysical(int value) {
  return value >= 0 && value <= kOFCCardJoker2;
}

}  // namespace

COFCTurnOrchestrator::COFCTurnOrchestrator() {
  ResetForKnownNewHand();
}

void COFCTurnOrchestrator::ResetForKnownNewHand() {
  active_ = false;
  blocked_ = false;
  baseline_.Reset();
  plan_.Reset();
  placement_executor_.ResetForKnownNewHand();
}

bool COFCTurnOrchestrator::FailAndBlock(
    string *error,
    const string &message) {
  blocked_ = true;
  if (error != NULL) *error = message;
  write_log(k_always_log_errors,
    "[DeepOFC R10] turn orchestration BLOCKED: %s\n", message.c_str());
  return false;
}

bool COFCTurnOrchestrator::SameStrategicDecision(
    const COFCState &a,
    const COFCState &b,
    string *error) const {
  if (!a.valid || !b.valid) {
    if (error != NULL) *error = "strategic decision comparison received invalid state";
    return false;
  }
  if (a.schema_version != b.schema_version
      || a.player_count != b.player_count
      || a.hero_chair != b.hero_chair
      || a.dealer_chair != b.dealer_chair
      || a.acting_chair != b.acting_chair
      || a.round_index != b.round_index) {
    if (error != NULL) *error = "strategic chair/round metadata changed during fixed turn";
    return false;
  }

  for (int p = 0; p < a.player_count; ++p) {
    const COFCPlayerState &pa = a.players[p];
    const COFCPlayerState &pb = b.players[p];
    if (pa.occupied != pb.occupied
        || pa.source_chair != pb.source_chair
        || pa.fantasy != pb.fantasy
        || pa.sitting_out != pb.sitting_out
        || pa.hidden_discard_count != pb.hidden_discard_count
        || pa.hidden_incoming_count != pb.hidden_incoming_count
        || !SameBoard(pa.board, pb.board)) {
      if (error != NULL) *error = "player canonical state changed during fixed turn";
      return false;
    }
  }

  if (a.hero_incoming_count != b.hero_incoming_count
      || a.hero_discard_count != b.hero_discard_count) {
    if (error != NULL) *error = "Hero incoming/discard counts changed during fixed turn";
    return false;
  }
  for (int i = 0; i < a.hero_incoming_count; ++i) {
    if (a.hero_incoming[i].value != b.hero_incoming[i].value) {
      if (error != NULL) *error = "Hero incoming physical identities changed during fixed turn";
      return false;
    }
  }
  for (int i = 0; i < a.hero_discard_count; ++i) {
    if (a.hero_discards[i].value != b.hero_discards[i].value) {
      if (error != NULL) *error = "Hero discard physical identities changed during fixed turn";
      return false;
    }
  }

  // Deliberately ignored here: pending[], hero_can_prepare,
  // hero_can_confirm and action_required. Those are UI progress for the same
  // already-fixed strategic decision and are validated separately.
  return true;
}

bool COFCTurnOrchestrator::ValidateProgress(
    const COFCState &state,
    bool *placements_complete,
    bool *ready_for_confirm,
    COFCStrategyPlacement *next,
    bool *has_next,
    string *error) const {
  if (placements_complete != NULL) *placements_complete = false;
  if (ready_for_confirm != NULL) *ready_for_confirm = false;
  if (has_next != NULL) *has_next = false;
  if (next != NULL) *next = COFCStrategyPlacement();

  if (!plan_.valid || !state.valid) {
    if (error != NULL) *error = "turn plan/state is invalid";
    return false;
  }
  if (state.acting_chair != state.hero_chair) {
    if (error != NULL) *error = "ordered actor changed away from Hero during placement turn";
    return false;
  }
  if (!state.hero_can_prepare) {
    if (error != NULL) *error = "Hero can no longer prepare placements";
    return false;
  }

  bool target_present[54] = {false};
  bool pending_present[54] = {false};
  EOFCRow pending_row[54];
  EOFCRow target_row[54];
  for (int i = 0; i < 54; ++i) {
    target_row[i] = kOFCRowUndefined;
    pending_row[i] = kOFCRowUndefined;
  }

  for (int i = 0; i < plan_.target_count; ++i) {
    const int card = plan_.target[i].card_value;
    const EOFCRow row = plan_.target[i].row;
    if (!KnownPhysical(card)
        || (row != kOFCRowTop && row != kOFCRowMiddle && row != kOFCRowBottom)
        || target_present[card]) {
      if (error != NULL) *error = "turn plan contains invalid/duplicate target placement";
      return false;
    }
    target_present[card] = true;
    target_row[card] = row;
  }

  int pending_count = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active) continue;
    const int incoming_index = state.pending[i].incoming_index;
    if (incoming_index < 0 || incoming_index >= state.hero_incoming_count) {
      if (error != NULL) *error = "fresh state contains invalid pending incoming index";
      return false;
    }
    const int card = state.hero_incoming[incoming_index].value;
    if (!KnownPhysical(card) || pending_present[card]) {
      if (error != NULL) *error = "fresh state contains invalid/duplicate pending physical card";
      return false;
    }
    pending_present[card] = true;
    pending_row[card] = state.pending[i].row;
    ++pending_count;
    if (!target_present[card]) {
      if (error != NULL) *error =
        "fresh pending card is not a solver target; rearrangement is not certified";
      return false;
    }
  }

  bool found_next = false;
  COFCStrategyPlacement candidate;
  for (int i = 0; i < plan_.target_count; ++i) {
    const int card = plan_.target[i].card_value;
    if (!pending_present[card] || pending_row[card] != target_row[card]) {
      candidate = plan_.target[i];
      found_next = true;
      break;
    }
  }

  if (found_next) {
    if (has_next != NULL) *has_next = true;
    if (next != NULL) *next = candidate;
    return true;
  }

  if (pending_count != plan_.target_count) {
    if (error != NULL) *error = "target set appears complete but pending cardinality disagrees";
    return false;
  }

  if (placements_complete != NULL) *placements_complete = true;
  // Confirm can legitimately appear one scrape later than the last placement.
  // Completion therefore does not require it. No further drag is allowed while
  // waiting; a later fresh scrape can promote this to ready_for_confirm.
  if (ready_for_confirm != NULL) {
    *ready_for_confirm = state.hero_can_confirm && state.action_required;
  }
  return true;
}

bool COFCTurnOrchestrator::BeginNextPlacement(
    const COFCState &state,
    const COFCVisualObservation &observation,
    const COFCStrategyPlacement &next,
    int duration_ms,
    bool starting_turn,
    string *error) {
  string placement_error;
  if (placement_executor_.BeginPlacement(
        state, observation, next.card_value, next.row,
        duration_ms, &placement_error)) {
    return true;
  }

  if (placement_executor_.blocked()) {
    return FailAndBlock(error, placement_error);
  }

  if (starting_turn) {
    // A refusal before the first physical mutation (for example disabled
    // runtime authority or missing calibrated source) leaves the table intact.
    // Abort this attempted turn rather than creating a half-active state.
    active_ = false;
    baseline_.Reset();
    plan_.Reset();
    if (error != NULL) *error = placement_error;
    return false;
  }

  // After any earlier placement in this turn, even a pre-mutation ambiguity in
  // planning the next card is terminal for automatic continuation. We must not
  // silently retry, change order or re-solve around a partially arranged UI.
  return FailAndBlock(error, placement_error);
}

bool COFCTurnOrchestrator::StartTurn(
    const COFCState &state,
    const COFCVisualObservation &observation,
    const COFCTurnPlan &plan,
    int duration_ms,
    bool *placements_complete,
    bool *ready_for_confirm,
    string *error) {
  if (error != NULL) error->clear();
  if (placements_complete != NULL) *placements_complete = false;
  if (ready_for_confirm != NULL) *ready_for_confirm = false;

  if (blocked()) {
    if (error != NULL) *error = "turn orchestrator is blocked until known new-hand reset";
    return false;
  }
  if (active_ || placement_executor_.awaiting_verification()) {
    return FailAndBlock(error,
      "attempted to start a second turn while previous turn is still active");
  }
  if (!plan.valid || !plan.decision_state.valid) {
    if (error != NULL) *error = "fixed solver turn plan is invalid/unbound";
    return false;
  }

  string decision_error;
  if (!SameStrategicDecision(plan.decision_state, state, &decision_error)) {
    if (error != NULL) *error = "stale solver turn plan: " + decision_error;
    return false;
  }

  baseline_ = plan.decision_state;
  plan_ = plan;
  active_ = true;

  COFCStrategyPlacement next;
  bool has_next = false;
  string progress_error;
  if (!ValidateProgress(
        state, placements_complete, ready_for_confirm,
        &next, &has_next, &progress_error)) {
    active_ = false;
    baseline_.Reset();
    plan_.Reset();
    if (error != NULL) *error = progress_error;
    return false;
  }

  if (!has_next) {
    return true;
  }

  return BeginNextPlacement(
    state, observation, next, duration_ms, true, error);
}

bool COFCTurnOrchestrator::AdvanceAfterFreshScrape(
    const COFCState &fresh_state,
    const COFCVisualObservation &fresh_observation,
    int duration_ms,
    bool *placements_complete,
    bool *ready_for_confirm,
    string *error) {
  if (error != NULL) error->clear();
  if (placements_complete != NULL) *placements_complete = false;
  if (ready_for_confirm != NULL) *ready_for_confirm = false;

  if (blocked()) {
    if (error != NULL) *error = "turn orchestrator is blocked until known new-hand reset";
    return false;
  }
  if (!active_) {
    if (error != NULL) *error = "no active fixed solver turn";
    return false;
  }

  string decision_error;
  if (!SameStrategicDecision(baseline_, fresh_state, &decision_error)) {
    return FailAndBlock(error,
      "strategy-relevant state drift after turn start: " + decision_error);
  }

  if (placement_executor_.awaiting_verification()) {
    string verify_error;
    if (!placement_executor_.VerifyAfterFreshScrape(
          fresh_state, &verify_error)) {
      return FailAndBlock(error, verify_error);
    }
  }

  COFCStrategyPlacement next;
  bool has_next = false;
  string progress_error;
  if (!ValidateProgress(
        fresh_state, placements_complete, ready_for_confirm,
        &next, &has_next, &progress_error)) {
    return FailAndBlock(error, progress_error);
  }

  if (!has_next) {
    return true;
  }

  return BeginNextPlacement(
    fresh_state, fresh_observation, next, duration_ms, false, error);
}
