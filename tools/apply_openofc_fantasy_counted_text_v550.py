from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(rel: str, old: str, new: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected one target, got {count}: {old[:180]!r}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_headers():
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.h"
    anchor = '''  // Rediscovers every currently loose card after a Fantasy drag. `upright`\n'''
    insertion = r'''  // OPENOFC_FANTASY_COUNTED_TEXT_V550. Geometry-only loose-card count.
  // Identity is deliberately NOT inferred here; the selected count tells the
  // scraper which count-specific TableMap rank/suit family to evaluate.
  static bool DetectLooseCount(
      HBITMAP table_bitmap,
      int *loose_count,
      double *score,
      std::string *error);

  // When a T7 rank region returns X, distinguish the two physical KKPoker
  // Jokers by the colored vertical JOKER marker inside that exact rank window.
  static bool ClassifyFanJokerAtRect(
      HBITMAP table_bitmap,
      const RECT &rank_rect,
      int *joker_id,
      std::string *error);

'''
    replace_once(rel, anchor, insertion + anchor)

    rel = "OpenHoldem/COFCFantasyPixelRecognizer.h"
    anchor = '''  static bool RecognizeLooseObjectsUnbound(\n'''
    insertion = r'''  static bool DetectLooseCount(
      HBITMAP table_bitmap,
      int *loose_count,
      double *score,
      std::string *error) {
    return COFCFantasy15PixelRecognizer::DetectLooseCount(
      table_bitmap, loose_count, score, error);
  }

  static bool ClassifyFanJokerAtRect(
      HBITMAP table_bitmap,
      const RECT &rank_rect,
      int *joker_id,
      std::string *error) {
    return COFCFantasy15PixelRecognizer::ClassifyFanJokerAtRect(
      table_bitmap, rank_rect, joker_id, error);
  }

'''
    replace_once(rel, anchor, insertion + anchor)


def patch_recognizer_cpp():
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    path, text, eol, bom = read_source(rel)
    marker = '''}  // namespace\n\nstd::string COFCFantasy15PixelCard::PhysicalLabel() const {\n'''
    if text.count(marker) != 1:
        raise RuntimeError("recognizer namespace marker missing")

    helpers = r'''// OPENOFC_FANTASY_COUNTED_TEXT_V550: measured stable loose-card geometry.
// Counts 06..16 come from the supplied FANTASY.zip replay frames. Count 17 is
// an interpolation from the measured 16-card fan and is kept uncalibrated by
// the TableMap until a real 17-card frame is captured.
struct FantasyCountTemplate {
  int count;
  const double (*points)[2];
};

static const double kFantasyCount06[6][2] = {
  {129.0,667.5},{160.0,664.0},{194.0,661.5},{226.5,661.0},{259.0,662.0},{292.0,664.0}};
static const double kFantasyCount07[7][2] = {
  {113.5,671.0},{145.0,666.0},{177.5,662.0},{210.5,660.5},{243.0,660.5},{275.0,663.0},{308.0,666.0}};
static const double kFantasyCount08[8][2] = {
  {97.0,674.0},{128.0,668.0},{161.0,664.0},{194.0,661.5},{226.5,661.0},{259.0,662.0},{292.0,664.0},{323.5,668.5}};
static const double kFantasyCount09[9][2] = {
  {81.5,678.0},{113.0,670.5},{144.5,666.0},{177.0,662.0},{210.5,660.5},{242.5,661.0},{275.5,663.0},{306.5,666.0},{340.0,672.0}};
static const double kFantasyCount11[11][2] = {
  {50.5,686.5},{80.5,677.0},{112.0,671.0},{145.0,666.0},{177.5,661.5},{210.5,661.0},{243.0,661.0},{274.5,663.0},{308.0,666.0},{339.5,671.5},{373.0,678.5}};
static const double kFantasyCount12[12][2] = {
  {35.0,691.5},{66.0,681.5},{96.5,673.5},{128.5,668.0},{161.5,664.0},{194.0,660.5},{226.5,660.5},{259.5,662.0},{290.5,664.5},{324.5,669.0},{355.5,675.0},{388.5,682.5}};
static const double kFantasyCount13[13][2] = {
  {29.5,693.0},{59.5,683.5},{87.5,676.0},{118.0,670.0},{150.0,667.0},{179.5,662.5},{210.0,660.5},{241.5,661.0},{271.5,663.0},{301.5,665.5},{333.5,670.0},{362.5,676.5},{394.0,684.0}};
static const double kFantasyCount14[14][2] = {
  {29.5,693.5},{55.5,684.5},{83.0,677.0},{110.5,671.0},{138.5,666.0},{168.0,663.0},{196.0,661.5},{224.5,660.5},{253.0,662.0},{281.5,663.5},{307.5,669.0},{337.0,671.0},{366.0,677.0},{394.0,684.0}};
static const double kFantasyCount15[15][2] = {
  {29.5,693.5},{55.0,685.5},{79.5,678.5},{105.0,672.0},{131.0,668.0},{157.0,664.0},{183.5,662.0},{210.5,661.0},{237.0,661.0},{263.5,661.5},{289.5,664.5},{316.0,667.0},{341.5,672.0},{368.5,677.0},{392.5,684.0}};
static const double kFantasyCount16[16][2] = {
  {29.5,693.0},{53.5,685.5},{75.5,678.5},{100.0,673.0},{124.0,669.0},{148.5,665.5},{173.0,662.5},{197.5,661.5},{222.5,661.0},{247.5,661.0},{270.5,663.0},{295.5,665.0},{321.0,668.0},{345.5,672.0},{368.5,678.0},{394.0,684.0}};
static const double kFantasyCount17[17][2] = {
  {29.5,693.0},{52.0,685.969},{72.75,679.375},{95.406,674.031},{118.0,670.0},{140.844,666.594},{163.812,663.625},{186.781,661.938},{210.0,661.25},{233.438,661.0},{256.125,661.75},{278.312,663.625},{301.875,665.75},{325.594,668.75},{348.375,672.75},{370.094,678.375},{394.0,684.0}};

static double CountTemplateScoreWithSkips(
    const std::vector<COFCFantasyRankAnchor> &anchors,
    const double (*expected)[2], int expected_count,
    int skip_a, int skip_b) {
  double total = 0.0;
  int e = 0;
  for (int a = 0; a < static_cast<int>(anchors.size()); ++a) {
    if (a == skip_a || a == skip_b) continue;
    if (e >= expected_count) return 1e100;
    const double dx = anchors[a].CenterX() - expected[e][0];
    const double dy = anchors[a].CenterY() - expected[e][1];
    total += dx * dx + 0.5 * dy * dy;
    ++e;
  }
  if (e != expected_count) return 1e100;
  return std::sqrt(total / expected_count);
}

static double BestCountTemplateScore(
    const std::vector<COFCFantasyRankAnchor> &anchors,
    const double (*expected)[2], int expected_count) {
  const int observed = static_cast<int>(anchors.size());
  const int extras = observed - expected_count;
  if (extras < 0 || extras > 2) return 1e100;
  double best = 1e100;
  if (extras == 0) {
    best = CountTemplateScoreWithSkips(anchors, expected, expected_count, -1, -1);
  } else if (extras == 1) {
    for (int a = 0; a < observed; ++a)
      best = std::min(best,
        CountTemplateScoreWithSkips(anchors, expected, expected_count, a, -1));
  } else {
    for (int a = 0; a < observed; ++a) {
      for (int b = a + 1; b < observed; ++b) {
        best = std::min(best,
          CountTemplateScoreWithSkips(anchors, expected, expected_count, a, b));
      }
    }
  }
  if (!std::isfinite(best)) return 1e100;
  return best + 6.0 * extras;
}

'''
    text = text.replace(marker, helpers + marker, 1)

    anchor = '''bool COFCFantasy15PixelRecognizer::VerifyFrozenModel(std::string *error) {\n'''
    methods = r'''bool COFCFantasy15PixelRecognizer::DetectLooseCount(
    HBITMAP table_bitmap,
    int *loose_count,
    double *score,
    std::string *error) {
  if (error != NULL) error->clear();
  if (loose_count == NULL) return Fail(error, "Fantasy loose-count output is null");
  *loose_count = 0;
  if (score != NULL) *score = 1e100;
  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;
  std::vector<COFCFantasyRankAnchor> anchors;
  std::vector<InkComponentWithPoints> components;
  if (!LocateDynamicAnchors(image, &anchors, &components, error)) return false;

  const FantasyCountTemplate candidates[] = {
    {6,kFantasyCount06},{7,kFantasyCount07},{8,kFantasyCount08},{9,kFantasyCount09},
    {11,kFantasyCount11},{12,kFantasyCount12},{13,kFantasyCount13},{14,kFantasyCount14},
    {15,kFantasyCount15},{16,kFantasyCount16},{17,kFantasyCount17}
  };
  double best = 1e100;
  double second = 1e100;
  int best_count = 0;
  for (size_t i = 0; i < sizeof(candidates) / sizeof(candidates[0]); ++i) {
    const double s = BestCountTemplateScore(
      anchors, candidates[i].points, candidates[i].count);
    if (s < best) {
      second = best;
      best = s;
      best_count = candidates[i].count;
    } else if (s < second) {
      second = s;
    }
  }
  if (!std::isfinite(best) || best > 8.0
      || (std::isfinite(second) && second - best < 3.0)) {
    std::ostringstream oss;
    oss << "Fantasy loose-count geometry ambiguous observed=" << anchors.size()
        << " best=" << best << " second=" << second;
    return Fail(error, oss.str());
  }
  *loose_count = best_count;
  if (score != NULL) *score = best;
  if (error != NULL) error->clear();
  return true;
}

bool COFCFantasy15PixelRecognizer::ClassifyFanJokerAtRect(
    HBITMAP table_bitmap,
    const RECT &rank_rect,
    int *joker_id,
    std::string *error) {
  if (error != NULL) error->clear();
  if (joker_id == NULL) return Fail(error, "Fantasy Joker output is null");
  *joker_id = 0;
  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;
  const int left = std::max(0, static_cast<int>(rank_rect.left));
  const int top = std::max(0, static_cast<int>(rank_rect.top));
  const int right = std::min(image.width, static_cast<int>(rank_rect.right));
  const int bottom = std::min(image.height, static_cast<int>(rank_rect.bottom));
  if (right <= left || bottom <= top)
    return Fail(error, "Fantasy Joker rank rectangle is empty/outside bitmap");
  int red = 0;
  int dark_gray = 0;
  for (int y = top; y < bottom; ++y) {
    for (int x = left; x < right; ++x) {
      const Pixel p = image.At(x, y);
      const int maximum = std::max(p.r, std::max(p.g, p.b));
      const int minimum = std::min(p.r, std::min(p.g, p.b));
      if (p.r > p.g + 35 && p.r > p.b + 35 && p.r > 100) ++red;
      if (maximum < 120 && maximum - minimum < 45) ++dark_gray;
    }
  }
  if (red >= 6 && red > dark_gray) {
    *joker_id = 1;
    return true;
  }
  if (dark_gray >= 6) {
    *joker_id = 2;
    return true;
  }
  std::ostringstream oss;
  oss << "Fantasy X glyph Joker color ambiguous red=" << red
      << " dark=" << dark_gray;
  return Fail(error, oss.str());
}

'''
    if text.count(anchor) != 1:
        raise RuntimeError("VerifyFrozenModel anchor missing")
    text = text.replace(anchor, methods + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: geometry-only count + X/Joker color classifier")


def patch_scraper():
    rel = "OpenHoldem/COFCScraper.cpp"
    path, text, eol, bom = read_source(rel)

    start_token = '''  std::vector<bool> occupied;\n  std::vector<COFCFantasyPixelCard> arrangement_cards;\n  std::vector<COFCFantasyPixelObject> loose;\n  bool loose_pre_recognized = false;\n  std::string recognition_error;\n'''
    start = text.find(start_token)
    end_token = '''  int arrangement_count = 0;\n'''
    end = text.find(end_token, start)
    if start < 0 or end < 0:
        raise RuntimeError("v5.4.10 Fantasy recognition block not found")

    replacement = r'''  std::vector<bool> occupied;
  std::vector<COFCFantasyPixelCard> arrangement_cards;
  std::vector<COFCFantasyPixelObject> loose;
  bool loose_pre_recognized = false;
  bool final_complement_inferred = false;
  std::string recognition_error;

  auto card_from_label = [&](const std::string &label,
      COFCFantasyPixelCard *card) -> bool {
    if (card == NULL) return false;
    *card = COFCFantasyPixelCard();
    if (label == "JK1") { card->valid = true; card->joker_id = 1; return true; }
    if (label == "JK2") { card->valid = true; card->joker_id = 2; return true; }
    if (label.size() != 2) return false;
    const std::string ranks = "23456789TJQKA";
    const std::string suits = "cdhs";
    if (ranks.find(label[0]) == std::string::npos
        || suits.find(label[1]) == std::string::npos) return false;
    card->valid = true;
    card->rank = label[0];
    card->suit = label[1];
    return true;
  };

  auto scrape_text_loose = [&](int loose_count,
      std::vector<COFCFantasyPixelObject> *out,
      std::string *text_error) -> bool {
    if (out == NULL) return false;
    out->clear();
    const bool supported =
      (loose_count >= 6 && loose_count <= 9)
      || (loose_count >= 11 && loose_count <= 17);
    if (!supported) {
      if (text_error != NULL) *text_error = "loose count has no stable text-map family";
      return false;
    }
    if (loose_count == 17
        && p_tablemap->GetTMSymbol("openofc_fantasy17_calibrated", 0) != 1) {
      if (text_error != NULL) *text_error = "17-card Fantasy text geometry is not field-calibrated";
      return false;
    }
    std::set<std::string> labels;
    for (int i = 0; i < loose_count; ++i) {
      CString base;
      base.Format("ofc_fantasy%02d_%02d", loose_count, i);
      const CString rank_region = base + "rank";
      const CString suit_region = base + "suit";
      if (!DeepOFCRegionExists(rank_region) || !DeepOFCRegionExists(suit_region)) {
        if (text_error != NULL) *text_error = "missing count-specific Fantasy rank/suit region";
        out->clear();
        return false;
      }
      CString rank_text;
      CString suit_text;
      if (!EvaluateRegion(rank_region, &rank_text)) {
        if (text_error != NULL) *text_error = "Fantasy T7 rank transform failed";
        out->clear();
        return false;
      }
      rank_text.Trim();
      rank_text.MakeUpper();

      COFCFantasyPixelObject object;
      object.valid = true;
      object.fresh_from_current_bitmap = true;
      object.detected_layout_count = loose_count;
      object.geometry_residual = 0.0;

      if (rank_text == "X") {
        RECT rank_rect;
        if (!DeepOFCReadRegionRect(rank_region, &rank_rect)) {
          if (text_error != NULL) *text_error = "Fantasy X rank rectangle missing";
          out->clear();
          return false;
        }
        int joker_id = 0;
        std::string joker_error;
        if (!COFCFantasyPixelRecognizer::ClassifyFanJokerAtRect(
              _entire_window_cur, rank_rect, &joker_id, &joker_error)) {
          if (text_error != NULL) *text_error = joker_error;
          out->clear();
          return false;
        }
        object.card.valid = true;
        object.card.joker_id = joker_id;
      } else {
        if (!EvaluateRegion(suit_region, &suit_text)) {
          if (text_error != NULL) *text_error = "Fantasy T7 suit transform failed";
          out->clear();
          return false;
        }
        suit_text.Trim();
        suit_text.MakeLower();
        char rank = 0;
        if (rank_text == "10") rank = 'T';
        else if (rank_text.GetLength() == 1) rank = rank_text[0];
        const std::string ranks = "23456789TJQKA";
        if (rank == 0 || ranks.find(rank) == std::string::npos
            || !IsSuitString(suit_text)) {
          if (text_error != NULL) *text_error = "Fantasy T7 rank/suit result is invalid";
          out->clear();
          return false;
        }
        object.card.valid = true;
        object.card.rank = rank;
        object.card.suit = static_cast<char>(tolower(suit_text[0]));
      }

      const std::string label = object.card.PhysicalLabel();
      if (label == "AMBIGUOUS" || !labels.insert(label).second) {
        if (text_error != NULL) *text_error = "Fantasy T7 returned duplicate/ambiguous physical card";
        out->clear();
        return false;
      }
      RECT rank_rect;
      RECT suit_rect;
      if (!DeepOFCReadRegionRect(rank_region, &rank_rect)
          || !DeepOFCReadRegionRect(suit_region, &suit_rect)) {
        if (text_error != NULL) *text_error = "Fantasy T7 source rectangles missing";
        out->clear();
        return false;
      }
      object.source_rect.left = std::min(rank_rect.left, suit_rect.left);
      object.source_rect.top = std::min(rank_rect.top, suit_rect.top);
      object.source_rect.right = std::max(rank_rect.right, suit_rect.right);
      object.source_rect.bottom = std::max(rank_rect.bottom, suit_rect.bottom);
      object.drag_anchor.x = (object.source_rect.left + object.source_rect.right) / 2;
      object.drag_anchor.y = (object.source_rect.top + object.source_rect.bottom) / 2;
      out->push_back(object);
    }
    if (text_error != NULL) text_error->clear();
    return true;
  };

  if (!original_labels.empty()) {
    if (!COFCFantasyPixelRecognizer::RecognizeArrangementOccupancy(
          _entire_window_cur, arrangement_rects, &occupied, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V550] occupancy rejected error=%s terminal=0\n",
        recognition_error.c_str());
      return false;
    }
    int occupied_hint = 0;
    for (size_t i = 0; i < occupied.size(); ++i)
      if (occupied[i]) ++occupied_hint;

    int text_count = 0;
    double count_score = 0.0;
    std::string count_error;
    const bool counted = COFCFantasyPixelRecognizer::DetectLooseCount(
      _entire_window_cur, &text_count, &count_score, &count_error);

    if (counted) {
      if (!scrape_text_loose(text_count, &loose, &recognition_error)) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY V550] text loose rejected count=%d score=%.3f error=%s terminal=0\n",
          text_count, count_score, recognition_error.c_str());
        return false;
      }
      std::set<string> loose_labels;
      for (size_t i = 0; i < loose.size(); ++i)
        loose_labels.insert(loose[i].card.PhysicalLabel());
      std::vector<string> expected_arrangement;
      for (size_t i = 0; i < original_labels.size(); ++i) {
        if (loose_labels.find(original_labels[i]) == loose_labels.end())
          expected_arrangement.push_back(original_labels[i]);
      }
      if (expected_arrangement.size() != static_cast<size_t>(occupied_hint)) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY V550] lineage partition mismatch prior=%d occupied=%d loose=%d expected_arranged=%d terminal=0\n",
          static_cast<int>(original_labels.size()), occupied_hint,
          static_cast<int>(loose.size()), static_cast<int>(expected_arrangement.size()));
        return false;
      }
      if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
            _entire_window_cur, arrangement_rects, expected_arrangement,
            &occupied, &arrangement_cards, &recognition_error)) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY V550] expected arrangement rejected count=%d error=%s terminal=0\n",
          text_count, recognition_error.c_str());
        return false;
      }
      loose_pre_recognized = true;
      write_log(true,
        "[OpenOFC FANTASY V550] count=%d score=%.3f identity=TABLEMAP_T7 occupied=%d\n",
        text_count, count_score, occupied_hint);
    } else if (occupied_hint == 13) {
      // Final bottom-row commit: 1..4 unused cards remain, but no further click
      // source is needed. Verify the fixed 13-card board and infer the unused
      // physical cards by exact lineage after the arrangement loop below.
      if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
            _entire_window_cur, arrangement_rects,
            &occupied, &arrangement_cards, &recognition_error)) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY V550] final arrangement strict verification failed error=%s terminal=0\n",
          recognition_error.c_str());
        return false;
      }
      write_log(true,
        "[OpenOFC FANTASY V550] count=FINAL_COMPLEMENT occupied=13 count_detail=%s\n",
        count_error.c_str());
    } else {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V550] loose count rejected occupied=%d error=%s terminal=0\n",
        occupied_hint, count_error.c_str());
      return false;
    }
  } else {
    if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
          _entire_window_cur, arrangement_rects,
          &occupied, &arrangement_cards, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V550] initial arrangement rejected error=%s terminal=0\n",
        recognition_error.c_str());
      return false;
    }
  }

'''
    text = text[:start] + replacement + text[end:]

    old = r'''  if (!loose_pre_recognized) {
    const bool upright = arrangement_count == 13;
    const bool ok = original_labels.empty()
      ? COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(
          _entire_window_cur, upright, &loose, &recognition_error)
      : COFCFantasyPixelRecognizer::RecognizeLooseObjectsBound(
          _entire_window_cur, upright, original_labels, &loose, &recognition_error);
    if (!ok) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY] loose recognition rejected arranged=%d error=%s terminal=0\n",
        arrangement_count, recognition_error.c_str());
      return false;
    }
  }
'''
    new = r'''  if (!loose_pre_recognized) {
    if (arrangement_count == 13 && !original_labels.empty()) {
      std::set<string> arranged(arrangement_labels.begin(), arrangement_labels.end());
      for (std::set<string>::const_iterator it = arranged.begin(); it != arranged.end(); ++it) {
        if (std::find(original_labels.begin(), original_labels.end(), *it)
            == original_labels.end()) {
          write_log(k_always_log_errors,
            "[OpenOFC FANTASY V550] final board contains off-lineage card=%s terminal=0\n",
            it->c_str());
          return false;
        }
      }
      for (size_t i = 0; i < original_labels.size(); ++i) {
        if (arranged.find(original_labels[i]) != arranged.end()) continue;
        COFCFantasyPixelObject object;
        if (!card_from_label(original_labels[i], &object.card)) return false;
        object.valid = true;
        object.fresh_from_current_bitmap = false;
        loose.push_back(object);
      }
      const int expected_unused = static_cast<int>(original_labels.size()) - 13;
      if (static_cast<int>(loose.size()) != expected_unused
          || expected_unused < 1 || expected_unused > 4) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY V550] final complement cardinality invalid prior=%d arranged=%d unused=%d terminal=0\n",
          static_cast<int>(original_labels.size()), arrangement_count,
          static_cast<int>(loose.size()));
        return false;
      }
      final_complement_inferred = true;
      write_log(true,
        "[OpenOFC FANTASY V550] final_unused=LINEAGE_COMPLEMENT count=%d no_source_required=1\n",
        static_cast<int>(loose.size()));
    } else {
      int text_count = 0;
      double count_score = 0.0;
      std::string count_error;
      if (!COFCFantasyPixelRecognizer::DetectLooseCount(
            _entire_window_cur, &text_count, &count_score, &count_error)
          || !scrape_text_loose(text_count, &loose, &recognition_error)) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY V550] initial/text loose recognition rejected arranged=%d count=%d count_error=%s text_error=%s terminal=0\n",
          arrangement_count, text_count, count_error.c_str(), recognition_error.c_str());
        return false;
      }
      write_log(true,
        "[OpenOFC FANTASY V550] count=%d score=%.3f identity=TABLEMAP_T7 bootstrap=%d\n",
        text_count, count_score, original_labels.empty() ? 1 : 0);
    }
  }
'''
    if text.count(old) != 1:
        raise RuntimeError("native loose-recognition tail block not found")
    text = text.replace(old, new, 1)

    old_loop = r'''    const int value = DeepOFCPixelCardValue(loose[i].card);
    if (value < 0 || !loose[i].valid || !loose[i].fresh_from_current_bitmap)
      return false;
    obs->hero_loose_cards[i].value = value;
    obs->hero_loose_sources[i].valid = true;
    obs->hero_loose_sources[i].card_value = value;
    obs->hero_loose_sources[i].rect = loose[i].source_rect;
    ++obs->hero_loose_count;
'''
    new_loop = r'''    const int value = DeepOFCPixelCardValue(loose[i].card);
    if (value < 0 || !loose[i].valid
        || (!loose[i].fresh_from_current_bitmap && !final_complement_inferred))
      return false;
    obs->hero_loose_cards[i].value = value;
    obs->hero_loose_sources[i].valid = loose[i].fresh_from_current_bitmap;
    obs->hero_loose_sources[i].card_value = value;
    if (loose[i].fresh_from_current_bitmap)
      obs->hero_loose_sources[i].rect = loose[i].source_rect;
    ++obs->hero_loose_count;
'''
    if text.count(old_loop) != 1:
        raise RuntimeError("Fantasy loose observation loop not found")
    text = text.replace(old_loop, new_loop, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}: count-first TableMap T7 loose identity + final complement")


def main():
    patch_headers()
    patch_recognizer_cpp()
    patch_scraper()
    print(
      "OPENOFC_FANTASY_COUNTED_TEXT_V550_MATERIALIZATION=PASS "
      "count=GEOMETRY_ONLY identity=TABLEMAP_T7 stable_counts=6,7,8,9,11,12,13,14,15,16,17 "
      "final_1_4=LINEAGE_COMPLEMENT"
    )


if __name__ == "__main__":
    main()
