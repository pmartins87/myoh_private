//******************************************************************************
//
// DeepOFC Fantasy15 real-pixel recognizer.
//
// Recognition-only component. It has no click/drag primitive and no runtime
// authority by itself. The current contract is deliberately narrow:
// KKPoker Joker Ultimate, HU, Hero chair 1, 450x830, initial 15-card Fantasy fan.
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
};

#endif  // INC_COFCFANTASY15PIXELRECOGNIZER_H
