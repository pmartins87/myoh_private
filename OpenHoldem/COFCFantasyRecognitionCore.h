//******************************************************************************
//
// DeepOFC portable recognition core.
//
// This header contains NO live table authority and NO GDI/tablemap access. It
// only implements the deterministic distance/margin classifiers shared by the
// future native KKPoker Fantasy pixel path and standalone CI self-tests.
//
//******************************************************************************

#ifndef INC_COFCFANTASYRECOGNITIONCORE_H
#define INC_COFCFANTASYRECOGNITIONCORE_H

#include <float.h>
#include <math.h>
#include <stdint.h>

static const int kDeepOFCGlyphWidth = 16;
static const int kDeepOFCGlyphHeight = 24;

struct COFCRankTemplate {
  char label;
  uint16_t rows[kDeepOFCGlyphHeight];
};

struct COFCRgbPrototype {
  char label;
  double r;
  double g;
  double b;
};

enum COFCRecognitionRejectReason {
  kOFCRecognitionAccepted = 0,
  kOFCRecognitionNoTemplates = 1,
  kOFCRecognitionDistance = 2,
  kOFCRecognitionMargin = 3,
};

struct COFCRecognitionResult {
  bool accepted;
  char label;
  double best_distance;
  double second_distance;
  double margin;
  COFCRecognitionRejectReason reason;

  void Reset() {
    accepted = false;
    label = 0;
    best_distance = DBL_MAX;
    second_distance = DBL_MAX;
    margin = 0.0;
    reason = kOFCRecognitionNoTemplates;
  }
};

class COFCFantasyRecognitionCore {
 public:
  static int Popcount16(uint16_t value) {
    int count = 0;
    while (value != 0) {
      value = static_cast<uint16_t>(value & static_cast<uint16_t>(value - 1));
      ++count;
    }
    return count;
  }

  static double BinaryUnionXorDistance(
      const uint16_t left[kDeepOFCGlyphHeight],
      const uint16_t right[kDeepOFCGlyphHeight]) {
    int xor_pixels = 0;
    int union_pixels = 0;
    for (int y = 0; y < kDeepOFCGlyphHeight; ++y) {
      xor_pixels += Popcount16(static_cast<uint16_t>(left[y] ^ right[y]));
      union_pixels += Popcount16(static_cast<uint16_t>(left[y] | right[y]));
    }
    if (union_pixels == 0) return 0.0;
    return static_cast<double>(xor_pixels) / static_cast<double>(union_pixels);
  }

  static void TranslateRows(
      const uint16_t source[kDeepOFCGlyphHeight],
      int dx,
      int dy,
      uint16_t out[kDeepOFCGlyphHeight]) {
    for (int y = 0; y < kDeepOFCGlyphHeight; ++y) out[y] = 0;
    for (int source_y = 0; source_y < kDeepOFCGlyphHeight; ++source_y) {
      const int target_y = source_y + dy;
      if (target_y < 0 || target_y >= kDeepOFCGlyphHeight) continue;
      if (dx >= 0) {
        if (dx >= kDeepOFCGlyphWidth) continue;
        out[target_y] = static_cast<uint16_t>(source[source_y] << dx);
      } else {
        if (-dx >= kDeepOFCGlyphWidth) continue;
        out[target_y] = static_cast<uint16_t>(source[source_y] >> (-dx));
      }
    }
  }

  static double AlignedBinaryDistance(
      const uint16_t observed[kDeepOFCGlyphHeight],
      const uint16_t reference[kDeepOFCGlyphHeight],
      int max_shift) {
    if (max_shift < 0) return DBL_MAX;
    double best = DBL_MAX;
    uint16_t shifted[kDeepOFCGlyphHeight];
    for (int dy = -max_shift; dy <= max_shift; ++dy) {
      for (int dx = -max_shift; dx <= max_shift; ++dx) {
        TranslateRows(reference, dx, dy, shifted);
        const double distance = BinaryUnionXorDistance(observed, shifted);
        if (distance < best) best = distance;
      }
    }
    return best;
  }

  static COFCRecognitionResult ClassifyRank(
      const uint16_t observed[kDeepOFCGlyphHeight],
      const COFCRankTemplate *templates,
      int template_count,
      int max_shift,
      double max_distance,
      double min_margin) {
    COFCRecognitionResult result;
    result.Reset();
    if (templates == NULL || template_count <= 0) return result;

    // Multiple exemplars for one rank collapse to that rank's best distance.
    // ASCII rank labels are sufficient for 2..9,T,J,Q,K,A.
    double per_label[256];
    bool present[256];
    for (int i = 0; i < 256; ++i) {
      per_label[i] = DBL_MAX;
      present[i] = false;
    }
    for (int i = 0; i < template_count; ++i) {
      const unsigned char label = static_cast<unsigned char>(templates[i].label);
      const double distance = AlignedBinaryDistance(
        observed, templates[i].rows, max_shift);
      present[label] = true;
      if (distance < per_label[label]) per_label[label] = distance;
    }

    char best_label = 0;
    double best = DBL_MAX;
    double second = DBL_MAX;
    for (int i = 0; i < 256; ++i) {
      if (!present[i]) continue;
      const double distance = per_label[i];
      if (distance < best || (distance == best && i < static_cast<unsigned char>(best_label))) {
        second = best;
        best = distance;
        best_label = static_cast<char>(i);
      } else if (distance < second) {
        second = distance;
      }
    }

    result.label = best_label;
    result.best_distance = best;
    result.second_distance = second;
    result.margin = (second == DBL_MAX) ? DBL_MAX : (second - best);
    if (best > max_distance) {
      result.label = 0;
      result.reason = kOFCRecognitionDistance;
      return result;
    }
    if (result.margin < min_margin) {
      result.label = 0;
      result.reason = kOFCRecognitionMargin;
      return result;
    }
    result.accepted = true;
    result.reason = kOFCRecognitionAccepted;
    return result;
  }

  static double RgbDistance(
      double r,
      double g,
      double b,
      const COFCRgbPrototype &prototype) {
    const double dr = r - prototype.r;
    const double dg = g - prototype.g;
    const double db = b - prototype.b;
    return sqrt(dr * dr + dg * dg + db * db);
  }

  static COFCRecognitionResult ClassifyRgb(
      double r,
      double g,
      double b,
      const COFCRgbPrototype *prototypes,
      int prototype_count,
      double max_distance,
      double min_margin) {
    COFCRecognitionResult result;
    result.Reset();
    if (prototypes == NULL || prototype_count <= 0) return result;

    char best_label = 0;
    double best = DBL_MAX;
    double second = DBL_MAX;
    for (int i = 0; i < prototype_count; ++i) {
      const double distance = RgbDistance(r, g, b, prototypes[i]);
      const unsigned char label = static_cast<unsigned char>(prototypes[i].label);
      if (distance < best
          || (distance == best && label < static_cast<unsigned char>(best_label))) {
        second = best;
        best = distance;
        best_label = prototypes[i].label;
      } else if (distance < second) {
        second = distance;
      }
    }

    result.label = best_label;
    result.best_distance = best;
    result.second_distance = second;
    result.margin = (second == DBL_MAX) ? DBL_MAX : (second - best);
    if (best > max_distance) {
      result.label = 0;
      result.reason = kOFCRecognitionDistance;
      return result;
    }
    if (result.margin < min_margin) {
      result.label = 0;
      result.reason = kOFCRecognitionMargin;
      return result;
    }
    result.accepted = true;
    result.reason = kOFCRecognitionAccepted;
    return result;
  }
};

#endif  // INC_COFCFANTASYRECOGNITIONCORE_H
