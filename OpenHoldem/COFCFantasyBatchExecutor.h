//******************************************************************************
// OpenOFC Fantasy row-batch click executor.
//******************************************************************************

#ifndef INC_COFCFANTASYBATCHEXECUTOR_H
#define INC_COFCFANTASYBATCHEXECUTOR_H

#include <string>

#include "COFCTurnPlan.h"
#include "COFCVisualObservation.h"

class COFCFantasyBatchExecutor {
 public:
  COFCFantasyBatchExecutor();

  void Reset();
  bool active() const { return phase_ != kIdle || plan_.valid; }

  // Starts/continues a Fantasy 3/5/5 arrangement using the measured KKPoker
  // interaction: select all cards for one empty row, then click that row's
  // yellow check button. A row that contains the wrong set is cleared through
  // the same contextual button (red X) and rebuilt from fresh loose geometry.
  bool Start(
      const COFCState &state,
      const COFCVisualObservation &observation,
      const COFCTurnPlan &plan,
      bool *arrangement_complete,
      std::string *error);

  // Called only after a fresh scrape. Verifies the prior row transaction before
  // any later click batch is allowed. At most one rebuild retry is permitted.
  bool AdvanceAfterFreshScrape(
      const COFCState &state,
      const COFCVisualObservation &observation,
      bool *arrangement_complete,
      std::string *error);

 private:
  enum Phase {
    kIdle,
    kAwaitRowCommit,
    kAwaitRowClear,
    kBlocked
  };

  bool StartNextStableAction(
      const COFCState &state,
      const COFCVisualObservation &observation,
      bool *arrangement_complete,
      std::string *error);
  bool SendBuildRowBatch(
      const COFCState &state,
      const COFCVisualObservation &observation,
      EOFCRow row,
      std::string *error);
  bool SendClearRow(EOFCRow row, bool consumes_retry, std::string *error);
  bool RowMatchesTarget(const COFCState &state, EOFCRow row) const;
  bool RowEmpty(const COFCState &state, EOFCRow row) const;
  bool ResolveLooseSource(
      const COFCVisualObservation &observation,
      int card_value,
      RECT *out,
      std::string *error) const;
  bool ResolveRowActionRect(EOFCRow row, RECT *out, std::string *error) const;
  bool Fail(std::string *error, const std::string &message);

 private:
  Phase phase_;
  COFCTurnPlan plan_;
  EOFCRow waiting_row_;
  int wait_cycles_;
  int retry_count_[3];
  bool clear_consumes_retry_;
};

#endif  // INC_COFCFANTASYBATCHEXECUTOR_H
