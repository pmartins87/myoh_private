//******************************************************************************
//
// DeepOFC R10 multi-placement turn orchestrator.
//
// NOT wired into live CAutoplayer. This composes the already validated fixed
// solver turn plan with the single-drag transactional executor. Exactly one
// physical mutation may be outstanding; every next placement requires a fresh
// canonical scrape that verifies the preceding drag first.
//
//******************************************************************************

#ifndef INC_COFCTURNORCHESTRATOR_H
#define INC_COFCTURNORCHESTRATOR_H

#include <string>

#include "COFCActionExecutor.h"
#include "COFCTurnPlan.h"

class COFCTurnOrchestrator {
 public:
  COFCTurnOrchestrator();

  void ResetForKnownNewHand();

  // Starts a fixed solver turn. May send at most one drag. If all target cards
  // are already correctly pending, no drag is sent and the output flags expose
  // whether the client is ready for a separately verified Confirm transaction.
  bool StartTurn(
      const COFCState &state,
      const COFCVisualObservation &observation,
      const COFCTurnPlan &plan,
      int duration_ms,
      bool *placements_complete,
      bool *ready_for_confirm,
      std::string *error);

  // Called only after a fresh raw->canonical scrape. It first verifies any
  // outstanding drag, revalidates the fixed strategic decision, then may send
  // at most one next drag from this same fresh observation.
  bool AdvanceAfterFreshScrape(
      const COFCState &fresh_state,
      const COFCVisualObservation &fresh_observation,
      int duration_ms,
      bool *placements_complete,
      bool *ready_for_confirm,
      std::string *error);

  bool active() const { return active_; }
  bool blocked() const { return blocked_ || placement_executor_.blocked(); }
  bool awaiting_drag_verification() const {
    return placement_executor_.awaiting_verification();
  }

 private:
  bool FailAndBlock(std::string *error, const std::string &message);
  bool SameStrategicDecision(
      const COFCState &a,
      const COFCState &b,
      std::string *error) const;
  bool ValidateProgress(
      const COFCState &state,
      bool *placements_complete,
      bool *ready_for_confirm,
      COFCStrategyPlacement *next,
      bool *has_next,
      std::string *error) const;
  bool BeginNextPlacement(
      const COFCState &state,
      const COFCVisualObservation &observation,
      const COFCStrategyPlacement &next,
      int duration_ms,
      bool starting_turn,
      std::string *error);

 private:
  bool active_;
  bool blocked_;
  COFCState baseline_;
  COFCTurnPlan plan_;
  COFCActionExecutor placement_executor_;
};

#endif  // INC_COFCTURNORCHESTRATOR_H
