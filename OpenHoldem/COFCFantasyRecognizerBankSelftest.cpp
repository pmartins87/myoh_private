#include <iostream>

#include "COFCFantasyRecognitionCore.h"
#include "COFCFantasyRecognizerBanks.generated.h"

using namespace std;

static bool Expect(bool condition, const char *message) {
  if (!condition) cerr << "FAIL: " << message << endl;
  return condition;
}

static bool TestAlphabet(
    const char *name,
    const COFCRankTemplate templates[13],
    double max_distance,
    double min_margin) {
  const char expected[14] = "23456789TJQKA";
  for (int i = 0; i < 13; ++i) {
    if (!Expect(templates[i].label == expected[i], "rank alphabet/order mismatch")) return false;
    COFCRecognitionResult result = COFCFantasyRecognitionCore::ClassifyRank(
      templates[i].rows,
      templates,
      13,
      kDeepOFCFanRankAlignmentPixels,
      max_distance,
      min_margin);
    if (!result.accepted || result.label != expected[i] || result.best_distance != 0.0) {
      cerr << "FAIL: " << name << " self-classification rank=" << expected[i]
           << " accepted=" << result.accepted
           << " got=" << result.label
           << " distance=" << result.best_distance
           << " margin=" << result.margin << endl;
      return false;
    }
  }
  return true;
}

int main() {
  if (!Expect(!kDeepOFCRecognizerBanksRuntimeAuthorized,
        "generated replay bank must never claim runtime authority")) return 1;

  if (!TestAlphabet(
        "fan15",
        kDeepOFCFantasy15FanRankTemplates,
        kDeepOFCFanRankMaxDistance,
        kDeepOFCFanRankMinMargin)) return 1;

  // Upright banks share the exact deterministic classifier. Their production
  // thresholds can later be separately tightened by replay evidence; for this
  // data-integrity gate, exact template self-classification must be unambiguous.
  if (!TestAlphabet(
        "upright-large",
        kDeepOFCUprightLargeRankTemplates,
        0.50,
        0.01)) return 1;
  if (!TestAlphabet(
        "upright-small",
        kDeepOFCUprightSmallRankTemplates,
        0.50,
        0.01)) return 1;

  for (int i = 0; i < 4; ++i) {
    const COFCRgbPrototype &prototype = kDeepOFCSuitPrototypes[i];
    COFCRecognitionResult result = COFCFantasyRecognitionCore::ClassifyRgb(
      prototype.r,
      prototype.g,
      prototype.b,
      kDeepOFCSuitPrototypes,
      4,
      kDeepOFCSuitMaxDistance,
      kDeepOFCSuitMinMargin);
    if (!Expect(result.accepted && result.label == prototype.label,
          "suit prototype self-classification failed")) return 1;
  }

  cout << "PASS: DeepOFC generated C++ recognizer banks" << endl;
  return 0;
}
