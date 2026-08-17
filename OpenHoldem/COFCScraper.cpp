//******************************************************************************
// DeepOFC read-only KKPoker Joker Ultimate scraper.
// Populates only COFCVisualObservation; legacy Hold'em cards are untouched.
//******************************************************************************

#include "StdAfx.h"
#include "CScraper.h"

#include <set>
#include <vector>

#include "CardFunctions.h"
#include "COFCFantasy15PixelRecognizer.h"
#include "CTableState.h"

using namespace std;

// Native Fantasy recognition is a separate capability from tablemap mode
// detection. Keep this 0 until a real-pixel C++ replay gate certifies the
// implementation. A tablemap value alone can never make an unfinished build
// treat Fantasy pixels as a valid observation.
#define DEEPOFC_NATIVE_FANTASY15_RECOGNIZER_CERTIFIED 1

static int DeepOFCPixelCardValue(const COFCFantasy15PixelCard &card) {
  if (!card.valid) return kOFCCardUnknown;
  if (card.joker_id == 1) return kOFCCardJoker1;
  if (card.joker_id == 2) return kOFCCardJoker2;
  if (card.rank == 0 || card.suit == 0) return kOFCCardUnknown;
  char code[3] = {card.rank, card.suit, 0};
  return CardStringToCardNumber(code);
}

static string DeepOFCPhysicalLabel(int value) {
  if (value == kOFCCardJoker1) return "JK1";
  if (value == kOFCCardJoker2) return "JK2";
  if (value < 0 || value > 51) return "AMBIGUOUS";
  const char ranks[] = "23456789TJQKA";
  const char suits[] = "cdhs";
  string label;
  label.push_back(ranks[StdDeck_RANK(value)]);
  label.push_back(suits[StdDeck_SUIT(value)]);
  return label;
}

static bool DeepOFCRegionExists(const CString &name) {
  return p_tablemap->r$()->find(name) != p_tablemap->r$()->end();
}

static bool DeepOFCReadRegionRect(const CString &name, RECT *out) {
  if (out == NULL) return false;
  SetRectEmpty(out);
  RMapCI it = p_tablemap->r$()->find(name);
  if (it == p_tablemap->r$()->end()) return false;
  out->left = static_cast<LONG>(it->second.left);
  out->top = static_cast<LONG>(it->second.top);
  out->right = static_cast<LONG>(it->second.right);
  out->bottom = static_cast<LONG>(it->second.bottom);
  return out->right > out->left && out->bottom > out->top;
}

int CScraper::ScrapeOFCSlot(CString base_name, COFCCard *card,
    bool *is_back, int *joker_id) {
  if ((card == NULL) || (is_back == NULL) || (joker_id == NULL)) return -1;
  card->Clear();
  *is_back = false;
  *joker_id = 0;

  const CString empty_region = base_name + "empty";
  const CString back_region = base_name + "back";
  const CString joker1_region = base_name + "joker1";
  const CString joker2_region = base_name + "joker2";
  const CString rank_region = base_name + "rank";
  const CString suit_region = base_name + "suit";

  // Negative/background gate: faces and card-backs do not share one reliable
  // positive occupancy colour. If the background is not empty, classification
  // must succeed or the whole OFC observation is rejected.
  if (!DeepOFCRegionExists(empty_region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Missing mandatory slot empty region: %s\n",
      empty_region.GetString());
    return -1;
  }
  bool empty = false;
  EvaluateTrueFalseRegion(&empty, empty_region);
  if (empty) return 0;

  if (!DeepOFCRegionExists(back_region)
      || !DeepOFCRegionExists(joker1_region)
      || !DeepOFCRegionExists(joker2_region)
      || !DeepOFCRegionExists(rank_region)
      || !DeepOFCRegionExists(suit_region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Non-empty slot lacks back/joker1/joker2/rank/suit contract: %s\n",
      base_name.GetString());
    return -1;
  }

  bool back = false;
  bool joker1 = false;
  bool joker2 = false;
  EvaluateTrueFalseRegion(&back, back_region);
  EvaluateTrueFalseRegion(&joker1, joker1_region);
  EvaluateTrueFalseRegion(&joker2, joker2_region);
  if ((joker1 && joker2) || (back && (joker1 || joker2))) {
    write_log(k_always_log_errors,
      "[DeepOFC] Ambiguous back/Joker identity classification: %s\n",
      base_name.GetString());
    return -2;
  }
  if (back) {
    *is_back = true;
    return 0;
  }

  // The supplied Fantasy replay proves persistent visual identity: JK1 is the
  // orange/red pineapple Joker and JK2 is the gray/black pineapple Joker. On a
  // confirmed board KKPoker may additionally show nominal rank/suit glyphs on
  // a gold card; the color-coded Joker marker still identifies the physical
  // card and therefore takes precedence over rank/suit parsing.
  if (joker1) {
    *joker_id = 1;
    card->value = kOFCCardJoker1;
    return 1;
  }
  if (joker2) {
    *joker_id = 2;
    card->value = kOFCCardJoker2;
    return 1;
  }


  RECT rank_rect;
  if (!DeepOFCReadRegionRect(rank_region, &rank_rect)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Non-empty slot has invalid rank geometry: %s\n",
      base_name.GetString());
    return -3;
  }
  RECT native_rect;
  native_rect.left = rank_rect.left;
  native_rect.top = rank_rect.top;
  native_rect.right = std::min<LONG>(450, native_rect.left + 55);
  native_rect.bottom = std::min<LONG>(830, native_rect.top + 71);

  int persistent_joker = 0;
  std::string native_error;
  const bool wide_normal_slot = base_name.Find("discard") < 0;
  if (wide_normal_slot) {
    if (!COFCFantasy15PixelRecognizer::DetectPersistentJoker(
          _entire_window_cur, native_rect, &persistent_joker, &native_error)) {
      write_log(k_always_log_errors,
        "[DeepOFC] Persistent Joker probe failed: %s\n", native_error.c_str());
      return -3;
    }
  }
  if (persistent_joker != 0) {
    *joker_id = persistent_joker;
    card->value = persistent_joker == 1 ? kOFCCardJoker1 : kOFCCardJoker2;
    return 1;
  }

  const int legacy_card = ScrapeCardByRankAndSuit(base_name);
  if ((legacy_card >= 0) && (legacy_card <= 51)) {
    card->value = legacy_card;
    return 1;
  }

  // Normal Hero Jokers do not expose a conventional rank/suit pair. Use the
  // same replay-backed upright physical-card classifier as Fantasy before
  // rejecting the whole observation. Small opponent transitional faces still
  // fail closed; their confirmed gold marker is handled above.
  COFCFantasy15PixelCard native_card;
  if (wide_normal_slot && COFCFantasy15PixelRecognizer::RecognizeUprightCard(
        _entire_window_cur, native_rect, &native_card, &native_error)) {
    const int value = DeepOFCPixelCardValue(native_card);
    if (value >= 0) {
      card->value = value;
      *joker_id = native_card.joker_id;
      return 1;
    }
  }

  write_log(k_always_log_errors,
    "[DeepOFC] Non-empty slot has no unambiguous standard/persistent-Joker face: %s (%s)\n",
    base_name.GetString(), native_error.c_str());
  return -3;
}

static bool DeepOFCRegisterKnownCard(int value, set<int> *seen) {
  if ((value < 0) || (value > kOFCCardJoker2)) return true;
  if (seen->find(value) != seen->end()) return false;
  seen->insert(value);
  return true;
}

static bool DeepOFCObservationHasUniqueKnownCards(
    const COFCVisualObservation *observation) {
  set<int> seen;
  for (int p = 0; p < observation->player_count; ++p) {
    const COFCPlayerBoard &b = observation->players[p].visual_board;
    for (int i = 0; i < kOFCTopCards; ++i)
      if (b.top[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(b.top[i].value, &seen)) return false;
    for (int i = 0; i < kOFCMiddleCards; ++i)
      if (b.middle[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(b.middle[i].value, &seen)) return false;
    for (int i = 0; i < kOFCBottomCards; ++i)
      if (b.bottom[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(b.bottom[i].value, &seen)) return false;
  }
  for (int i = 0; i < observation->hero_loose_count; ++i)
    if (observation->hero_loose_cards[i].IsKnownPhysicalCard()
        && !DeepOFCRegisterKnownCard(observation->hero_loose_cards[i].value, &seen)) return false;
  for (int i = 0; i < observation->hero_discard_tracker_count; ++i)
    if (observation->hero_discard_tracker[i].IsKnownPhysicalCard()
        && !DeepOFCRegisterKnownCard(observation->hero_discard_tracker[i].value, &seen)) return false;
  return true;
}

static bool DeepOFCReadMandatoryBoolean(CScraper *scraper,
    const CString &region, bool *value) {
  if (!DeepOFCRegionExists(region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Missing mandatory boolean region: %s\n", region.GetString());
    return false;
  }
  *value = false;
  scraper->EvaluateTrueFalseRegion(value, region);
  return true;
}

bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {
  // TableMap authority and a separately certified native capability must both
  // be present. An edited tablemap alone can never activate pixel recognition.
  if (!p_tablemap->OFCFantasyRecognizerCalibrated()) {
    write_log(k_always_log_errors,
      "[DeepOFC] Fantasy recognizer route called without tablemap authority\n");
    return false;
  }
  if (!p_tablemap->OFCFantasy15GeometryMeasured()) {
    write_log(k_always_log_errors,
      "[DeepOFC] Fantasy recognizer authority present but measured Fantasy15 geometry is absent\n");
    return false;
  }
  if (player_count != 2 || hero_chair != 1) {
    // Current measured 450x830 Fantasy geometry is HU/hero-chair-1 only.
    // Never extrapolate it to 3-player or another chair mapping.
    write_log(k_always_log_errors,
      "[DeepOFC] Current Fantasy15 geometry only certifies HU hero_chair=1\n");
    return false;
  }

  // Prove that the geometry package contains the complete measured source
  // and arrangement contract before any pixel classifier is allowed to run.
  CString region;
  for (int i = 0; i < 15; ++i) {
    region.Format("ofc_fantasy15_src%02d", i);
    if (!DeepOFCRegionExists(region)) {
      write_log(k_always_log_errors,
        "[DeepOFC] Missing measured Fantasy15 source region: %s\n",
        region.GetString());
      return false;
    }
  }
  const int row_counts[3] = {3, 5, 5};
  const char *row_names[3] = {"top", "middle", "bottom"};
  for (int row = 0; row < 3; ++row) {
    for (int i = 0; i < row_counts[row]; ++i) {
      region.Format("ofc_fantasy15_arrange_%s%d", row_names[row], i);
      if (!DeepOFCRegionExists(region)) {
        write_log(k_always_log_errors,
          "[DeepOFC] Missing measured Fantasy15 arrangement region: %s\n",
          region.GetString());
        return false;
      }
    }
  }
  if (!DeepOFCRegionExists("ofc_fantasy15_unused_span")) {
    write_log(k_always_log_errors,
      "[DeepOFC] Missing measured Fantasy15 unused-card span\n");
    return false;
  }

#if DEEPOFC_NATIVE_FANTASY15_RECOGNIZER_CERTIFIED
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

  // Opponent board geometry does not move while Hero arranges Fantasy.
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

  std::vector<RECT> arrangement_rects;
  for (int row = 0; row < 3; ++row) {
    for (int i = 0; i < row_counts[row]; ++i) {
      CString name;
      name.Format("ofc_fantasy15_arrange_%s%d", row_names[row], i);
      RECT rect;
      if (!DeepOFCReadRegionRect(name, &rect)) return false;
      arrangement_rects.push_back(rect);
    }
  }

  // The validated initial Fantasy15 state is also a physical-card lineage.
  // It lets the final upright 13-card layout resolve weak T/5 glyphs without
  // guessing: first identify the two unused cards, then match the remaining
  // exact physical set one-to-one against the arrangement slots.
  std::vector<string> original_labels;
  const COFCState *previous = p_table_state->OFCState();
  if (previous->valid && previous->hero_chair == hero_chair
      && previous->players[hero_chair].fantasy
      && previous->round_index == -1
      && previous->hero_incoming_count == 15) {
    for (int i = 0; i < previous->hero_incoming_count; ++i) {
      original_labels.push_back(
        DeepOFCPhysicalLabel(previous->hero_incoming[i].value));
    }
  }

  std::vector<bool> occupied;
  std::vector<COFCFantasy15PixelCard> arrangement_cards;
  std::vector<COFCFantasyPixelObject> loose;
  bool loose_pre_recognized = false;
  std::string recognition_error;
  if (!COFCFantasy15PixelRecognizer::RecognizeArrangementSlots(
        _entire_window_cur, arrangement_rects,
        &occupied, &arrangement_cards, &recognition_error)) {
    const std::string strict_error = recognition_error;
    bool expected_match = false;
    if (original_labels.size() == 15
        && COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
          _entire_window_cur, true, original_labels,
          &loose, &recognition_error)
        && loose.size() == 2) {
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
          COFCFantasy15PixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
            _entire_window_cur, arrangement_rects, expected_arrangement,
            &occupied, &arrangement_cards, &recognition_error);
      }
    }
    if (!expected_match) {
      write_log(k_always_log_errors,
        "[DeepOFC] Fantasy arrangement recognition rejected: strict=%s fallback=%s\n",
        strict_error.c_str(), recognition_error.c_str());
      return false;
    }
    loose_pre_recognized = true;
  }

  int arrangement_count = 0;
  int flat = 0;
  for (int row = 0; row < 3; ++row) {
    bool saw_empty = false;
    for (int i = 0; i < row_counts[row]; ++i, ++flat) {
      if (!occupied[flat]) {
        saw_empty = true;
        continue;
      }
      if (saw_empty) {
        write_log(k_always_log_errors,
          "[DeepOFC] Fantasy arrangement has a gap inside row=%d\n", row);
        return false;
      }
      const int value = DeepOFCPixelCardValue(arrangement_cards[flat]);
      if (value < 0) return false;
      COFCCard *destination = NULL;
      if (row == kOFCRowTop) destination =
        &obs->players[hero_chair].visual_board.top[i];
      else if (row == kOFCRowMiddle) destination =
        &obs->players[hero_chair].visual_board.middle[i];
      else destination = &obs->players[hero_chair].visual_board.bottom[i];
      destination->value = value;
      ++arrangement_count;
    }
  }

  if (arrangement_count == 0) {
    if (!COFCFantasy15PixelRecognizer::RecognizeInitialFanObjects(
          _entire_window_cur, &loose, &recognition_error)) {
      write_log(k_always_log_errors,
        "[DeepOFC] Initial Fantasy15 fan rejected: %s\n",
        recognition_error.c_str());
      return false;
    }
    original_labels.clear();
    for (size_t i = 0; i < loose.size(); ++i) {
      original_labels.push_back(loose[i].card.PhysicalLabel());
    }
  } else if (!loose_pre_recognized) {
    if (original_labels.size() != 15) {
      write_log(k_always_log_errors,
        "[DeepOFC] Dynamic Fantasy reflow lacks a validated original 15-card lineage\n");
      return false;
    }
    if (!COFCFantasy15PixelRecognizer::RecognizeCurrentLooseObjects(
          _entire_window_cur, arrangement_count == 13,
          original_labels, &loose, &recognition_error)) {
      write_log(k_always_log_errors,
        "[DeepOFC] Dynamic Fantasy loose-card recognition rejected: %s\n",
        recognition_error.c_str());
      return false;
    }
  }
  if (arrangement_count + static_cast<int>(loose.size()) != 15) {
    write_log(k_always_log_errors,
      "[DeepOFC] Operational Fantasy15 requires exactly 15 cards; got pending=%d loose=%d\n",
      arrangement_count, static_cast<int>(loose.size()));
    return false;
  }
  for (size_t i = 0; i < loose.size(); ++i) {
    if (i >= static_cast<size_t>(kOFCMaxIncomingCards)) return false;
    const int value = DeepOFCPixelCardValue(loose[i].card);
    if (value < 0 || !loose[i].valid || !loose[i].fresh_from_current_bitmap) return false;
    obs->hero_loose_cards[i].value = value;
    obs->hero_loose_sources[i].valid = true;
    obs->hero_loose_sources[i].card_value = value;
    obs->hero_loose_sources[i].rect = loose[i].source_rect;
    ++obs->hero_loose_count;
  }

  int dealer_count = 0;
  int actor_count = 0;
  for (int p = 0; p < player_count; ++p) {
    bool value = false;
    CString name;
    name.Format("ofc_p%d_dealer", p);
    if (!DeepOFCReadMandatoryBoolean(this, name, &value)) return false;
    if (value) { obs->dealer_chair = p; ++dealer_count; }
    name.Format("ofc_p%d_turn", p);
    if (!DeepOFCReadMandatoryBoolean(this, name, &value)) return false;
    if (value) { obs->acting_chair = p; ++actor_count; }
  }
  if (dealer_count != 1 || actor_count != 1) return false;
  if (!DeepOFCReadMandatoryBoolean(
        this, "ofc_fantasy15_confirm_visible", &obs->confirm_visible)) {
    return false;
  }
  obs->hero_can_prepare = obs->acting_chair == hero_chair;
  if (!DeepOFCObservationHasUniqueKnownCards(obs)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Duplicate physical card in Fantasy15 observation\n");
    return false;
  }
  obs->valid = true;
  write_log(true,
    "[DeepOFC] Fantasy15 raw valid pending=%d loose=%d confirm=%d\n",
    arrangement_count, obs->hero_loose_count, obs->confirm_visible ? 1 : 0);
  return true;
#else
  write_log(k_always_log_errors,
    "[DeepOFC] Fantasy tablemap authority requested, but this OH build has no certified native Fantasy15 pixel recognizer\n");
  return false;
#endif
}
bool CScraper::ScrapeOFCVisualObservation() {
  if (!p_tablemap->SupportsOFCJokerUltimate()) return false;
  if (p_tablemap->GetTMSymbol("ofc_joker_detector_calibrated", 0) != 1) {
    write_log(k_always_log_errors,
      "[DeepOFC] Native standard/Joker recognition lacks explicit calibrated authority\n");
    return false;
  }

  COFCVisualObservation *obs = p_table_state->OFCVisualObservation();
  obs->Reset();

  const int player_count = p_tablemap->GetTMSymbol("ofc_players", 0);
  const int hero_chair = p_tablemap->GetTMSymbol("ofc_hero_chair", -1);
  if (((player_count != 2) && (player_count != 3))
      || (hero_chair < 0) || (hero_chair >= player_count)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Invalid ofc_players/ofc_hero_chair tablemap contract\n");
    return false;
  }
  obs->player_count = player_count;
  obs->hero_chair = hero_chair;

  // Route Fantasy BEFORE touching normal Hero row/incoming geometry.
  // Supplied replay evidence proves active Fantasy shifts/compresses the
  // Hero board and uses a curved 14..17-card fan. Reusing normal slots
  // could manufacture a plausible but false canonical normal-play state.
  bool fantasy_active = false;
  if (!DeepOFCReadMandatoryBoolean(this,
        "ofc_fantasy_active", &fantasy_active)) return false;
  if (fantasy_active) {
    if (!p_tablemap->OFCFantasyRecognizerCalibrated()) {
      write_log(k_always_log_errors,
        "[DeepOFC] Fantasy arrangement detected; normal geometry is forbidden and Fantasy recognizer authority is OFF\n");
      return false;
    }
    // Never fall through to normal row/incoming geometry while Fantasy is
    // active. The isolated path has its own tablemap and build authority.
    return ScrapeOFCFantasyVisualObservation(player_count, hero_chair);
  }

  int visible_joker_count = 0;

  for (int p = 0; p < player_count; ++p) {
    COFCVisualPlayerObservation *player = &obs->players[p];
    player->occupied = true;
    player->source_chair = p;
    CString base;

    for (int i = 0; i < kOFCTopCards; ++i) {
      base.Format("ofc_p%d_top%d", p, i);
      bool back = false; int joker_id = 0;
      int rc = ScrapeOFCSlot(base, &player->visual_board.top[i], &back, &joker_id);
      if (rc < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker_id != 0) ++visible_joker_count;
    }
    for (int i = 0; i < kOFCMiddleCards; ++i) {
      base.Format("ofc_p%d_middle%d", p, i);
      bool back = false; int joker_id = 0;
      int rc = ScrapeOFCSlot(base, &player->visual_board.middle[i], &back, &joker_id);
      if (rc < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker_id != 0) ++visible_joker_count;
    }
    for (int i = 0; i < kOFCBottomCards; ++i) {
      base.Format("ofc_p%d_bottom%d", p, i);
      bool back = false; int joker_id = 0;
      int rc = ScrapeOFCSlot(base, &player->visual_board.bottom[i], &back, &joker_id);
      if (rc < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker_id != 0) ++visible_joker_count;
    }

    if (p == hero_chair) {
      if (player->hidden_incoming_count != 0) {
        write_log(k_always_log_errors,
          "[DeepOFC] Unexpected hidden Hero cardback in row source slots\n");
        return false;
      }
      continue;
    }

    for (int i = 0; i < kOFCMaxDiscards; ++i) {
      base.Format("ofc_p%d_discard%d", p, i);
      COFCCard discard_face;
      bool back = false; int joker_id = 0;
      int rc = ScrapeOFCSlot(base, &discard_face, &back, &joker_id);
      if (rc < 0) return false;
      if (back) {
        ++player->hidden_discard_count;
      } else if (rc > 0) {
        write_log(k_always_log_errors,
          "[DeepOFC] Opponent discard identity visible while R1 D1 unresolved: p=%d slot=%d\n",
          p, i);
        return false;
      }
    }
  }

  // Three later-round loose slots are mandatory in the current 450x830 replay
  // geometry. Slots 3/4 remain optional until five-loose-card first-round
  // evidence is captured; physical-card accounting fails closed if needed.
  for (int i = 0; i < 5; ++i) {
    CString base;
    base.Format("ofc_hero_in%d", i);
    if (!DeepOFCRegionExists(base + "empty")) {
      if (i < 3) {
        write_log(k_always_log_errors,
          "[DeepOFC] Missing mandatory Hero incoming slot: %s\n", base.GetString());
        return false;
      }
      continue;
    }
    COFCCard card;
    bool back = false; int joker_id = 0;
    int rc = ScrapeOFCSlot(base, &card, &back, &joker_id);
    if (rc < 0) return false;
    if (back) return false;
    if (joker_id != 0) ++visible_joker_count;
    if (rc > 0) {
      const int loose_index = obs->hero_loose_count;
      obs->hero_loose_cards[loose_index] = card;
      COFCVisualCardSource *source = &obs->hero_loose_sources[loose_index];
      RECT source_rect;
      if (DeepOFCReadRegionRect(base + "drag", &source_rect)) {
        source->valid = true;
        source->card_value = card.value;
        source->rect = source_rect;
      }
      ++obs->hero_loose_count;
    }
  }

  for (int i = 0; i < kOFCMaxDiscards; ++i) {
    CString base;
    base.Format("ofc_hero_discard%d", i);
    COFCCard card;
    bool back = false; int joker_id = 0;
    int rc = ScrapeOFCSlot(base, &card, &back, &joker_id);
    if (rc < 0) return false;
    if (back) return false;
    if (joker_id != 0) ++visible_joker_count;
    if (rc > 0) obs->hero_discard_tracker[obs->hero_discard_tracker_count++] = card;
  }

  int dealer_count = 0, actor_count = 0;
  for (int p = 0; p < player_count; ++p) {
    CString region;
    bool value = false;
    region.Format("ofc_p%d_dealer", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) { obs->dealer_chair = p; ++dealer_count; }

    value = false;
    region.Format("ofc_p%d_turn", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &value)) return false;
    if (value) { obs->acting_chair = p; ++actor_count; }
  }
  if ((dealer_count != 1) || (actor_count != 1)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Expected one dealer/actor; got dealer=%d actor=%d\n",
      dealer_count, actor_count);
    return false;
  }

  if (!DeepOFCReadMandatoryBoolean(this,
        "ofc_confirm_visible", &obs->confirm_visible)) return false;

  const int total_dealt = obs->players[hero_chair].visual_board.CountKnownCards()
    + obs->hero_loose_count + obs->hero_discard_tracker_count;
  switch (total_dealt) {
    case 5: obs->round_index = 0; break;
    case 8: obs->round_index = 1; break;
    case 11: obs->round_index = 2; break;
    case 14: obs->round_index = 3; break;
    case 17: obs->round_index = 4; break;
    default:
      write_log(k_always_log_errors,
        "[DeepOFC] Invalid normal Hero visible-card total: %d\n", total_dealt);
      return false;
  }
  obs->hero_can_prepare = true;

  if (!DeepOFCObservationHasUniqueKnownCards(obs)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Duplicate known physical card in raw observation\n");
    return false;
  }

  obs->valid = true;
  write_log(true,
    "[DeepOFC] raw valid players=%d hero=%d dealer=%d actor=%d round=%d confirm=%d loose=%d discards=%d visible_jokers=%d\n",
    obs->player_count, obs->hero_chair, obs->dealer_chair,
    obs->acting_chair, obs->round_index, obs->confirm_visible ? 1 : 0,
    obs->hero_loose_count, obs->hero_discard_tracker_count, visible_joker_count);
  return true;
}
