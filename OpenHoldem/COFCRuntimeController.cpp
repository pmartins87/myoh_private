//******************************************************************************
// DeepOFC FP0 live turn controller.
//******************************************************************************

#include "StdAfx.h"
#include "COFCRuntimeController.h"

#include <algorithm>
#include <sstream>
#include <vector>

#include "COFCBaselinePolicy.h"
#include "CardFunctions.h"
#include "CCasinoInterface.h"
#include "CTableState.h"
#include "..\CTablemap\CTablemap.h"

using namespace std;

namespace {

bool ReadRegion(const CString &name, RECT *rect) {
  if (p_tablemap == NULL || rect == NULL) return false;
  RMapCI it = p_tablemap->r$()->find(name);
  if (it == p_tablemap->r$()->end()) return false;
  rect->left = static_cast<LONG>(it->second.left);
  rect->top = static_cast<LONG>(it->second.top);
  rect->right = static_cast<LONG>(it->second.right);
  rect->bottom = static_cast<LONG>(it->second.bottom);
  return rect->right > rect->left && rect->bottom > rect->top;
}

string CardLabel(int value) {
  if (value == kOFCCardJoker1) return "JK1";
  if (value == kOFCCardJoker2) return "JK2";
  if (value < 0 || value > 51) return "INVALID";
  const char ranks[] = "23456789TJQKA";
  const char suits[] = "cdhs";
  string label;
  label.push_back(ranks[StdDeck_RANK(value)]);
  label.push_back(suits[StdDeck_SUIT(value)]);
  return label;
}

const char *RowLabel(EOFCRow row) {
  switch (row) {
    case kOFCRowTop: return "top";
    case kOFCRowMiddle: return "middle";
    case kOFCRowBottom: return "bottom";
    default: return "undefined";
  }
}

void LogStrategyAction(const COFCStrategyAction &action) {
  ostringstream placements;
  placements << "[";
  for (int i = 0; i < action.placement_count; ++i) {
    if (i != 0) placements << ",";
    placements << CardLabel(action.placements[i].card_value)
      << "->" << RowLabel(action.placements[i].row);
  }
  placements << "]";
  ostringstream unused;
  unused << "[";
  for (int i = 0; i < action.unused_count; ++i) {
    if (i != 0) unused << ",";
    unused << CardLabel(action.unused_cards[i]);
  }
  unused << "]";
  write_log(true,
    "[DeepOFC POLICY] valid=%d placements=%s unused=%s\n",
    action.valid ? 1 : 0, placements.str().c_str(), unused.str().c_str());
}

}  // namespace

COFCRuntimeController::COFCRuntimeController()
    : phase_(kIdle), pending_before_drag_(0) {}

int COFCRuntimeController::PendingCount(const COFCState &state) {
  int count = 0;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i)
    if (state.pending[i].active) ++count;
  return count;
}

string COFCRuntimeController::PendingSignature(const COFCState &state) {
  vector<pair<int, int> > placements;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active) continue;
    const int index = state.pending[i].incoming_index;
    if (index < 0 || index >= state.hero_incoming_count) continue;
    placements.push_back(make_pair(
      state.hero_incoming[index].value,
      static_cast<int>(state.pending[i].row)));
  }
  sort(placements.begin(), placements.end());
  ostringstream out;
  for (size_t i = 0; i < placements.size(); ++i)
    out << placements[i].first << '@' << placements[i].second << ',';
  return out.str();
}

string COFCRuntimeController::IncomingSignature(const COFCState &state) {
  vector<int> cards;
  for (int i = 0; i < state.hero_incoming_count; ++i)
    cards.push_back(state.hero_incoming[i].value);
  sort(cards.begin(), cards.end());
  ostringstream out;
  out << (state.players[state.hero_chair].fantasy ? "F" : "N")
      << ':' << state.dealer_chair << ':';
  for (size_t i = 0; i < cards.size(); ++i) out << cards[i] << ',';
  return out.str();
}

bool COFCRuntimeController::IsKnownNewHand(const COFCState &state) const {
  if (!state.valid || state.hero_chair < 0
      || state.hero_chair >= state.player_count) return false;
  const bool initial_normal = !state.players[state.hero_chair].fantasy
    && state.round_index == 0
    && state.players[state.hero_chair].board.CountKnownCards() == 0;
  const bool initial_fantasy = state.players[state.hero_chair].fantasy
    && state.round_index == -1 && PendingCount(state) == 0
    && state.hero_incoming_count == 15;
  return (initial_normal || initial_fantasy)
    && IncomingSignature(state) != hand_signature_;
}

void COFCRuntimeController::ResetForKnownNewHand(const COFCState &state) {
  orchestrator_.ResetForKnownNewHand();
  plan_.Reset();
  confirm_before_.Reset();
  pending_before_drag_ = 0;
  pending_signature_before_drag_.clear();
  hand_signature_ = IncomingSignature(state);
  phase_ = kIdle;
  write_log(true, "[DeepOFC FP0] known new hand; runtime reset\n");
}

void COFCRuntimeController::Block(const string &message) {
  phase_ = kBlocked;
  write_log(k_always_log_errors,
    "[DeepOFC FP0] AUTOMATION BLOCKED until a known new hand: %s\n",
    message.c_str());
}

bool COFCRuntimeController::SendConfirm(const COFCState &state) {
  if (!state.valid || !state.hero_can_confirm || !state.action_required
      || state.acting_chair != state.hero_chair) {
    Block("attempted Confirm without exact canonical Hero authority");
    return false;
  }
  CString region = state.players[state.hero_chair].fantasy
    ? CString("ofc_fantasy15_confirm_button")
    : CString("ofc_confirm_button");
  RECT rect;
  if (!ReadRegion(region, &rect)) {
    Block("missing calibrated Confirm button region");
    return false;
  }
  write_log(true,
    "[DeepOFC CONFIRM] sending region=%s rect=(%ld,%ld,%ld,%ld) round=%d fantasy=%d\n",
    region.GetString(), rect.left, rect.top, rect.right, rect.bottom,
    state.round_index, state.players[state.hero_chair].fantasy ? 1 : 0);
  if (p_casino_interface == NULL || !p_casino_interface->ClickRectSafely(rect)) {
    Block("safe Confirm click was refused after transaction start");
    return false;
  }
  confirm_before_ = state;
  phase_ = kConfirmSent;
  write_log(true,
    "[DeepOFC FP0] Confirm sent once; duplicate clicks prohibited\n");
  return true;
}

bool COFCRuntimeController::StartDecision(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  COFCStrategyAction action;
  string error;
  if (!COFCBaselinePolicy::Choose(state, &action, &error)) {
    write_log(k_always_log_errors,
      "[DeepOFC POLICY] result=REJECTED reason=\"%s\"\n", error.c_str());
    Block("policy refused state: " + error);
    return false;
  }
  LogStrategyAction(action);
  if (!COFCTurnPlanBuilder::Build(state, action, &plan_, &error)) {
    Block("turn-plan validation failed: " + error);
    return false;
  }
  write_log(true,
    "[DeepOFC PLAN] target=%d already_correct=%d to_add=%d unused=%d\n",
    plan_.target_count, plan_.already_correct_count,
    plan_.to_add_count, plan_.unused_count);
  bool complete = false;
  bool ready = false;
  const int duration = max(100,
    p_tablemap->GetTMSymbol("ofc_drag_duration_ms", 350));
  pending_before_drag_ = PendingCount(state);
  pending_signature_before_drag_ = PendingSignature(state);
  if (!orchestrator_.StartTurn(
        state, observation, plan_, duration,
        &complete, &ready, &error)) {
    Block("turn start failed: " + error);
    return false;
  }
  phase_ = kArranging;
  if (complete && ready) return SendConfirm(state);
  return true;
}

bool COFCRuntimeController::AdvanceArrangement(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  const int current_pending = PendingCount(state);
  if (orchestrator_.awaiting_drag_verification()
      && PendingSignature(state) == pending_signature_before_drag_) {
    write_log(true,
      "[DeepOFC WAIT] drag not visible yet pending_signature=\"%s\"\n",
      pending_signature_before_drag_.c_str());
    return true;  // Current frame has not incorporated the drag yet.
  }
  bool complete = false;
  bool ready = false;
  string error;
  const int duration = max(100,
    p_tablemap->GetTMSymbol("ofc_drag_duration_ms", 350));
  if (!orchestrator_.AdvanceAfterFreshScrape(
        state, observation, duration, &complete, &ready, &error)) {
    Block("post-drag verification/continuation failed: " + error);
    return false;
  }
  pending_before_drag_ = current_pending;
  pending_signature_before_drag_ = PendingSignature(state);
  if (complete && ready) return SendConfirm(state);
  return true;
}

bool COFCRuntimeController::HandlePostConfirm(const COFCState &state) {
  // Never resend Confirm. A still-identical actionable state is simply a wait.
  if (state.round_index == confirm_before_.round_index
      && state.acting_chair == state.hero_chair
      && state.hero_can_confirm) return true;

  if (confirm_before_.players[confirm_before_.hero_chair].fantasy
      || confirm_before_.round_index == 4) {
    // The supplied post-Fantasy/final-round teardown geometry is not part of
    // the actionable scraper contract. The next known hand performs reset.
    return true;
  }

  COFCConfirmReceipt receipt;
  string error;
  if (!COFCConfirmVerifier::VerifyNormalTransition(
        confirm_before_, state, plan_, &receipt, &error)) {
    Block("Confirm transition was not proven: " + error);
    return false;
  }
  if (receipt.transition == kOFCConfirmNextRoundCommitted) {
    orchestrator_.ResetForKnownNewHand();
    plan_.Reset();
    confirm_before_.Reset();
    phase_ = kIdle;
    if (state.acting_chair == state.hero_chair && state.hero_can_prepare)
      return StartDecision(state, *p_table_state->OFCVisualObservation());
  }
  return true;
}

void COFCRuntimeController::Tick(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  write_log(true,
    "[DeepOFC TICK] phase=%d state_valid=%d raw_valid=%d actor=%d hero=%d "
    "round=%d prepare=%d confirm=%d action_required=%d pending=%d\n",
    static_cast<int>(phase_), state.valid ? 1 : 0, observation.valid ? 1 : 0,
    state.acting_chair, state.hero_chair, state.round_index,
    state.hero_can_prepare ? 1 : 0, state.hero_can_confirm ? 1 : 0,
    state.action_required ? 1 : 0, PendingCount(state));
  if (!state.valid || !observation.valid) {
    write_log(true, "[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION\n");
    return;
  }
  if (IsKnownNewHand(state)) ResetForKnownNewHand(state);
  if (phase_ == kBlocked) {
    write_log(true, "[DeepOFC TICK] action=NONE reason=RUNTIME_BLOCKED\n");
    return;
  }
  if (phase_ == kConfirmSent) {
    HandlePostConfirm(state);
    return;
  }
  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare) {
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=WAITING_TURN actor=%d hero=%d prepare=%d\n",
      state.acting_chair, state.hero_chair, state.hero_can_prepare ? 1 : 0);
    return;
  }
  if (phase_ == kIdle) {
    if (hand_signature_.empty()) hand_signature_ = IncomingSignature(state);
    StartDecision(state, observation);
    return;
  }
  if (phase_ == kArranging) AdvanceArrangement(state, observation);
}
