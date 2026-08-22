//******************************************************************************
// DeepOFC recoverable-runtime liveness contract.
//******************************************************************************

#ifndef __COFC_RECOVERY_LIVENESS_H__
#define __COFC_RECOVERY_LIVENESS_H__

// A runtime/action fault is never allowed to create an absorbing state.
// Perception continues every heartbeat.  When a UI action may already have
// been dispatched, we first give the table a bounded observation window to
// expose the resulting Hero-state change.  If the same valid semantic state
// persists for the entire window, that persistence is evidence that the action
// was not observed and the controller is released to re-plan/retry.
//
// This helper is deliberately dependency-free so the exact liveness decision
// used by COFCRuntimeController can be regression-tested outside MFC/OpenHoldem.

enum EOFCRecoveryLivenessReason {
  kOFCRecoveryWaitInvalidPerception = 0,
  kOFCRecoveryReleaseHeroStateChanged,
  kOFCRecoveryWaitStableObservation,
  kOFCRecoveryReleaseSameStateTimeout
};

struct COFCRecoveryLivenessDecision {
  COFCRecoveryLivenessDecision()
      : release(false), stable_cycles(0), required_cycles(0),
        reason(kOFCRecoveryWaitInvalidPerception) {}

  bool release;
  int stable_cycles;
  int required_cycles;
  EOFCRecoveryLivenessReason reason;
};

inline COFCRecoveryLivenessDecision EvaluateOFCRecoveryLiveness(
    bool perception_valid,
    bool hero_state_changed,
    bool action_may_have_been_dispatched,
    int prior_stable_cycles) {
  COFCRecoveryLivenessDecision out;

  // Invalid perception is transient.  Do not consume the stability budget;
  // simply wait for the next scrape.
  if (!perception_valid) {
    out.stable_cycles = prior_stable_cycles < 0 ? 0 : prior_stable_cycles;
    out.reason = kOFCRecoveryWaitInvalidPerception;
    return out;
  }

  // A changed Hero semantic state proves that the old transaction is no
  // longer current.  Re-plan immediately from the newly perceived table.
  if (hero_state_changed) {
    out.release = true;
    out.reason = kOFCRecoveryReleaseHeroStateChanged;
    return out;
  }

  // If an input might already have been sent (drag or Confirm), use a longer
  // debounce to avoid a duplicate while the client animation catches up.
  // Otherwise two stable valid observations are enough to retry.
  out.required_cycles = action_may_have_been_dispatched ? 8 : 2;
  out.stable_cycles = (prior_stable_cycles < 0 ? 0 : prior_stable_cycles) + 1;

  if (out.stable_cycles >= out.required_cycles) {
    out.release = true;
    out.reason = kOFCRecoveryReleaseSameStateTimeout;
  } else {
    out.reason = kOFCRecoveryWaitStableObservation;
  }
  return out;
}

inline const char *OFCRecoveryLivenessReasonLabel(
    EOFCRecoveryLivenessReason reason) {
  switch (reason) {
    case kOFCRecoveryWaitInvalidPerception:
      return "INVALID_PERCEPTION";
    case kOFCRecoveryReleaseHeroStateChanged:
      return "HERO_STATE_CHANGED";
    case kOFCRecoveryWaitStableObservation:
      return "STABLE_OBSERVATION_DEBOUNCE";
    case kOFCRecoveryReleaseSameStateTimeout:
      return "SAME_STATE_TIMEOUT_REPLAN";
    default:
      return "UNKNOWN";
  }
}

#endif  // __COFC_RECOVERY_LIVENESS_H__
