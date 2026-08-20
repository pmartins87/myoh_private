//******************************************************************************
//
// DeepOFC Fantasy15 real-pixel recognizer.
//
// Recognition-only component. It has no click/drag primitive and no runtime
// authority by itself. The initial-15 compatibility API now also exposes fresh
// physical-card objects shaped for the dynamic source-geometry pipeline.
//
//******************************************************************************

#ifndef INC_COFCFANTASY15PIXELRECOGNIZER_H
#define INC_COFCFANTASY15PIXELRECOGNIZER_H

#include <Windows.h>
#include <string>
#include <vector>

struct COFCFantasy15PixelCard {
  bool valid;
  int joker_id;  // 0 standard, 1 JK1 orange/red, 2 JK2 gray/black
  char rank;     // 2..9,T,J,Q,K,A for standard cards; 0 for Joker
  char suit;     // h,c,d,s for standard cards; 0 for Joker
  double rank_distance;
  double rank_margin;

  COFCFantasy15PixelCard()
      : valid(false), joker_id(0), rank(0), suit(0),
        rank_distance(0.0), rank_margin(0.0) {}

  std::string PhysicalLabel() const;
};

struct COFCFantasyPixelObject {
  bool valid;
  bool fresh_from_current_bitmap;
  COFCFantasy15PixelCard card;
  RECT source_rect;
  POINT drag_anchor;
  int detected_layout_count;
  double geometry_residual;

  COFCFantasyPixelObject()
      : valid(false), fresh_from_current_bitmap(false),
        detected_layout_count(0), geometry_residual(0.0) {
    source_rect.left = source_rect.top = 0;
    source_rect.right = source_rect.bottom = 0;
    drag_anchor.x = drag_anchor.y = 0;
  }
};

class COFCFantasy15PixelRecognizer {
 public:
  // Verifies the exact frozen quantized model imported from DeepOFC.
  // This is a structural integrity check, not runtime certification.
  static bool VerifyFrozenModel(std::string *error);

  // Recognizes the complete 15-card initial Fantasy fan from a fresh 450x830
  // OpenHoldem table bitmap. Any ambiguous slot, duplicate physical card,
  // unsupported bitmap geometry or extraction failure invalidates the WHOLE fan.
  static bool RecognizeInitialFan(
      HBITMAP table_bitmap,
      std::vector<COFCFantasy15PixelCard> *cards_left_to_right,
      std::string *error);

  // Native object-contract bridge for the supplied initial 15-card geometry.
  // Every returned object is rebuilt from the current bitmap. This does NOT
  // claim dynamic reflow support and does NOT enable scraper/runtime authority.
  static bool RecognizeInitialFanObjects(
      HBITMAP table_bitmap,
      std::vector<COFCFantasyPixelObject> *objects_left_to_right,
      std::string *error);

  // Recognizes the fixed Fantasy arrangement slots. `occupied[i] == false`
  // means that the slot contains no rank/Joker glyph. A visible but ambiguous
  // glyph rejects the complete observation instead of being treated as empty.
  static bool RecognizeArrangementSlots(
      HBITMAP table_bitmap,
      const std::vector<RECT> &slots,
      std::vector<bool> *occupied,
      std::vector<COFCFantasy15PixelCard> *cards,
      std::string *error);

  // Final 13-card arrangement matcher. It constrains the upright glyphs to an
  // exact physical-card set (original Fantasy15 minus the two recognized
  // unused cards), resolving weak T/5 upright glyphs by a minimum-distance
  // one-to-one assignment instead of inventing a duplicate identity.
  static bool RecognizeArrangementSlotsAgainstExpected(
      HBITMAP table_bitmap,
      const std::vector<RECT> &slots,
      const std::vector<std::string> &expected_physical_cards,
      std::vector<bool> *occupied,
      std::vector<COFCFantasy15PixelCard> *cards,
      std::string *error);

  // Rediscovers every currently loose card after a Fantasy drag. `upright`
  // is true only after all 13 arrangement positions are occupied, when the
  // supplied client displays the two unused cards upright instead of fanned.
  static bool RecognizeCurrentLooseObjects(
      HBITMAP table_bitmap,
      bool upright,
      const std::vector<std::string> &original_fantasy_cards,
      std::vector<COFCFantasyPixelObject> *objects_left_to_right,
      std::string *error);

  // Shared upright-card fallback for normal Hero incoming/pending slots.
  static bool RecognizeUprightCard(
      HBITMAP table_bitmap,
      const RECT &card_rect,
      COFCFantasy15PixelCard *card,
      std::string *error);

  // Detects the persistent colored pineapple marker KKPoker draws in the
  // otherwise blank upper-right corner of a gold substituted Joker card.
  static bool DetectPersistentJoker(
      HBITMAP table_bitmap,
      const RECT &card_rect,
      int *joker_id,
      std::string *error);
};

#endif  // INC_COFCFANTASY15PIXELRECOGNIZER_H
