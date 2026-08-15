//******************************************************************************
// DeepOFC read-only KKPoker Joker Ultimate scraper.
// Populates only COFCVisualObservation; legacy Hold'em cards are untouched.
//******************************************************************************

#include "StdAfx.h"
#include "CScraper.h"

#include <set>

#include "CTableState.h"

using namespace std;

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

  const int legacy_card = ScrapeCardByRankAndSuit(base_name);
  if ((legacy_card >= 0) && (legacy_card <= 51)) {
    card->value = legacy_card;
    return 1;
  }

  write_log(k_always_log_errors,
    "[DeepOFC] Non-empty slot has no unambiguous standard/persistent-Joker face: %s\n",
    base_name.GetString());
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

bool CScraper::ScrapeOFCVisualObservation() {
  if (!p_tablemap->SupportsOFCJokerUltimate()) return false;

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
    write_log(k_always_log_errors,
      "[DeepOFC] Fantasy arrangement detected; normal geometry is forbidden until the 14-17-card Fantasy pixel path is certified\n");
    return false;
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
