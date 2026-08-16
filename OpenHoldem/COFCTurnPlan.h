//******************************************************************************
//
// DeepOFC R10 solver-action -> physical-turn semantic bridge.
//
// This file contains NO poker strategy and NO mouse geometry. A solver/policy
// supplies one canonical physical-card action; this layer only validates that
// action against the current COFCState and computes the still-needed placement
// delta for the already transactional single-drag executor.
//
//******************************************************************************

#ifndef INC_COFCTURNPLAN_H
#define INC_COFCTURNPLAN_H

#include <string>

#include "COFCState.h"

const int kOFCStrategyActionSchemaVersion = 1;

struct COFCStrategyPlacement {
  int card_value;
  EOFCRow row;

  COFCStrategyPlacement()
    : card_value(kOFCCardNoCard), row(kOFCRowUndefined) {}
};

// Pure strategy output contract. `unused_cards` means cards intentionally left
// loose for KKPoker to discard on Confirm; it does NOT authorize an invented
// discard-to-trash gesture.
struct COFCStrategyAction {
  bool valid;
  int schema_version;
  COFCStrategyPlacement placements[kOFCMaxIncomingCards];
  int placement_count;
  int unused_cards[kOFCMaxIncomingCards];
  int unused_count;

  COFCStrategyAction() { Reset(); }

  void Reset() {
    valid = false;
    schema_version = kOFCStrategyActionSchemaVersion;
    placement_count = 0;
    unused_count = 0;
    for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
      placements[i] = COFCStrategyPlacement();
      unused_cards[i] = kOFCCardNoCard;
    }
  }
};

struct COFCTurnPlan {
  bool valid;

  // Exact canonical state against which the solver action was validated.
  // Runtime orchestration compares fresh states to this binding while ignoring
  // only tentative Hero placement/UI-progress fields. This prevents a stale
  // plan from being reused after any strategy-relevant state drift.
  COFCState decision_state;

  COFCStrategyPlacement target[kOFCMaxIncomingCards];
  int target_count;
  COFCStrategyPlacement already_correct[kOFCMaxIncomingCards];
  int already_correct_count;
  COFCStrategyPlacement to_add[kOFCMaxIncomingCards];
  int to_add_count;
  int unused_cards[kOFCMaxIncomingCards];
  int unused_count;

  COFCTurnPlan() { Reset(); }

  void Reset() {
    valid = false;
    decision_state.Reset();
    target_count = 0;
    already_correct_count = 0;
    to_add_count = 0;
    unused_count = 0;
    for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
      target[i] = COFCStrategyPlacement();
      already_correct[i] = COFCStrategyPlacement();
      to_add[i] = COFCStrategyPlacement();
      unused_cards[i] = kOFCCardNoCard;
    }
  }
};

class COFCTurnPlanBuilder {
 public:
  static bool Build(
      const COFCState &state,
      const COFCStrategyAction &action,
      COFCTurnPlan *out,
      std::string *error);
};

#endif  // INC_COFCTURNPLAN_H
