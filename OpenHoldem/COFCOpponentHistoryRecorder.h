//******************************************************************************
// OpenOFC opponent hand-history recorder.
//
// Runtime responsibility is deliberately narrow:
//   * keep the latest complete public board snapshot for each normal OFC round;
//   * remember the public Hero board visible at the same instant;
//   * on the opponent-discard face-up edge, preserve the exact evidence frame;
//   * emit one durable JSONL hand envelope for later idempotent SQLite import.
//
// Opponent discard recognition is passive evidence only. It must never veto
// gameplay or canonical state reconstruction.
//******************************************************************************

#ifndef INC_COFCOPPONENTHISTORYRECORDER_H
#define INC_COFCOPPONENTHISTORYRECORDER_H

#include <string>

#include "COFCState.h"
#include "COFCVisualObservation.h"

class COFCOpponentHistoryRecorder {
 public:
  COFCOpponentHistoryRecorder();

  void ObserveCanonical(
    const COFCState &state,
    const COFCVisualObservation &observation);

  // May be called even when the current result bitmap is not canonically
  // reconstructable. The last canonical state still contains the accumulated
  // public-board lineage, while the raw observation contains reveal evidence.
  void ObserveTerminalReveal(
    const COFCVisualObservation &observation,
    const COFCState *last_canonical_state);

  void Reset();

 private:
  struct RoundSnapshot {
    bool seen;
    int opponent_known;
    int hero_known;
    COFCPlayerBoard opponent_board;
    COFCPlayerBoard hero_board;

    void Reset() {
      seen = false;
      opponent_known = 0;
      hero_known = 0;
      opponent_board.Reset();
      hero_board.Reset();
    }
  };

  void StartHand(
    const COFCState &state,
    const COFCVisualObservation &observation);
  void UpdateRoundSnapshot(const COFCState &state);
  void UpdateIdentity(const COFCVisualObservation &observation);
  void MergeReveal(const COFCVisualObservation &observation);
  void Flush(const char *status, const char *reason, bool terminal_record);
  bool SaveEvidenceBitmap(std::string *relative_path);
  std::string MakeHandId() const;

 private:
  bool hand_active_;
  bool reveal_edge_seen_;
  bool partial_written_;
  bool flushed_;
  unsigned long hand_sequence_;
  unsigned long result_frame_sequence_;
  int hero_chair_;
  int opponent_chair_;
  int dealer_chair_;
  int highest_round_seen_;
  int reveal_mask_;
  int reveal_count_;
  bool hero_fantasy_result_;
  bool opponent_fantasy_result_;
  std::string hand_id_;
  std::string opponent_raw_name_;
  std::string result_frame_relative_path_;
  COFCCard revealed_discards_[kOFCMaxDiscards];
  RoundSnapshot rounds_[5];
};

#endif  // INC_COFCOPPONENTHISTORYRECORDER_H
