//******************************************************************************
// OpenOFC v5.4.3H Fantasy Confirm dispatch fence.
//
// Pure state machine: no mouse, TableMap, scraper, or policy dependencies.
//******************************************************************************

#ifndef INC_COFCFANTASYCONFIRMFENCE_H
#define INC_COFCFANTASYCONFIRMFENCE_H

#include <string>

class COFCFantasyConfirmFence {
 public:
  enum AckDecision {
    kAckWait,
    kAckTimeoutReacquire
  };

  COFCFantasyConfirmFence() { ResetForNewHand(); }

  void ResetForNewHand() {
    dispatched_fingerprint_.clear();
    ack_wait_cycles_ = 0;
  }

  bool HasAnyDispatch() const {
    return !dispatched_fingerprint_.empty();
  }

  bool HasDispatched(const std::string &fingerprint) const {
    return !fingerprint.empty()
      && !dispatched_fingerprint_.empty()
      && dispatched_fingerprint_ == fingerprint;
  }

  // Once the mouse DLL has been invoked for a Fantasy Confirm, no second
  // physical Confirm is allowed in that Fantasy hand. The fingerprint is kept
  // for diagnostics/correlation, while the one-shot rule is deal-wide.
  bool CanDispatch(const std::string &fingerprint) const {
    return !fingerprint.empty() && !HasAnyDispatch();
  }

  void MarkDispatched(const std::string &fingerprint) {
    dispatched_fingerprint_ = fingerprint;
    ack_wait_cycles_ = 0;
  }

  AckDecision ObserveUnchangedAfterDispatch(int timeout_cycles) {
    if (timeout_cycles < 1) timeout_cycles = 1;
    ++ack_wait_cycles_;
    if (ack_wait_cycles_ >= timeout_cycles)
      return kAckTimeoutReacquire;
    return kAckWait;
  }

  void ObserveChangedState() {
    ack_wait_cycles_ = 0;
  }

  int ack_wait_cycles() const { return ack_wait_cycles_; }
  const std::string &dispatched_fingerprint() const {
    return dispatched_fingerprint_;
  }

 private:
  std::string dispatched_fingerprint_;
  int ack_wait_cycles_;
};

#endif  // INC_COFCFANTASYCONFIRMFENCE_H
