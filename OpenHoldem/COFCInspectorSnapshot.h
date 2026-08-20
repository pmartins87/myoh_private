//******************************************************************************
// OpenOFC canonical inspector snapshot.
//
// Read-only presentation helper for the OFC runtime. It exposes exactly what
// the scraper/reconstructor believe about the table without evaluating any
// Hold'em symbol engine. The compact snapshot is intended for the status bar;
// the full snapshot is emitted only when the canonical/visual state changes so
// a diagnostic run can prove every visible row, incoming card and discard.
//******************************************************************************

#ifndef INC_COFCINSPECTORSNAPSHOT_H
#define INC_COFCINSPECTORSNAPSHOT_H

#include "COFCState.h"
#include "COFCVisualObservation.h"
#include "..\pokereval\include\deck_std.h"

class COFCInspectorSnapshot {
 public:
  static CString CardText(int value) {
    if (value == kOFCCardNoCard) return "--";
    if (value == kOFCCardBack) return "BACK";
    if (value == kOFCCardUnknown) return "?";
    if (value == kOFCCardJoker1) return "JK1";
    if (value == kOFCCardJoker2) return "JK2";
    if (value < 0 || value > 51) return "INVALID";
    static const char ranks[] = "23456789TJQKA";
    static const char suits[] = "cdhs";
    CString out;
    out.Format("%c%c", ranks[StdDeck_RANK(value)], suits[StdDeck_SUIT(value)]);
    return out;
  }

  static CString CardsText(const COFCCard *cards, int count) {
    CString out = "[";
    for (int i = 0; i < count; ++i) {
      if (i != 0) out += ",";
      out += CardText(cards[i].value);
    }
    out += "]";
    return out;
  }

  static CString BoardText(const COFCPlayerBoard &board) {
    CString out;
    out.Format("T%s M%s B%s",
      CardsText(board.top, kOFCTopCards).GetString(),
      CardsText(board.middle, kOFCMiddleCards).GetString(),
      CardsText(board.bottom, kOFCBottomCards).GetString());
    return out;
  }

  static CString Compact(const COFCVisualObservation *raw,
      const COFCState *state, int contract) {
    CString out;
    const char *raw_text = raw == NULL ? "WAIT" : (raw->valid ? "OK" : "REJECT");
    const char *state_text = state == NULL ? "WAIT" : (state->valid ? "OK" : "REJECT");
    if (state == NULL || !state->valid) {
      out.Format("TMv%d | READ=%s STATE=%s", contract, raw_text, state_text);
      return out;
    }
    out.Format("TMv%d | READ=%s STATE=%s | P%d H%d A%d D%d R%d | IN%d DISC%d",
      contract, raw_text, state_text, state->player_count, state->hero_chair,
      state->acting_chair, state->dealer_chair, state->round_index,
      state->hero_incoming_count, state->hero_discard_count);
    return out;
  }

  static CString Full(const COFCVisualObservation *raw,
      const COFCState *state, int contract) {
    CString out = Compact(raw, state, contract);
    if (state == NULL) return out;

    for (int p = 0; p < state->player_count && p < kOFCMaxPlayers; ++p) {
      CString player;
      player.Format(" | P%d{%s fantasy=%d hidden_in=%d hidden_disc=%d}",
        p, BoardText(state->players[p].board).GetString(),
        state->players[p].fantasy ? 1 : 0,
        state->players[p].hidden_incoming_count,
        state->players[p].hidden_discard_count);
      out += player;
    }

    CString incoming;
    incoming.Format(" | IN=%s",
      CardsText(state->hero_incoming, state->hero_incoming_count).GetString());
    out += incoming;
    CString discards;
    discards.Format(" | DISC=%s",
      CardsText(state->hero_discards, state->hero_discard_count).GetString());
    out += discards;

    if (raw != NULL) {
      CString raw_tail;
      raw_tail.Format(" | RAW{prepare=%d confirm=%d loose=%d tracker=%d}",
        raw->hero_can_prepare ? 1 : 0, raw->confirm_visible ? 1 : 0,
        raw->hero_loose_count, raw->hero_discard_tracker_count);
      out += raw_tail;
    }
    return out;
  }
};

#endif  // INC_COFCINSPECTORSNAPSHOT_H
