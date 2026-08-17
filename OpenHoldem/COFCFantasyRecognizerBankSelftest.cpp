#include <iostream>
#include <string>
#include <vector>

#include "COFCFantasyDynamicGeometry.h"
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

  vector<COFCFantasyInkComponent> components;
  vector<COFCFantasyInkComponent> uppers;
  const int xs[4] = {75, 108, 140, 173};
  for (int i = 0; i < 4; ++i) {
    COFCFantasyInkComponent upper(COFCPixelRect(xs[i], 650, xs[i] + 8, 668), 72);
    COFCFantasyInkComponent lower(COFCPixelRect(xs[i] + 1, 679, xs[i] + 9, 691), 38);
    components.push_back(upper);
    components.push_back(lower);
    uppers.push_back(upper);
  }
  components.push_back(COFCFantasyInkComponent(
    COFCPixelRect(300, 650, 310, 668), 70));  // no suit -> reject
  vector<COFCFantasyRankAnchor> paired;
  if (!Expect(COFCFantasyDynamicGeometry::PairRankAnchors(
        components, uppers, &paired) && paired.size() == 4,
        "dynamic rank/suit anchor pairing failed")) return 1;

  vector<COFCFantasyRankAnchor> regular;
  const int regular_xs[6] = {76, 108, 141, 173, 206, 238};
  for (int i = 0; i < 6; ++i) {
    regular.push_back(COFCFantasyRankAnchor(
      COFCPixelRect(regular_xs[i], 650, regular_xs[i] + 8, 668),
      70,
      COFCPixelRect(regular_xs[i], 678, regular_xs[i] + 8, 690)));
  }
  COFCFantasyGridFit fit;
  string geometry_error;
  if (!Expect(COFCFantasyDynamicGeometry::FitRegularGrid(
        regular, &fit, &geometry_error)
        && fit.valid && fit.count == 6
        && fabs(fit.pitch - 32.0) < 1e-9
        && fit.maximum_residual <= 1.0,
        "dynamic regular-grid fit failed")) return 1;

  regular[3].bounds.left += 8;
  regular[3].bounds.right += 8;
  if (!Expect(!COFCFantasyDynamicGeometry::FitRegularGrid(
        regular, &fit, &geometry_error),
        "animation-like irregular grid was not rejected")) return 1;

  vector<string> cards;
  cards.push_back("Ah"); cards.push_back("3c");
  vector<string> original;
  original.push_back("Ah"); original.push_back("3c"); original.push_back("2s");
  if (!Expect(COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(
        cards, &geometry_error), "unique physical cards rejected")) return 1;
  if (!Expect(COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(
        cards, original, &geometry_error), "valid physical lineage rejected")) return 1;
  cards[1] = "5c";
  if (!Expect(!COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(
        cards, original, &geometry_error), "invalid physical lineage accepted")) return 1;

  cout << "PASS: DeepOFC generated C++ recognizer banks and dynamic geometry" << endl;
  return 0;
}
