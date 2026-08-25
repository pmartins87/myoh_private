//******************************************************************************
// OpenOFC reversible UNKNOWN-card probe state machine.
//******************************************************************************

#ifndef INC_COFCUNKNOWNCARDPROBE_H
#define INC_COFCUNKNOWNCARDPROBE_H

#include <set>
#include <string>

#include "COFCVisualObservation.h"

class COFCUnknownCardProbe {
 public:
  enum Phase {
    kIdle = 0,
    kAwaitNormalPlacement,
    kAwaitFantasyPlacement,
    kAwaitFantasyClear,
    kComplete,
    kFailed
  };

  COFCUnknownCardProbe();
  void Reset();

  bool BeginNormal(
      const COFCState &state,
      const COFCVisualObservation &observation,
      EOFCRow staging_row,
      const RECT &source_rect,
      std::string *error);
  bool BeginFantasy(
      const COFCVisualObservation &observation,
      EOFCRow staging_row,
      std::string *error);

  // These methods consume only fresh semantic observations. They never send
  // input and are therefore standalone-testable.
  bool ObservePlacement(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int maximum_wait_cycles,
      int *resolved_card,
      std::string *event);
  void MarkFantasyClearSent();
  bool ObserveFantasyClear(
      const COFCVisualObservation &observation,
      int maximum_wait_cycles,
      std::string *event);
  void Fail(const std::string &reason);

  Phase phase() const { return phase_; }
  bool active() const {
    return phase_ == kAwaitNormalPlacement
      || phase_ == kAwaitFantasyPlacement
      || phase_ == kAwaitFantasyClear;
  }
  bool fantasy() const { return fantasy_; }
  EOFCRow staging_row() const { return staging_row_; }
  const RECT &source_rect() const { return source_rect_; }
  int fantasy_card_count() const { return fantasy_card_count_; }
  int resolved_card() const { return resolved_card_; }
  const std::string &failure_reason() const { return failure_reason_; }

 private:
  static void CollectKnown(
      const COFCState &state,
      const COFCVisualObservation &observation,
      std::set<int> *values);
  static void CollectVisualRowKnown(
      const COFCVisualObservation &observation,
      EOFCRow row,
      std::set<int> *values);
  bool ObserveUniqueDelta(
      const COFCState &state,
      const COFCVisualObservation &observation,
      int *resolved_card,
      std::string *event);

  Phase phase_;
  bool fantasy_;
  EOFCRow staging_row_;
  RECT source_rect_;
  int fantasy_card_count_;
  int wait_cycles_;
  int resolved_card_;
  std::set<int> known_before_;
  std::string failure_reason_;
};

#endif  // INC_COFCUNKNOWNCARDPROBE_H
