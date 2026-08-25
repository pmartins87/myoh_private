//******************************************************************************
// OpenOFC v5.7.0 exact Fantasy 14..17 search kernel.
//******************************************************************************

#ifndef INC_COFCFANTASYEXACTSOLVER_H
#define INC_COFCFANTASYEXACTSOLVER_H

#include <string>

#include "COFCExactEvaluator.h"
#include "COFCTurnPlan.h"

struct COFCFantasyExactReport {
  bool exact_available;
  bool applied;
  int incoming_count;
  unsigned long long mask_pairs;
  unsigned long long legal_boards;
  unsigned long long universal_improvements;
  int baseline_royalties;
  int selected_royalties;
  bool baseline_refantasy;
  bool selected_refantasy;
  COFCExactHandRank baseline_rows[3];
  COFCExactHandRank selected_rows[3];

  COFCFantasyExactReport();
};

class COFCFantasyExactSolver {
 public:
  // Exhaustively searches every ordered bottom/middle partition for Fantasy
  // 14..17 and uses an admissible frontier to remove only top choices that are
  // provably dominated for the same remaining cards. Before a calibrated
  // hidden-opponent and
  // continuation value model exists, production authority is deliberately
  // restricted to universal dominance: every row is at least as strong,
  // royalties are no lower, re-Fantasy is not lost, and one dimension is
  // strictly better.  Therefore the replacement is independent of guessed EV
  // weights and of the temporarily occluded opponent board.
  static bool ImproveUniversally(
      const COFCState &state,
      const COFCStrategyAction &baseline,
      COFCStrategyAction *selected,
      COFCFantasyExactReport *report,
      std::string *error);
};

#endif  // INC_COFCFANTASYEXACTSOLVER_H
