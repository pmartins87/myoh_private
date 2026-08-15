//******************************************************************************
//
// DeepOFC read-only KKPoker Joker Ultimate scraper.
//
// This compilation unit is intentionally isolated from legacy Hold'em
// hole/common-card storage. It populates only COFCVisualObservation.
// Integration into the heartbeat/project file remains gated by replay and
// Windows-build validation.
//
//******************************************************************************

#include "StdAfx.h"
#include "CScraper.h"

#include <set>

#include "CTableState.h"

using namespace std;

static bool DeepOFCRegionExists(const CString &name) {
  return p_tablemap->r$()->find(name) != p_tablemap->r$()->end();
}

int CScraper::ScrapeOFCSlot(CString base_name, COFCCard *card,
    bool *is_back, bool *is_joker) {
  if (card == NULL || is_back == NULL || is_joker == NULL) {
    return -1;
  }
  card->Clear();
  *is_back = false;
  *is_joker = false;

  const CString occupied_region = base_name + "occupied";
  const CString back_region = base_name + "back";
  const CString joker_region = base_name + "joker";
  const CString rank_region = base_name + "rank";
  const CString suit_region = base_name + "suit";

  // Explicit occupancy is mandatory. This is the fail-closed guard that
  // prevents a rank/suit OCR miss from being silently treated as an empty slot.
  if (!DeepOFCRegionExists(occupied_region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Missing mandatory slot occupancy region: %s\n",
      occupied_region.GetString());
    return -1;
  }

  bool occupied = false;
  EvaluateTrueFalseRegion(&occupied, occupied_region);
  if (!occupied) {
    return 0;
  }

  if (!DeepOFCRegionExists(back_region)
      || !DeepOFCRegionExists(joker_region)
      || !DeepOFCRegionExists(rank_region)
      || !DeepOFCRegionExists(suit_region)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Occupied slot lacks back/joker/rank/suit contract: %s\n",
      base_name.GetString());
    return -1;
  }

  bool back = false;
  bool joker = false;
  EvaluateTrueFalseRegion(&back, back_region);
  EvaluateTrueFalseRegion(&joker, joker_region);
  if (back && joker) {
    write_log(k_always_log_errors,
      "[DeepOFC] Slot classified as both cardback and Joker: %s\n",
      base_name.GetString());
    return -2;
  }
  if (back) {
    *is_back = true;
    return 0;
  }
  if (joker) {
    *is_joker = true;
    return 1;
  }

  int legacy_card = ScrapeCardByRankAndSuit(base_name);
  if ((legacy_card >= 0) && (legacy_card <= 51)) {
    card->value = legacy_card;
    return 1;
  }

  write_log(k_always_log_errors,
    "[DeepOFC] Occupied slot has no unambiguous standard/Joker face: %s\n",
    base_name.GetString());
  return -3;
}

static bool DeepOFCAssignFrameLocalJoker(COFCCard *card, int *joker_count) {
  if (*joker_count >= 2) {
    return false;
  }
  card->value = kOFCCardJoker1 + *joker_count;
  ++(*joker_count);
  return true;
}

static bool DeepOFCRegisterKnownCard(int value, set<int> *seen) {
  if ((value < 0) || (value > kOFCCardJoker2)) {
    return true;
  }
  if (seen->find(value) != seen->end()) {
    return false;
  }
  seen->insert(value);
  return true;
}

static bool DeepOFCObservationHasUniqueKnownCards(
    const COFCVisualObservation *observation) {
  set<int> seen;
  for (int p = 0; p < observation->player_count; ++p) {
    const COFCPlayerBoard &board = observation->players[p].visual_board;
    for (int i = 0; i < kOFCTopCards; ++i) {
      if (board.top[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(board.top[i].value, &seen)) return false;
    }
    for (int i = 0; i < kOFCMiddleCards; ++i) {
      if (board.middle[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(board.middle[i].value, &seen)) return false;
    }
    for (int i = 0; i < kOFCBottomCards; ++i) {
      if (board.bottom[i].IsKnownPhysicalCard()
          && !DeepOFCRegisterKnownCard(board.bottom[i].value, &seen)) return false;
    }
  }
  for (int i = 0; i < observation->hero_loose_count; ++i) {
    if (observation->hero_loose_cards[i].IsKnownPhysicalCard()
        && !DeepOFCRegisterKnownCard(observation->hero_loose_cards[i].value, &seen)) return false;
  }
  for (int i = 0; i < observation->hero_discard_tracker_count; ++i) {
    if (observation->hero_discard_tracker[i].IsKnownPhysicalCard()
        && !DeepOFCRegisterKnownCard(observation->hero_discard_tracker[i].value, &seen)) return false;
  }
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
  if (!p_tablemap->SupportsOFCJokerUltimate()) {
    return false;
  }

  COFCVisualObservation *observation = p_table_state->OFCVisualObservation();
  observation->Reset();

  const int player_count = p_tablemap->GetTMSymbol("ofc_players", 0);
  const int hero_chair = p_tablemap->GetTMSymbol("ofc_hero_chair", -1);
  if (((player_count != 2) && (player_count != 3))
      || (hero_chair < 0) || (hero_chair >= player_count)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Invalid ofc_players/ofc_hero_chair tablemap contract\n");
    return false;
  }
  observation->player_count = player_count;
  observation->hero_chair = hero_chair;

  // KKPoker's two Jokers may render identically. Scrape assigns frame-local
  // deterministic JK1/JK2 labels in scan order. Strategic state must treat the
  // two physical Jokers as exchangeable under a permutation of these labels.
  int joker_count = 0;

  for (int p = 0; p < player_count; ++p) {
    COFCVisualPlayerObservation *player = &observation->players[p];
    player->occupied = true;
    player->source_chair = p;

    CString base;
    for (int i = 0; i < kOFCTopCards; ++i) {
      base.Format("ofc_p%d_top%d", p, i);
      bool back = false;
      bool joker = false;
      int result = ScrapeOFCSlot(base, &player->visual_board.top[i], &back, &joker);
      if (result < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker && !DeepOFCAssignFrameLocalJoker(&player->visual_board.top[i], &joker_count)) return false;
    }
    for (int i = 0; i < kOFCMiddleCards; ++i) {
      base.Format("ofc_p%d_middle%d", p, i);
      bool back = false;
      bool joker = false;
      int result = ScrapeOFCSlot(base, &player->visual_board.middle[i], &back, &joker);
      if (result < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker && !DeepOFCAssignFrameLocalJoker(&player->visual_board.middle[i], &joker_count)) return false;
    }
    for (int i = 0; i < kOFCBottomCards; ++i) {
      base.Format("ofc_p%d_bottom%d", p, i);
      bool back = false;
      bool joker = false;
      int result = ScrapeOFCSlot(base, &player->visual_board.bottom[i], &back, &joker);
      if (result < 0) return false;
      if (back) ++player->hidden_incoming_count;
      if (joker && !DeepOFCAssignFrameLocalJoker(&player->visual_board.bottom[i], &joker_count)) return false;
    }

    if (p == hero_chair) {
      if (player->hidden_incoming_count != 0) {
        write_log(k_always_log_errors,
          "[DeepOFC] Unexpected hidden Hero cardback in row slots\n");
        return false;
      }
      continue;
    }

    // Current rule contract exposes opponent discard count, not identities.
    // A face-up discard in these slots is therefore a deliberate unsupported
    // state until R1 probe D1 changes the information model.
    for (int i = 0; i < kOFCMaxDiscards; ++i) {
      base.Format("ofc_p%d_discard%d", p, i);
      COFCCard discard_face;
      bool back = false;
      bool joker = false;
      int result = ScrapeOFCSlot(base, &discard_face, &back, &joker);
      if (result < 0) return false;
      if (back) {
        ++player->hidden_discard_count;
      } else if (result > 0) {
        write_log(k_always_log_errors,
          "[DeepOFC] Opponent discard identity became visible but R1 D1 is unresolved: p=%d slot=%d\n",
          p, i);
        return false;
      }
    }
  }

  // Normal-play Hero loose cards: first three source slots are mandatory for
  // the supplied 450x830 evidence. Slots 3/4 are optional until first-round
  // loose-card geometry is captured; absence is safe because card accounting
  // will fail if such cards are actually needed/visible there.
  for (int i = 0; i < 5; ++i) {
    CString base;
    base.Format("ofc_hero_in%d", i);
    CString occupied = base + "occupied";
    if (!DeepOFCRegionExists(occupied)) {
      if (i < 3) {
        write_log(k_always_log_errors,
          "[DeepOFC] Missing mandatory Hero incoming slot: %s\n", base.GetString());
        return false;
      }
      continue;
    }
    COFCCard card;
    bool back = false;
    bool joker = false;
    int result = ScrapeOFCSlot(base, &card, &back, &joker);
    if (result < 0) return false;
    if (back) {
      write_log(k_always_log_errors,
        "[DeepOFC] Hero incoming slot classified as hidden cardback\n");
      return false;
    }
    if (joker && !DeepOFCAssignFrameLocalJoker(&card, &joker_count)) return false;
    if (result > 0) {
      if (observation->hero_loose_count >= kOFCMaxIncomingCards) return false;
      observation->hero_loose_cards[observation->hero_loose_count] = card;
      ++observation->hero_loose_count;
    }
  }

  for (int i = 0; i < kOFCMaxDiscards; ++i) {
    CString base;
    base.Format("ofc_hero_discard%d", i);
    COFCCard card;
    bool back = false;
    bool joker = false;
    int result = ScrapeOFCSlot(base, &card, &back, &joker);
    if (result < 0) return false;
    if (back) {
      write_log(k_always_log_errors,
        "[DeepOFC] Hero discard tracker contains hidden cardback\n");
      return false;
    }
    if (joker && !DeepOFCAssignFrameLocalJoker(&card, &joker_count)) return false;
    if (result > 0) {
      if (observation->hero_discard_tracker_count >= kOFCMaxDiscards) return false;
      observation->hero_discard_tracker[observation->hero_discard_tracker_count] = card;
      ++observation->hero_discard_tracker_count;
    }
  }

  int dealer_count = 0;
  int actor_count = 0;
  for (int p = 0; p < player_count; ++p) {
    CString region;
    bool dealer = false;
    region.Format("ofc_p%d_dealer", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &dealer)) return false;
    if (dealer) {
      observation->dealer_chair = p;
      ++dealer_count;
    }

    bool acting = false;
    region.Format("ofc_p%d_turn", p);
    if (!DeepOFCReadMandatoryBoolean(this, region, &acting)) return false;
    if (acting) {
      observation->acting_chair = p;
      ++actor_count;
    }
  }
  if ((dealer_count != 1) || (actor_count != 1)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Expected exactly one dealer and one acting player; got dealer=%d actor=%d\n",
      dealer_count, actor_count);
    return false;
  }

  if (!DeepOFCReadMandatoryBoolean(this,
        "ofc_confirm_visible", &observation->confirm_visible)) return false;

  const COFCPlayerBoard &hero_visual = observation->players[hero_chair].visual_board;
  const int total_dealt = hero_visual.CountKnownCards()
    + observation->hero_loose_count
    + observation->hero_discard_tracker_count;
  switch (total_dealt) {
    case 5:  observation->round_index = 0; break;
    case 8:  observation->round_index = 1; break;
    case 11: observation->round_index = 2; break;
    case 14: observation->round_index = 3; break;
    case 17: observation->round_index = 4; break;
    default:
      write_log(k_always_log_errors,
        "[DeepOFC] Invalid normal-play Hero visible-card total: %d\n", total_dealt);
      return false;
  }
  observation->hero_can_prepare = true;

  if (!DeepOFCObservationHasUniqueKnownCards(observation)) {
    write_log(k_always_log_errors,
      "[DeepOFC] Duplicate known physical card in raw visual observation\n");
    return false;
  }

  observation->valid = true;
  write_log(true,
    "[DeepOFC] raw observation valid players=%d hero=%d dealer=%d actor=%d round=%d confirm_visible=%d loose=%d discards=%d jokers=%d\n",
    observation->player_count,
    observation->hero_chair,
    observation->dealer_chair,
    observation->acting_chair,
    observation->round_index,
    observation->confirm_visible ? 1 : 0,
    observation->hero_loose_count,
    observation->hero_discard_tracker_count,
    joker_count);
  return true;
}
