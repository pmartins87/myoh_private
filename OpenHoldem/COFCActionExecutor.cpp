//******************************************************************************
//
// DeepOFC R10 single-drag transaction executor.
//
// Enforces one physical drag followed by a fresh canonical verification before
// another drag can begin. The controller never retries an uncertain mutation.
//
//******************************************************************************

#include "StdAfx.h"
#include "COFCActionExecutor.h"

#include "..\CTablemap\CTablemap.h"
#include "CCasinoInterface.h"

using namespace std;

COFCActionExecutor::COFCActionExecutor() {
  ResetForKnownNewHand();
}

void COFCActionExecutor::ResetForKnownNewHand() {
  awaiting_verification_ = false;
  blocked_ = false;
  card_value_ = kOFCCardNoCard;
  row_ = kOFCRowUndefined;
  before_.Reset();
}

bool COFCActionExecutor::FailAndBlock(string *error, const string &message) {
  blocked_ = true;
  awaiting_verification_ = false;
  if (error != NULL) *error = message;
  write_log(k_always_log_errors,
    "[DeepOFC R10] transaction BLOCKED: %s\n", message.c_str());
  return false;
}

bool COFCActionExecutor::RuntimeExecutionExplicitlyEnabled(string *error) const {
  if (p_tablemap == NULL || !p_tablemap->SupportsOFCJokerUltimate()) {
    if (error != NULL) *error = "tablemap is not explicitly Joker Ultimate";
    return false;
  }
  SMapCI it = p_tablemap->s$()->find(CString("ofc_executor_enabled"));
  if (it == p_tablemap->s$()->end()) {
    if (error != NULL) *error = "s$ofc_executor_enabled is missing";
    return false;
  }
  CString value = it->second.text;
  value.Trim();
  if (value != "1") {
    if (error != NULL) *error = "s$ofc_executor_enabled != 1";
    return false;
  }
  return true;
}

bool COFCActionExecutor::BeginPlacement(
    const COFCState &state,
    const COFCVisualObservation &observation,
    int card_value,
    EOFCRow row,
    int duration_ms,
    string *error) {
  if (error != NULL) error->clear();
  if (blocked_) {
    if (error != NULL) *error = "executor is blocked until a known new-hand reset";
    return false;
  }
  if (awaiting_verification_) {
    return FailAndBlock(error,
      "attempted second drag before mandatory verification of previous drag");
  }

  string enable_error;
  if (!RuntimeExecutionExplicitlyEnabled(&enable_error)) {
    // Missing/disabled execution authority is not a table-state corruption, so
    // refuse without latching BLOCKED. A certified future runtime may enable it
    // deliberately; replay drafts always keep it at 0.
    if (error != NULL) *error = enable_error;
    return false;
  }
  if (p_casino_interface == NULL) {
    return FailAndBlock(error, "casino interface is unavailable");
  }

  COFCUIPlacementStep step;
  string plan_error;
  if (!COFCActionPlanner::BuildPlacementStepFromObservation(
        state, observation, card_value, row, &step, &plan_error)) {
    // A planning refusal happens before physical mutation, so it is safe to
    // reject without permanently latching the executor.
    if (error != NULL) *error = plan_error;
    return false;
  }

  before_ = state;
  card_value_ = card_value;
  row_ = row;
  awaiting_verification_ = true;

  if (!p_casino_interface->DragRectToRect(
        step.source_rect, step.target_rect, duration_ms)) {
    // Once the physical primitive was attempted we cannot prove whether KKPoker
    // accepted a partial/complete movement until a later scrape. Block rather
    // than retrying or issuing another action.
    return FailAndBlock(error,
      "physical drag primitive failed or was refused after transaction start");
  }

  write_log(true,
    "[DeepOFC R10] drag sent card=%d row=%d; awaiting fresh canonical verification\n",
    card_value_, static_cast<int>(row_));
  return true;
}

bool COFCActionExecutor::VerifyAfterFreshScrape(
    const COFCState &after,
    string *error) {
  if (error != NULL) error->clear();
  if (blocked_) {
    if (error != NULL) *error = "executor is blocked until a known new-hand reset";
    return false;
  }
  if (!awaiting_verification_) {
    return FailAndBlock(error,
      "verification requested without an active drag transaction");
  }

  string verify_error;
  if (!COFCActionPlanner::VerifyPendingTransition(
        before_, after, card_value_, row_, &verify_error)) {
    return FailAndBlock(error, verify_error);
  }

  write_log(true,
    "[DeepOFC R10] drag VERIFIED card=%d row=%d; next placement may be planned\n",
    card_value_, static_cast<int>(row_));
  awaiting_verification_ = false;
  card_value_ = kOFCCardNoCard;
  row_ = kOFCRowUndefined;
  before_.Reset();
  return true;
}
