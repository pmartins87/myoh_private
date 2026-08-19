//******************************************************************************
//
// DeepOFC portable dynamic Fantasy geometry kernel.
//
// No GDI, tablemap, scraper, mouse, or runtime authority lives here. The same
// fail-closed geometry/physical-lineage contract is shared by native replay
// tests and the future HBITMAP detector.
//
//******************************************************************************

#ifndef INC_COFCFANTASYDYNAMICGEOMETRY_H
#define INC_COFCFANTASYDYNAMICGEOMETRY_H

#include <algorithm>
#include <cmath>
#include <set>
#include <string>
#include <vector>

struct COFCPixelRect {
  int left;
  int top;
  int right;
  int bottom;

  COFCPixelRect() : left(0), top(0), right(0), bottom(0) {}
  COFCPixelRect(int l, int t, int r, int b)
      : left(l), top(t), right(r), bottom(b) {}

  int Width() const { return right - left; }
  int Height() const { return bottom - top; }
  double CenterX() const { return (left + right) / 2.0; }
  double CenterY() const { return (top + bottom) / 2.0; }
  bool Valid() const { return right > left && bottom > top; }
};

struct COFCFantasyInkComponent {
  COFCPixelRect bounds;
  int area;

  COFCFantasyInkComponent() : area(0) {}
  COFCFantasyInkComponent(const COFCPixelRect &rect, int pixel_area)
      : bounds(rect), area(pixel_area) {}
};

struct COFCFantasyRankAnchor {
  COFCPixelRect bounds;
  int area;
  COFCPixelRect suit_bounds;

  COFCFantasyRankAnchor() : area(0) {}
  COFCFantasyRankAnchor(
      const COFCPixelRect &rank_rect,
      int pixel_area,
      const COFCPixelRect &suit_rect)
      : bounds(rank_rect), area(pixel_area), suit_bounds(suit_rect) {}

  double CenterX() const { return bounds.CenterX(); }
  double CenterY() const { return bounds.CenterY(); }
};

struct COFCFantasyGridFit {
  bool valid;
  int count;
  double center;
  double pitch;
  double maximum_residual;

  COFCFantasyGridFit()
      : valid(false), count(0), center(0.0), pitch(0.0),
        maximum_residual(0.0) {}
};

class COFCFantasyDynamicGeometry {
 public:
  static double Median(std::vector<double> values) {
    if (values.empty()) return 0.0;
    std::sort(values.begin(), values.end());
    const size_t middle = values.size() / 2;
    if ((values.size() % 2) != 0) return values[middle];
    return (values[middle - 1] + values[middle]) / 2.0;
  }

  static bool PairRankAnchors(
      const std::vector<COFCFantasyInkComponent> &components,
      const std::vector<COFCFantasyInkComponent> &eligible_upper_components,
      std::vector<COFCFantasyRankAnchor> *anchors) {
    if (anchors == NULL) return false;
    anchors->clear();
    std::vector<COFCFantasyRankAnchor> candidates;
    for (size_t i = 0; i < eligible_upper_components.size(); ++i) {
      const COFCFantasyInkComponent &upper = eligible_upper_components[i];
      if (upper.area < 20 || upper.area > 350
          || upper.bounds.Width() < 3 || upper.bounds.Width() > 30
          || upper.bounds.Height() < 10 || upper.bounds.Height() > 36
          || upper.bounds.CenterY() > 696.0) {
        continue;
      }

      int best_lower = -1;
      double best_dy = 1e100;
      double best_dx = 1e100;
      int best_area = -1;
      for (size_t j = 0; j < components.size(); ++j) {
        const COFCFantasyInkComponent &lower = components[j];
        const double dy = lower.bounds.CenterY() - upper.bounds.CenterY();
        const double dx = std::fabs(
          lower.bounds.CenterX() - upper.bounds.CenterX());
        if (dy < 13.0 || dy > 42.0 || dx > 8.0) continue;
        if (dy < best_dy
            || (dy == best_dy && dx < best_dx)
            || (dy == best_dy && dx == best_dx && lower.area > best_area)) {
          best_lower = static_cast<int>(j);
          best_dy = dy;
          best_dx = dx;
          best_area = lower.area;
        }
      }
      if (best_lower >= 0) {
        candidates.push_back(COFCFantasyRankAnchor(
          upper.bounds, upper.area, components[best_lower].bounds));
      }
    }

    std::sort(candidates.begin(), candidates.end(), StrongerAnchorFirst);
    for (size_t i = 0; i < candidates.size(); ++i) {
      bool suppressed = false;
      for (size_t j = 0; j < anchors->size(); ++j) {
        if (std::fabs(candidates[i].CenterX() - (*anchors)[j].CenterX()) < 12.0) {
          suppressed = true;
          break;
        }
      }
      if (!suppressed) anchors->push_back(candidates[i]);
    }
    std::sort(anchors->begin(), anchors->end(), AnchorLeftToRight);
    return !anchors->empty();
  }

  static bool FitRegularGrid(
      const std::vector<COFCFantasyRankAnchor> &anchors,
      COFCFantasyGridFit *fit,
      std::string *error,
      double minimum_pitch = 24.0,
      double maximum_pitch = 42.0,
      double allowed_residual = 3.5) {
    if (fit == NULL) return Fail(error, "dynamic Fantasy grid output is null");
    *fit = COFCFantasyGridFit();
    if (anchors.size() < 2) {
      return Fail(error, "dynamic Fantasy grid requires at least two anchors");
    }
    std::vector<double> centers;
    for (size_t i = 0; i < anchors.size(); ++i) {
      centers.push_back(anchors[i].CenterX());
    }
    std::sort(centers.begin(), centers.end());
    std::vector<double> differences;
    for (size_t i = 1; i < centers.size(); ++i) {
      differences.push_back(centers[i] - centers[i - 1]);
    }
    const double pitch = Median(differences);
    if (pitch < minimum_pitch || pitch > maximum_pitch) {
      return Fail(error, "dynamic Fantasy grid pitch is out of range");
    }
    std::vector<double> implied_centers;
    const double half = (centers.size() - 1) / 2.0;
    for (size_t i = 0; i < centers.size(); ++i) {
      implied_centers.push_back(centers[i] - (static_cast<double>(i) - half) * pitch);
    }
    const double center = Median(implied_centers);
    double residual = 0.0;
    for (size_t i = 0; i < centers.size(); ++i) {
      const double expected = center + (static_cast<double>(i) - half) * pitch;
      residual = std::max(residual, std::fabs(centers[i] - expected));
    }
    if (residual > allowed_residual) {
      return Fail(error, "dynamic Fantasy grid residual is too high");
    }
    fit->valid = true;
    fit->count = static_cast<int>(centers.size());
    fit->center = center;
    fit->pitch = pitch;
    fit->maximum_residual = residual;
    if (error != NULL) error->clear();
    return true;
  }

  static COFCPixelRect RecognitionPatch(const COFCFantasyRankAnchor &anchor) {
    return COFCPixelRect(
      anchor.bounds.left - 8,
      anchor.bounds.top - 2,
      anchor.bounds.left - 8 + 34,
      anchor.bounds.top - 2 + 46);
  }

  static COFCPixelRect CurrentSourceRect(const COFCFantasyRankAnchor &anchor) {
    COFCPixelRect rect = RecognitionPatch(anchor);
    rect.bottom += 20;
    return rect;
  }

  static bool RequireUniquePhysicalCards(
      const std::vector<std::string> &cards,
      std::string *error) {
    if (cards.empty()) {
      return Fail(error, "dynamic Fantasy detector returned no cards");
    }
    std::set<std::string> seen;
    for (size_t i = 0; i < cards.size(); ++i) {
      if (cards[i].empty() || cards[i] == "AMBIGUOUS") {
        return Fail(error, "dynamic Fantasy detector returned an ambiguous card");
      }
      if (!seen.insert(cards[i]).second) {
        return Fail(error, "dynamic Fantasy detector returned duplicate physical cards");
      }
    }
    if (error != NULL) error->clear();
    return true;
  }

  static bool RequirePhysicalCardLineage(
      const std::vector<std::string> &cards,
      const std::vector<std::string> &original_fantasy_cards,
      std::string *error) {
    std::set<std::string> allowed(
      original_fantasy_cards.begin(), original_fantasy_cards.end());
    for (size_t i = 0; i < cards.size(); ++i) {
      if (allowed.find(cards[i]) == allowed.end()) {
        return Fail(error,
          "dynamic Fantasy detector violated physical-card lineage: " + cards[i]);
      }
    }
    if (error != NULL) error->clear();
    return true;
  }

 private:
  static bool Fail(std::string *error, const std::string &message) {
    if (error != NULL) *error = message;
    return false;
  }

  static bool StrongerAnchorFirst(
      const COFCFantasyRankAnchor &left,
      const COFCFantasyRankAnchor &right) {
    if (left.area != right.area) return left.area > right.area;
    if (left.CenterY() != right.CenterY()) return left.CenterY() < right.CenterY();
    return left.CenterX() < right.CenterX();
  }

  static bool AnchorLeftToRight(
      const COFCFantasyRankAnchor &left,
      const COFCFantasyRankAnchor &right) {
    return left.CenterX() < right.CenterX();
  }
};

#endif  // INC_COFCFANTASYDYNAMICGEOMETRY_H
