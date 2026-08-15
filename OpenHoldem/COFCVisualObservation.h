//******************************************************************************
//
// DeepOFC raw visual observation scaffold.
//
// This layer stores what the KKPoker frame visibly exposes before stateful
// interpretation. In particular, Hero cards drawn over a row may still be
// tentative; a visible Confirm control does not by itself prove Hero is the
// legal acting player.
//
//******************************************************************************

#ifndef INC_COFCVISUALOBSERVATION_H
#define INC_COFCVISUALOBSERVATION_H

#include <windows.h>

#include "COFCState.h"

struct COFCVisualPlayerObservation {
  bool occupied;
  int source_chair;
  bool fantasy;
  bool sitting_out;
  int hidden_incoming_count;
  int hidden_discard_count;
  COFCPlayerBoard visual_board;

  void Reset() {
    occupied = false;
    source_chair = -1;
    fantasy = false;
    sitting_out = false;
    hidden_incoming_count = 0;
    hidden_discard_count = 0;
    board_source_geometry_known = false;
    visual_board.Reset();
  }

  // Reserved for future per-row source geometry if R10 needs to manipulate a
  // tentatively placed card. Strategic state never depends on this UI detail.
  bool board_source_geometry_known;
};

// Ephemeral UI geometry for one currently loose Hero physical card. This is
// deliberately raw-observation metadata, not canonical solver state. Fantasy
// fan cards may reflow after every drag, so source rectangles must be rebuilt
// from each fresh scrape rather than persisted as card "slots".
struct COFCVisualCardSource {
  bool valid;
  int card_value;
  RECT rect;

  void Reset() {
    valid = false;
    card_value = kOFCCardNoCard;
    // Assign fields directly instead of calling SetRectEmpty(). The native
    // COFCReconstructor self-test intentionally links as a tiny standalone
    // console executable without User32; reset semantics do not need a WinAPI
    // dependency merely to zero a POD rectangle.
    rect.left = 0;
    rect.top = 0;
    rect.right = 0;
    rect.bottom = 0;
  }
};

class COFCVisualObservation {
 public:
  COFCVisualObservation() { Reset(); }

  void Reset() {
    valid = false;
    schema_version = kOFCStateSchemaVersion;
    player_count = 0;
    hero_chair = -1;
    dealer_chair = -1;
    acting_chair = -1;
    round_index = -1;
    hero_loose_count = 0;
    hero_discard_tracker_count = 0;
    hero_can_prepare = false;
    confirm_visible = false;
    for (int i = 0; i < kOFCMaxPlayers; ++i) {
      players[i].Reset();
    }
    for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
      hero_loose_cards[i].Clear();
      hero_loose_sources[i].Reset();
    }
    for (int i = 0; i < kOFCMaxDiscards; ++i) {
      hero_discard_tracker[i].Clear();
    }
  }

 public:
  bool valid;
  int schema_version;
  int player_count;
  int hero_chair;
  int dealer_chair;
  int acting_chair;
  int round_index;
  bool hero_can_prepare;
  // Raw UI fact only. Canonical safe Hero confirm additionally requires that
  // the ordered OFC acting chair is Hero.
  bool confirm_visible;

  COFCVisualPlayerObservation players[kOFCMaxPlayers];
  COFCCard hero_loose_cards[kOFCMaxIncomingCards];
  COFCVisualCardSource hero_loose_sources[kOFCMaxIncomingCards];
  int hero_loose_count;
  COFCCard hero_discard_tracker[kOFCMaxDiscards];
  int hero_discard_tracker_count;
};

#endif INC_COFCVISUALOBSERVATION_H
