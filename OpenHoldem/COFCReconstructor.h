//******************************************************************************
//
// DeepOFC stateful raw-observation -> canonical-state reconstructor.
//
// R9 is read-only. This component interprets scraped KKPoker Joker Ultimate
// evidence but never performs any casino action.
//
//******************************************************************************

#ifndef INC_COFCRECONSTRUCTOR_H
#define INC_COFCRECONSTRUCTOR_H

#include <string>

#include "COFCState.h"
#include "COFCVisualObservation.h"

class COFCReconstructor {
 public:
  // Reconstruct one canonical state. `previous` may be NULL only for a normal
  // round-0 attachment. Failure is fail-closed and leaves `out` reset/invalid.
  static bool Reconstruct(
      const COFCVisualObservation &observation,
      const COFCState *previous,
      COFCState *out,
      std::string *error);

  // Deterministic numeric JSON snapshot used by the replay equality gate.
  // Standard cards use OpenHoldem/StdDeck 0..51 and Joker occurrences 52/53.
  static std::string DiagnosticSnapshot(const COFCState &state);
};

#endif INC_COFCRECONSTRUCTOR_H
