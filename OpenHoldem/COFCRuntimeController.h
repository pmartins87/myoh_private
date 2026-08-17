//******************************************************************************
// DeepOFC FP0 live turn controller.
//******************************************************************************

#ifndef INC_COFCRUNTIMECONTROLLER_H
#define INC_COFCRUNTIMECONTROLLER_H

#include <string>

#include "COFCConfirmVerifier.h"
#include "COFCTurnOrchestrator.h"

class COFCRuntimeController {
 public:
  COFCRuntimeController();

  // One heartbeat. Sends at most one physical input and never retries an
  // unverified drag or Confirm click.
  void Tick(
      const COFCState &state,
      const COFCVisualObservation &observation);

 private:
  enum Phase {
    kIdle,
    kArranging,
    kConfirmSent,
    kBlocked
  };

  void ResetForKnownNewHand(const COFCState &state);
  void Block(const std::string &message);
  bool StartDecision(
      const COFCState &state,
      const COFCVisualObservation &observation);
  bool AdvanceArrangement(
      const COFCState &state,
      const COFCVisualObservation &observation);
  bool SendConfirm(const COFCState &state);
  bool HandlePostConfirm(const COFCState &state);
  bool IsKnownNewHand(const COFCState &state) const;
  static int PendingCount(const COFCState &state);
  static std::string PendingSignature(const COFCState &state);
  static std::string IncomingSignature(const COFCState &state);

 private:
  Phase phase_;
  COFCTurnOrchestrator orchestrator_;
  COFCTurnPlan plan_;
  COFCState confirm_before_;
  int pending_before_drag_;
  std::string pending_signature_before_drag_;
  std::string hand_signature_;
};

#endif  // INC_COFCRUNTIMECONTROLLER_H
