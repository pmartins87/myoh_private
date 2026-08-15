#include <iostream>
#include <string.h>

#include "COFCFantasyRecognitionCore.h"

using namespace std;

static void Clear(uint16_t rows[kDeepOFCGlyphHeight]) {
  for (int i = 0; i < kDeepOFCGlyphHeight; ++i) rows[i] = 0;
}

static bool Expect(bool condition, const char *message) {
  if (!condition) cerr << "FAIL: " << message << endl;
  return condition;
}

int main() {
  uint16_t a[kDeepOFCGlyphHeight];
  uint16_t shifted[kDeepOFCGlyphHeight];
  Clear(a);
  // A compact glyph deliberately kept away from borders.
  a[7] = 0x0010;
  a[8] = 0x0038;
  a[9] = 0x0054;
  a[10] = 0x0010;
  a[11] = 0x0010;
  COFCFantasyRecognitionCore::TranslateRows(a, 1, 1, shifted);
  if (!Expect(
        COFCFantasyRecognitionCore::BinaryUnionXorDistance(a, a) == 0.0,
        "identity distance must be zero")) return 1;
  if (!Expect(
        COFCFantasyRecognitionCore::AlignedBinaryDistance(a, shifted, 1) == 0.0,
        "alignment must recover one-pixel translated glyph")) return 1;

  COFCRankTemplate templates[2];
  templates[0].label = 'A';
  templates[1].label = 'K';
  for (int y = 0; y < kDeepOFCGlyphHeight; ++y) {
    templates[0].rows[y] = a[y];
    templates[1].rows[y] = 0;
  }
  templates[1].rows[7] = 0x0044;
  templates[1].rows[8] = 0x0048;
  templates[1].rows[9] = 0x0070;
  templates[1].rows[10] = 0x0048;

  COFCRecognitionResult rank = COFCFantasyRecognitionCore::ClassifyRank(
    a, templates, 2, 0, 0.10, 0.10);
  if (!Expect(rank.accepted && rank.label == 'A',
        "exact rank template must be accepted")) return 1;

  // Two different labels with the same shape must fail the margin gate rather
  // than accepting whichever label happens to be first.
  for (int y = 0; y < kDeepOFCGlyphHeight; ++y)
    templates[1].rows[y] = a[y];
  rank = COFCFantasyRecognitionCore::ClassifyRank(
    a, templates, 2, 0, 0.10, 0.10);
  if (!Expect(!rank.accepted && rank.reason == kOFCRecognitionMargin,
        "ambiguous equal-rank shapes must fail margin gate")) return 1;

  uint16_t noise[kDeepOFCGlyphHeight];
  Clear(noise);
  for (int y = 0; y < kDeepOFCGlyphHeight; y += 2) noise[y] = 0xFFFF;
  templates[1].rows[7] = 0x0044;
  rank = COFCFantasyRecognitionCore::ClassifyRank(
    noise, templates, 2, 0, 0.20, 0.01);
  if (!Expect(!rank.accepted && rank.reason == kOFCRecognitionDistance,
        "distant nearest rank must fail distance gate")) return 1;

  const COFCRgbPrototype suits[4] = {
    {'c', 30.0, 148.0, 1.0},
    {'d', 20.0, 97.25, 192.0},
    {'h', 227.0, 11.0, 24.5},
    {'s', 48.0, 48.0, 48.0},
  };
  COFCRecognitionResult suit = COFCFantasyRecognitionCore::ClassifyRgb(
    227.0, 11.0, 24.5, suits, 4, 40.0, 80.0);
  if (!Expect(suit.accepted && suit.label == 'h',
        "exact heart RGB prototype must be accepted")) return 1;

  const COFCRgbPrototype pair[2] = {
    {'c', 0.0, 100.0, 0.0},
    {'d', 100.0, 0.0, 0.0},
  };
  suit = COFCFantasyRecognitionCore::ClassifyRgb(
    50.0, 50.0, 0.0, pair, 2, 200.0, 1.0);
  if (!Expect(!suit.accepted && suit.reason == kOFCRecognitionMargin,
        "equidistant suit feature must fail margin gate")) return 1;

  cout << "PASS: DeepOFC portable Fantasy recognition core" << endl;
  return 0;
}
