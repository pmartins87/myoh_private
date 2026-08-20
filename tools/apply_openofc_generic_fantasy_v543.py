from __future__ import annotations

from pathlib import Path
import re

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
        raise RuntimeError(
            f"{rel}: expected one target, got {count}: {old[:180]!r}"
        )
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def regex_once(rel: str, pattern: str, replacement: str, flags=re.S):
    path, text, eol, bom = read_source(rel)
    new, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(
            f"{rel}: regex expected one target, got {count}: {pattern[:180]}"
        )
    write_source(path, new, eol, bom)
    print(f"patched {rel}")


def patch_fantasy_count_contract():
    for rel in ("OpenHoldem/COFCVisualObservation.h", "OpenHoldem/COFCState.h"):
        replace_once(
            rel,
            '''    round_index = -1;\n    hero_can_prepare = false;\n''',
            '''    round_index = -1;\n    // OPENOFC_GENERIC_FANTASY_V543: one Fantasy state; count is data.\n    fantasy_card_count = 0;\n    hero_can_prepare = false;\n''')
        replace_once(
            rel,
            '''  int round_index;\n  bool hero_can_prepare;\n''',
            '''  int round_index;\n  // Zero outside Fantasy; 14..17 while Hero is in Fantasy.\n  int fantasy_card_count;\n  bool hero_can_prepare;\n''')


def patch_tablemap_generic_gate():
    rel = "CTablemap/CTablemap.h"
    replace_once(
        rel,
        '''\tconst bool OFCFantasy15GeometryMeasured() {\n\t\treturn GetTMSymbol("ofc_fantasy15_geometry_measured", 0) == 1;\n\t}\n''',
        '''\t// OPENOFC_GENERIC_FANTASY_V543. New packages use the generic symbol.\n\t// The old count-specific symbol is accepted only as a compatibility alias\n\t// for already-captured 450x830 tablemaps; runtime semantics stay 14..17.\n\tconst bool OFCFantasyGeometryMeasured() {\n\t\tconst int generic = GetTMSymbol("ofc_fantasy_geometry_measured", -1);\n\t\tif (generic >= 0) return generic == 1;\n\t\treturn GetTMSymbol("ofc_fantasy15_geometry_measured", 0) == 1;\n\t}\n\tconst bool OFCFantasy15GeometryMeasured() {\n\t\treturn OFCFantasyGeometryMeasured();  // legacy API alias only\n\t}\n''')


def patch_dynamic_recognizer_unbound_mode():
    rel = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    old = '''  std::string identity_error;\n  if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(\n        labels, &identity_error)\n      || !COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(\n        labels, original_fantasy_cards, &identity_error)) {\n    objects_left_to_right->clear();\n    return Fail(error, identity_error);\n  }\n  return true;\n}\n\nbool COFCFantasy15PixelRecognizer::RecognizeUprightCard(\n'''
    new = '''  std::string identity_error;\n  if (!COFCFantasyDynamicGeometry::RequireUniquePhysicalCards(\n        labels, &identity_error)) {\n    objects_left_to_right->clear();\n    return Fail(error, identity_error);\n  }\n  // OPENOFC_GENERIC_FANTASY_V543: an empty lineage means bootstrap from the\n  // current screen. Recognition still requires unique exact physical cards and\n  // regular current geometry; only the stale-process subset check is omitted.\n  if (!original_fantasy_cards.empty()\n      && !COFCFantasyDynamicGeometry::RequirePhysicalCardLineage(\n        labels, original_fantasy_cards, &identity_error)) {\n    objects_left_to_right->clear();\n    return Fail(error, identity_error);\n  }\n  return true;\n}\n\nbool COFCFantasy15PixelRecognizer::RecognizeUprightCard(\n'''
    replace_once(rel, old, new)


def patch_scraper_generic_fantasy():
    rel = "OpenHoldem/COFCScraper.cpp"
    path, text, eol, bom = read_source(rel)
    if '#include "COFCFantasy15PixelRecognizer.h"\n' not in text:
        raise RuntimeError("legacy Fantasy recognizer include missing")
    text = text.replace(
        '#include "COFCFantasy15PixelRecognizer.h"\n',
        '#include "COFCFantasyPixelRecognizer.h"\n', 1)
    text = text.replace("COFCFantasy15PixelCard", "COFCFantasyPixelCard")
    write_source(path, text, eol, bom)

    # Runtime-facing raw log now surfaces the generic count explicitly.
    replace_once(
        rel,
        '''    "round=%d prepare=%d confirm=%d loose=%d discards=%d\\n",\n    route, obs.valid ? 1 : 0, obs.player_count, obs.hero_chair,\n    obs.dealer_chair, obs.acting_chair, obs.round_index,\n    obs.hero_can_prepare ? 1 : 0, obs.confirm_visible ? 1 : 0,\n    obs.hero_loose_count, obs.hero_discard_tracker_count);\n''',
        '''    "round=%d fantasy_card_count=%d prepare=%d confirm=%d loose=%d discards=%d\\n",\n    route, obs.valid ? 1 : 0, obs.player_count, obs.hero_chair,\n    obs.dealer_chair, obs.acting_chair, obs.round_index,\n    obs.fantasy_card_count,\n    obs.hero_can_prepare ? 1 : 0, obs.confirm_visible ? 1 : 0,\n    obs.hero_loose_count, obs.hero_discard_tracker_count);\n''')

    helper_anchor = '''static bool DeepOFCReadMandatoryBoolean(CScraper *scraper,\n    const CString &region, bool *value) {\n'''
    path, text, eol, bom = read_source(rel)
    if text.count(helper_anchor) != 1:
        raise RuntimeError("mandatory boolean helper anchor missing")
    # Insert compatibility helpers immediately before the Fantasy function.
    function_anchor = "bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {\n"
    if text.count(function_anchor) != 1:
        raise RuntimeError("Fantasy scraper function anchor missing")
    compat_helpers = r'''// OPENOFC_GENERIC_FANTASY_V543 compatibility helpers. Generic names win;
// old count-specific TableMap regions are read only as aliases.
static bool DeepOFCReadRegionRectCompat(
    const CString &generic_name,
    const CString &legacy_name,
    RECT *out) {
  if (DeepOFCRegionExists(generic_name))
    return DeepOFCReadRegionRect(generic_name, out);
  if (!legacy_name.IsEmpty() && DeepOFCRegionExists(legacy_name))
    return DeepOFCReadRegionRect(legacy_name, out);
  return false;
}

static bool DeepOFCReadBooleanCompat(
    CScraper *scraper,
    const CString &generic_name,
    const CString &legacy_name,
    bool *value) {
  if (value == NULL) return false;
  *value = false;
  if (DeepOFCRegionExists(generic_name)) {
    scraper->EvaluateTrueFalseRegion(value, generic_name);
    return true;
  }
  if (!legacy_name.IsEmpty() && DeepOFCRegionExists(legacy_name)) {
    scraper->EvaluateTrueFalseRegion(value, legacy_name);
    return true;
  }
  write_log(k_always_log_errors,
    "[DeepOFC] Missing generic/legacy Fantasy boolean region: %s / %s\n",
    generic_name.GetString(), legacy_name.GetString());
  return false;
}

'''
    text = text.replace(function_anchor, compat_helpers + function_anchor, 1)
    write_source(path, text, eol, bom)

    replacement = r'''bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {
  if (!p_tablemap->OFCFantasyRecognizerCalibrated()) {
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY] recognizer authority missing terminal=0\n");
    return false;
  }
  if (!p_tablemap->OFCFantasyGeometryMeasured()) {
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY] measured geometry authority missing terminal=0\n");
    return false;
  }
  if (player_count != 2 || hero_chair != 1) {
    // Count is generic, but the currently measured board/action geometry is HU
    // hero-chair-1. Never extrapolate physical click geometry to another chair.
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY] current 450x830 geometry certifies HU hero_chair=1 only\n");
    return false;
  }

  COFCVisualObservation *obs = p_table_state->OFCVisualObservation();
  obs->Reset();
  obs->player_count = player_count;
  obs->hero_chair = hero_chair;
  obs->round_index = -1;
  for (int p = 0; p < player_count; ++p) {
    obs->players[p].occupied = true;
    obs->players[p].source_chair = p;
    obs->players[p].fantasy = (p == hero_chair);
  }

  // Opponent board geometry is stable while Hero arranges Fantasy.
  const int opponent = 1 - hero_chair;
  CString base;
  for (int i = 0; i < kOFCTopCards; ++i) {
    base.Format("ofc_p%d_top%d", opponent, i);
    bool back = false; int joker = 0;
    if (ScrapeOFCSlot(base,
          &obs->players[opponent].visual_board.top[i], &back, &joker) < 0
        || back) return false;
  }
  for (int i = 0; i < kOFCMiddleCards; ++i) {
    base.Format("ofc_p%d_middle%d", opponent, i);
    bool back = false; int joker = 0;
    if (ScrapeOFCSlot(base,
          &obs->players[opponent].visual_board.middle[i], &back, &joker) < 0
        || back) return false;
  }
  for (int i = 0; i < kOFCBottomCards; ++i) {
    base.Format("ofc_p%d_bottom%d", opponent, i);
    bool back = false; int joker = 0;
    if (ScrapeOFCSlot(base,
          &obs->players[opponent].visual_board.bottom[i], &back, &joker) < 0
        || back) return false;
  }

  const int row_counts[3] = {3, 5, 5};
  const char *row_names[3] = {"top", "middle", "bottom"};
  std::vector<RECT> arrangement_rects;
  for (int row = 0; row < 3; ++row) {
    for (int i = 0; i < row_counts[row]; ++i) {
      CString generic_name;
      CString legacy_name;
      generic_name.Format("ofc_fantasy_arrange_%s%d", row_names[row], i);
      legacy_name.Format("ofc_fantasy15_arrange_%s%d", row_names[row], i);
      RECT rect;
      if (!DeepOFCReadRegionRectCompat(generic_name, legacy_name, &rect)) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY] missing arrangement region generic=%s legacy=%s\n",
          generic_name.GetString(), legacy_name.GetString());
        return false;
      }
      arrangement_rects.push_back(rect);
    }
  }

  std::vector<string> original_labels;
  const COFCState *previous = p_table_state->OFCState();
  if (previous->valid && previous->hero_chair == hero_chair
      && previous->players[hero_chair].fantasy
      && previous->round_index == -1
      && previous->fantasy_card_count >= 14
      && previous->fantasy_card_count <= 17
      && previous->hero_incoming_count == previous->fantasy_card_count) {
    for (int i = 0; i < previous->hero_incoming_count; ++i)
      original_labels.push_back(DeepOFCPhysicalLabel(previous->hero_incoming[i].value));
  }

  std::vector<bool> occupied;
  std::vector<COFCFantasyPixelCard> arrangement_cards;
  std::vector<COFCFantasyPixelObject> loose;
  bool loose_pre_recognized = false;
  std::string recognition_error;
  if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
        _entire_window_cur, arrangement_rects,
        &occupied, &arrangement_cards, &recognition_error)) {
    const std::string strict_error = recognition_error;
    bool expected_match = false;
    // Expected-set fallback is lineage-bound and therefore available only when
    // the same Fantasy deal was already certified before this frame.
    if (!original_labels.empty()
        && COFCFantasyPixelRecognizer::RecognizeLooseObjectsBound(
          _entire_window_cur, true, original_labels,
          &loose, &recognition_error)) {
      std::set<string> unused_labels;
      for (size_t i = 0; i < loose.size(); ++i)
        unused_labels.insert(loose[i].card.PhysicalLabel());
      std::vector<string> expected_arrangement;
      for (size_t i = 0; i < original_labels.size(); ++i) {
        if (unused_labels.find(original_labels[i]) == unused_labels.end())
          expected_arrangement.push_back(original_labels[i]);
      }
      if (expected_arrangement.size() == 13) {
        expected_match =
          COFCFantasyPixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
            _entire_window_cur, arrangement_rects, expected_arrangement,
            &occupied, &arrangement_cards, &recognition_error);
      }
    }
    if (!expected_match) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY] arrangement rejected strict=%s fallback=%s terminal=0\n",
        strict_error.c_str(), recognition_error.c_str());
      return false;
    }
    loose_pre_recognized = true;
  }

  int arrangement_count = 0;
  int flat = 0;
  std::vector<string> arrangement_labels;
  for (int row = 0; row < 3; ++row) {
    bool saw_empty = false;
    for (int i = 0; i < row_counts[row]; ++i, ++flat) {
      if (!occupied[flat]) {
        saw_empty = true;
        continue;
      }
      if (saw_empty) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY] arrangement gap row=%d terminal=0\n", row);
        return false;
      }
      const int value = DeepOFCPixelCardValue(arrangement_cards[flat]);
      if (value < 0) return false;
      COFCCard *destination = NULL;
      if (row == kOFCRowTop)
        destination = &obs->players[hero_chair].visual_board.top[i];
      else if (row == kOFCRowMiddle)
        destination = &obs->players[hero_chair].visual_board.middle[i];
      else
        destination = &obs->players[hero_chair].visual_board.bottom[i];
      destination->value = value;
      arrangement_labels.push_back(arrangement_cards[flat].PhysicalLabel());
      ++arrangement_count;
    }
  }

  // Every bootstrap path comes from the CURRENT bitmap. With prior lineage we
  // additionally require subset membership; after process restart, the union of
  // exact tentative-board cards and exact loose objects is itself the deal.
  if (!loose_pre_recognized) {
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

  const int detected_count = arrangement_count + static_cast<int>(loose.size());
  if (detected_count < 14 || detected_count > 17) {
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY] count rejected arranged=%d loose=%d total=%d expected=14..17 terminal=0\n",
      arrangement_count, static_cast<int>(loose.size()), detected_count);
    return false;
  }
  if (!original_labels.empty()
      && detected_count != static_cast<int>(original_labels.size())) {
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY] lineage count changed prior=%d current=%d terminal=0\n",
      static_cast<int>(original_labels.size()), detected_count);
    return false;
  }
  obs->fantasy_card_count = detected_count;

  for (size_t i = 0; i < loose.size(); ++i) {
    if (i >= static_cast<size_t>(kOFCMaxIncomingCards)) return false;
    const int value = DeepOFCPixelCardValue(loose[i].card);
    if (value < 0 || !loose[i].valid || !loose[i].fresh_from_current_bitmap)
      return false;
    obs->hero_loose_cards[i].value = value;
    obs->hero_loose_sources[i].valid = true;
    obs->hero_loose_sources[i].card_value = value;
    obs->hero_loose_sources[i].rect = loose[i].source_rect;
    ++obs->hero_loose_count;
  }

  // Dealer identity is confidence data, not a Fantasy-frame validity gate.
  int dealer_count = 0;
  int actor_marker_count = 0;
  for (int p = 0; p < player_count; ++p) {
    bool value = false;
    CString name;
    name.Format("ofc_p%d_dealer", p);
    if (DeepOFCRegionExists(name)) {
      EvaluateTrueFalseRegion(&value, name);
      if (value) { obs->dealer_chair = p; ++dealer_count; }
    }
    value = false;
    name.Format("ofc_p%d_turn", p);
    if (DeepOFCRegionExists(name)) {
      EvaluateTrueFalseRegion(&value, name);
      if (value) ++actor_marker_count;
    }
  }
  obs->dealer_known = dealer_count == 1;
  if (!obs->dealer_known) obs->dealer_chair = -1;

  // Active Fantasy + exact draggable Hero objects is direct turn authority for
  // preparation. A blinking legacy actor marker cannot make the process stop.
  obs->acting_chair = hero_chair;
  obs->hero_can_prepare = true;
  write_log(true,
    "[OpenOFC FANTASY] actor_authority=FANTASY_UI raw_actor_markers=%d dealer_known=%d dealer=%d\n",
    actor_marker_count, obs->dealer_known ? 1 : 0, obs->dealer_chair);

  if (!DeepOFCReadBooleanCompat(
        this, "ofc_fantasy_confirm_visible",
        "ofc_fantasy15_confirm_visible", &obs->confirm_visible)) {
    return false;
  }

  if (!DeepOFCObservationHasUniqueKnownCards(obs)) {
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY] duplicate physical card in current-screen observation terminal=0\n");
    return false;
  }
  obs->valid = true;
  DeepOFCLogRawObservation(*obs, "FANTASY");
  write_log(true,
    "[OpenOFC FANTASY] raw_valid=1 fantasy_card_count=%d arranged=%d loose=%d confirm=%d lineage=%s\n",
    obs->fantasy_card_count, arrangement_count, obs->hero_loose_count,
    obs->confirm_visible ? 1 : 0,
    original_labels.empty() ? "CURRENT_SCREEN_BOOTSTRAP" : "PRIOR_PLUS_CURRENT");
  return true;
}
'''
    regex_once(
        rel,
        r'''bool CScraper::ScrapeOFCFantasyVisualObservation\(int player_count, int hero_chair\) \{.*?\n\}\nbool CScraper::ScrapeOFCVisualObservation\(\) \{''',
        replacement + 'bool CScraper::ScrapeOFCVisualObservation() {')


def patch_reconstructor_fantasy_count():
    rel = "OpenHoldem/COFCReconstructor.cpp"

    replace_once(
        rel,
        '''  if (current_incoming.size() < 14 || current_incoming.size() > 17) {\n    ostringstream oss;\n    oss << "Fantasy decision requires 14..17 visible Hero physical cards; got "\n        << current_incoming.size();\n    return Fail(out, error, oss.str());\n  }\n''',
        '''  if (current_incoming.size() < 14 || current_incoming.size() > 17) {\n    ostringstream oss;\n    oss << "Fantasy decision requires 14..17 visible Hero physical cards; got "\n        << current_incoming.size();\n    return Fail(out, error, oss.str());\n  }\n  if (observation.fantasy_card_count < 14\n      || observation.fantasy_card_count > 17\n      || observation.fantasy_card_count != static_cast<int>(current_incoming.size())) {\n    ostringstream oss;\n    oss << "Fantasy card-count contract disagrees with current screen: field="\n        << observation.fantasy_card_count << " visible=" << current_incoming.size();\n    return Fail(out, error, oss.str());\n  }\n''')

    path, text, eol, bom = read_source(rel)
    old = '''  out->dealer_carried = dealer_carried;\n  out->acting_chair = observation.acting_chair;\n  out->round_index = observation.round_index;\n'''
    new = '''  out->dealer_carried = dealer_carried;\n  out->acting_chair = observation.acting_chair;\n  out->round_index = observation.round_index;\n  out->fantasy_card_count = observation.players[observation.hero_chair].fantasy\n    ? observation.fantasy_card_count : 0;\n'''
    count = text.count(old)
    if count != 1:
        # Fantasy normalization helper uses explicit round -1 and is normalized
        # separately below; normal output owns observation.round_index.
        raise RuntimeError(f"{rel}: expected one normal metadata count target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)

    # The v5.4.2C normalization makes Fantasy dealer_carried explicitly false.
    replace_once(
        rel,
        '''  out->dealer_carried = false;\n  out->acting_chair = observation.acting_chair;\n  out->round_index = -1;\n''',
        '''  out->dealer_carried = false;\n  out->acting_chair = observation.acting_chair;\n  out->round_index = -1;\n  out->fantasy_card_count = observation.fantasy_card_count;\n''')

    replace_once(
        rel,
        '''  seed.acting_chair = observation.acting_chair;\n  seed.round_index = observation.round_index;\n  seed.hero_can_prepare = observation.hero_can_prepare;\n''',
        '''  seed.acting_chair = observation.acting_chair;\n  seed.round_index = observation.round_index;\n  seed.fantasy_card_count = observation.players[observation.hero_chair].fantasy\n    ? observation.fantasy_card_count : 0;\n  seed.hero_can_prepare = observation.hero_can_prepare;\n''')

    replace_once(
        rel,
        '''      << ",\\\"round_index\\\":" << state.round_index\n      << ",\\\"players\\\":[";\n''',
        '''      << ",\\\"round_index\\\":" << state.round_index\n      << ",\\\"fantasy_card_count\\\":" << state.fantasy_card_count\n      << ",\\\"players\\\":[";\n''')


def patch_generic_policy():
    rel = "OpenHoldem/COFCBaselinePolicy.cpp"
    generic = r'''bool ChooseFantasy(
    const COFCState &state, COFCStrategyAction *action, string *error) {
  const int fantasy_count = state.fantasy_card_count;
  if (fantasy_count < 14 || fantasy_count > 17
      || state.hero_incoming_count != fantasy_count) {
    return Fail(action, error,
      "Fantasy policy requires fantasy_card_count=hero_incoming_count in 14..17");
  }
  vector<PolicyCard> incoming;
  for (int i = 0; i < fantasy_count; ++i) {
    if (!state.hero_incoming[i].IsKnownPhysicalCard())
      return Fail(action, error, "Fantasy incoming contains unknown card");
    incoming.push_back(Convert(state.hero_incoming[i].value));
  }

  const unsigned int limit = 1u << fantasy_count;
  const unsigned int all = limit - 1;
  vector<unsigned int> masks5;
  vector<vector<HandRank> > top(limit);
  vector<vector<HandRank> > five(limit);
  for (unsigned int mask = 0; mask < limit; ++mask) {
    const int count = Popcount(mask);
    if (count == 3) {
      top[mask] = CandidateRanks(CardsForMask(incoming, mask), true);
    } else if (count == 5) {
      masks5.push_back(mask);
      five[mask] = CandidateRanks(CardsForMask(incoming, mask), false);
    }
  }

  long long best_score = -1;
  unsigned int best_top = 0;
  unsigned int best_middle = 0;
  unsigned int best_bottom = 0;
  vector<map<HandRank, unsigned int> > top_frontier(limit);
  vector<unsigned char> top_frontier_ready(limit, 0);
  for (size_t b = 0; b < masks5.size(); ++b) {
    const unsigned int bottom_mask = masks5[b];
    const HandRank bottom = five[bottom_mask][0];
    for (size_t m = 0; m < masks5.size(); ++m) {
      const unsigned int middle_mask = masks5[m];
      if ((bottom_mask & middle_mask) != 0) continue;
      HandRank middle;
      bool found_middle = false;
      for (size_t r = 0; r < five[middle_mask].size(); ++r) {
        if (LessOrEqual(five[middle_mask][r], bottom)) {
          middle = five[middle_mask][r];
          found_middle = true;
          break;
        }
      }
      if (!found_middle) continue;
      const unsigned int remaining = all ^ (bottom_mask | middle_mask);
      if (!top_frontier_ready[remaining]) {
        map<HandRank, unsigned int> &frontier = top_frontier[remaining];
        for (unsigned int top_mask = remaining; top_mask != 0;
             top_mask = (top_mask - 1) & remaining) {
          if (Popcount(top_mask) != 3) continue;
          for (size_t r = 0; r < top[top_mask].size(); ++r) {
            map<HandRank, unsigned int>::iterator old = frontier.find(top[top_mask][r]);
            if (old == frontier.end() || top_mask < old->second)
              frontier[top[top_mask][r]] = top_mask;
          }
        }
        top_frontier_ready[remaining] = 1;
      }
      map<HandRank, unsigned int> &frontier = top_frontier[remaining];
      map<HandRank, unsigned int>::iterator best = frontier.upper_bound(middle);
      if (best == frontier.begin()) continue;
      --best;
      const HandRank top_rank = best->first;
      const unsigned int top_mask = best->second;
      array<HandRank, 3> ranks = {{top_rank, middle, bottom}};
      const int fantasy_points = Royalties(ranks)
        + FantasyContinuationValue(ranks, fantasy_count);
      const long long score = static_cast<long long>(fantasy_points) * 1000000000LL
        + RankScalar(bottom) * 10000LL
        + RankScalar(middle) * 100LL
        + RankScalar(top_rank);
      if (score > best_score
          || (score == best_score
              && (top_mask < best_top
                  || (top_mask == best_top && middle_mask < best_middle)
                  || (top_mask == best_top && middle_mask == best_middle
                      && bottom_mask < best_bottom)))) {
        best_score = score;
        best_top = top_mask;
        best_middle = middle_mask;
        best_bottom = bottom_mask;
      }
    }
  }
  if (best_score < 0) return Fail(action, error, "no valid Fantasy board found");

  action->Reset();
  for (int i = 0; i < fantasy_count; ++i) {
    EOFCRow row = kOFCRowUndefined;
    if ((best_top & (1u << i)) != 0) row = kOFCRowTop;
    else if ((best_middle & (1u << i)) != 0) row = kOFCRowMiddle;
    else if ((best_bottom & (1u << i)) != 0) row = kOFCRowBottom;
    if (row == kOFCRowUndefined) {
      action->unused_cards[action->unused_count++] = incoming[i].value;
    } else {
      COFCStrategyPlacement &placement = action->placements[action->placement_count++];
      placement.card_value = incoming[i].value;
      placement.row = row;
    }
  }
  action->valid = action->placement_count == 13
    && action->unused_count == fantasy_count - 13;
  return action->valid;
}

'''
    regex_once(
        rel,
        r'''bool ChooseFantasy15\(\n    const COFCState &state, COFCStrategyAction \*action, string \*error\) \{.*?\n\}\n\nvoid BoardRows\(''',
        generic + 'void BoardRows(')
    replace_once(
        rel,
        '''  if (state.players[state.hero_chair].fantasy)\n    return ChooseFantasy15(state, action, error);\n''',
        '''  if (state.players[state.hero_chair].fantasy)\n    return ChooseFantasy(state, action, error);\n''')


def patch_executor_never_terminal():
    rel = "OpenHoldem/COFCFantasyBatchExecutor.h"
    replace_once(
        rel,
        '''    kIdle,\n    kAwaitRowCommit,\n    kAwaitRowClear,\n    kBlocked\n''',
        '''    kIdle,\n    kAwaitRowCommit,\n    kAwaitRowClear\n''')

    rel = "OpenHoldem/COFCFantasyBatchExecutor.cpp"
    replace_once(
        rel,
        '''bool COFCFantasyBatchExecutor::Fail(\n    string *error, const string &message) {\n  phase_ = kBlocked;\n  if (error != NULL) *error = message;\n  write_log(k_always_log_errors,\n    "[OpenOFC FANTASY V5] BLOCKED reason=\\\"%s\\\"\\n", message.c_str());\n  return false;\n}\n''',
        '''bool COFCFantasyBatchExecutor::Fail(\n    string *error, const string &message) {\n  // OPENOFC_GENERIC_FANTASY_V543: transaction failure is recoverable. The\n  // current click is suppressed, local plan/phase is discarded, and the outer\n  // continuity supervisor will fresh-scrape/reconstruct/replan.\n  phase_ = kIdle;\n  plan_.Reset();\n  waiting_row_ = kOFCRowUndefined;\n  wait_cycles_ = 0;\n  retry_count_[0] = retry_count_[1] = retry_count_[2] = 0;\n  clear_consumes_retry_ = false;\n  if (error != NULL) *error = message;\n  write_log(k_always_log_errors,\n    "[OpenOFC FANTASY] executor_fault reason=\\\"%s\\\" terminal=0 "\n    "action=SUPPRESSED_THIS_FRAME replan=1 continue_scraping=1\\n",\n    message.c_str());\n  return false;\n}\n''')
    replace_once(
        rel,
        '''  if (phase_ == kBlocked) {\n    if (error != NULL) *error = "Fantasy executor remains blocked";\n    return false;\n  }\n''',
        '''  // No absorbing executor phase exists. Any previous transaction fault reset\n  // this executor and the outer runtime must bind a fresh plan.\n''')


def patch_existing_selftests():
    rel = "OpenHoldem/COFCRuntimeContinuitySelftest.cpp"
    replace_once(
        rel,
        '''  obs.round_index = -1;\n  obs.hero_can_prepare = true;\n''',
        '''  obs.round_index = -1;\n  obs.fantasy_card_count = count;\n  obs.hero_can_prepare = true;\n''')


def assert_contract():
    required = {
        "OpenHoldem/COFCVisualObservation.h": ["fantasy_card_count", "OPENOFC_GENERIC_FANTASY_V543"],
        "OpenHoldem/COFCState.h": ["fantasy_card_count", "OPENOFC_GENERIC_FANTASY_V543"],
        "CTablemap/CTablemap.h": ["OFCFantasyGeometryMeasured", "ofc_fantasy_geometry_measured"],
        "OpenHoldem/COFCScraper.cpp": [
            'route=FANTASY',
            'fantasy_card_count=%d',
            'CURRENT_SCREEN_BOOTSTRAP',
            'ofc_fantasy_confirm_visible',
            'COFCFantasyPixelRecognizer',
        ],
        "OpenHoldem/COFCReconstructor.cpp": ["Fantasy card-count contract", "fantasy_card_count"],
        "OpenHoldem/COFCBaselinePolicy.cpp": ["bool ChooseFantasy(", "fantasy_count - 13"],
        "OpenHoldem/COFCFantasyBatchExecutor.cpp": ["executor_fault", "terminal=0"],
    }
    for rel, needles in required.items():
        text = (ROOT / rel).read_text(encoding="utf-8-sig", errors="strict")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise RuntimeError(f"{rel}: missing v5.4.3 markers: {missing}")

    scraper = (ROOT / "OpenHoldem/COFCScraper.cpp").read_text(encoding="utf-8-sig")
    policy = (ROOT / "OpenHoldem/COFCBaselinePolicy.cpp").read_text(encoding="utf-8-sig")
    executor_h = (ROOT / "OpenHoldem/COFCFantasyBatchExecutor.h").read_text(encoding="utf-8-sig")
    executor_cpp = (ROOT / "OpenHoldem/COFCFantasyBatchExecutor.cpp").read_text(encoding="utf-8-sig")
    if "Operational Fantasy15 requires exactly 15 cards" in scraper:
        raise RuntimeError("count-specific Fantasy scraper gate survived v5.4.3")
    if "hero_incoming_count == 15" in scraper or "hero_incoming_count != 15" in policy:
        raise RuntimeError("hard-coded operational 15-card Fantasy count survived")
    if "ChooseFantasy15(" in policy:
        raise RuntimeError("count-specific Fantasy policy entry point survived")
    if "kBlocked" in executor_h or "kBlocked" in executor_cpp:
        raise RuntimeError("absorbing Fantasy executor phase survived")
    print("OpenOFC v5.4.3 generic Fantasy source contract passed")


def main():
    patch_fantasy_count_contract()
    patch_tablemap_generic_gate()
    patch_dynamic_recognizer_unbound_mode()
    patch_scraper_generic_fantasy()
    patch_reconstructor_fantasy_count()
    patch_generic_policy()
    patch_executor_never_terminal()
    patch_existing_selftests()
    assert_contract()
    print("OpenOFC v5.4.3 generic Fantasy runtime patch applied successfully")


if __name__ == "__main__":
    main()
