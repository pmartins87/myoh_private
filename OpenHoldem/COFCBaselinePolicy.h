//******************************************************************************
// DeepOFC FP0 deterministic legal policy.
//******************************************************************************

#ifndef INC_COFCBASELINEPOLICY_H
#define INC_COFCBASELINEPOLICY_H

#include <string>

#include "COFCTurnPlan.h"

class COFCBaselinePolicy {
 public:
  // Produces a deterministic physical-card action. Fantasy15 is solved by an
  // exhaustive valid-board search. Normal play enumerates every legal current
  // placement/discard action and uses an exact completed-board foul gate plus
  // a conservative partial-board heuristic.
  static bool Choose(
      const COFCState &state,
      COFCStrategyAction *action,
      std::string *error);
};

#endif  // INC_COFCBASELINEPOLICY_H
