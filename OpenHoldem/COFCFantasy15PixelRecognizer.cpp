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
#include "COFCFantasy15PixelModel.generated.h"

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

  std::string model_error;
  if (!VerifyFrozenModel(&model_error)) {
    return Fail(error, model_error);
  }

  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;

  std::set<std::string> seen;
  for (int i = 0; i < kFanSlots; ++i) {
    COFCFantasy15PixelCard card;
    std::string slot_error;
    if (!RecognizePatch(image, kInitialFanRects[i], &card, &slot_error)) {
      cards_left_to_right->clear();
      std::ostringstream oss;
      oss << "Fantasy15 slot " << i << " failed closed: " << slot_error;
      return Fail(error, oss.str());
    }
    const std::string label = card.PhysicalLabel();
    if (label == "AMBIGUOUS" || !seen.insert(label).second) {
      cards_left_to_right->clear();
      std::ostringstream oss;
      oss << "Fantasy15 slot " << i
          << " produced ambiguous/duplicate physical card " << label;
      return Fail(error, oss.str());
    }
    cards_left_to_right->push_back(card);
  }

  if (cards_left_to_right->size() != kFanSlots) {
    cards_left_to_right->clear();
    return Fail(error, "Fantasy15 fan did not produce exactly 15 physical cards");
  }
  return true;
}
