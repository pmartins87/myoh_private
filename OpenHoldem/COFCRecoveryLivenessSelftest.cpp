//******************************************************************************
// Standalone regression for the DeepOFC non-absorbing recovery contract.
//******************************************************************************

#include "COFCRecoveryLiveness.h"

#include <iostream>

namespace {

bool Expect(bool condition, const char *message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << std::endl;
    return false;
  }
  return true;
}

}  // namespace

int main() {
  bool ok = true;

  // Invalid scrapes are transient events: no release and no stability-budget
  // consumption.  Future valid observations must still be evaluated.
  COFCRecoveryLivenessDecision d = EvaluateOFCRecoveryLiveness(
      false, false, true, 3);
  ok &= Expect(!d.release, "invalid perception must wait");
  ok &= Expect(d.stable_cycles == 3,
      "invalid perception must preserve the stable-cycle counter");
  ok &= Expect(d.reason == kOFCRecoveryWaitInvalidPerception,
      "invalid perception reason mismatch");

  // Any proven Hero-state change releases recovery immediately.
  d = EvaluateOFCRecoveryLiveness(true, true, true, 0);
  ok &= Expect(d.release, "Hero-state change must release immediately");
  ok &= Expect(d.reason == kOFCRecoveryReleaseHeroStateChanged,
      "Hero-state-change reason mismatch");

  // Faults before UI dispatch use a short two-observation debounce.
  d = EvaluateOFCRecoveryLiveness(true, false, false, 0);
  ok &= Expect(!d.release && d.stable_cycles == 1 && d.required_cycles == 2,
      "safe same-state retry must wait one observation");
  d = EvaluateOFCRecoveryLiveness(true, false, false, d.stable_cycles);
  ok &= Expect(d.release && d.reason == kOFCRecoveryReleaseSameStateTimeout,
      "safe same-state retry must release on observation two");

  // Critical regression: after a drag/Confirm may have been sent, an unchanged
  // Hero state is allowed a longer observation window but can NEVER wait
  // forever.  Seven stable valid observations wait; the eighth releases to a
  // fresh plan/retry.  This is the exact class that previously became
  // RUNTIME_BLOCKED / "until a known new hand".
  int stable = 0;
  for (int i = 1; i <= 7; ++i) {
    d = EvaluateOFCRecoveryLiveness(true, false, true, stable);
    ok &= Expect(!d.release,
        "dispatched-action recovery released before bounded debounce expired");
    ok &= Expect(d.required_cycles == 8,
        "dispatched-action recovery must use eight-observation debounce");
    stable = d.stable_cycles;
  }
  d = EvaluateOFCRecoveryLiveness(true, false, true, stable);
  ok &= Expect(d.release,
      "unchanged valid Hero state must not create an absorbing recovery state");
  ok &= Expect(d.stable_cycles == 8,
      "bounded dispatched-action recovery must release on observation eight");
  ok &= Expect(d.reason == kOFCRecoveryReleaseSameStateTimeout,
      "bounded same-state release reason mismatch");

  // A state change during the debounce wins immediately and does not wait for
  // the timeout.
  d = EvaluateOFCRecoveryLiveness(true, true, true, 5);
  ok &= Expect(d.release &&
      d.reason == kOFCRecoveryReleaseHeroStateChanged,
      "mid-debounce Hero-state change must release immediately");

  if (!ok) return 1;
  std::cout
      << "PASS: invalid scrape remains transient" << std::endl
      << "PASS: changed Hero state releases immediately" << std::endl
      << "PASS: pre-dispatch fault retries after 2 stable observations" << std::endl
      << "PASS: post-dispatch same state retries after 8 stable observations" << std::endl
      << "PASS: no absorbing runtime recovery state exists in liveness helper"
      << std::endl;
  return 0;
}
