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


def replace_once(rel: str, old: str, new: str, label: str | None = None):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label or rel}: expected one target, got {count}: {old[:180]!r}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}: {label or 'replace'}")


def regex_once(rel: str, pattern: str, replacement: str, label: str, flags=re.S):
    path, text, eol, bom = read_source(rel)
    new, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"{label}: regex expected one target, got {count}: {pattern[:180]}")
    write_source(path, new, eol, bom)
    print(f"patched {rel}: {label}")


def patch_card_occupancy_contract():
    rel = "OpenHoldem/COFCState.h"
    replace_once(
        rel,
        '''  bool IsKnownPhysicalCard() const {
    return IsKnownStandardCard() || IsJoker();
  }
  bool IsCardBack() const { return value == kOFCCardBack; }
''',
        '''  bool IsKnownPhysicalCard() const {
    return IsKnownStandardCard() || IsJoker();
  }
  // OPENOFC_UNKNOWN_OCCUPIED_V544: UNKNOWN is not EMPTY.  It is a proven
  // physical card whose rank/suit identity was unreadable in this bitmap.
  bool IsUnknownOccupied() const { return value == kOFCCardUnknown; }
  bool IsOccupiedPhysicalCard() const {
    return IsKnownPhysicalCard() || IsUnknownOccupied();
  }
  bool IsCardBack() const { return value == kOFCCardBack; }
''',
        "COFCCard UNKNOWN occupancy")

    replace_once(
        rel,
        '''  int CountKnownCards() const {
    int count = 0;
    for (int i = 0; i < kOFCTopCards; ++i) if (top[i].IsKnownPhysicalCard()) ++count;
    for (int i = 0; i < kOFCMiddleCards; ++i) if (middle[i].IsKnownPhysicalCard()) ++count;
    for (int i = 0; i < kOFCBottomCards; ++i) if (bottom[i].IsKnownPhysicalCard()) ++count;
    return count;
  }
''',
        '''  int CountKnownCards() const {
    int count = 0;
    for (int i = 0; i < kOFCTopCards; ++i) if (top[i].IsKnownPhysicalCard()) ++count;
    for (int i = 0; i < kOFCMiddleCards; ++i) if (middle[i].IsKnownPhysicalCard()) ++count;
    for (int i = 0; i < kOFCBottomCards; ++i) if (bottom[i].IsKnownPhysicalCard()) ++count;
    return count;
  }

  int CountOccupiedCards() const {
    int count = 0;
    for (int i = 0; i < kOFCTopCards; ++i) if (top[i].IsOccupiedPhysicalCard()) ++count;
    for (int i = 0; i < kOFCMiddleCards; ++i) if (middle[i].IsOccupiedPhysicalCard()) ++count;
    for (int i = 0; i < kOFCBottomCards; ++i) if (bottom[i].IsOccupiedPhysicalCard()) ++count;
    return count;
  }
''',
        "board occupied cardinality")


def patch_scraper_unknown_and_fantasy_entry():
    rel = "OpenHoldem/COFCScraper.cpp"

    # A non-empty slot whose glyph could not be classified is a physical card,
    # not an invalid/empty slot.  Return a positive occupied result so all
    # callers retain its geometry/cardinality.
    pattern = r'''  DeepOFCLogSlot\(base_name, "REJECTED", kOFCCardUnknown,\n    rank_result, suit_result, empty, back, joker1, joker2,\n    failure_detail\.str\(\)\);\n  write_log\(k_always_log_errors,\n    "\[DeepOFC\] Non-empty slot rejected by TableMap text transforms: %s "\n    "rank=\\"%s\\" suit=\\"%s\\"\\n",\n    base_name\.GetString\(\), rank_result\.GetString\(\), suit_result\.GetString\(\)\);\n  return -3;'''
    replacement = r'''  card->value = kOFCCardUnknown;
  DeepOFCLogSlot(base_name, "UNKNOWN_OCCUPIED", kOFCCardUnknown,
    rank_result, suit_result, empty, back, joker1, joker2,
    failure_detail.str());
  write_log(k_always_log_errors,
    "[OpenOFC UNKNOWN] slot=%s occupied=1 identity=UNREAD rank=\"%s\" suit=\"%s\" terminal=0\n",
    base_name.GetString(), rank_result.GetString(), suit_result.GetString());
  // Positive means an occupied face-card slot.  Value -3 remains distinct from
  // both EMPTY (-2) and cardback (-1) all the way through reconstruction.
  return 2;'''
    regex_once(rel, pattern, replacement, "non-empty UNKNOWN remains occupied")

    # v4.2 owns normal round inference.  Count occupied board slots, not only
    # successfully classified identities.
    replace_once(
        rel,
        '''  const int hero_board_known =
    obs->players[hero_chair].visual_board.CountKnownCards();
  const int board_plus_current = hero_board_known + obs->hero_loose_count;
''',
        '''  const int hero_board_occupied =
    obs->players[hero_chair].visual_board.CountOccupiedCards();
  const int board_plus_current = hero_board_occupied + obs->hero_loose_count;
''',
        "round cardinality counts UNKNOWN")
    path, text, eol, bom = read_source(rel)
    # Only the v4.2 diagnostic block uses this local variable name.
    text = text.replace("hero_board_known, obs->hero_loose_count", "hero_board_occupied, obs->hero_loose_count")
    write_source(path, text, eol, bom)

    # Insert a cheap current-bitmap Fantasy probe after the generic compatibility
    # helpers have been materialized.  It uses the same dynamic recognizer that
    # later supplies the draggable objects; the static one-pixel region becomes
    # a hint, not a single point of failure.
    function_anchor = "bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {\n"
    path, text, eol, bom = read_source(rel)
    if text.count(function_anchor) != 1:
        raise RuntimeError("Fantasy scraper function anchor not unique")
    helper = r'''// OPENOFC_FANTASY_ENTRY_V544.  Independent current-bitmap proof that the
// screen contains one complete Fantasy deal.  It has no click authority and
// does not mutate canonical state.
static bool OpenOFCProbeFantasyCurrentBitmap(
    HBITMAP table_bitmap,
    int player_count,
    int hero_chair,
    int *detected_count,
    std::string *detail) {
  if (detected_count != NULL) *detected_count = 0;
  if (detail != NULL) detail->clear();
  if (p_tablemap == NULL
      || !p_tablemap->OFCFantasyRecognizerCalibrated()
      || !p_tablemap->OFCFantasyGeometryMeasured()
      || player_count != 2 || hero_chair != 1) {
    if (detail != NULL) *detail = "authority_or_geometry_unavailable";
    return false;
  }

  const int row_counts[3] = {3, 5, 5};
  const char *row_names[3] = {"top", "middle", "bottom"};
  std::vector<RECT> arrangement_rects;
  for (int row = 0; row < 3; ++row) {
    for (int i = 0; i < row_counts[row]; ++i) {
      CString generic_name, legacy_name;
      generic_name.Format("ofc_fantasy_arrange_%s%d", row_names[row], i);
      legacy_name.Format("ofc_fantasy15_arrange_%s%d", row_names[row], i);
      RECT rect;
      if (!DeepOFCReadRegionRectCompat(generic_name, legacy_name, &rect)) {
        if (detail != NULL) *detail = "arrangement_geometry_missing";
        return false;
      }
      arrangement_rects.push_back(rect);
    }
  }

  std::vector<bool> occupied;
  std::vector<COFCFantasyPixelCard> arrangement_cards;
  std::string error;
  if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
        table_bitmap, arrangement_rects,
        &occupied, &arrangement_cards, &error)) {
    if (detail != NULL) *detail = "arrangement:" + error;
    return false;
  }

  int arranged = 0;
  std::set<int> seen;
  for (size_t i = 0; i < occupied.size(); ++i) {
    if (!occupied[i]) continue;
    const int value = DeepOFCPixelCardValue(arrangement_cards[i]);
    if (value < 0 || !seen.insert(value).second) {
      if (detail != NULL) *detail = "arrangement_identity_rejected";
      return false;
    }
    ++arranged;
  }

  std::vector<COFCFantasyPixelObject> loose;
  if (!COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(
        table_bitmap, arranged == 13, &loose, &error)) {
    if (detail != NULL) *detail = "loose:" + error;
    return false;
  }
  for (size_t i = 0; i < loose.size(); ++i) {
    if (!loose[i].valid || !loose[i].fresh_from_current_bitmap) {
      if (detail != NULL) *detail = "loose_object_not_fresh";
      return false;
    }
    const int value = DeepOFCPixelCardValue(loose[i].card);
    if (value < 0 || !seen.insert(value).second) {
      if (detail != NULL) *detail = "loose_identity_rejected";
      return false;
    }
  }

  const int total = arranged + static_cast<int>(loose.size());
  if (total < 14 || total > 17) {
    if (detail != NULL) {
      std::ostringstream oss;
      oss << "count=" << total << " arranged=" << arranged
          << " loose=" << loose.size();
      *detail = oss.str();
    }
    return false;
  }
  if (detected_count != NULL) *detected_count = total;
  if (detail != NULL) *detail = "current_bitmap_14_17";
  return true;
}

'''
    text = text.replace(function_anchor, helper + function_anchor, 1)
    write_source(path, text, eol, bom)

    # Replace the mandatory static gate.  Previous Fantasy is a continuity hint;
    # if it is the only hint and the full Fantasy scrape fails, strict normal
    # scraping is allowed to prove that the client has left Fantasy.
    pattern = r'''  bool fantasy_active = false;\n  if \(!DeepOFCReadMandatoryBoolean\(this,\n        "ofc_fantasy_active", &fantasy_active\)\) return false;\n  if \(fantasy_active\) \{.*?\n    return ScrapeOFCFantasyVisualObservation\(player_count, hero_chair\);\n  \}\n\n  int visible_joker_count = 0;'''
    replacement = r'''  bool fantasy_static = false;
  const bool have_static_fantasy_region =
    DeepOFCRegionExists("ofc_fantasy_active");
  if (have_static_fantasy_region)
    EvaluateTrueFalseRegion(&fantasy_static, "ofc_fantasy_active");

  const COFCState *previous_state = p_table_state->OFCState();
  const bool fantasy_previous = previous_state != NULL
    && previous_state->valid
    && previous_state->hero_chair == hero_chair
    && previous_state->hero_chair >= 0
    && previous_state->hero_chair < previous_state->player_count
    && previous_state->players[previous_state->hero_chair].fantasy;

  int fantasy_dynamic_count = 0;
  std::string fantasy_probe_detail;
  const bool fantasy_dynamic = OpenOFCProbeFantasyCurrentBitmap(
    _entire_window_cur, player_count, hero_chair,
    &fantasy_dynamic_count, &fantasy_probe_detail);

  if (fantasy_static || fantasy_previous || fantasy_dynamic) {
    write_log(true,
      "[OpenOFC FANTASY ENTRY] static=%d previous=%d dynamic=%d dynamic_count=%d detail=\"%s\" route=TRY_FANTASY\n",
      fantasy_static ? 1 : 0, fantasy_previous ? 1 : 0,
      fantasy_dynamic ? 1 : 0, fantasy_dynamic_count,
      fantasy_probe_detail.c_str());
    if (ScrapeOFCFantasyVisualObservation(player_count, hero_chair)) {
      return true;
    }
    if (fantasy_static || fantasy_dynamic) {
      // Current-screen evidence says Fantasy is active.  Never fall through to
      // shifted normal geometry merely because a later Fantasy glyph was weak.
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY ENTRY] route=FANTASY_RETRY_NEXT_FRAME terminal=0 normal_fallthrough=0\n");
      return false;
    }

    // Prior-state-only hint can be stale after Fantasy ends.  The failed full
    // Fantasy scrape plus no static/dynamic evidence allows the strict normal
    // path to prove the next screen; reset the partial Fantasy observation first.
    obs->Reset();
    obs->player_count = player_count;
    obs->hero_chair = hero_chair;
    OpenOFCScrapePhaseMarkers(this, obs, player_count, hero_chair);
    write_log(true,
      "[OpenOFC FANTASY ENTRY] previous_hint_stale_candidate=1 route=TRY_STRICT_NORMAL\n");
  }

  int visible_joker_count = 0;'''
    regex_once(rel, pattern, replacement, "Fantasy static/dynamic/continuity entry gate")


def patch_reconstructor_unknown_lineage():
    rel = "OpenHoldem/COFCReconstructor.cpp"
    path, text, eol, bom = read_source(rel)

    # Helper block is inserted before the first public method, after all private
    # board/set helpers are available.
    anchor = "}  // namespace\n\nbool COFCReconstructor::Reconstruct("
    if text.count(anchor) != 1:
        raise RuntimeError("COFCReconstructor namespace/public-method anchor missing")
    helpers = r'''
// OPENOFC_UNKNOWN_LINEAGE_V544 -------------------------------------------------
int UnknownCount(const COFCCard *cards, int count) {
  int result = 0;
  for (int i = 0; i < count; ++i)
    if (cards[i].value == kOFCCardUnknown) ++result;
  return result;
}

void CopyKnownAndUnknownToCards(
    const set<int> &known,
    int unknown_count,
    COFCCard *out,
    int capacity,
    int *out_count) {
  if (out_count != NULL) *out_count = 0;
  int index = 0;
  for (set<int>::const_iterator it = known.begin();
       it != known.end() && index < capacity; ++it) {
    out[index++].value = *it;
  }
  for (int i = 0; i < unknown_count && index < capacity; ++i)
    out[index++].value = kOFCCardUnknown;
  if (out_count != NULL) *out_count = index;
}

COFCCard *MutableRowCards(COFCPlayerBoard *board, EOFCRow row, int *count) {
  if (board == NULL || count == NULL) return NULL;
  if (row == kOFCRowTop) { *count = kOFCTopCards; return board->top; }
  if (row == kOFCRowMiddle) { *count = kOFCMiddleCards; return board->middle; }
  if (row == kOFCRowBottom) { *count = kOFCBottomCards; return board->bottom; }
  *count = 0;
  return NULL;
}

void RepairCommittedUnknownRows(
    COFCVisualObservation *observation,
    const COFCState *previous) {
  if (observation == NULL || previous == NULL || !previous->valid) return;
  if (observation->player_count != previous->player_count) return;
  for (int p = 0; p < observation->player_count; ++p) {
    for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
      const EOFCRow row = static_cast<EOFCRow>(r);
      const vector<int> old_values = KnownRowValues(previous->players[p].board, row);
      set<int> raw_known;
      vector<int> unknown_slots;
      int count = 0;
      COFCCard *raw = MutableRowCards(
        &observation->players[p].visual_board, row, &count);
      if (raw == NULL) continue;
      for (int i = 0; i < count; ++i) {
        if (raw[i].IsKnownPhysicalCard()) raw_known.insert(raw[i].value);
        else if (raw[i].value == kOFCCardUnknown) unknown_slots.push_back(i);
      }
      vector<int> missing;
      for (size_t i = 0; i < old_values.size(); ++i)
        if (raw_known.find(old_values[i]) == raw_known.end())
          missing.push_back(old_values[i]);
      // Exact cardinality is deliberate.  If a current-round pending UNKNOWN
      // shares the row with a missing committed card, assignment is ambiguous
      // and the frame is allowed to retry instead of guessing.
      if (!missing.empty() && missing.size() == unknown_slots.size()) {
        sort(missing.begin(), missing.end());
        for (size_t i = 0; i < missing.size(); ++i)
          raw[unknown_slots[i]].value = missing[i];
#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE
        write_log(true,
          "[OpenOFC UNKNOWN] repair=COMMITTED_LINEAGE player=%d row=%d count=%d\n",
          p, r, static_cast<int>(missing.size()));
#endif
      }
    }
  }
}

set<int> CurrentHeroKnownOutsideCommitted(
    const COFCVisualObservation &observation,
    const COFCState &previous) {
  set<int> result = CardArraySet(
    observation.hero_loose_cards, observation.hero_loose_count);
  const set<int> committed = KnownBoardSet(previous.players[previous.hero_chair].board);
  const COFCPlayerBoard &visual = observation.players[observation.hero_chair].visual_board;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    const vector<int> values = KnownRowValues(visual, static_cast<EOFCRow>(r));
    for (size_t i = 0; i < values.size(); ++i)
      if (committed.find(values[i]) == committed.end()) result.insert(values[i]);
  }
  return result;
}

int CurrentHeroUnknownOutsideCommitted(const COFCVisualObservation &observation) {
  int result = UnknownCount(observation.hero_loose_cards, observation.hero_loose_count);
  const COFCPlayerBoard &visual = observation.players[observation.hero_chair].visual_board;
  for (int i = 0; i < kOFCTopCards; ++i)
    if (visual.top[i].value == kOFCCardUnknown) ++result;
  for (int i = 0; i < kOFCMiddleCards; ++i)
    if (visual.middle[i].value == kOFCCardUnknown) ++result;
  for (int i = 0; i < kOFCBottomCards; ++i)
    if (visual.bottom[i].value == kOFCCardUnknown) ++result;
  return result;
}

bool ReplaceOneCurrentUnknown(COFCVisualObservation *observation, int value) {
  if (observation == NULL) return false;
  for (int i = 0; i < observation->hero_loose_count; ++i) {
    if (observation->hero_loose_cards[i].value != kOFCCardUnknown) continue;
    observation->hero_loose_cards[i].value = value;
    if (observation->hero_loose_sources[i].valid)
      observation->hero_loose_sources[i].card_value = value;
    return true;
  }
  COFCPlayerBoard *visual = &observation->players[observation->hero_chair].visual_board;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    int count = 0;
    COFCCard *cards = MutableRowCards(visual, static_cast<EOFCRow>(r), &count);
    for (int i = 0; i < count; ++i) {
      if (cards[i].value == kOFCCardUnknown) {
        cards[i].value = value;
        return true;
      }
    }
  }
  return false;
}

bool ReplaceOneCurrentKnownWithUnknown(
    COFCVisualObservation *observation, int value) {
  if (observation == NULL) return false;
  for (int i = 0; i < observation->hero_loose_count; ++i) {
    if (observation->hero_loose_cards[i].value != value) continue;
    observation->hero_loose_cards[i].value = kOFCCardUnknown;
    if (observation->hero_loose_sources[i].valid)
      observation->hero_loose_sources[i].card_value = kOFCCardUnknown;
    return true;
  }
  COFCPlayerBoard *visual = &observation->players[observation->hero_chair].visual_board;
  const set<int> committed = KnownBoardSet(
    p_table_state == NULL ? COFCPlayerBoard()
      : COFCPlayerBoard());
  (void)committed;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    int count = 0;
    COFCCard *cards = MutableRowCards(visual, static_cast<EOFCRow>(r), &count);
    for (int i = 0; i < count; ++i) {
      if (cards[i].value == value) {
        cards[i].value = kOFCCardUnknown;
        return true;
      }
    }
  }
  return false;
}

void RepairSameRoundIncomingIdentity(
    COFCVisualObservation *observation,
    const COFCState *previous) {
  if (observation == NULL || previous == NULL || !previous->valid) return;
  if (observation->hero_chair != previous->hero_chair
      || observation->round_index != previous->round_index
      || observation->round_index < 0
      || previous->players[previous->hero_chair].fantasy) return;

  const set<int> previous_known = CardArraySet(
    previous->hero_incoming, previous->hero_incoming_count);
  const int previous_unknown = UnknownCount(
    previous->hero_incoming, previous->hero_incoming_count);
  set<int> current_known = CurrentHeroKnownOutsideCommitted(*observation, *previous);
  int current_unknown = CurrentHeroUnknownOutsideCommitted(*observation);

  if (previous_unknown == 0 && current_unknown == 1) {
    const set<int> missing = Difference(previous_known, current_known);
    const set<int> extra = Difference(current_known, previous_known);
    if (missing.size() == 1 && extra.empty()) {
      ReplaceOneCurrentUnknown(observation, *missing.begin());
#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE
      write_log(true,
        "[OpenOFC UNKNOWN] repair=CURRENT_INCOMING_LINEAGE value=%d\n",
        *missing.begin());
#endif
    }
  } else if (previous_unknown == 1 && current_unknown == 0) {
    // Once a genuinely new later-round card was unread, the policy treats that
    // physical card as the safe unused card for the rest of this fixed turn.
    // If a later bitmap happens to classify it, preserve the semantic UNKNOWN
    // token so an in-flight plan cannot drift/re-solve around the same object.
    const set<int> extra = Difference(current_known, previous_known);
    if (extra.size() == 1) {
      ReplaceOneCurrentKnownWithUnknown(observation, *extra.begin());
#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE
      write_log(true,
        "[OpenOFC UNKNOWN] preserve=CURRENT_INCOMING_UNKNOWN newly_read_value=%d\n",
        *extra.begin());
#endif
    }
  }
}
// -----------------------------------------------------------------------------

'''
    text = text.replace(anchor, helpers + anchor, 1)
    write_source(path, text, eol, bom)

    # Apply lineage repair to a mutable copy before any normal validation.
    replace_once(
        rel,
        '''  COFCVisualObservation observation = input_observation;
''',
        '''  COFCVisualObservation observation = input_observation;
  RepairCommittedUnknownRows(&observation, previous);
  RepairSameRoundIncomingIdentity(&observation, previous);
''',
        "repair transient UNKNOWN before reconstruction")

    # v4.2 derived-discard block: known prior cards committed + one UNKNOWN means
    # the UNKNOWN is the derived unused card.  R0 still refuses to advance with
    # an unresolved opening identity because all five cards must be placed.
    pattern = r'''      set<int> prior_incoming =\n        CardArraySet\(previous->hero_incoming, previous->hero_incoming_count\);\n      if \(prior_incoming.empty\(\)\) \{.*?\n      canonical_discards.insert\(discard_delta.begin\(\), discard_delta.end\(\)\);'''
    replacement = r'''      set<int> prior_incoming =
        CardArraySet(previous->hero_incoming, previous->hero_incoming_count);
      const int prior_unknown = UnknownCount(
        previous->hero_incoming, previous->hero_incoming_count);
      if (prior_incoming.empty() && prior_unknown == 0) {
        return Fail(out, error, "cannot advance round without previous Hero incoming cards");
      }
      if (prior_unknown > 1) {
        return Fail(out, error, "previous Hero incoming has more than one UNKNOWN physical card");
      }

      set<int> committed_from_prior;
      for (set<int>::const_iterator it = prior_incoming.begin();
           it != prior_incoming.end(); ++it) {
        EOFCRow visible_row = kOFCRowUndefined;
        if (FindUniqueVisualRow(hero_visual, *it, &visible_row))
          committed_from_prior.insert(*it);
      }
      const int expected_commit_count = previous->round_index == 0 ? 5 : 2;
      const int expected_discard_count = previous->round_index == 0 ? 0 : 1;
      set<int> discard_delta;

      if (prior_unknown == 1) {
        if (previous->round_index == 0) {
          return Fail(out, error,
            "opening round cannot commit an unresolved UNKNOWN card");
        }
        // Later-round UNKNOWN is deliberately left loose as the unused card.
        // Therefore every known prior incoming card must now be committed.
        if (static_cast<int>(prior_incoming.size()) != expected_commit_count
            || committed_from_prior != prior_incoming) {
          return Fail(out, error,
            "UNKNOWN-unused transition did not commit both known prior incoming cards");
        }
#ifndef DEEPOFC_RECONSTRUCTOR_STANDALONE
        write_log(true,
          "[OpenOFC DISCARD] source=DERIVED_UNKNOWN_OCCUPIED previous_round=%d identity=UNREAD canonical_known_discards=%d\n",
          previous->round_index, static_cast<int>(canonical_discards.size()));
#endif
      } else {
        discard_delta = Difference(prior_incoming, committed_from_prior);
        if (static_cast<int>(committed_from_prior.size()) != expected_commit_count
            || static_cast<int>(discard_delta.size()) != expected_discard_count) {
          ostringstream oss;
          oss << "round transition visibility proof failed: previous_round="
              << previous->round_index
              << " committed=" << committed_from_prior.size()
              << "/" << expected_commit_count
              << " discarded=" << discard_delta.size()
              << "/" << expected_discard_count;
          return Fail(out, error, oss.str());
        }
        canonical_discards.insert(discard_delta.begin(), discard_delta.end());
      }'''
    regex_once(rel, pattern, replacement, "derived discard supports one UNKNOWN")

    # Replace normal current-incoming set cardinality with known + exactly one
    # optional UNKNOWN token.  Pending UNKNOWN is represented but the planner
    # will only authorize UNKNOWN as later-round unused, never as a target.
    pattern = r'''  set<int> committed_cards = KnownBoardSet\(hero_committed\);\n  set<int> pending_cards;\n  vector<pair<int, EOFCRow> > pending;.*?\n  if \(static_cast<int>\(current_incoming.size\(\)\) != expected_incoming\) \{\n    ostringstream oss;\n    oss << "round " << observation.round_index << " requires "\n        << expected_incoming << " current Hero cards; got "\n        << current_incoming.size\(\);\n    return Fail\(out, error, oss.str\(\)\);\n  \}'''
    replacement = r'''  set<int> committed_cards = KnownBoardSet(hero_committed);
  set<int> pending_known;
  int pending_unknown = 0;
  vector<pair<int, EOFCRow> > pending;
  for (int r = kOFCRowTop; r <= kOFCRowBottom; ++r) {
    EOFCRow row = static_cast<EOFCRow>(r);
    int count = 0;
    const COFCCard *cards = RowCards(hero_visual, row, &count);
    for (int i = 0; i < count; ++i) {
      const int value = cards[i].value;
      if (cards[i].IsKnownPhysicalCard()) {
        if (committed_cards.find(value) != committed_cards.end()) continue;
        if (!pending_known.insert(value).second)
          return Fail(out, error, "duplicate current Hero pending physical card");
        pending.push_back(make_pair(value, row));
      } else if (value == kOFCCardUnknown) {
        ++pending_unknown;
        pending.push_back(make_pair(kOFCCardUnknown, row));
      }
    }
  }

  set<int> loose_known = CardArraySet(
    observation.hero_loose_cards, observation.hero_loose_count);
  const int loose_unknown = UnknownCount(
    observation.hero_loose_cards, observation.hero_loose_count);
  const int current_unknown = pending_unknown + loose_unknown;
  if (current_unknown > 1) {
    return Fail(out, error,
      "normal decision supports at most one UNKNOWN occupied current card");
  }
  set<int> current_incoming = SetUnion(pending_known, loose_known);

  if (previous != NULL && previous->valid
      && previous->round_index == observation.round_index) {
    const set<int> old_incoming = CardArraySet(
      previous->hero_incoming, previous->hero_incoming_count);
    const int old_unknown = UnknownCount(
      previous->hero_incoming, previous->hero_incoming_count);
    if (old_incoming != current_incoming || old_unknown != current_unknown) {
      return Fail(out, error,
        "same-round incoming physical set changed outside UNKNOWN lineage repair");
    }
  }

  const int expected_incoming = observation.round_index == 0 ? 5 : 3;
  const int current_total =
    static_cast<int>(current_incoming.size()) + current_unknown;
  if (current_total != expected_incoming) {
    ostringstream oss;
    oss << "round " << observation.round_index << " requires "
        << expected_incoming << " current Hero cards; got "
        << current_total << " (known=" << current_incoming.size()
        << " unknown=" << current_unknown << ")";
    return Fail(out, error, oss.str());
  }'''
    regex_once(rel, pattern, replacement, "normal incoming preserves UNKNOWN occupancy")

    # Canonical incoming copy: known identities sorted, optional UNKNOWN token last.
    replace_once(
        rel,
        '''  if (static_cast<int>(current_incoming.size()) > kOFCMaxIncomingCards) {
    return Fail(out, error, "too many current incoming cards");
  }
  CopySortedValuesToCards(
    current_incoming, out->hero_incoming,
    kOFCMaxIncomingCards, &out->hero_incoming_count);
''',
        '''  if (static_cast<int>(current_incoming.size()) + current_unknown
      > kOFCMaxIncomingCards) {
    return Fail(out, error, "too many current incoming cards");
  }
  CopyKnownAndUnknownToCards(
    current_incoming, current_unknown,
    out->hero_incoming, kOFCMaxIncomingCards,
    &out->hero_incoming_count);
''',
        "canonical incoming copies UNKNOWN")

    # Current-screen recovery can also bootstrap a later round with three loose
    # cards when one is UNKNOWN and the committed board itself is fully known.
    pattern = r'''  set<int> current = CardArraySet\(\n    observation.hero_loose_cards, observation.hero_loose_count\);\n  if \(current.size\(\) != 3\) \{\n    return Fail\(out, error,\n      "current-screen normal recovery requires three unique known loose cards"\);\n  \}'''
    replacement = r'''  set<int> current = CardArraySet(
    observation.hero_loose_cards, observation.hero_loose_count);
  const int current_unknown = UnknownCount(
    observation.hero_loose_cards, observation.hero_loose_count);
  if (current_unknown > 1
      || static_cast<int>(current.size()) + current_unknown != 3) {
    return Fail(out, error,
      "current-screen normal recovery requires three occupied loose cards with at most one UNKNOWN");
  }'''
    regex_once(rel, pattern, replacement, "current-screen recovery accepts one loose UNKNOWN")

    replace_once(
        rel,
        '''  CopySortedValuesToCards(
    current, seed.hero_incoming, kOFCMaxIncomingCards,
    &seed.hero_incoming_count);
''',
        '''  CopyKnownAndUnknownToCards(
    current, current_unknown,
    seed.hero_incoming, kOFCMaxIncomingCards,
    &seed.hero_incoming_count);
''',
        "current-screen seed copies UNKNOWN")


def patch_policy_unknown_and_pending_discard():
    rel = "OpenHoldem/COFCBaselinePolicy.cpp"

    # Add a safe later-round branch before the all-known path.  No rank/suit is
    # invented: the unread physical card is simply the unused card, and the two
    # known cards are placed optimally against the committed board.
    anchor = '''  vector<PolicyCard> incoming;
  for (int i = 0; i < expected; ++i) {
    if (!state.hero_incoming[i].IsKnownPhysicalCard())
      return Fail(action, error, "normal incoming contains unknown card");
    incoming.push_back(Convert(state.hero_incoming[i].value));
  }
'''
    special = r'''  int unknown_count = 0;
  for (int i = 0; i < expected; ++i) {
    if (state.hero_incoming[i].value == kOFCCardUnknown) ++unknown_count;
    else if (!state.hero_incoming[i].IsKnownPhysicalCard())
      return Fail(action, error, "normal incoming contains non-physical card");
  }
  if (unknown_count > 1)
    return Fail(action, error, "normal incoming contains more than one UNKNOWN occupied card");
  if (unknown_count == 1) {
    if (state.round_index == 0) {
      // All five opening cards must be placed.  Without the fifth identity the
      // strategy cannot rank rows safely, so keep the valid occupied state and
      // let the next bitmap retry recognition rather than inventing a card.
      return Fail(action, error, "WAIT_TRANSIENT_UNKNOWN_OPENING");
    }
    vector<PolicyCard> readable;
    vector<int> readable_values;
    for (int i = 0; i < expected; ++i) {
      if (state.hero_incoming[i].value == kOFCCardUnknown) continue;
      readable.push_back(Convert(state.hero_incoming[i].value));
      readable_values.push_back(state.hero_incoming[i].value);
    }
    if (readable.size() != 2)
      return Fail(action, error, "UNKNOWN later round does not leave exactly two readable cards");
    vector<PolicyCard> baseline_unknown[3];
    BoardRows(state.players[state.hero_chair].board, baseline_unknown);
    long long best_unknown_score = -1;
    int best_unknown_assignments[5] = {-2, -2, -2, -2, -2};
    int assignments[5] = {-2, -2, -2, -2, -2};
    EnumerateNormal(readable, 0, -1, baseline_unknown, assignments, false,
      &best_unknown_score, best_unknown_assignments);
    if (best_unknown_score < 0) {
      // Keep v4.3's unavoidable-foul behavior for this reduced two-card search.
      best_unknown_score = (std::numeric_limits<long long>::min)() / 4;
      for (int i = 0; i < 5; ++i) best_unknown_assignments[i] = -2;
      int fallback_assignments[5] = {-2, -2, -2, -2, -2};
      vector<PolicyCard> fallback_rows[3] = {
        baseline_unknown[0], baseline_unknown[1], baseline_unknown[2]};
      EnumerateNormalAllowFoul(readable, 0, -1, fallback_rows,
        fallback_assignments, false,
        &best_unknown_score, best_unknown_assignments);
    }
    if (best_unknown_score == (std::numeric_limits<long long>::min)() / 4)
      return Fail(action, error, "no structural placement for two readable cards");

    action->Reset();
    for (int i = 0; i < 2; ++i) {
      if (best_unknown_assignments[i] < 0)
        return Fail(action, error, "readable card unexpectedly became unused");
      COFCStrategyPlacement &placement =
        action->placements[action->placement_count++];
      placement.card_value = readable_values[i];
      placement.row = static_cast<EOFCRow>(best_unknown_assignments[i]);
    }
    action->unused_cards[action->unused_count++] = kOFCCardUnknown;
    action->valid = action->placement_count == 2 && action->unused_count == 1;
    return action->valid;
  }

  vector<PolicyCard> incoming;
  for (int i = 0; i < expected; ++i)
    incoming.push_back(Convert(state.hero_incoming[i].value));
'''
    replace_once(rel, anchor, special, "later-round UNKNOWN safe discard policy")

    # Prefer a genuinely loose non-Joker discard whenever one exists.  This
    # prevents the planner from selecting an already-pending card as unused and
    # asking for the unsupported pending->loose reverse gesture.
    loop_anchor = '''  const int first_unused = state.round_index == 0 ? -1 : 0;
  const int last_unused = state.round_index == 0 ? -1 : expected - 1;
  for (int unused = first_unused; unused <= last_unused; ++unused) {
'''
    loop_replacement = r'''  const int first_unused = state.round_index == 0 ? -1 : 0;
  const int last_unused = state.round_index == 0 ? -1 : expected - 1;
  bool pending_value[54] = {false};
  for (int p = 0; p < kOFCMaxIncomingCards; ++p) {
    if (!state.pending[p].active) continue;
    const int index = state.pending[p].incoming_index;
    if (index < 0 || index >= state.hero_incoming_count) continue;
    const int value = state.hero_incoming[index].value;
    if (value >= 0 && value < 54) pending_value[value] = true;
  }
  bool have_loose_nonjoker_discard = false;
  for (int i = 0; i < expected; ++i) {
    const int value = state.hero_incoming[i].value;
    if (value >= 0 && value < 54
        && !pending_value[value]
        && value != kOFCCardJoker1 && value != kOFCCardJoker2) {
      have_loose_nonjoker_discard = true;
    }
  }
  for (int unused = first_unused; unused <= last_unused; ++unused) {
'''
    replace_once(rel, loop_anchor, loop_replacement, "identify loose discard candidates")

    # There are two loops after v4.3: strict and unavoidable-foul fallback.
    path, text, eol, bom = read_source(rel)
    needle = '''    if (unused >= 0 && incoming[unused].joker != 0) continue;
'''
    if text.count(needle) != 2:
        raise RuntimeError(f"expected two normal discard loops after v4.3, got {text.count(needle)}")
    guarded = '''    if (unused >= 0 && incoming[unused].joker != 0) continue;
    if (unused >= 0 && have_loose_nonjoker_discard
        && pending_value[incoming[unused].value]) continue;
'''
    text = text.replace(needle, guarded)
    write_source(path, text, eol, bom)


def patch_turn_plan_unknown_unused():
    rel = "OpenHoldem/COFCTurnPlan.cpp"

    replace_once(
        rel,
        '''  bool incoming[54] = {false};
  bool target_present[54] = {false};
  bool unused_present[54] = {false};
''',
        '''  bool incoming[54] = {false};
  bool target_present[54] = {false};
  bool unused_present[54] = {false};
  int incoming_unknown = 0;
  int unused_unknown = 0;
''',
        "turn-plan UNKNOWN counters")

    replace_once(
        rel,
        '''  for (int i = 0; i < state.hero_incoming_count; ++i) {
    const int card = state.hero_incoming[i].value;
    if (!KnownPhysical(card)) {
      return Fail(out, error, "Hero incoming contains non-physical/unknown card");
    }
    if (incoming[card]) {
      return Fail(out, error, "Hero incoming contains duplicate physical card");
    }
    incoming[card] = true;
  }
''',
        '''  for (int i = 0; i < state.hero_incoming_count; ++i) {
    const int card = state.hero_incoming[i].value;
    if (card == kOFCCardUnknown) {
      ++incoming_unknown;
      if (incoming_unknown > 1)
        return Fail(out, error, "Hero incoming contains multiple UNKNOWN occupied cards");
      continue;
    }
    if (!KnownPhysical(card)) {
      return Fail(out, error, "Hero incoming contains non-physical card");
    }
    if (incoming[card]) {
      return Fail(out, error, "Hero incoming contains duplicate physical card");
    }
    incoming[card] = true;
  }
''',
        "turn-plan accepts one UNKNOWN incoming")

    replace_once(
        rel,
        '''  for (int i = 0; i < action.unused_count; ++i) {
    const int card = action.unused_cards[i];
    if (!KnownPhysical(card) || !incoming[card]) {
      return Fail(out, error, "strategy unused card is not a current Hero incoming physical card");
    }
    if (target_present[card] || unused_present[card]) {
      return Fail(out, error, "strategy action accounts for one physical card more than once");
    }
    unused_present[card] = true;
    out->unused_cards[out->unused_count++] = card;
  }
''',
        '''  for (int i = 0; i < action.unused_count; ++i) {
    const int card = action.unused_cards[i];
    if (card == kOFCCardUnknown) {
      if (incoming_unknown != 1 || unused_unknown != 0)
        return Fail(out, error, "strategy UNKNOWN unused card does not match incoming occupancy");
      ++unused_unknown;
      out->unused_cards[out->unused_count++] = card;
      continue;
    }
    if (!KnownPhysical(card) || !incoming[card]) {
      return Fail(out, error, "strategy unused card is not a current Hero incoming physical card");
    }
    if (target_present[card] || unused_present[card]) {
      return Fail(out, error, "strategy action accounts for one physical card more than once");
    }
    unused_present[card] = true;
    out->unused_cards[out->unused_count++] = card;
  }
''',
        "turn-plan allows UNKNOWN only as unused")

    replace_once(
        rel,
        '''  for (int card = 0; card < 54; ++card) {
    if (incoming[card] != (target_present[card] || unused_present[card])) {
      return Fail(out, error, "strategy action does not partition the full incoming physical-card set");
    }
  }
''',
        '''  for (int card = 0; card < 54; ++card) {
    if (incoming[card] != (target_present[card] || unused_present[card])) {
      return Fail(out, error, "strategy action does not partition the full incoming physical-card set");
    }
  }
  if (incoming_unknown != unused_unknown) {
    return Fail(out, error,
      "UNKNOWN occupied incoming must remain loose as the strategy unused card");
  }
''',
        "turn-plan partitions UNKNOWN")

    # Pending UNKNOWN cannot be reversed to loose; refuse before any physical
    # mutation with an explicit transient reason.
    replace_once(
        rel,
        '''    const int card = state.hero_incoming[incoming_index].value;
    if (!KnownPhysical(card) || pending_present[card]) {
      return Fail(out, error, "pending placement physical identity is invalid/duplicated");
    }
''',
        '''    const int card = state.hero_incoming[incoming_index].value;
    if (card == kOFCCardUnknown) {
      return Fail(out, error,
        "UNKNOWN occupied card is already pending; wait for a fresh readable frame before planning");
    }
    if (!KnownPhysical(card) || pending_present[card]) {
      return Fail(out, error, "pending placement physical identity is invalid/duplicated");
    }
''',
        "pending UNKNOWN stays fail-safe")


def patch_runtime_stabilization_and_recovery():
    hrel = "OpenHoldem/COFCRuntimeController.h"
    path, text, eol, bom = read_source(hrel)
    marker = "  static std::string StateFingerprint(const COFCState &state);\n"
    if text.count(marker) != 1:
        raise RuntimeError("runtime header StateFingerprint marker missing")
    text = text.replace(
        marker,
        marker
        + "  void ArmDecisionStabilization(const COFCState &state, const char *reason);\n"
          "  bool DecisionStabilized(const COFCState &state);\n"
          "  static int UnknownIncomingCount(const COFCState &state);\n",
        1)
    member = "  bool recovery_requires_change_;\n"
    if text.count(member) != 1:
        raise RuntimeError("runtime header recovery member missing")
    text = text.replace(
        member,
        member
        + "  // OPENOFC_ROUND_STABILIZATION_V544: no drag is emitted until the\n"
          "  Hero semantic fingerprint has remained unchanged for the configured\n"
          "  post-deal animation interval.\n"
          "  bool decision_stabilizing_;\n"
          "  DWORD decision_stable_since_tick_;\n"
          "  std::string decision_stable_fingerprint_;\n",
        1)
    write_source(path, text, eol, bom)

    rel = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_source(rel)

    # Constructor body is created by v5.4 continuity; initialize the new fields.
    replace = '''  reacquire_stable_cycles_ = 0;
  recovery_requires_change_ = false;
'''
    if text.count(replace) != 1:
        raise RuntimeError("runtime constructor v5.4 body missing")
    text = text.replace(
        replace,
        replace
        + "  decision_stabilizing_ = false;\n"
          "  decision_stable_since_tick_ = 0;\n",
        1)

    anchor = "void COFCRuntimeController::ResetForKnownNewHand(const COFCState &state) {\n"
    if text.count(anchor) != 1:
        raise RuntimeError("ResetForKnownNewHand anchor missing")
    methods = r'''int COFCRuntimeController::UnknownIncomingCount(const COFCState &state) {
  int count = 0;
  for (int i = 0; i < state.hero_incoming_count; ++i)
    if (state.hero_incoming[i].value == kOFCCardUnknown) ++count;
  return count;
}

void COFCRuntimeController::ArmDecisionStabilization(
    const COFCState &state, const char *reason) {
  decision_stabilizing_ = true;
  decision_stable_since_tick_ = GetTickCount();
  decision_stable_fingerprint_ = StateFingerprint(state);
  write_log(true,
    "[OpenOFC STABILIZE] arm=1 reason=%s round=%d fantasy=%d fingerprint=\"%s\"\n",
    reason == NULL ? "UNSPECIFIED" : reason,
    state.round_index,
    (state.hero_chair >= 0 && state.hero_chair < state.player_count
      && state.players[state.hero_chair].fantasy) ? 1 : 0,
    decision_stable_fingerprint_.c_str());
}

bool COFCRuntimeController::DecisionStabilized(const COFCState &state) {
  if (!decision_stabilizing_) return true;
  const string now = StateFingerprint(state);
  if (now != decision_stable_fingerprint_) {
    decision_stable_fingerprint_ = now;
    decision_stable_since_tick_ = GetTickCount();
    write_log(true,
      "[OpenOFC STABILIZE] reset=1 reason=SEMANTIC_STATE_CHANGED round=%d\n",
      state.round_index);
    return false;
  }
  const int configured = p_tablemap == NULL ? 1000
    : p_tablemap->GetTMSymbol("ofc_round_stabilize_ms", 1000);
  const DWORD required = static_cast<DWORD>(max(0, configured));
  const DWORD elapsed = GetTickCount() - decision_stable_since_tick_;
  if (elapsed < required) {
    write_log(true,
      "[OpenOFC STABILIZE] wait=1 round=%d elapsed_ms=%lu required_ms=%lu\n",
      state.round_index,
      static_cast<unsigned long>(elapsed),
      static_cast<unsigned long>(required));
    return false;
  }
  decision_stabilizing_ = false;
  write_log(true,
    "[OpenOFC STABILIZE] ready=1 round=%d elapsed_ms=%lu\n",
    state.round_index, static_cast<unsigned long>(elapsed));
  return true;
}

'''
    text = text.replace(anchor, methods + anchor, 1)

    # Every known-new-hand reset clears stale stabilization bookkeeping; Tick
    # immediately arms a fresh barrier for the new semantic edge.
    reset_tail = '''  recovery_requires_change_ = false;
  phase_ = kIdle;
'''
    if text.count(reset_tail) != 1:
        raise RuntimeError("ResetForKnownNewHand v5.4 tail missing")
    text = text.replace(
        reset_tail,
        '''  recovery_requires_change_ = false;
  decision_stabilizing_ = false;
  decision_stable_since_tick_ = 0;
  decision_stable_fingerprint_.clear();
  phase_ = kIdle;
''',
        1)

    # Next-round semantic edge must arm, not immediately drag in the same Tick.
    pattern = r'''  g_openofc_flow_phase = kOpenOFCFlowRoundActive;\n  g_openofc_expected_round = state.round_index;\n  return StartDecision\(state, \*p_table_state->OFCVisualObservation\(\)\);\n\}'''
    replacement = r'''  g_openofc_flow_phase = kOpenOFCFlowRoundActive;
  g_openofc_expected_round = state.round_index;
  ArmDecisionStabilization(state, "NEXT_ROUND_EDGE");
  return true;
}'''
    regex_once(rel, pattern, replacement, "post-Confirm round edge stabilization")
    path, text, eol, bom = read_source(rel)

    # New hand edge in Tick.
    old = '''    ResetForKnownNewHand(state);
    g_openofc_flow_phase = kOpenOFCFlowRoundActive;
'''
    if text.count(old) != 1:
        raise RuntimeError("Tick known-new-hand block missing")
    text = text.replace(
        old,
        '''    ResetForKnownNewHand(state);
    ArmDecisionStabilization(state, "NEW_HAND_EDGE");
    g_openofc_flow_phase = kOpenOFCFlowRoundActive;
''',
        1)

    # Runtime reacquire acceptance is another animation-sensitive edge.
    old = '''    recovery_requires_change_ = false;
    write_log(k_always_log_errors,
      "[OpenOFC REACQUIRE_ACCEPT] source=RUNTIME_CONTROLLER hero_state_changed=%d next=IDLE terminal=0\\n",
'''
    if text.count(old) != 1:
        raise RuntimeError("runtime reacquire accept block missing")
    text = text.replace(
        old,
        '''    recovery_requires_change_ = false;
    ArmDecisionStabilization(state, "REACQUIRE_ACCEPT");
    write_log(k_always_log_errors,
      "[OpenOFC REACQUIRE_ACCEPT] source=RUNTIME_CONTROLLER hero_state_changed=%d next=IDLE terminal=0\\n",
''',
        1)

    # Idle: R0 with an unread card is valid perception, but strategy waits for a
    # readable identity; all other decisions must pass the stabilization fence.
    old = '''  if (phase_ == kIdle) {
    if (!OpenOFCNormalDecisionReady(state)) {
'''
    if text.count(old) != 1:
        raise RuntimeError("runtime Idle decision block missing")
    text = text.replace(
        old,
        '''  if (phase_ == kIdle) {
    if (!state.players[state.hero_chair].fantasy
        && state.round_index == 0
        && UnknownIncomingCount(state) > 0) {
      write_log(true,
        "[OpenOFC UNKNOWN] action=WAIT reason=OPENING_IDENTITY_UNREAD occupied_incoming=%d terminal=0 continue_scraping=1\\n",
        state.hero_incoming_count);
      return;
    }
    if (!DecisionStabilized(state)) return;
    if (!OpenOFCNormalDecisionReady(state)) {
''',
        1)

    # If a fresh valid state proves that the game already advanced to another
    # normal round while an old drag transaction was active, the old plan is
    # superseded rather than fed into SameStrategicDecision and converted into a
    # stale REACQUIRE loop.
    old = '''  if (phase_ == kArranging) AdvanceArrangement(state, observation);
'''
    if text.count(old) != 1:
        raise RuntimeError("runtime arranging tail missing")
    text = text.replace(
        old,
        '''  if (phase_ == kArranging && plan_.valid
      && !state.players[state.hero_chair].fantasy
      && plan_.decision_state.round_index >= 0
      && state.round_index >= 0
      && state.round_index != plan_.decision_state.round_index) {
    write_log(k_always_log_errors,
      "[OpenOFC TRANSACTION] superseded=1 old_round=%d new_round=%d action=ABANDON_OLD_PLAN terminal=0\\n",
      plan_.decision_state.round_index, state.round_index);
    orchestrator_.ResetForKnownNewHand();
    fantasy_executor_.Reset();
    plan_.Reset();
    confirm_before_.Reset();
    pending_before_drag_ = 0;
    pending_signature_before_drag_.clear();
    drag_wait_cycles_ = 0;
    drag_retry_count_ = 0;
    provisional_ = false;
    phase_ = kIdle;
    ArmDecisionStabilization(state, "ROUND_SUPERSEDED_OLD_TRANSACTION");
    return;
  }
  if (phase_ == kArranging) AdvanceArrangement(state, observation);
''',
        1)

    # Expose retry tuning in the TableMap without changing conservative defaults.
    text = text.replace(
        '''    const int kOpenOFCDragObservationWaitCycles = 8;
''',
        '''    const int kOpenOFCDragObservationWaitCycles = p_tablemap == NULL ? 8
      : max(2, p_tablemap->GetTMSymbol("ofc_drag_verify_wait_cycles", 8));
''',
        1)
    text = text.replace(
        '''    if (drag_retry_count_ < 1) {
''',
        '''    const int drag_retry_limit = p_tablemap == NULL ? 1
      : max(0, p_tablemap->GetTMSymbol("ofc_drag_retry_limit", 1));
    if (drag_retry_count_ < drag_retry_limit) {
''',
        1)

    write_source(path, text, eol, bom)


def assert_contract():
    required = {
        "OpenHoldem/COFCState.h": [
            "OPENOFC_UNKNOWN_OCCUPIED_V544",
            "IsOccupiedPhysicalCard",
            "CountOccupiedCards",
        ],
        "OpenHoldem/COFCScraper.cpp": [
            "OPENOFC_FANTASY_ENTRY_V544",
            "OpenOFCProbeFantasyCurrentBitmap",
            "UNKNOWN_OCCUPIED",
            "fantasy_dynamic",
            "CountOccupiedCards",
        ],
        "OpenHoldem/COFCReconstructor.cpp": [
            "OPENOFC_UNKNOWN_LINEAGE_V544",
            "RepairCommittedUnknownRows",
            "current_unknown",
            "DERIVED_UNKNOWN_OCCUPIED",
        ],
        "OpenHoldem/COFCBaselinePolicy.cpp": [
            "WAIT_TRANSIENT_UNKNOWN_OPENING",
            "have_loose_nonjoker_discard",
            "action->unused_cards[action->unused_count++] = kOFCCardUnknown",
        ],
        "OpenHoldem/COFCTurnPlan.cpp": [
            "incoming_unknown",
            "UNKNOWN occupied incoming must remain loose",
        ],
        "OpenHoldem/COFCRuntimeController.cpp": [
            "OPENOFC STABILIZE",
            "ofc_round_stabilize_ms",
            "ROUND_SUPERSEDED_OLD_TRANSACTION",
            "ofc_drag_retry_limit",
            "OPENING_IDENTITY_UNREAD",
        ],
    }
    for rel, markers in required.items():
        text = (ROOT / rel).read_text(encoding="utf-8-sig")
        missing = [m for m in markers if m not in text]
        if missing:
            raise RuntimeError(f"{rel}: missing v5.4.4 markers: {missing}")

    runtime = (ROOT / "OpenHoldem/COFCRuntimeController.cpp").read_text(
        encoding="utf-8-sig")
    scraper = (ROOT / "OpenHoldem/COFCScraper.cpp").read_text(
        encoding="utf-8-sig")
    if 'DeepOFCReadMandatoryBoolean(this,\n        "ofc_fantasy_active"' in scraper:
        raise RuntimeError("mandatory single-pixel Fantasy entry gate survived")
    if "return StartDecision(state, *p_table_state->OFCVisualObservation());" in runtime:
        raise RuntimeError("same-tick next-round StartDecision survived stabilization patch")
    print("OpenOFC v5.4.4 field-recovery source contract: PASS")


def main():
    patch_card_occupancy_contract()
    patch_scraper_unknown_and_fantasy_entry()
    patch_reconstructor_unknown_lineage()
    patch_policy_unknown_and_pending_discard()
    patch_turn_plan_unknown_unused()
    patch_runtime_stabilization_and_recovery()
    assert_contract()
    print("OpenOFC v5.4.4 Fantasy/UNKNOWN/runtime recovery patch applied successfully")


if __name__ == "__main__":
    main()
