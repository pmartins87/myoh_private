//******************************************************************************
// OpenOFC v5.6.0 production decision-policy composition.
//******************************************************************************

#ifndef INC_COFCDECISIONPOLICY_H
#define INC_COFCDECISIONPOLICY_H

#include <string>

#include "COFCR4ExactTeacher.h"

struct COFCDecisionPolicyReport {
  bool exact_r4_attempted;
  std::string exact_r4_reason;
  COFCR4ExactTeacherReport exact_r4;

  COFCDecisionPolicyReport();
};

class COFCDecisionPolicy {
 public:
  // The smart deterministic policy remains the total fallback. At normal R4,
  // a complete-information exact teacher may replace it only through its
  // Pareto-safety contract. Teacher unavailability never rejects a legal
  // baseline action.
  static bool Choose(
      const COFCState &state,
      COFCStrategyAction *action,
      COFCDecisionPolicyReport *report,
      std::string *error);
};

#endif  // INC_COFCDECISIONPOLICY_H
