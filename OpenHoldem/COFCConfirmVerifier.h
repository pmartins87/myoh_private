//******************************************************************************
//
// DeepOFC R10 normal-play Confirm semantic verifier.
//
// This component does NOT click Confirm. It only proves, from a fresh canonical
// state, that a separately attempted normal-round Confirm was accepted.
// Fantasy and final-round teardown are deliberately separate future routes.
//
//******************************************************************************

#ifndef INC_COFCCONFIRMVERIFIER_H
#define INC_COFCCONFIRMVERIFIER_H

#include <string>

#include "COFCTurnPlan.h"


enum EOFCConfirmTransition {
  kOFCConfirmTransitionUndefined = 0,
  kOFCConfirmSameRoundHandoff = 1,
  kOFCConfirmNextRoundCommitted = 2,
};

struct COFCConfirmReceipt {
  bool accepted;
  EOFCConfirmTransition transition;
  int previous_round;
  int observed_round;

  COFCConfirmReceipt()
    : accepted(false),
      transition(kOFCConfirmTransitionUndefined),
      previous_round(-1),
      observed_round(-1) {}
};

class COFCConfirmVerifier {
 public:
  static bool VerifyNormalTransition(
      const COFCState &before,
      const COFCState &after,
      const COFCTurnPlan &plan,
      COFCConfirmReceipt *receipt,
      std::string *error);
};

#endif  // INC_COFCCONFIRMVERIFIER_H
