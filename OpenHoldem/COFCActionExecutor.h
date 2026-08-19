//******************************************************************************
//
// DeepOFC R10 single-drag transaction executor.
//
// Runtime transaction boundary: one physical drag, then mandatory fresh-scrape
// canonical verification before any second drag is permitted.
//
//******************************************************************************

#ifndef INC_COFCACTIONEXECUTOR_H
#define INC_COFCACTIONEXECUTOR_H

#include <string>

#include "COFCActionPlanner.h"

class COFCActionExecutor {
 public:
  COFCActionExecutor();

  void ResetForKnownNewHand();

  bool BeginPlacement(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int card_value,
      EOFCRow row,
      int duration_ms,
      std::string *error);

  bool VerifyAfterFreshScrape(
      const COFCState &after,
      std::string *error);

  bool awaiting_verification() const { return awaiting_verification_; }
  bool blocked() const { return blocked_; }

 private:
  bool RuntimeExecutionExplicitlyEnabled(std::string *error) const;
  bool FailAndBlock(std::string *error, const std::string &message);

 private:
  bool awaiting_verification_;
  bool blocked_;
  int card_value_;
  EOFCRow row_;
  COFCState before_;
};

#endif  // INC_COFCACTIONEXECUTOR_H
