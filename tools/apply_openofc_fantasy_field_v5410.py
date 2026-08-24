from __future__ import annotations

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
        raise RuntimeError(f"{rel}: expected one target, got {count}: {old[:160]!r}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_dynamic_geometry():
    rel = "OpenHoldem/COFCFantasyDynamicGeometry.h"
    anchor = '''  static COFCPixelRect RecognitionPatch(const COFCFantasyRankAnchor &anchor) {\n'''
    method = r'''  // OPENOFC_FANTASY_FIELD_V5410: the KKPoker initial 15-card fan is
  // deliberately curved. A regular-grid residual therefore rejects a valid
  // field frame by construction (3.75 px versus the old 3.5 px limit).
  // This fallback validates the measured non-uniform 15-card fan profile under
  // a small affine x translation/scale. It is count-specific and never weakens
  // the generic 14..17 regular-grid gate.
  static bool FitMeasuredInitialFan15(
      const std::vector<COFCFantasyRankAnchor> &anchors,
      COFCFantasyGridFit *fit,
      std::string *error,
      double allowed_residual = 3.0) {
    if (fit == NULL) return Fail(error, "initial Fantasy fan output is null");
    *fit = COFCFantasyGridFit();
    if (anchors.size() != 15) {
      return Fail(error, "measured initial Fantasy fan requires exactly 15 anchors");
    }
    static const double expected[15] = {
      28.0, 54.0, 79.0, 105.0, 131.0,
      158.0, 184.0, 210.0, 237.0, 263.0,
      289.0, 316.0, 343.0, 370.0, 396.0
    };
    std::vector<double> actual;
    actual.reserve(15);
    for (size_t i = 0; i < anchors.size(); ++i)
      actual.push_back(anchors[i].CenterX());
    std::sort(actual.begin(), actual.end());

    // Least-squares affine fit actual ~= offset + scale * expected.
    double sum_x = 0.0, sum_y = 0.0, sum_xx = 0.0, sum_xy = 0.0;
    for (int i = 0; i < 15; ++i) {
      sum_x += expected[i];
      sum_y += actual[i];
      sum_xx += expected[i] * expected[i];
      sum_xy += expected[i] * actual[i];
    }
    const double n = 15.0;
    const double denom = n * sum_xx - sum_x * sum_x;
    if (std::fabs(denom) < 1e-9) {
      return Fail(error, "measured initial Fantasy fan affine fit is singular");
    }
    const double scale = (n * sum_xy - sum_x * sum_y) / denom;
    const double offset = (sum_y - scale * sum_x) / n;
    if (scale < 0.97 || scale > 1.03) {
      return Fail(error, "measured initial Fantasy fan scale is out of range");
    }
    double residual = 0.0;
    for (int i = 0; i < 15; ++i) {
      const double predicted = offset + scale * expected[i];
      residual = std::max(residual, std::fabs(actual[i] - predicted));
    }
    if (residual > allowed_residual) {
      return Fail(error, "measured initial Fantasy fan profile residual is too high");
    }
    fit->valid = true;
    fit->count = 15;
    fit->center = offset + scale * expected[7];
    fit->pitch = scale * 26.0;  // diagnostic only; profile itself is non-uniform.
    fit->maximum_residual = residual;
    if (error != NULL) error->clear();
    return true;
  }

'''
    replace_once(rel, anchor, method + anchor)


def patch_recognizer_header():
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.h"
    anchor = '''  // Final 13-card arrangement matcher. It constrains the upright glyphs to an\n'''
    declaration = r'''  // Occupancy-only arrangement pass. Card identity is intentionally omitted.
  // It is used after a Fantasy deal has a certified physical-card lineage so
  // weak per-glyph rank margins can be resolved globally against that lineage.
  static bool RecognizeArrangementOccupancy(
      HBITMAP table_bitmap,
      const std::vector<RECT> &slots,
      std::vector<bool> *occupied,
      std::string *error);

'''
    replace_once(rel, anchor, declaration + anchor)


def patch_recognizer_cpp():
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"

    anchor = '''  std::vector<InkComponentWithPoints> components;\n  ConnectedInkComponents(image, roi, true, 140, &components);\n'''
    brightness = r'''  // OPENOFC_FANTASY_FIELD_V5410: card-face occupancy gate.
  // Field fixtures show a very large separation: empty green slots have 0%
  // bright substrate pixels here, while occupied upright cards are ~65-80%.
  // Use a deliberately low 20% threshold to reject only obvious empty UI.
  int bright_face_pixels = 0;
  int face_pixels = 0;
  for (int y = roi.top; y < roi.bottom; ++y) {
    for (int x = roi.left; x < roi.right; ++x) {
      const Pixel p = image.At(x, y);
      const double mean = (p.r + p.g + p.b) / 3.0;
      if (mean >= 165.0 && std::max(p.r, std::max(p.g, p.b)) >= 175)
        ++bright_face_pixels;
      ++face_pixels;
    }
  }
  if (face_pixels <= 0 || bright_face_pixels * 5 < face_pixels) {
    feature->empty = true;
    return true;
  }

  std::vector<InkComponentWithPoints> components;
  ConnectedInkComponents(image, roi, true, 140, &components);
'''
    replace_once(rel, anchor, brightness)

    anchor2 = '''bool COFCFantasy15PixelRecognizer::RecognizeArrangementSlotsAgainstExpected(\n'''
    occupancy_func = r'''bool COFCFantasy15PixelRecognizer::RecognizeArrangementOccupancy(
    HBITMAP table_bitmap,
    const std::vector<RECT> &slots,
    std::vector<bool> *occupied,
    std::string *error) {
  if (error != NULL) error->clear();
  if (occupied == NULL) return Fail(error, "Fantasy occupancy output is null");
  occupied->clear();
  Image image;
  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;
  for (size_t i = 0; i < slots.size(); ++i) {
    const RECT &slot = slots[i];
    UprightRawFeature raw;
    if (!ExtractUprightRaw(
          image, COFCPixelRect(slot.left, slot.top, slot.right, slot.bottom),
          &raw, error)) {
      occupied->clear();
      return false;
    }
    occupied->push_back(!raw.empty);
  }
  return true;
}

'''
    replace_once(rel, anchor2, occupancy_func + anchor2)

    old = '''  COFCFantasyGridFit fit;\n  if (!COFCFantasyDynamicGeometry::FitRegularGrid(anchors, &fit, error)) return false;\n\n  std::vector<std::string> labels;\n'''
    new = r'''  COFCFantasyGridFit fit;
  std::string regular_grid_error;
  if (!COFCFantasyDynamicGeometry::FitRegularGrid(
        anchors, &fit, &regular_grid_error)) {
    bool geometry_recovered = false;
    if (!upright && anchors.size() == 15) {
      std::string fan_error;
      geometry_recovered =
        COFCFantasyDynamicGeometry::FitMeasuredInitialFan15(
          anchors, &fit, &fan_error);
      if (!geometry_recovered && error != NULL)
        *error = regular_grid_error + "; fan15=" + fan_error;
    }
    if (!geometry_recovered && !upright && !original_fantasy_cards.empty()) {
      // Once the exact deal lineage is known, geometry is only a source-object
      // locator. Identity still has to be unique and a subset of the exact
      // physical deal, so a small residual allowance does not create cards.
      geometry_recovered =
        COFCFantasyDynamicGeometry::FitRegularGrid(
          anchors, &fit, error, 24.0, 42.0, 5.5);
    }
    if (!geometry_recovered) {
      if (error != NULL && error->empty()) *error = regular_grid_error;
      return false;
    }
  }

  std::vector<std::string> labels;
'''
    replace_once(rel, old, new)


def patch_generic_wrapper():
    rel = "OpenHoldem/COFCFantasyPixelRecognizer.h"
    anchor = '''  static bool RecognizeArrangementSlotsAgainstExpected(\n'''
    wrapper = r'''  static bool RecognizeArrangementOccupancy(
      HBITMAP table_bitmap,
      const std::vector<RECT> &slots,
      std::vector<bool> *occupied,
      std::string *error) {
    return COFCFantasy15PixelRecognizer::RecognizeArrangementOccupancy(
      table_bitmap, slots, occupied, error);
  }

'''
    replace_once(rel, anchor, wrapper + anchor)


def patch_scraper_lineage_path():
    rel = "OpenHoldem/COFCScraper.cpp"
    path, text, eol, bom = read_source(rel)
    start_token = '''  std::vector<bool> occupied;\n  std::vector<COFCFantasyPixelCard> arrangement_cards;\n  std::vector<COFCFantasyPixelObject> loose;\n  bool loose_pre_recognized = false;\n  std::string recognition_error;\n'''
    start = text.find(start_token)
    if start < 0:
        raise RuntimeError(f"{rel}: Fantasy recognition block start missing")
    end_token = '''  int arrangement_count = 0;\n'''
    end = text.find(end_token, start)
    if end < 0:
        raise RuntimeError(f"{rel}: Fantasy recognition block end missing")

    replacement = r'''  std::vector<bool> occupied;
  std::vector<COFCFantasyPixelCard> arrangement_cards;
  std::vector<COFCFantasyPixelObject> loose;
  bool loose_pre_recognized = false;
  std::string recognition_error;

  if (!original_labels.empty()) {
    // OPENOFC_FANTASY_FIELD_V5410: after one exact Fantasy frame, use the
    // physical deal itself as the identity authority. First determine only which
    // arrangement slots contain cards (bright card-face substrate), then
    // recognize the remaining loose cards as a strict subset of the prior deal,
    // and finally solve arranged identities one-to-one against the complement.
    if (!COFCFantasyPixelRecognizer::RecognizeArrangementOccupancy(
          _entire_window_cur, arrangement_rects, &occupied, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V5410] occupancy rejected error=%s terminal=0\n",
        recognition_error.c_str());
      return false;
    }
    int occupied_hint = 0;
    for (size_t i = 0; i < occupied.size(); ++i)
      if (occupied[i]) ++occupied_hint;

    const bool loose_upright = occupied_hint == 13;
    if (!COFCFantasyPixelRecognizer::RecognizeLooseObjectsBound(
          _entire_window_cur, loose_upright, original_labels,
          &loose, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V5410] lineage loose rejected occupied=%d upright=%d error=%s terminal=0\n",
        occupied_hint, loose_upright ? 1 : 0, recognition_error.c_str());
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
        "[OpenOFC FANTASY V5410] lineage partition mismatch prior=%d occupied=%d loose=%d expected_arranged=%d terminal=0\n",
        static_cast<int>(original_labels.size()), occupied_hint,
        static_cast<int>(loose.size()),
        static_cast<int>(expected_arrangement.size()));
      return false;
    }
    if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
          _entire_window_cur, arrangement_rects, expected_arrangement,
          &occupied, &arrangement_cards, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V5410] lineage arrangement rejected occupied=%d error=%s terminal=0\n",
        occupied_hint, recognition_error.c_str());
      return false;
    }
    loose_pre_recognized = true;
    write_log(true,
      "[OpenOFC FANTASY V5410] recognition=LINEAGE_CONSTRAINED occupied=%d loose=%d total=%d\n",
      occupied_hint, static_cast<int>(loose.size()),
      occupied_hint + static_cast<int>(loose.size()));
  } else {
    if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
          _entire_window_cur, arrangement_rects,
          &occupied, &arrangement_cards, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY] arrangement rejected strict=%s fallback=NO_PRIOR_LINEAGE terminal=0\n",
        recognition_error.c_str());
      return false;
    }
  }

'''
    text = text[:start] + replacement + text[end:]
    write_source(path, text, eol, bom)
    print(f"patched {rel}: lineage-constrained partial Fantasy recognition")


def main():
    patch_dynamic_geometry()
    patch_recognizer_header()
    patch_recognizer_cpp()
    patch_generic_wrapper()
    patch_scraper_lineage_path()
    print(
      "OPENOFC_FANTASY_FIELD_V5410_MATERIALIZATION=PASS "
      "empty_slot=BRIGHT_FACE_GATE fan15=PROFILE_FALLBACK "
      "partial=LINEAGE_CONSTRAINED regular_thresholds=UNCHANGED"
    )


if __name__ == "__main__":
    main()
