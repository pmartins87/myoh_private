//******************************************************************************
// OpenOFC v5.7.0 production decision-policy composition.
//******************************************************************************

#ifndef INC_COFCDECISIONPOLICY_H
#define INC_COFCDECISIONPOLICY_H

#include <string>

#include "COFCFantasyExactSolver.h"
#include "COFCR4ExactTeacher.h"

struct COFCDecisionPolicyReport {
  bool exact_fantasy_attempted;
  std::string exact_fantasy_reason;
  COFCFantasyExactReport exact_fantasy;
  bool exact_r4_attempted;
  std::string exact_r4_reason;
  COFCR4ExactTeacherReport exact_r4;

  COFCDecisionPolicyReport();
};

class COFCDecisionPolicy {
 public:
  // The smart deterministic policy remains the total fallback. Fantasy 14..17
  // is exhaustively searched and may be replaced through universal dominance;
  // normal R4 keeps its complete-opponent Pareto contract. Exact-layer
  // unavailability never rejects a legal baseline action.
  static bool Choose(
      const COFCState &state,
      COFCStrategyAction *action,
      COFCDecisionPolicyReport *report,
      std::string *error);
};

#endif  // INC_COFCDECISIONPOLICY_H
