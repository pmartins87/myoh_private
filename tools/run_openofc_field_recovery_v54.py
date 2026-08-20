from __future__ import annotations

import apply_openofc_field_recovery_v54 as v54


_original_replace_once = v54.replace_once
_original_regex_once = v54.regex_once


def replace_once_contextual(rel: str, old: str, new: str):
    recognizer_tail = (
        rel == "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
        and old.startswith("  std::string identity_error;\n")
        and "RequirePhysicalCardLineage" in old
        and "RecognizeUprightCard" in old
    )
    if not recognizer_tail:
        return _original_replace_once(rel, old, new)

    path, text, eol, bom = v54.read_source(rel)
    function_start = text.find(
        "bool COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(")
    function_end = text.find(
        "bool COFCFantasy15PixelRecognizer::RecognizeUprightCard(",
        function_start + 1)
    if function_start < 0 or function_end < 0:
        raise RuntimeError("v5.4 current-loose function boundary missing")

    segment = text[function_start:function_end]
    identity_pos = segment.rfind("  std::string identity_error;")
    if identity_pos < 0:
        raise RuntimeError("v5.4 current-loose identity tail marker missing")

    replacement = '''  std::string identity_error;\n  if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(\n        labels, &identity_error)) {\n    objects_left_to_right->clear();\n    return Fail(error, identity_error);\n  }\n  if (original_fantasy_cards.empty()) {\n    // OPENOFC_FANTASY_UNBOUND_RECONNECT_V54: used for a fresh attachment or\n    // initial 14..17 fan. Total-card validation remains in the OFC scraper,\n    // where tentative board cards and loose cards can be counted together.\n    return true;\n  }\n  if (!COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(\n        labels, original_fantasy_cards, &identity_error)) {\n    objects_left_to_right->clear();\n    return Fail(error, identity_error);\n  }\n  return true;\n}\n\n'''
    segment = segment[:identity_pos] + replacement
    text = text[:function_start] + segment + text[function_end:]
    v54.write_source(path, text, eol, bom)
    print(f"patched {rel}: positional current-loose lineage")


def _replace_span(rel: str, start_marker: str, end_marker: str, replacement: str):
    path, text, eol, bom = v54.read_source(rel)
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"{rel}: structural start marker missing: {start_marker[:100]!r}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise RuntimeError(f"{rel}: structural end marker missing: {end_marker[:100]!r}")
    text = text[:start] + replacement + text[end + len(end_marker):]
    v54.write_source(path, text, eol, bom)
    print(f"patched {rel}: structural span")


def regex_once_contextual(rel: str, pattern: str, replacement: str):
    if rel == "OpenHoldem/COFCScraper.cpp" and pattern.startswith(
        "bool CScraper::ScrapeOFCFantasyVisualObservation"
    ):
        _replace_span(
            rel,
            "bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {",
            "bool CScraper::ScrapeOFCVisualObservation() {",
            replacement,
        )
        return

    if rel == "OpenHoldem/COFCScraper.cpp" and "fantasy_active" in pattern:
        _replace_span(
            rel,
            "  // Route Fantasy BEFORE touching normal Hero row/incoming geometry.",
            "  int visible_joker_count = 0;",
            replacement,
        )
        return

    return _original_regex_once(rel, pattern, replacement)


def ensure_native_mode_definition():
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    path, text, eol, bom = v54.read_source(rel)
    if "COFCFantasy15PixelRecognizer::DetectFantasyMode" in text:
        return
    anchor = "bool COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects("
    pos = text.find(anchor)
    if pos < 0:
        raise RuntimeError("v5.4 could not locate RecognizeCurrentLooseObjects for native mode definition")
    method = '''bool COFCFantasy15PixelRecognizer::DetectFantasyMode(\n    HBITMAP table_bitmap, bool *active, std::string *error) {\n  if (error != NULL) error->clear();\n  if (active == NULL) return Fail(error, "Fantasy mode output is null");\n  *active = false;\n  Image image;\n  if (!ReadTopDownRgb(table_bitmap, &image, error)) return false;\n  const int points[4][2] = {\n    {225, 740}, {225, 760}, {170, 780}, {280, 780}\n  };\n  int brown = 0;\n  for (int i = 0; i < 4; ++i) {\n    const Pixel p = image.At(points[i][0], points[i][1]);\n    if (std::abs(static_cast<int>(p.r) - 135) <= 28\n        && std::abs(static_cast<int>(p.g) - 76) <= 24\n        && p.b <= 35) {\n      ++brown;\n    }\n  }\n  *active = brown >= 3;\n  return true;\n}\n\n'''
    text = text[:pos] + method + text[pos:]
    v54.write_source(path, text, eol, bom)
    print(f"patched {rel}: ensured DetectFantasyMode definition")


def ensure_phase_marker_helpers():
    rel = "OpenHoldem/COFCScraper.cpp"
    path, text, eol, bom = v54.read_source(rel)
    if "static void OpenOFCScrapePhaseMarkers(" in text:
        return
    anchor = "bool CScraper::ScrapeOFCVisualObservation() {"
    pos = text.find(anchor)
    if pos < 0:
        raise RuntimeError("v5.4 could not locate ScrapeOFCVisualObservation for phase helpers")
    helper = r'''
static bool OpenOFCReadOptionalBoolean(
    CScraper *scraper, const CString &region, bool *value) {
  if (scraper == NULL || value == NULL) return false;
  *value = false;
  if (!DeepOFCRegionExists(region)) return false;
  scraper->EvaluateTrueFalseRegion(value, region);
  return true;
}

static void OpenOFCScrapePhaseMarkers(
    CScraper *scraper,
    COFCVisualObservation *obs,
    int player_count,
    int hero_chair) {
  if (scraper == NULL || obs == NULL) return;

  if (player_count == 2 && hero_chair >= 0 && hero_chair < 2) {
    const int opponent = 1 - hero_chair;
    int faceup = 0;
    for (int i = 0; i < 3; ++i) {
      CString empty_region, back_region;
      empty_region.Format("ofc_p%d_discard%dempty", opponent, i);
      back_region.Format("ofc_p%d_discard%dback", opponent, i);
      bool empty = true;
      bool back = false;
      const bool have_empty =
        OpenOFCReadOptionalBoolean(scraper, empty_region, &empty);
      const bool have_back =
        OpenOFCReadOptionalBoolean(scraper, back_region, &back);
      if (have_empty && have_back && !empty && !back) ++faceup;
    }
    obs->opponent_result_faceup_discards = faceup;
    obs->result_screen_visible = faceup >= 2;
  }

  bool per_player_fantasy[kOFCMaxPlayers] = {false, false, false};
  for (int p = 0; p < player_count; ++p) {
    int hits = 0;
    for (int i = 0; i < 3; ++i) {
      CString region;
      region.Format("ofc_p%d_result_fantasy%d", p, i);
      bool value = false;
      if (OpenOFCReadOptionalBoolean(scraper, region, &value) && value) {
        ++hits;
      }
    }
    per_player_fantasy[p] = hits >= 2;
  }
  if (hero_chair >= 0 && hero_chair < player_count) {
    obs->hero_result_fantasy = per_player_fantasy[hero_chair];
    if (player_count == 2) {
      obs->opponent_result_fantasy = per_player_fantasy[1 - hero_chair];
    }
  }

  if (obs->result_screen_visible
      || obs->hero_result_fantasy
      || obs->opponent_result_fantasy) {
    write_log(true,
      "[OpenOFC PHASE] result=%d opp_faceup_discards=%d hero_fantasy=%d opponent_fantasy=%d\n",
      obs->result_screen_visible ? 1 : 0,
      obs->opponent_result_faceup_discards,
      obs->hero_result_fantasy ? 1 : 0,
      obs->opponent_result_fantasy ? 1 : 0);
  }
}

'''
    text = text[:pos] + helper + text[pos:]
    v54.write_source(path, text, eol, bom)
    print(f"patched {rel}: restored phase-marker helpers")


v54.replace_once = replace_once_contextual
v54.regex_once = regex_once_contextual

if __name__ == "__main__":
    v54.main()
    ensure_native_mode_definition()
    ensure_phase_marker_helpers()
