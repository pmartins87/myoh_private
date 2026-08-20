//******************************************************************************
//
// DeepOFC R10 physical-placement planner.
//
// This class deliberately does NOT send mouse input. It validates the current
// canonical OFC state, resolves a card source rectangle to a canonical row drop
// target, and verifies the post-drag pending transition. The R9 hard no-click
// guard remains the only live autoplayer path until the runtime gates advance.
//
//******************************************************************************

#ifndef INC_COFCACTIONPLANNER_H
#define INC_COFCACTIONPLANNER_H

#include <windows.h>
#include <string>

#include "COFCState.h"
#include "COFCVisualObservation.h"

struct COFCUIPlacementStep {
  int card_value;
  EOFCRow row;
  RECT source_rect;
  RECT target_rect;

  COFCUIPlacementStep() : card_value(kOFCCardNoCard), row(kOFCRowUndefined) {
    SetRectEmpty(&source_rect);
    SetRectEmpty(&target_rect);
  }
};

class COFCActionPlanner {
 public:
  // Preferred R10 entry point: resolve the current physical source rectangle
  // directly from the same fresh raw observation that produced `state`.
  // Fantasy can later populate the identical ephemeral source contract after
  // each fan reflow; no strategic "slot identity" is introduced.
  static bool BuildPlacementStepFromObservation(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int card_value,
      EOFCRow row,
      COFCUIPlacementStep *out,
      std::string *error);

  // Lower-level overload retained for unit/sandbox planners that already own a
  // current source rectangle. Production execution should prefer the raw-
  // observation entry point so stale geometry cannot be passed accidentally.
  static bool BuildPlacementStep(
      const COFCState &state,
      int card_value,
      EOFCRow row,
      const RECT &source_rect,
      COFCUIPlacementStep *out,
      std::string *error);

  // Verify that a rescraped state contains the requested physical card as a
  // tentative placement in exactly the requested canonical row. This is the
  // minimum gate before any later drag may be planned/executed.
  static bool VerifyPendingTransition(
      const COFCState &before,
      const COFCState &after,
      int card_value,
      EOFCRow row,
      std::string *error);

 private:
  static bool ResolveLooseSource(
      const COFCVisualObservation &observation,
      int card_value,
      RECT *out,
      std::string *error);
  static bool ResolveDropTarget(
      const COFCState &state, EOFCRow row, RECT *out, std::string *error);
  static int FindIncomingIndex(const COFCState &state, int card_value);
  static bool PendingContains(const COFCState &state, int incoming_index, EOFCRow row);
  static bool IsUsableRect(const RECT &rect);
};

#endif  // INC_COFCACTIONPLANNER_H
