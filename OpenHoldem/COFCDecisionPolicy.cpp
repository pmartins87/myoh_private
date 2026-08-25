//******************************************************************************
// OpenOFC v5.6.0 production decision-policy composition.
//******************************************************************************

#ifndef DEEPOFC_POLICY_STANDALONE
#include "StdAfx.h"
#endif

#include "COFCDecisionPolicy.h"

#include "COFCBaselinePolicy.h"

using namespace std;

COFCDecisionPolicyReport::COFCDecisionPolicyReport()
    : exact_r4_attempted(false) {}

bool COFCDecisionPolicy::Choose(
    const COFCState &state,
    COFCStrategyAction *action,
    COFCDecisionPolicyReport *report,
    string *error) {
  if (action == NULL || report == NULL) return false;
  *report = COFCDecisionPolicyReport();
  if (!COFCBaselinePolicy::Choose(state, action, error)) return false;

  if (!state.valid || state.round_index != 4
      || state.hero_chair < 0 || state.hero_chair >= state.player_count
      || state.players[state.hero_chair].fantasy) return true;

  report->exact_r4_attempted = true;
  COFCStrategyAction exact_action;
  string teacher_error;
  if (!COFCR4ExactTeacher::Improve(
        state, *action, &exact_action, &report->exact_r4, &teacher_error)) {
    report->exact_r4_reason = teacher_error;
    return true;
  }
  if (report->exact_r4.applied) *action = exact_action;
  return true;
}
