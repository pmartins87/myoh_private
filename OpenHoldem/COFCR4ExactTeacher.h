//******************************************************************************
// OpenOFC v5.6.0 exact normal-R4 teacher.
//******************************************************************************

#ifndef INC_COFCR4EXACTTEACHER_H
#define INC_COFCR4EXACTTEACHER_H

#include <string>

#include "COFCTurnPlan.h"

struct COFCR4ExactTeacherReport {
  bool exact_available;
  bool applied;
  int candidates;
  int legal_candidates;
  int baseline_points;
  int selected_points;
  int baseline_fantasy_cards;
  int selected_fantasy_cards;
  int baseline_royalties;
  int selected_royalties;

  COFCR4ExactTeacherReport();
};

class COFCR4ExactTeacher {
 public:
  // Evaluates every legal discard/placement at normal R4 against all complete,
  // visible opponents.  It replaces `baseline` only when the exact candidate
  // has no lower immediate score and no lower Fantasy tier, with at least one
  // strict improvement.  This Pareto gate introduces no guessed conversion
  // rate between current points and future Fantasy value.
  static bool Improve(
      const COFCState &state,
      const COFCStrategyAction &baseline,
      COFCStrategyAction *selected,
      COFCR4ExactTeacherReport *report,
      std::string *error);
};

#endif  // INC_COFCR4EXACTTEACHER_H
