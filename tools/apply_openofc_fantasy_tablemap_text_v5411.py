from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = Path("OpenHoldem/COFCScraper.cpp")
MARKER = "OPENOFC_FANTASY_TABLEMAP_TEXT_V5411"


def load():
    path = ROOT / REL
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def save(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, got {count}")
    return text.replace(old, new, 1)


def main() -> None:
    path, text, eol, bom = load()
    if MARKER in text:
        raise RuntimeError("v5.4.11 already materialized")

    # The generic v5.4.3 materializer changes this include before v5.4.11 runs.
    include_anchor = '#include <set>\n'
    if '#include <algorithm>\n' not in text:
        text = replace_once(
            text, include_anchor,
            '#include <algorithm>\n#include <set>\n',
            "algorithm include",
        )

    function_anchor = (
        'bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {\n'
    )
    if text.count(function_anchor) != 1:
        raise RuntimeError("Fantasy scraper function anchor missing/non-unique")

    helpers = r'''// OPENOFC_FANTASY_TABLEMAP_TEXT_V5411
// ---------------------------------------------------------------------------
// Count-selected TableMap text route for KKPoker Fantasy.
//
// The current executor commits complete rows TOP(3) -> MIDDLE(5) -> BOTTOM(5).
// Therefore only three stable loose-card groups can exist before completion:
//   arrangement=0 : 14,15,16,17 loose
//   arrangement=3 : 11,12,13,14 loose
//   arrangement=8 :  6, 7, 8, 9 loose
// After arrangement=13 the remaining 1..4 unused physical cards are carried
// from the already-certified Fantasy lineage; they never need a clickable/text
// hand layout. This is the central reason no 1..5 TableMap families are needed.
//
// A TableMap family is accepted only if EVERY required rank/suit slot resolves,
// every physical card is unique, the count is legal for the current phase, and
// (when prior lineage exists) every card belongs to that exact Fantasy deal.
// Multiple passing families are ambiguous and therefore rejected.
// ---------------------------------------------------------------------------

static bool DeepOFCFantasyTextRank(const CString &input, char *rank) {
  if (rank == NULL) return false;
  CString text(input);
  text.Trim();
  if (text.GetLength() != 1) return false;
  char value = static_cast<char>(text.GetAt(0));
  if (value >= 'a' && value <= 'z') value = static_cast<char>(value - 'a' + 'A');
  const string allowed = "23456789TJQKAXRG";
  if (allowed.find(value) == string::npos) return false;
  *rank = value;
  return true;
}

static bool DeepOFCFantasyTextSuit(const CString &input, char *suit) {
  if (suit == NULL) return false;
  CString text(input);
  text.Trim();
  if (text.GetLength() != 1) return false;
  char value = static_cast<char>(text.GetAt(0));
  if (value >= 'A' && value <= 'Z') value = static_cast<char>(value - 'A' + 'a');
  const string allowed = "cdhs";
  if (allowed.find(value) == string::npos) return false;
  *suit = value;
  return true;
}

static RECT DeepOFCFantasyTextSourceRect(const RECT &rank, const RECT &suit) {
  RECT out;
  out.left = min(rank.left, suit.left);
  out.top = min(rank.top, suit.top);
  out.right = max(rank.right, suit.right);
  out.bottom = max(rank.bottom, suit.bottom);
  // Keep the click inside the exposed rank/suit corner. Expanding a fan card to
  // its nominal full width could overlap the next physical card.
  out.left = max<LONG>(0, out.left - 1);
  out.top = max<LONG>(0, out.top - 1);
  out.right = min<LONG>(450, out.right + 1);
  out.bottom = min<LONG>(830, out.bottom + 1);
  return out;
}

static bool DeepOFCFantasyTextReadObject(
    CScraper *scraper,
    const CString &base,
    int family_count,
    COFCFantasyPixelObject *object,
    string *error) {
  if (scraper == NULL || object == NULL) {
    if (error != NULL) *error = "Fantasy text object received null scraper/output";
    return false;
  }
  *object = COFCFantasyPixelObject();
  const CString rank_name = base + "rank";
  const CString suit_name = base + "suit";
  if (!DeepOFCRegionExists(rank_name) || !DeepOFCRegionExists(suit_name)) {
    if (error != NULL) *error = "Fantasy text family is missing rank/suit region";
    return false;
  }

  CString rank_text;
  if (!scraper->EvaluateRegion(rank_name, &rank_text)) {
    if (error != NULL) *error = "Fantasy text rank region could not be evaluated";
    return false;
  }
  char rank = 0;
  if (!DeepOFCFantasyTextRank(rank_text, &rank)) {
    if (error != NULL) *error = "Fantasy text rank transform returned no valid token";
    return false;
  }

  RECT rank_rect;
  RECT suit_rect;
  if (!DeepOFCReadRegionRect(rank_name, &rank_rect)
      || !DeepOFCReadRegionRect(suit_name, &suit_rect)) {
    if (error != NULL) *error = "Fantasy text rank/suit rectangle is unavailable";
    return false;
  }

  COFCFantasyPixelCard card;
  card.valid = true;
  if (rank == 'R') {
    // Experimental T7 token: red/orange physical Joker = JK1.
    card.joker_id = 1;
  } else if (rank == 'G') {
    // Experimental T7 token: gray/black physical Joker = JK2.
    card.joker_id = 2;
  } else if (rank == 'X') {
    // Legacy/generic Joker token. Keep it unresolved until family-level lineage
    // can prove which physical Joker remains; never guess here.
    card.joker_id = 3;
  } else {
    CString suit_text;
    if (!scraper->EvaluateRegion(suit_name, &suit_text)) {
      if (error != NULL) *error = "Fantasy text suit region could not be evaluated";
      return false;
    }
    char suit = 0;
    if (!DeepOFCFantasyTextSuit(suit_text, &suit)) {
      if (error != NULL) *error = "Fantasy text suit transform returned no valid token";
      return false;
    }
    card.rank = rank;
    card.suit = suit;
  }

  object->valid = true;
  object->fresh_from_current_bitmap = true;
  object->card = card;
  object->source_rect = DeepOFCFantasyTextSourceRect(rank_rect, suit_rect);
  object->drag_anchor.x = object->source_rect.left
    + (object->source_rect.right - object->source_rect.left) / 2;
  object->drag_anchor.y = object->source_rect.top
    + (object->source_rect.bottom - object->source_rect.top) / 2;
  object->detected_layout_count = family_count;
  object->geometry_residual = 0.0;
  return true;
}

static bool DeepOFCFantasyTextContainsLabel(
    const vector<string> &labels, const string &needle) {
  return find(labels.begin(), labels.end(), needle) != labels.end();
}

static bool DeepOFCFantasyTextResolveGenericJokers(
    const vector<string> &original_labels,
    const vector<string> &arrangement_labels,
    vector<COFCFantasyPixelObject> *objects,
    string *error) {
  if (objects == NULL) return false;
  vector<int> unresolved;
  bool explicit_jk1 = false;
  bool explicit_jk2 = false;
  for (size_t i = 0; i < objects->size(); ++i) {
    const int joker = (*objects)[i].card.joker_id;
    if (joker == 3) unresolved.push_back(static_cast<int>(i));
    else if (joker == 1) explicit_jk1 = true;
    else if (joker == 2) explicit_jk2 = true;
  }
  if (unresolved.empty()) return true;

  // Generic X is accepted only when prior physical lineage makes the remaining
  // Joker identity deterministic. Initial/cold bootstrap must use R/G tokens or
  // fall back to the native recognizer.
  if (original_labels.empty()) {
    if (error != NULL) *error = "generic X Joker has no prior physical lineage";
    return false;
  }
  vector<int> available;
  if (DeepOFCFantasyTextContainsLabel(original_labels, "JK1")
      && !DeepOFCFantasyTextContainsLabel(arrangement_labels, "JK1")
      && !explicit_jk1) available.push_back(1);
  if (DeepOFCFantasyTextContainsLabel(original_labels, "JK2")
      && !DeepOFCFantasyTextContainsLabel(arrangement_labels, "JK2")
      && !explicit_jk2) available.push_back(2);
  if (available.size() != unresolved.size()) {
    if (error != NULL) *error = "generic X Joker count is not deterministic from lineage";
    return false;
  }
  for (size_t i = 0; i < unresolved.size(); ++i)
    (*objects)[unresolved[i]].card.joker_id = available[i];
  return true;
}

static bool DeepOFCFantasyTextFamily(
    CScraper *scraper,
    int count,
    const vector<string> &original_labels,
    const vector<string> &arrangement_labels,
    vector<COFCFantasyPixelObject> *objects,
    string *error) {
  if (objects == NULL) return false;
  objects->clear();
  if (count < 6 || count > 17 || count == 10) {
    if (error != NULL) *error = "unsupported Fantasy text family count";
    return false;
  }
  vector<string> labels;
  for (int i = 0; i < count; ++i) {
    CString base;
    base.Format("ofc_fantasy%02d_%02d", count, i);
    COFCFantasyPixelObject object;
    string local_error;
    if (!DeepOFCFantasyTextReadObject(
          scraper, base, count, &object, &local_error)) {
      objects->clear();
      if (error != NULL) {
        ostringstream out;
        out << "family=" << count << " slot=" << i << " " << local_error;
        *error = out.str();
      }
      return false;
    }
    objects->push_back(object);
  }
  if (!DeepOFCFantasyTextResolveGenericJokers(
        original_labels, arrangement_labels, objects, error)) {
    objects->clear();
    return false;
  }

  set<string> unique;
  for (size_t i = 0; i < objects->size(); ++i) {
    const string label = (*objects)[i].card.PhysicalLabel();
    if (label.empty() || label == "INVALID" || label == "AMBIGUOUS"
        || !unique.insert(label).second) {
      objects->clear();
      if (error != NULL) *error = "Fantasy text family contains invalid/duplicate card";
      return false;
    }
    if (!original_labels.empty()
        && !DeepOFCFantasyTextContainsLabel(original_labels, label)) {
      objects->clear();
      if (error != NULL) *error = "Fantasy text family violates prior physical lineage";
      return false;
    }
  }
  return true;
}

static vector<int> DeepOFCFantasyLegalLooseCounts(
    int arrangement_count,
    int prior_total) {
  vector<int> counts;
  if (prior_total >= 14 && prior_total <= 17) {
    const int expected = prior_total - arrangement_count;
    if ((arrangement_count == 0 && expected >= 14 && expected <= 17)
        || (arrangement_count == 3 && expected >= 11 && expected <= 14)
        || (arrangement_count == 8 && expected >= 6 && expected <= 9)) {
      counts.push_back(expected);
    }
    return counts;
  }
  if (arrangement_count == 0) {
    for (int n = 14; n <= 17; ++n) counts.push_back(n);
  } else if (arrangement_count == 3) {
    for (int n = 11; n <= 14; ++n) counts.push_back(n);
  } else if (arrangement_count == 8) {
    for (int n = 6; n <= 9; ++n) counts.push_back(n);
  }
  return counts;
}

static bool DeepOFCFantasySelectTextFamily(
    CScraper *scraper,
    int arrangement_count,
    const vector<string> &original_labels,
    const vector<string> &arrangement_labels,
    vector<COFCFantasyPixelObject> *objects,
    int *selected_count,
    string *error) {
  if (objects == NULL || selected_count == NULL) return false;
  objects->clear();
  *selected_count = 0;
  const int prior_total = static_cast<int>(original_labels.size());
  const vector<int> legal = DeepOFCFantasyLegalLooseCounts(
    arrangement_count, prior_total);
  vector<COFCFantasyPixelObject> winner;
  int pass_count = 0;
  string last_error;
  for (size_t i = 0; i < legal.size(); ++i) {
    vector<COFCFantasyPixelObject> candidate;
    string candidate_error;
    if (!DeepOFCFantasyTextFamily(
          scraper, legal[i], original_labels, arrangement_labels,
          &candidate, &candidate_error)) {
      last_error = candidate_error;
      continue;
    }
    ++pass_count;
    winner = candidate;
    *selected_count = legal[i];
  }
  if (pass_count != 1) {
    objects->clear();
    *selected_count = 0;
    if (error != NULL) {
      ostringstream out;
      out << "Fantasy text family selection passes=" << pass_count
          << " legal=";
      for (size_t i = 0; i < legal.size(); ++i) {
        if (i != 0) out << ",";
        out << legal[i];
      }
      if (!last_error.empty()) out << " last_error=" << last_error;
      *error = out.str();
    }
    return false;
  }
  *objects = winner;
  return true;
}

static bool DeepOFCFantasyObjectFromPhysicalLabel(
    const string &label, COFCFantasyPixelObject *object) {
  if (object == NULL) return false;
  *object = COFCFantasyPixelObject();
  object->valid = true;
  object->fresh_from_current_bitmap = false;
  object->detected_layout_count = -13;  // final unused card carried from lineage
  if (label == "JK1") object->card.joker_id = 1;
  else if (label == "JK2") object->card.joker_id = 2;
  else {
    if (label.size() != 2) return false;
    object->card.rank = label[0];
    object->card.suit = label[1];
  }
  object->card.valid = true;
  return true;
}

'''
    text = text.replace(function_anchor, helpers + function_anchor, 1)

    # Keep the already-field-proven arrangement/native path for now. Replace only
    # loose identity discovery. The 13 fixed T1 arrangement text regions shipped
    # with the test TableMap are a separately staged fallback, so this patch does
    # not destabilize row verification and Joker-gold-card handling at once.
    old_loose = r'''  // Every bootstrap path comes from the CURRENT bitmap. With prior lineage we
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
'''
    new_loose = r'''  // OPENOFC_FANTASY_TABLEMAP_TEXT_V5411: prefer mature OpenHoldem Tn text
  // transforms for count-specific loose-card families. Families that do not
  // correspond to the current structural phase are never evaluated.
  bool final_unused_from_lineage = false;
  if (!loose_pre_recognized) {
    bool text_ok = false;
    int selected_text_count = 0;
    string text_error;

    if (arrangement_count == 13 && !original_labels.empty()) {
      // Bottom was committed. We need the original 14..17 physical identities
      // for canonical reconstruction, but no remaining card will ever be
      // clicked. Carry exactly the original cards not present in the verified
      // 13-card arrangement instead of mapping 1..4 transient loose layouts.
      set<string> arranged(arrangement_labels.begin(), arrangement_labels.end());
      for (size_t i = 0; i < original_labels.size(); ++i) {
        if (arranged.find(original_labels[i]) != arranged.end()) continue;
        COFCFantasyPixelObject object;
        if (!DeepOFCFantasyObjectFromPhysicalLabel(original_labels[i], &object)) {
          loose.clear();
          text_error = "failed to carry final unused physical Fantasy card";
          break;
        }
        loose.push_back(object);
      }
      text_ok = static_cast<int>(loose.size())
        == static_cast<int>(original_labels.size()) - 13;
      final_unused_from_lineage = text_ok;
      if (text_ok) selected_text_count = static_cast<int>(loose.size());
    } else if (arrangement_count == 0 || arrangement_count == 3
        || arrangement_count == 8) {
      text_ok = DeepOFCFantasySelectTextFamily(
        this, arrangement_count, original_labels, arrangement_labels,
        &loose, &selected_text_count, &text_error);
    }

    if (text_ok) {
      loose_pre_recognized = true;
      write_log(true,
        "[OpenOFC FANTASY TEXT V5411] route=TABLEMAP_TEXT arranged=%d "
        "loose=%d family=%d prior_total=%d final_lineage_carry=%d\n",
        arrangement_count, static_cast<int>(loose.size()), selected_text_count,
        static_cast<int>(original_labels.size()), final_unused_from_lineage ? 1 : 0);
    } else {
      write_log(true,
        "[OpenOFC FANTASY TEXT V5411] route=FALLBACK_NATIVE arranged=%d "
        "prior_total=%d reason=\"%s\"\n",
        arrangement_count, static_cast<int>(original_labels.size()),
        text_error.c_str());
      const bool upright = arrangement_count == 13;
      const bool ok = original_labels.empty()
        ? COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(
            _entire_window_cur, upright, &loose, &recognition_error)
        : COFCFantasyPixelRecognizer::RecognizeLooseObjectsBound(
            _entire_window_cur, upright, original_labels, &loose, &recognition_error);
      if (!ok) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY] loose recognition rejected arranged=%d "
          "text_error=%s native_error=%s terminal=0\n",
          arrangement_count, text_error.c_str(), recognition_error.c_str());
        return false;
      }
    }
  }
'''
    text = replace_once(text, old_loose, new_loose, "Fantasy loose recognition block")

    old_source_loop = r'''    if (value < 0 || !loose[i].valid || !loose[i].fresh_from_current_bitmap)
      return false;
    obs->hero_loose_cards[i].value = value;
    obs->hero_loose_sources[i].valid = true;
    obs->hero_loose_sources[i].card_value = value;
    obs->hero_loose_sources[i].rect = loose[i].source_rect;
    ++obs->hero_loose_count;
'''
    new_source_loop = r'''    const bool carried_final_unused =
      arrangement_count == 13 && loose[i].detected_layout_count == -13;
    if (value < 0 || !loose[i].valid
        || (!loose[i].fresh_from_current_bitmap && !carried_final_unused))
      return false;
    obs->hero_loose_cards[i].value = value;
    // Final unused cards are lineage-only reconstruction data. They are never
    // click sources after all 13 board cards have been verified.
    obs->hero_loose_sources[i].valid = !carried_final_unused;
    obs->hero_loose_sources[i].card_value = value;
    obs->hero_loose_sources[i].rect = loose[i].source_rect;
    ++obs->hero_loose_count;
'''
    text = replace_once(text, old_source_loop, new_source_loop, "Fantasy loose source loop")

    # Add an explicit source marker to the final raw-valid log. This helps field
    # diagnosis without changing its existing parsing prefix.
    old_log = r'''  write_log(true,
    "[OpenOFC FANTASY] raw_valid=1 fantasy_card_count=%d arranged=%d loose=%d confirm=%d lineage=%s\n",
    obs->fantasy_card_count, arrangement_count, obs->hero_loose_count,
    obs->confirm_visible ? 1 : 0,
    original_labels.empty() ? "CURRENT_SCREEN_BOOTSTRAP" : "PRIOR_PLUS_CURRENT");
'''
    new_log = r'''  write_log(true,
    "[OpenOFC FANTASY] raw_valid=1 fantasy_card_count=%d arranged=%d loose=%d "
    "confirm=%d lineage=%s text_sources=%d\n",
    obs->fantasy_card_count, arrangement_count, obs->hero_loose_count,
    obs->confirm_visible ? 1 : 0,
    original_labels.empty() ? "CURRENT_SCREEN_BOOTSTRAP" : "PRIOR_PLUS_CURRENT",
    p_tablemap->GetTMSymbol("openofc_fantasy_text_sources", 0) == 1 ? 1 : 0);
'''
    text = replace_once(text, old_log, new_log, "Fantasy raw-valid log")

    # Runtime opt-in: without the new TM symbol, the helper code is inert and
    # the previous native route remains authoritative.
    selector_call = r'''      text_ok = DeepOFCFantasySelectTextFamily(
        this, arrangement_count, original_labels, arrangement_labels,
        &loose, &selected_text_count, &text_error);
'''
    gated_selector = r'''      if (p_tablemap->GetTMSymbol("openofc_fantasy_text_sources", 0) == 1) {
        text_ok = DeepOFCFantasySelectTextFamily(
          this, arrangement_count, original_labels, arrangement_labels,
          &loose, &selected_text_count, &text_error);
      } else {
        text_error = "TableMap text-source opt-in is disabled";
      }
'''
    text = replace_once(text, selector_call, gated_selector, "Fantasy text opt-in selector")

    # Final-lineage carry is also part of the new route and must remain inert on
    # legacy TableMaps. Gate it with the same explicit symbol.
    text = text.replace(
        '    if (arrangement_count == 13 && !original_labels.empty()) {\n',
        '    if (arrangement_count == 13 && !original_labels.empty()\n'
        '        && p_tablemap->GetTMSymbol("openofc_fantasy_text_sources", 0) == 1) {\n',
        1,
    )

    # Structural contract assertions.
    required = (
        MARKER,
        'ofc_fantasy%02d_%02d',
        'passes=',
        'arrangement_count == 0 || arrangement_count == 3',
        'arrangement_count == 8',
        'detected_layout_count = -13',
        'route=TABLEMAP_TEXT',
        'route=FALLBACK_NATIVE',
        'openofc_fantasy_text_sources',
    )
    missing = [needle for needle in required if needle not in text]
    if missing:
        raise RuntimeError(f"v5.4.11 source contract missing: {missing}")
    if 'for (int n = 1; n <= 5' in text:
        raise RuntimeError("v5.4.11 unexpectedly maps final 1..5 loose-card families")

    save(path, text, eol, bom)
    print(
        "OPENOFC_FANTASY_TABLEMAP_TEXT_V5411_MATERIALIZATION=PASS "
        "stable_counts=6,7,8,9,11,12,13,14,15,16,17 "
        "count_selector=PHASE_PLUS_LINEAGE final_1to4=LINEAGE_CARRY "
        "native_fallback=PRESERVED legacy_tm=INERT"
    )


if __name__ == "__main__":
    main()
