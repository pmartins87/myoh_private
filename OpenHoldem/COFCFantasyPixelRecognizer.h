//******************************************************************************
// OpenOFC v5.4.3 generic Fantasy pixel-recognition API.
//
// Runtime-facing code uses one Fantasy state whose card count is data (14..17).
// The legacy COFCFantasy15PixelRecognizer remains an implementation detail for
// the already-certified rank/suit banks and compatibility fixtures; no new
// runtime authority should depend on a count-specific Fantasy mode name.
//******************************************************************************

#ifndef INC_COFCFANTASYPIXELRECOGNIZER_H
#define INC_COFCFANTASYPIXELRECOGNIZER_H

#include "COFCFantasy15PixelRecognizer.h"

#include <string>
#include <vector>

// Generic runtime name. The legacy storage type is retained so we do not clone
// calibrated classifier data or silently change its binary contract.
typedef COFCFantasy15PixelCard COFCFantasyPixelCard;

class COFCFantasyPixelRecognizer {
 public:
  static bool RecognizeLooseObjectsUnbound(
      HBITMAP table_bitmap,
      bool upright,
      std::vector<COFCFantasyPixelObject> *objects_left_to_right,
      std::string *error) {
    const std::vector<std::string> no_prior_lineage;
    return COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
      table_bitmap, upright, no_prior_lineage, objects_left_to_right, error);
  }

  static bool RecognizeLooseObjectsBound(
      HBITMAP table_bitmap,
      bool upright,
      const std::vector<std::string> &original_fantasy_cards,
      std::vector<COFCFantasyPixelObject> *objects_left_to_right,
      std::string *error) {
    return COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
      table_bitmap, upright, original_fantasy_cards,
      objects_left_to_right, error);
  }

  static bool RecognizeArrangementSlots(
      HBITMAP table_bitmap,
      const std::vector<RECT> &slots,
      std::vector<bool> *occupied,
      std::vector<COFCFantasyPixelCard> *cards,
      std::string *error) {
    return COFCFantasy15PixelRecognizer::RecognizeArrangementSlots(
      table_bitmap, slots, occupied, cards, error);
  }

  static bool RecognizeArrangementSlotsAgainstExpected(
      HBITMAP table_bitmap,
      const std::vector<RECT> &slots,
      const std::vector<std::string> &expected_physical_cards,
      std::vector<bool> *occupied,
      std::vector<COFCFantasyPixelCard> *cards,
      std::string *error) {
    return COFCFantasy15PixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
      table_bitmap, slots, expected_physical_cards, occupied, cards, error);
  }
};

#endif  // INC_COFCFANTASYPIXELRECOGNIZER_H
