//******************************************************************************
//
// DeepOFC Fantasy15 real-pixel recognizer implementation.
//
// This translation unit is intentionally inert until a separate certification
// gate wires it into COFCScraper. It contains no input/action primitive.
//
//******************************************************************************

#include "StdAfx.h"
#include "COFCFantasy15PixelRecognizer.h"
#include "COFCFantasyDynamicGeometry.h"
#include "COFCFantasy15PixelModel.generated.h"
#include "COFCFantasyRecognizerBanks.generated.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <set>
#include <sstream>
#include <stdint.h>
#include <vector>

namespace {

const int kExpectedWidth = 450;
const int kExpectedHeight = 830;
const int kFanSlots = 15;
const int kFeatureSide = 32;
const int kHogBins = 9;

struct Pixel {
  unsigned char r;
  unsigned char g;
  unsigned char b;
};

struct Image {
  int width;
  int height;
  std::vector<Pixel> pixels;

  Image() : width(0), height(0) {}

  const Pixel &At(int x, int y) const {
    return pixels[static_cast<size_t>(y) * width + x];
  }
};

struct PatchRect {
  int x1;
  int y1;
  int x2;
  int y2;
};

struct InkPoint {
  int x;
  int y;
};

struct InkComponentWithPoints {
  COFCFantasyInkComponent component;
  std::vector<InkPoint> points;
};

const PatchRect kInitialFanRects[kFanSlots] = {
  {15, 681, 41, 727},
  {41, 673, 67, 719},
  {66, 665, 92, 711},
  {92, 659, 118, 705},
  {118, 654, 144, 700},
  {145, 651, 171, 697},
  {171, 648, 197, 694},
  {197, 647, 223, 693},
  {224, 647, 250, 693},
  {250, 649, 276, 695},
  {276, 651, 302, 697},
  {303, 654, 329, 700},
  {330, 658, 356, 704},
  {357, 664, 383, 710},
  {383, 672, 409, 718}
};

bool Fail(std::string *error, const std::string &message) {
  if (error != NULL) *error = message;
  return false;
}

bool IsRectInside(const PatchRect &rect, const Image &image) {
  return rect.x1 >= 0 && rect.y1 >= 0
      && rect.x2 > rect.x1 && rect.y2 > rect.y1
      && rect.x2 <= image.width && rect.y2 <= image.height;
}

bool ReadTopDownRgb(HBITMAP bitmap, Image *image, std::string *error) {
  if (bitmap == NULL || image == NULL) {
    return Fail(error, "Fantasy15 pixel recognizer received null bitmap/output");
  }

  BITMAP bm;
  ZeroMemory(&bm, sizeof(bm));
  if (GetObject(bitmap, sizeof(bm), &bm) != sizeof(bm)) {
    return Fail(error, "GetObject failed for Fantasy15 table bitmap");
  }
  const int width = bm.bmWidth;
  const int height = bm.bmHeight < 0 ? -bm.bmHeight : bm.bmHeight;
  if (width != kExpectedWidth || height != kExpectedHeight) {
    std::ostringstream oss;
    oss << "Fantasy15 pixel recognizer requires exact 450x830 bitmap; got "
        << width << "x" << height;
    return Fail(error, oss.str());
  }

  BITMAPINFO info;
  ZeroMemory(&info, sizeof(info));
  info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
  info.bmiHeader.biWidth = width;
  info.bmiHeader.biHeight = -height;  // request deterministic top-down pixels
  info.bmiHeader.biPlanes = 1;
  info.bmiHeader.biBitCount = 32;
  info.bmiHeader.biCompression = BI_RGB;

  std::vector<unsigned char> bgra(
      static_cast<size_t>(width) * height * 4, 0);
  HDC screen_dc = GetDC(NULL);
  if (screen_dc == NULL) {
    return Fail(error, "GetDC failed for Fantasy15 bitmap extraction");
  }
  const int copied = GetDIBits(
      screen_dc, bitmap, 0, static_cast<UINT>(height),
      &bgra[0], &info, DIB_RGB_COLORS);
  ReleaseDC(NULL, screen_dc);
  if (copied != height) {
    return Fail(error, "GetDIBits failed/incomplete for Fantasy15 table bitmap");
  }

  image->width = width;
  image->height = height;
  image->pixels.resize(static_cast<size_t>(width) * height);
  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) {
      const size_t src = (static_cast<size_t>(y) * width + x) * 4;
      Pixel p;
      p.b = bgra[src + 0];
      p.g = bgra[src + 1];
      p.r = bgra[src + 2];
      image->pixels[static_cast<size_t>(y) * width + x] = p;
    }
  }
  return true;
}

bool IsInk(const Pixel &p) {
  const int r = p.r;
  const int g = p.g;
  const int b = p.b;
  const int maximum = std::max(r, std::max(g, b));
  const int minimum = std::min(r, std::min(g, b));
  return (r > g + 35 && r > b + 35 && r > 100)
      || (g > r + 25 && g > b + 20 && g > 80)
      || (b > g + 25 && b > r + 25 && b > 100)
      || (maximum < 120 && maximum - minimum < 45);
}

double WhiteDensity(const Image &image, int x, int y, int radius) {
  const int left = std::max(0, x - radius);
  const int top = std::max(0, y - radius);
  const int right = std::min(image.width, x + radius + 1);
  const int bottom = std::min(image.height, y + radius + 1);
  int white = 0;
  int total = 0;
  for (int py = top; py < bottom; ++py) {
    for (int px = left; px < right; ++px) {
      const Pixel p = image.At(px, py);
      const int maximum = std::max(p.r, std::max(p.g, p.b));
      const int minimum = std::min(p.r, std::min(p.g, p.b));
      if (minimum > 175 && maximum - minimum < 55) ++white;
      ++total;
    }
  }
  return total == 0 ? 0.0 : static_cast<double>(white) / total;
}

void ConnectedInkComponents(
    const Image &image,
    const COFCPixelRect &roi,
    bool threshold_mode,
    int threshold,
    std::vector<InkComponentWithPoints> *components) {
  components->clear();
  const int width = roi.Width();
  const int height = roi.Height();
  if (width <= 0 || height <= 0) return;
  std::vector<unsigned char> mask(static_cast<size_t>(width) * height, 0);
  std::vector<unsigned char> seen(static_cast<size_t>(width) * height, 0);
  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) {
      const Pixel p = image.At(roi.left + x, roi.top + y);
      const bool enabled = threshold_mode
        ? std::min(p.r, std::min(p.g, p.b)) < threshold
        : IsInk(p);
      mask[static_cast<size_t>(y) * width + x] = enabled ? 1 : 0;
    }
  }

  for (int y = 0; y < height; ++y) {
    for (int x = 0; x < width; ++x) {
      const size_t index = static_cast<size_t>(y) * width + x;
      if (!mask[index] || seen[index]) continue;
      std::vector<InkPoint> stack;
      stack.push_back(InkPoint{x, y});
      seen[index] = 1;
      InkComponentWithPoints current;
      int minimum_x = x;
      int maximum_x = x;
      int minimum_y = y;
      int maximum_y = y;
      while (!stack.empty()) {
        const InkPoint point = stack.back();
        stack.pop_back();
        InkPoint absolute = {roi.left + point.x, roi.top + point.y};
        current.points.push_back(absolute);
        minimum_x = std::min(minimum_x, point.x);
        maximum_x = std::max(maximum_x, point.x);
        minimum_y = std::min(minimum_y, point.y);
        maximum_y = std::max(maximum_y, point.y);
        for (int dy = -1; dy <= 1; ++dy) {
          for (int dx = -1; dx <= 1; ++dx) {
            if (dx == 0 && dy == 0) continue;
            const int nx = point.x + dx;
            const int ny = point.y + dy;
            if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue;
            const size_t next = static_cast<size_t>(ny) * width + nx;
            if (!mask[next] || seen[next]) continue;
            seen[next] = 1;
            stack.push_back(InkPoint{nx, ny});
          }
        }
      }
      current.component = COFCFantasyInkComponent(
        COFCPixelRect(
          roi.left + minimum_x, roi.top + minimum_y,
          roi.left + maximum_x + 1, roi.top + maximum_y + 1),
        static_cast<int>(current.points.size()));
      components->push_back(current);
    }
  }
}

double MedianChannel(std::vector<int> values) {
  if (values.empty()) return 0.0;
  std::sort(values.begin(), values.end());
  const size_t middle = values.size() / 2;
  if ((values.size() % 2) != 0) return values[middle];
  return (values[middle - 1] + values[middle]) / 2.0;
}

void MedianRgb(
    const Image &image,
    const std::vector<InkPoint> &points,
    double *r,
    double *g,
    double *b) {
  std::vector<int> rs;
  std::vector<int> gs;
  std::vector<int> bs;
  for (size_t i = 0; i < points.size(); ++i) {
    const Pixel p = image.At(points[i].x, points[i].y);
    rs.push_back(p.r);
    gs.push_back(p.g);
    bs.push_back(p.b);
  }
  *r = MedianChannel(rs);
  *g = MedianChannel(gs);
  *b = MedianChannel(bs);
}

void NormalizeComponent(
    const std::vector<InkPoint> &points,
    uint16_t rows[kDeepOFCGlyphHeight]) {
  for (int y = 0; y < kDeepOFCGlyphHeight; ++y) rows[y] = 0;
  if (points.empty()) return;
  int x1 = points[0].x;
  int x2 = points[0].x;
  int y1 = points[0].y;
  int y2 = points[0].y;
  for (size_t i = 1; i < points.size(); ++i) {
    x1 = std::min(x1, points[i].x);
    x2 = std::max(x2, points[i].x);
    y1 = std::min(y1, points[i].y);
    y2 = std::max(y2, points[i].y);
  }
  const int source_width = x2 - x1 + 1;
  const int source_height = y2 - y1 + 1;
  std::vector<unsigned char> source(
    static_cast<size_t>(source_width) * source_height, 0);
  for (size_t i = 0; i < points.size(); ++i) {
    source[static_cast<size_t>(points[i].y - y1) * source_width
      + points[i].x - x1] = 1;
  }
  const double scale = std::min(
    14.0 / source_width, 22.0 / source_height);
  const int normalized_width = std::max(1,
    static_cast<int>(std::floor(source_width * scale + 0.5)));
  const int normalized_height = std::max(1,
    static_cast<int>(std::floor(source_height * scale + 0.5)));
  const int offset_x = (kDeepOFCGlyphWidth - normalized_width) / 2;
  const int offset_y = (kDeepOFCGlyphHeight - normalized_height) / 2;
  for (int y = 0; y < normalized_height; ++y) {
    const int source_y = std::min(
      source_height - 1, y * source_height / normalized_height);
    for (int x = 0; x < normalized_width; ++x) {
      const int source_x = std::min(
        source_width - 1, x * source_width / normalized_width);
      if (source[static_cast<size_t>(source_y) * source_width + source_x]) {
        rows[offset_y + y] = static_cast<uint16_t>(
          rows[offset_y + y] | static_cast<uint16_t>(1u << (offset_x + x)));
      }
    }
  }
}

double DynamicFanAngle(double center_x) {
  const double centers[kFanSlots] = {
    28.0, 54.0, 79.0, 105.0, 131.0,
    158.0, 184.0, 210.0, 237.0, 263.0,
    289.0, 316.0, 343.0, 370.0, 396.0};
  const double angles[kFanSlots] = {
    -18.85, -16.52, -14.22, -11.79, -9.31,
    -6.69, -4.15, -1.59, 1.08, 3.64,
    6.18, 8.8, 11.39, 13.92, 16.32};
  if (center_x <= centers[0]) return angles[0];
  if (center_x >= centers[kFanSlots - 1]) return angles[kFanSlots - 1];
  for (int i = 0; i < kFanSlots - 1; ++i) {
    if (center_x < centers[i] || center_x > centers[i + 1]) continue;
    const double fraction =
      (center_x - centers[i]) / (centers[i + 1] - centers[i]);
    return angles[i] + fraction * (angles[i + 1] - angles[i]);
  }
  return 0.0;
}

std::vector<InkPoint> DeskewDynamicRank(
    const std::vector<InkPoint> &points,
    double anchor_center_x) {
  if (points.empty()) return points;
  double center_x = 0.0;
  double center_y = 0.0;
  for (size_t i = 0; i < points.size(); ++i) {
    center_x += points[i].x;
    center_y += points[i].y;
  }
  center_x /= points.size();
  center_y /= points.size();
  const double pi = 3.14159265358979323846;
  const double radians = 0.8 * DynamicFanAngle(anchor_center_x) * pi / 180.0;
  const double cosine = std::cos(radians);
  const double sine = std::sin(radians);
  std::set<std::pair<int, int> > unique;
  for (size_t i = 0; i < points.size(); ++i) {
    const double x = points[i].x - center_x;
    const double y = points[i].y - center_y;
    const int rotated_x = static_cast<int>(
      std::floor(center_x + x * cosine - y * sine + 0.5));
    const int rotated_y = static_cast<int>(
      std::floor(center_y + x * sine + y * cosine + 0.5));
    unique.insert(std::make_pair(rotated_x, rotated_y));
  }
  std::vector<InkPoint> result;
  for (std::set<std::pair<int, int> >::const_iterator it = unique.begin();
       it != unique.end(); ++it) {
    result.push_back(InkPoint{it->first, it->second});
  }
  return result;
}

bool CardFromFeature(
    const uint16_t rows[kDeepOFCGlyphHeight],
    double r,
    double g,
    double b,
    int area,
    int width,
    int height,
    bool upright,
    bool allow_ten_fallback,
    COFCFantasy15PixelCard *card,
    std::string *error) {
  *card = COFCFantasy15PixelCard();
  if (area < 60 && width <= 8 && height <= 10) {
    const double spread = std::max(r, std::max(g, b))
      - std::min(r, std::min(g, b));
    if (r - std::max(g, b) > 100.0) {
      card->joker_id = 1;
      card->valid = true;
      return true;
    }
    const double mean = (r + g + b) / 3.0;
    if (spread < 25.0 && mean >= 50.0 && mean <= 160.0) {
      card->joker_id = 2;
      card->valid = true;
      return true;
    }
    return Fail(error, "ambiguous Fantasy Joker-like glyph");
  }

  COFCRecognitionResult rank = COFCFantasyRecognitionCore::ClassifyRank(
    rows,
    upright ? kDeepOFCUprightLargeRankTemplates
            : kDeepOFCFantasy15FanRankTemplates,
    13,
    2,
    upright ? 0.36 : kDeepOFCFanRankMaxDistance,
    upright ? 0.04 : kDeepOFCFanRankMinMargin);
  if (!rank.accepted && !upright && allow_ten_fallback) {
    const COFCRecognitionResult fallback =
      COFCFantasyRecognitionCore::ClassifyRank(
        rows, kDeepOFCUprightLargeRankTemplates, 13, 2, 0.51, 0.10);
    if (fallback.accepted && fallback.label == 'T') rank = fallback;
  }
  if (!rank.accepted) {
    std::ostringstream oss;
    oss << "Fantasy rank rejected distance=" << rank.best_distance
        << " margin=" << rank.margin;
    return Fail(error, oss.str());
  }

  const COFCRecognitionResult suit = COFCFantasyRecognitionCore::ClassifyRgb(
    r, g, b, kDeepOFCSuitPrototypes, 4,
    kDeepOFCSuitMaxDistance, kDeepOFCSuitMinMargin);
  if (!suit.accepted) {
    std::ostringstream oss;
    oss << "Fantasy suit rejected distance=" << suit.best_distance
        << " margin=" << suit.margin;
    return Fail(error, oss.str());
  }
  card->rank = rank.label;
  card->suit = suit.label;
  card->rank_distance = rank.best_distance;
  card->rank_margin = rank.margin;
  card->valid = true;
  return true;
}

struct UprightRawFeature {
  bool empty;
  uint16_t rows[kDeepOFCGlyphHeight];
  double r;
  double g;
  double b;
  int area;
  int width;
  int height;

  UprightRawFeature()
      : empty(false), r(0.0), g(0.0), b(0.0),
        area(0), width(0), height(0) {
    for (int y = 0; y < kDeepOFCGlyphHeight; ++y) rows[y] = 0;
  }
};

bool ExtractUprightRaw(
    const Image &image,
    const COFCPixelRect &rect,
    UprightRawFeature *feature,
    std::string *error) {
  if (feature == NULL) return Fail(error, "upright raw output is null");
  *feature = UprightRawFeature();
  const COFCPixelRect roi(
    rect.left, rect.top,
    std::min(rect.right, rect.left + 27),
    std::min(rect.bottom, rect.top + 47));
  if (!roi.Valid() || roi.left < 0 || roi.top < 0
      || roi.right > image.width || roi.bottom > image.height) {
    return Fail(error, "Fantasy upright slot is outside bitmap");
  }
  std::vector<InkComponentWithPoints> components;
  ConnectedInkComponents(image, roi, true, 140, &components);
  int best = -1;
  double best_score = -1e100;
  for (size_t i = 0; i < components.size(); ++i) {
    const InkComponentWithPoints &candidate = components[i];
    if (candidate.component.area < 5) continue;
    double cx = 0.0;
    double cy = 0.0;
    for (size_t p = 0; p < candidate.points.size(); ++p) {
      cx += candidate.points[p].x - roi.left;
      cy += candidate.points[p].y - roi.top;
    }
    cx /= candidate.points.size();
    cy /= candidate.points.size();
    if (cy >= 0.82 * 24.0) continue;
    const double score = candidate.component.area
      - 2.0 * std::fabs(cx - 8.0) - std::max(0.0, cy - 13.2);
    if (score > best_score) {
      best_score = score;
      best = static_cast<int>(i);
    }
  }
  if (best < 0) {
    feature->empty = true;
    return true;
  }

  const InkComponentWithPoints &selected = components[best];
  NormalizeComponent(selected.points, feature->rows);
  MedianRgb(image, selected.points, &feature->r, &feature->g, &feature->b);
  feature->area = selected.component.area;
  feature->width = selected.component.bounds.Width();
  feature->height = selected.component.bounds.Height();
  return true;
}

bool ExtractUprightFeature(
    const Image &image,
    const COFCPixelRect &rect,
    COFCFantasy15PixelCard *card,
    bool *empty,
    std::string *error) {
  UprightRawFeature feature;
  if (!ExtractUprightRaw(image, rect, &feature, error)) return false;
  *empty = feature.empty;
  if (feature.empty) return true;
  return CardFromFeature(
    feature.rows, feature.r, feature.g, feature.b,
    feature.area, feature.width, feature.height,
    true, false, card, error);
}

bool LocateDynamicAnchors(
    const Image &image,
    std::vector<COFCFantasyRankAnchor> *anchors,
    std::vector<InkComponentWithPoints> *components,
    std::string *error) {
  const COFCPixelRect roi(20, 630, 430, 735);
  ConnectedInkComponents(image, roi, false, 0, components);
  std::vector<COFCFantasyInkComponent> simple;
  std::vector<COFCFantasyInkComponent> upper;
  for (size_t i = 0; i < components->size(); ++i) {
    simple.push_back((*components)[i].component);
    const COFCPixelRect &bounds = (*components)[i].component.bounds;
    if (WhiteDensity(
          image,
          static_cast<int>(std::floor(bounds.CenterX() + 0.5)),
          static_cast<int>(std::floor(bounds.CenterY() + 0.5)), 4) >= 0.12) {
      upper.push_back((*components)[i].component);
    }
  }
  COFCFantasyDynamicGeometry::PairRankAnchors(simple, upper, anchors);

  // A narrow rank+suit column may be one 8-connected component.
  for (size_t i = 0; i < upper.size(); ++i) {
    const COFCPixelRect bounds = upper[i].bounds;
    if (bounds.Height() < 30 || bounds.Height() > 38 || bounds.Width() > 20) continue;
    bool band_used = false;
    for (size_t j = 0; j < anchors->size(); ++j) {
      if (std::fabs(bounds.CenterX() - (*anchors)[j].CenterX()) < 12.0) {
        band_used = true;
        break;
      }
    }
    if (band_used) continue;
    const int split = std::min(24, bounds.Height() - 10);
    anchors->push_back(COFCFantasyRankAnchor(
      COFCPixelRect(bounds.left, bounds.top, bounds.right, bounds.top + split),
      upper[i].area,
      COFCPixelRect(bounds.left, bounds.top + split, bounds.right, bounds.bottom)));
  }
  std::sort(anchors->begin(), anchors->end(),
    [](const COFCFantasyRankAnchor &left, const COFCFantasyRankAnchor &right) {
      return left.CenterX() < right.CenterX();
    });
  if (anchors->size() < 2) {
    return Fail(error, "dynamic Fantasy detector found fewer than two loose cards");
  }
  return true;
}

const InkComponentWithPoints *FindComponent(
    const std::vector<InkComponentWithPoints> &components,
    const COFCPixelRect &bounds) {
  for (size_t i = 0; i < components.size(); ++i) {
    const COFCPixelRect &candidate = components[i].component.bounds;
    if (candidate.left == bounds.left && candidate.top == bounds.top
        && candidate.right == bounds.right && candidate.bottom == bounds.bottom) {
      return &components[i];
    }
  }
  // Recovered narrow rank+suit columns deliberately split one connected
  // component into an upper rank anchor and lower suit bounds.
  for (size_t i = 0; i < components.size(); ++i) {
    const COFCPixelRect &candidate = components[i].component.bounds;
    if (candidate.left <= bounds.left && candidate.top <= bounds.top
        && candidate.right >= bounds.right && candidate.bottom >= bounds.bottom) {
      return &components[i];
    }
  }
  return NULL;
}

bool RankHog(
    const Image &image,
    const PatchRect &rect,
    std::vector<double> *feature,
    std::string *error) {
  if (feature == NULL || !IsRectInside(rect, image)) {
    return Fail(error, "Fantasy15 HOG patch is invalid/outside bitmap");
  }
  const int patch_width = rect.x2 - rect.x1;
  const int patch_height = rect.y2 - rect.y1;
  const int crop_height = std::min(30, patch_height);
  if (patch_width <= 0 || crop_height <= 0) {
    return Fail(error, "Fantasy15 HOG patch has empty rank crop");
  }

  double binary[kFeatureSide][kFeatureSide] = {};
  for (int y = 0; y < kFeatureSide; ++y) {
    const int sy = rect.y1 + std::min(y * crop_height / kFeatureSide, crop_height - 1);
    for (int x = 0; x < kFeatureSide; ++x) {
      const int sx = rect.x1 + std::min(x * patch_width / kFeatureSide, patch_width - 1);
      const Pixel p = image.At(sx, sy);
      const double gray = 0.299 * p.r + 0.587 * p.g + 0.114 * p.b;
      binary[y][x] = gray < 200.0 ? 1.0 : 0.0;
    }
  }

  double magnitude[kFeatureSide][kFeatureSide] = {};
  int angle_bin[kFeatureSide][kFeatureSide] = {};
  const double kPi = 3.14159265358979323846;
  for (int y = 1; y < kFeatureSide - 1; ++y) {
    for (int x = 1; x < kFeatureSide - 1; ++x) {
      const double gx = binary[y][x + 1] - binary[y][x - 1];
      const double gy = binary[y + 1][x] - binary[y - 1][x];
      magnitude[y][x] = std::sqrt(gx * gx + gy * gy);
      double angle = std::atan2(gy, gx) * 180.0 / kPi;
      while (angle < 0.0) angle += 180.0;
      while (angle >= 180.0) angle -= 180.0;
      angle_bin[y][x] = static_cast<int>(angle / 20.0) % kHogBins;
    }
  }

  double cells[4][4][kHogBins] = {};
  for (int cy = 0; cy < 4; ++cy) {
    for (int cx = 0; cx < 4; ++cx) {
      for (int y = cy * 8; y < (cy + 1) * 8; ++y) {
        for (int x = cx * 8; x < (cx + 1) * 8; ++x) {
          cells[cy][cx][angle_bin[y][x]] += magnitude[y][x];
        }
      }
    }
  }

  feature->clear();
  feature->reserve(deepofc_f15_model::kFeatureCount);
  for (int cy = 0; cy < 3; ++cy) {
    for (int cx = 0; cx < 3; ++cx) {
      double norm2 = 1e-18;
      for (int yy = cy; yy <= cy + 1; ++yy) {
        for (int xx = cx; xx <= cx + 1; ++xx) {
          for (int k = 0; k < kHogBins; ++k) {
            norm2 += cells[yy][xx][k] * cells[yy][xx][k];
          }
        }
      }
      const double norm = std::sqrt(norm2);
      for (int yy = cy; yy <= cy + 1; ++yy) {
        for (int xx = cx; xx <= cx + 1; ++xx) {
          for (int k = 0; k < kHogBins; ++k) {
            feature->push_back(cells[yy][xx][k] / norm);
          }
        }
      }
    }
  }
  if (feature->size() != static_cast<size_t>(deepofc_f15_model::kFeatureCount)) {
    return Fail(error, "Fantasy15 HOG feature length drift");
  }
  return true;
}

void InkCounts(const Image &image, const PatchRect &rect, int counts[4]) {
  // Order is h,c,d,s. These are the exact KKPoker color signatures used by the
  // independent real-pixel holdout benchmark.
  counts[0] = counts[1] = counts[2] = counts[3] = 0;
  for (int y = rect.y1; y < rect.y2; ++y) {
    for (int x = rect.x1; x < rect.x2; ++x) {
      const Pixel p = image.At(x, y);
      const int r = p.r;
      const int g = p.g;
      const int b = p.b;
      const int mx = std::max(r, std::max(g, b));
      const int mn = std::min(r, std::min(g, b));
      if (r > g + 35 && r > b + 35 && r > 100) ++counts[0];
      if (g > r + 25 && g > b + 20 && g > 80) ++counts[1];
      if (b > g + 25 && b > r + 25 && b > 100) ++counts[2];
      if (mx < 120 && (mx - mn) < 45) ++counts[3];
    }
  }
}

bool UniqueSuit(const int counts[4], char *suit) {
  const char suits[4] = {'h', 'c', 'd', 's'};
  int best_index = 0;
  bool tie = false;
  for (int i = 1; i < 4; ++i) {
    if (counts[i] > counts[best_index]) {
      best_index = i;
      tie = false;
    } else if (counts[i] == counts[best_index]) {
      tie = true;
    }
  }
  if (tie || counts[best_index] <= 0) return false;
  *suit = suits[best_index];
  return true;
}

double RankDistance(const std::vector<double> &feature, int rank_index) {
  double total = 0.0;
  for (int i = 0; i < deepofc_f15_model::kFeatureCount; ++i) {
    const double centroid =
        static_cast<double>(deepofc_f15_model::kRankCentroidsQ[rank_index][i]) / 255.0;
    const double d = feature[static_cast<size_t>(i)] - centroid;
    total += d * d;
  }
  return total;
}

bool RecognizePatch(
    const Image &image,
    const PatchRect &rect,
    COFCFantasy15PixelCard *card,
    std::string *error) {
  if (card == NULL) return Fail(error, "Fantasy15 card output is null");
  *card = COFCFantasy15PixelCard();

  std::vector<double> feature;
  if (!RankHog(image, rect, &feature, error)) return false;

  int best_rank = -1;
  double best = std::numeric_limits<double>::infinity();
  double second = std::numeric_limits<double>::infinity();
  for (int r = 0; r < deepofc_f15_model::kRankCount; ++r) {
    const double distance = RankDistance(feature, r);
    if (distance < best) {
      second = best;
      best = distance;
      best_rank = r;
    } else if (distance < second) {
      second = distance;
    }
  }
  if (best_rank < 0 || !std::isfinite(best) || !std::isfinite(second)) {
    return Fail(error, "Fantasy15 rank distances are invalid");
  }

  const double margin = second - best;
  card->rank_distance = best;
  card->rank_margin = margin;
  int counts[4];
  InkCounts(image, rect, counts);

  if (best >= deepofc_f15_model::kJokerMinDistance) {
    if (counts[0] == counts[3]) {
      return Fail(error, "Fantasy15 Joker color identity is ambiguous");
    }
    card->joker_id = counts[0] > counts[3] ? 1 : 2;
    card->valid = true;
    return true;
  }

  if (best > deepofc_f15_model::kStandardMaxDistance
      || margin < deepofc_f15_model::kStandardMinMargin) {
    std::ostringstream oss;
    oss << "Fantasy15 standard rank is ambiguous: distance=" << best
        << " margin=" << margin;
    return Fail(error, oss.str());
  }

  char suit = 0;
  if (!UniqueSuit(counts, &suit)) {
    return Fail(error, "Fantasy15 standard suit is ambiguous");
  }
  card->rank = deepofc_f15_model::kRanks[best_rank][0];
  card->suit = suit;
  card->valid = true;
  return true;
}

struct ExpectedPhysicalCard {
  std::string label;
  char rank;
  char suit;
  int joker_id;
};

bool ParseExpectedCard(
    const std::string &label,
    ExpectedPhysicalCard *card) {
  card->label = label;
  card->rank = 0;
  card->suit = 0;
  card->joker_id = 0;
  if (label == "JK1") { card->joker_id = 1; return true; }
  if (label == "JK2") { card->joker_id = 2; return true; }
  if (label.size() != 2) return false;
  const std::string ranks = "23456789TJQKA";
  const std::string suits = "hcds";
  if (ranks.find(label[0]) == std::string::npos
      || suits.find(label[1]) == std::string::npos) return false;
  card->rank = label[0];
  card->suit = label[1];
  return true;
}

const COFCRankTemplate *UprightTemplate(char rank) {
  for (int i = 0; i < 13; ++i)
    if (kDeepOFCUprightLargeRankTemplates[i].label == rank)
      return &kDeepOFCUprightLargeRankTemplates[i];
  return NULL;
}

void MatchExpectedRecursive(
    const std::vector<int> &slot_indices,
    const std::vector<int> &expected_indices,
    const std::vector<UprightRawFeature> &raw,
    const std::vector<ExpectedPhysicalCard> &expected,
    int depth,
    std::vector<bool> *used,
    std::vector<int> *current,
    double total,
    double *best_total,
    std::vector<int> *best) {
  if (depth == static_cast<int>(slot_indices.size())) {
    if (total < *best_total) {
      *best_total = total;
      *best = *current;
    }
    return;
  }
  const int slot = slot_indices[depth];
  for (size_t i = 0; i < expected_indices.size(); ++i) {
    if ((*used)[i]) continue;
    const int expected_index = expected_indices[i];
    const COFCRankTemplate *rank_template =
      UprightTemplate(expected[expected_index].rank);
    if (rank_template == NULL) continue;
    const double distance = COFCFantasyRecognitionCore::AlignedBinaryDistance(
      raw[slot].rows, rank_template->rows, 2);
    if (distance > 0.70) continue;
    (*used)[i] = true;
    (*current)[depth] = expected_index;
    MatchExpectedRecursive(
      slot_indices, expected_indices, raw, expected,
      depth + 1, used, current, total + distance, best_total, best);
    (*used)[i] = false;
  }
}

}  // namespace

std::string COFCFantasy15PixelCard::PhysicalLabel() const {
  if (!valid) return "AMBIGUOUS";
  if (joker_id == 1) return "JK1";
  if (joker_id == 2) return "JK2";
  if (joker_id != 0 || rank == 0 || suit == 0) return "AMBIGUOUS";
  std::string out;
  out.push_back(rank);
  out.push_back(suit);
  return out;
}

bool COFCFantasy15PixelRecognizer::VerifyFrozenModel(std::string *error) {
  if (error != NULL) error->clear();
  if (deepofc_f15_model::kFeatureCount != 324
      || deepofc_f15_model::kRankCount != 13) {
    return Fail(error, "Fantasy15 frozen model dimensions changed");
  }

  const long expected_sum[13] = {
    5834, 6827, 6329, 6496, 6290, 5830, 6981,
    6464, 6341, 5928, 6716, 6898, 6604
  };
  const long expected_weighted[13] = {
    848875, 1048906, 1058735, 1037829, 1026041, 915146, 1120686,
    1044284, 1055344, 914813, 1089315, 1162766, 1112071
  };

  for (int r = 0; r < deepofc_f15_model::kRankCount; ++r) {
    long sum = 0;
    long weighted = 0;
    for (int i = 0; i < deepofc_f15_model::kFeatureCount; ++i) {
      const int value = deepofc_f15_model::kRankCentroidsQ[r][i];
      sum += value;
      weighted += static_cast<long>(i + 1) * value;
    }
    if (sum != expected_sum[r] || weighted != expected_weighted[r]) {
      std::ostringstream oss;
      oss << "Fantasy15 frozen model checksum mismatch at rank index " << r;
      return Fail(error, oss.str());
    }
  }

  if (std::fabs(deepofc_f15_model::kStandardMaxDistance - 2.25) > 1e-9
      || std::fabs(deepofc_f15_model::kStandardMinMargin - 0.15) > 1e-9
      || std::fabs(deepofc_f15_model::kJokerMinDistance - 3.20) > 1e-9) {
    return Fail(error, "Fantasy15 frozen model thresholds changed");
  }
  return true;
}

bool COFCFantasy15PixelRecognizer::RecognizeInitialFan(
    HBITMAP table_bitmap,
    std::vector<COFCFantasy15PixelCard> *cards_left_to_right,
    std::string *error) {
  if (error != NULL) error->clear();
  if (cards_left_to_right == NULL) {
    return Fail(error, "Fantasy15 fan output is null");
  }
  cards_left_to_right->clear();

  std::vector<COFCFantasyPixelObject> objects;
  if (!RecognizeInitialFanObjects(table_bitmap, &objects, error)) return false;
  for (size_t i = 0; i < objects.size(); ++i) {
    cards_left_to_right->push_back(objects[i].card);
  }
  return true;
}

bool COFCFantasy15PixelRecognizer::RecognizeInitialFanObjects(
    HBITMAP table_bitmap,
    std::vector<COFCFantasyPixelObject> *objects_left_to_right,
    std::string *error) {
  if (error != NULL) error->clear();
  if (objects_left_to_right == NULL) {
    return Fail(error, "Fantasy15 object output is null");
  }
  objects_left_to_right->clear();

  std::string model_error;
  if (!VerifyFrozenModel(&model_error)) {
    return Fail(error, model_error);
  }

  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;

  std::vector<std::string> labels;
  for (int i = 0; i < kFanSlots; ++i) {
    COFCFantasy15PixelCard card;
    std::string slot_error;
    if (!RecognizePatch(image, kInitialFanRects[i], &card, &slot_error)) {
      objects_left_to_right->clear();
      std::ostringstream oss;
      oss << "Fantasy15 slot " << i << " failed closed: " << slot_error;
      return Fail(error, oss.str());
    }
    const std::string label = card.PhysicalLabel();
    labels.push_back(label);

    COFCFantasyPixelObject object;
    object.valid = true;
    object.fresh_from_current_bitmap = true;
    object.card = card;
    object.source_rect.left = kInitialFanRects[i].x1;
    object.source_rect.top = kInitialFanRects[i].y1;
    object.source_rect.right = kInitialFanRects[i].x2;
    object.source_rect.bottom = std::min(kExpectedHeight, kInitialFanRects[i].y2 + 20);
    object.drag_anchor.x =
      (object.source_rect.left + object.source_rect.right) / 2;
    object.drag_anchor.y =
      (object.source_rect.top + object.source_rect.bottom) / 2;
    object.detected_layout_count = kFanSlots;
    object.geometry_residual = 0.0;
    objects_left_to_right->push_back(object);
  }

  std::string identity_error;
  if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(
        labels, &identity_error)) {
    objects_left_to_right->clear();
    return Fail(error, identity_error);
  }
  if (objects_left_to_right->size() != kFanSlots) {
    objects_left_to_right->clear();
    return Fail(error, "Fantasy15 fan did not produce exactly 15 physical cards");
  }
  return true;
}

bool COFCFantasy15PixelRecognizer::RecognizeArrangementSlots(
    HBITMAP table_bitmap,
    const std::vector<RECT> &slots,
    std::vector<bool> *occupied,
    std::vector<COFCFantasy15PixelCard> *cards,
    std::string *error) {
  if (error != NULL) error->clear();
  if (occupied == NULL || cards == NULL) {
    return Fail(error, "Fantasy arrangement output is null");
  }
  occupied->clear();
  cards->clear();
  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;
  std::vector<std::string> labels;
  for (size_t i = 0; i < slots.size(); ++i) {
    const RECT &slot = slots[i];
    const COFCPixelRect rect(slot.left, slot.top, slot.right, slot.bottom);
    COFCFantasy15PixelCard card;
    bool empty = false;
    std::string slot_error;
    if (!ExtractUprightFeature(image, rect, &card, &empty, &slot_error)) {
      occupied->clear();
      cards->clear();
      std::ostringstream oss;
      oss << "Fantasy arrangement slot " << i
          << " failed closed: " << slot_error;
      return Fail(error, oss.str());
    }
    occupied->push_back(!empty);
    cards->push_back(card);
    if (!empty) labels.push_back(card.PhysicalLabel());
  }
  if (!labels.empty()) {
    std::string unique_error;
    if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(
          labels, &unique_error)) {
      occupied->clear();
      cards->clear();
      return Fail(error, unique_error);
    }
  }
  return true;
}

bool COFCFantasy15PixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
    HBITMAP table_bitmap,
    const std::vector<RECT> &slots,
    const std::vector<std::string> &expected_physical_cards,
    std::vector<bool> *occupied,
    std::vector<COFCFantasy15PixelCard> *cards,
    std::string *error) {
  if (error != NULL) error->clear();
  if (occupied == NULL || cards == NULL) {
    return Fail(error, "expected-arrangement output is null");
  }
  occupied->clear();
  cards->assign(slots.size(), COFCFantasy15PixelCard());
  std::set<std::string> expected_unique(
    expected_physical_cards.begin(), expected_physical_cards.end());
  if (expected_unique.size() != expected_physical_cards.size()) {
    return Fail(error, "expected arrangement contains duplicate physical cards");
  }
  std::vector<ExpectedPhysicalCard> expected;
  for (size_t i = 0; i < expected_physical_cards.size(); ++i) {
    ExpectedPhysicalCard parsed;
    if (!ParseExpectedCard(expected_physical_cards[i], &parsed)) {
      return Fail(error, "expected arrangement contains invalid physical label");
    }
    expected.push_back(parsed);
  }

  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;
  std::vector<UprightRawFeature> raw(slots.size());
  int occupied_count = 0;
  for (size_t i = 0; i < slots.size(); ++i) {
    const RECT &slot = slots[i];
    if (!ExtractUprightRaw(
          image, COFCPixelRect(slot.left, slot.top, slot.right, slot.bottom),
          &raw[i], error)) {
      occupied->clear();
      cards->clear();
      return false;
    }
    occupied->push_back(!raw[i].empty);
    if (!raw[i].empty) ++occupied_count;
  }
  if (occupied_count != static_cast<int>(expected.size())) {
    return Fail(error, "occupied arrangement count disagrees with expected physical set");
  }

  std::vector<bool> expected_used(expected.size(), false);
  std::vector<int> standard_slots_by_suit[4];
  const char suits[4] = {'h', 'c', 'd', 's'};
  for (size_t slot = 0; slot < slots.size(); ++slot) {
    if (raw[slot].empty) continue;
    int joker = 0;
    if (raw[slot].area < 60 && raw[slot].width <= 8 && raw[slot].height <= 10) {
      const double spread = std::max(raw[slot].r,
        std::max(raw[slot].g, raw[slot].b)) - std::min(raw[slot].r,
        std::min(raw[slot].g, raw[slot].b));
      if (raw[slot].r - std::max(raw[slot].g, raw[slot].b) > 100.0) joker = 1;
      const double mean = (raw[slot].r + raw[slot].g + raw[slot].b) / 3.0;
      if (joker == 0 && spread < 25.0 && mean >= 50.0 && mean <= 160.0) joker = 2;
      if (joker == 0) return Fail(error, "ambiguous expected-arrangement Joker glyph");
    }
    if (joker != 0) {
      int match = -1;
      for (size_t i = 0; i < expected.size(); ++i) {
        if (!expected_used[i] && expected[i].joker_id == joker) {
          match = static_cast<int>(i);
          break;
        }
      }
      if (match < 0) return Fail(error, "unexpected/duplicate Joker in arrangement");
      expected_used[match] = true;
      (*cards)[slot].valid = true;
      (*cards)[slot].joker_id = joker;
      continue;
    }

    const COFCRecognitionResult suit = COFCFantasyRecognitionCore::ClassifyRgb(
      raw[slot].r, raw[slot].g, raw[slot].b,
      kDeepOFCSuitPrototypes, 4,
      kDeepOFCSuitMaxDistance, kDeepOFCSuitMinMargin);
    if (!suit.accepted) return Fail(error, "expected-arrangement suit rejected");
    int suit_index = -1;
    for (int i = 0; i < 4; ++i) if (suits[i] == suit.label) suit_index = i;
    if (suit_index < 0) return Fail(error, "expected-arrangement suit is invalid");
    standard_slots_by_suit[suit_index].push_back(static_cast<int>(slot));
  }

  for (int suit_index = 0; suit_index < 4; ++suit_index) {
    std::vector<int> expected_indices;
    for (size_t i = 0; i < expected.size(); ++i) {
      if (!expected_used[i] && expected[i].joker_id == 0
          && expected[i].suit == suits[suit_index]) {
        expected_indices.push_back(static_cast<int>(i));
      }
    }
    const std::vector<int> &slot_indices = standard_slots_by_suit[suit_index];
    if (slot_indices.size() != expected_indices.size()) {
      return Fail(error, "expected-arrangement suit cardinality mismatch");
    }
    if (slot_indices.empty()) continue;
    std::vector<bool> used(expected_indices.size(), false);
    std::vector<int> current(slot_indices.size(), -1);
    std::vector<int> best;
    double best_total = std::numeric_limits<double>::infinity();
    MatchExpectedRecursive(
      slot_indices, expected_indices, raw, expected,
      0, &used, &current, 0.0, &best_total, &best);
    if (best.size() != slot_indices.size() || !std::isfinite(best_total)) {
      return Fail(error, "expected-arrangement rank assignment has no safe solution");
    }
    for (size_t i = 0; i < slot_indices.size(); ++i) {
      const int expected_index = best[i];
      const int slot = slot_indices[i];
      const COFCRankTemplate *rank_template =
        UprightTemplate(expected[expected_index].rank);
      const double distance = COFCFantasyRecognitionCore::AlignedBinaryDistance(
        raw[slot].rows, rank_template->rows, 2);
      expected_used[expected_index] = true;
      (*cards)[slot].valid = true;
      (*cards)[slot].rank = expected[expected_index].rank;
      (*cards)[slot].suit = expected[expected_index].suit;
      (*cards)[slot].rank_distance = distance;
      (*cards)[slot].rank_margin = 0.0;
    }
  }
  for (size_t i = 0; i < expected_used.size(); ++i)
    if (!expected_used[i]) return Fail(error, "expected physical card was not assigned");
  return true;
}

bool COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
    HBITMAP table_bitmap,
    bool upright,
    const std::vector<std::string> &original_fantasy_cards,
    std::vector<COFCFantasyPixelObject> *objects_left_to_right,
    std::string *error) {
  if (error != NULL) error->clear();
  if (objects_left_to_right == NULL) {
    return Fail(error, "dynamic Fantasy object output is null");
  }
  objects_left_to_right->clear();
  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;

  std::vector<COFCFantasyRankAnchor> anchors;
  std::vector<InkComponentWithPoints> components;
  if (!LocateDynamicAnchors(image, &anchors, &components, error)) return false;
  COFCFantasyGridFit fit;
  if (!COFCFantasyDynamicGeometry::FitRegularGrid(anchors, &fit, error)) return false;

  std::vector<std::string> labels;
  for (size_t i = 0; i < anchors.size(); ++i) {
    const COFCFantasyRankAnchor &anchor = anchors[i];
    const InkComponentWithPoints *rank_component =
      FindComponent(components, anchor.bounds);
    if (rank_component == NULL) {
      return Fail(error, "dynamic Fantasy rank component lineage was lost");
    }
    std::vector<InkPoint> rank_points;
    for (size_t p = 0; p < rank_component->points.size(); ++p) {
      const InkPoint point = rank_component->points[p];
      if (point.x >= anchor.bounds.left && point.x < anchor.bounds.right
          && point.y >= anchor.bounds.top && point.y < anchor.bounds.bottom) {
        rank_points.push_back(point);
      }
    }
    if (rank_points.empty()) {
      return Fail(error, "dynamic Fantasy rank anchor contains no ink pixels");
    }
    COFCFantasy15PixelCard card;
    std::string card_error;
    if (upright) {
      const COFCPixelRect source =
        COFCFantasyDynamicGeometry::CurrentSourceRect(anchor);
      bool empty = false;
      if (!ExtractUprightFeature(
            image, source, &card, &empty, &card_error) || empty) {
        return Fail(error, "upright loose Fantasy card rejected: " + card_error);
      }
    } else {
      uint16_t rows[kDeepOFCGlyphHeight];
      const std::vector<InkPoint> deskewed =
        DeskewDynamicRank(rank_points, anchor.CenterX());
      NormalizeComponent(deskewed, rows);
      double r = 0.0;
      double g = 0.0;
      double b = 0.0;
      MedianRgb(image, rank_points, &r, &g, &b);
      if (!CardFromFeature(
            rows, r, g, b,
            static_cast<int>(rank_points.size()),
            anchor.bounds.Width(),
            anchor.bounds.Height(),
            false, true, &card, &card_error)) {
        return Fail(error, "reflow loose Fantasy card rejected: " + card_error);
      }
    }

    const COFCPixelRect source =
      COFCFantasyDynamicGeometry::CurrentSourceRect(anchor);
    COFCFantasyPixelObject object;
    object.valid = true;
    object.fresh_from_current_bitmap = true;
    object.card = card;
    object.source_rect.left = source.left;
    object.source_rect.top = source.top;
    object.source_rect.right = source.right;
    object.source_rect.bottom = source.bottom;
    object.drag_anchor.x = static_cast<LONG>(std::floor(source.CenterX() + 0.5));
    object.drag_anchor.y = static_cast<LONG>(std::floor(source.CenterY() + 0.5));
    object.detected_layout_count = fit.count;
    object.geometry_residual = fit.maximum_residual;
    objects_left_to_right->push_back(object);
    labels.push_back(card.PhysicalLabel());
  }

  std::string identity_error;
  if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(
        labels, &identity_error)
      || !COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(
        labels, original_fantasy_cards, &identity_error)) {
    objects_left_to_right->clear();
    return Fail(error, identity_error);
  }
  return true;
}

bool COFCFantasy15PixelRecognizer::RecognizeUprightCard(
    HBITMAP table_bitmap,
    const RECT &card_rect,
    COFCFantasy15PixelCard *card,
    std::string *error) {
  if (error != NULL) error->clear();
  if (card == NULL) return Fail(error, "upright card output is null");
  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;
  bool empty = false;
  if (!ExtractUprightFeature(
        image,
        COFCPixelRect(card_rect.left, card_rect.top,
          card_rect.right, card_rect.bottom),
        card, &empty, error)) return false;
  if (empty) return Fail(error, "upright card contains no rank/Joker glyph");
  return true;
}

bool COFCFantasy15PixelRecognizer::DetectPersistentJoker(
    HBITMAP table_bitmap,
    const RECT &card_rect,
    int *joker_id,
    std::string *error) {
  if (error != NULL) error->clear();
  if (joker_id == NULL) return Fail(error, "persistent Joker output is null");
  *joker_id = 0;
  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;
  const int left = card_rect.left + 28;
  const int top = card_rect.top + 3;
  const int right = std::min(card_rect.right, card_rect.left + 53);
  const int bottom = std::min(card_rect.bottom, card_rect.top + 28);
  if (left < 0 || top < 0 || right > image.width || bottom > image.height
      || right <= left || bottom <= top) {
    return Fail(error, "persistent Joker probe is outside bitmap");
  }
  int red_marker = 0;
  int gray_marker = 0;
  for (int y = top; y < bottom; ++y) {
    for (int x = left; x < right; ++x) {
      const Pixel p = image.At(x, y);
      if (p.r > 180 && p.r > p.g + 50 && p.r > p.b + 50) ++red_marker;
      const int maximum = std::max(p.r, std::max(p.g, p.b));
      const int minimum = std::min(p.r, std::min(p.g, p.b));
      const double mean = (p.r + p.g + p.b) / 3.0;
      if (maximum - minimum < 25 && mean >= 50.0 && mean <= 190.0)
        ++gray_marker;
    }
  }
  if (red_marker >= 40 && gray_marker >= 40) {
    return Fail(error, "persistent Joker marker is color-ambiguous");
  }
  if (red_marker >= 40) *joker_id = 1;
  else if (gray_marker >= 40) *joker_id = 2;
  return true;
}
