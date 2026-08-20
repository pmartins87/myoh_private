from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_text(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def rewrite(rel: str, old: str, new: str, expected: int = 1):
    path, text, eol, bom = read_text(rel)
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{rel}: expected {expected} generic-Fantasy normalization target(s), got {count}")
    text = text.replace(old, new, expected)
    write_text(path, text, eol, bom)


def restore_phase_marker_helpers():
    """Repair composition with the frozen v4 phase patch.

    The legacy v5.4.3 replacement originally matched from the Fantasy scraper
    through the next ScrapeOFCVisualObservation declaration. The frozen v4
    patch inserts its result/Fantasy-continuation helpers between those two
    functions, so that broad replacement could remove the helper definitions
    while leaving the call site intact. Preserve the v4 contract explicitly.
    """
    rel = "OpenHoldem/COFCScraper.cpp"
    path, text, eol, bom = read_text(rel)

    have_optional = "static bool OpenOFCReadOptionalBoolean(" in text
    have_phase = "static void OpenOFCScrapePhaseMarkers(" in text
    if have_optional and have_phase:
        print("v4 phase-marker helpers already preserved")
        return
    if have_optional != have_phase:
        raise RuntimeError("COFCScraper.cpp: partial v4 phase-marker helper set survived; refusing duplicate/ambiguous repair")

    call = "OpenOFCScrapePhaseMarkers(this, obs, player_count, hero_chair);"
    if call not in text:
        raise RuntimeError("COFCScraper.cpp: v4 phase-marker call site missing after v5.4.3")

    anchor = "bool CScraper::ScrapeOFCVisualObservation() {"
    if text.count(anchor) != 1:
        raise RuntimeError("COFCScraper.cpp: expected one ScrapeOFCVisualObservation anchor")

    helpers = r'''static bool OpenOFCReadOptionalBoolean(
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

  // Terminal result marker: opponent discards are face-up only on the scoring
  // result screen. During R1..R4 they are hidden backs. Identity is irrelevant,
  // so missing T2 K/X can never suppress this end-of-hand signal.
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
    // Two-of-three avoids a single animated score/gold pixel becoming Fantasy.
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
    text = text.replace(anchor, helpers + anchor, 1)
    write_text(path, text, eol, bom)
    print("restored frozen v4 phase-marker helpers after generic Fantasy replacement")


# The frozen v5.3 policy regression fixtures predate fantasy_card_count. Their
# two 15-card fixtures remain useful, but count is now explicit data rather than
# a runtime mode. Mark the fixture data truthfully after v5.4.3 materializes.
rewrite(
    "OpenHoldem/COFCBaselinePolicySelftest.cpp",
    '''  state.hero_incoming_count = 15;\n  for (int i = 0; i < 15; ++i) state.hero_incoming[i].value = cards[i];\n''',
    '''  state.fantasy_card_count = 15;\n  state.hero_incoming_count = 15;\n  for (int i = 0; i < 15; ++i) state.hero_incoming[i].value = cards[i];\n''',
    expected=2)

restore_phase_marker_helpers()

print("normalized legacy 15-card policy fixtures and preserved v4 phase-marker helpers")
