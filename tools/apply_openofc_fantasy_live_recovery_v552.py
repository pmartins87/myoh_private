from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_source(relative: str):
    path = ROOT / relative
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool) -> None:
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path, text, eol, bom = read_source(relative)
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{relative}: {label} expected exactly one target, got {count}"
        )
    write_source(path, text.replace(old, new, 1), eol, bom)
    print(f"patched {relative}: {label}", flush=True)


def replace_all(
    relative: str, old: str, new: str, expected: int, label: str
) -> None:
    path, text, eol, bom = read_source(relative)
    count = text.count(old)
    if count != expected:
        raise SystemExit(
            f"{relative}: {label} expected {expected} targets, got {count}"
        )
    write_source(path, text.replace(old, new), eol, bom)
    print(f"patched {relative}: {label} ({count} sites)", flush=True)


def patch_refantasy_rollover() -> None:
    old = r'''      std::set<string> loose_labels;
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
'''
    new = r'''      std::set<string> loose_labels;
      for (size_t i = 0; i < loose.size(); ++i)
        loose_labels.insert(loose[i].card.PhysicalLabel());

      // OPENOFC_FANTASY_LIVE_RECOVERY_V552: an empty 14..17-card fan is a
      // complete current-screen deal. If it differs from the prior lineage,
      // the client has dealt a re-Fantasy hand; retaining the old set would
      // reject every new frame forever. The same physical set is deliberately
      // not reset, because that can be the player clearing the current layout.
      const std::set<string> prior_labels(
        original_labels.begin(), original_labels.end());
      if (occupied_hint == 0
          && text_count >= 14 && text_count <= 17
          && loose_labels != prior_labels) {
        const int prior_count = static_cast<int>(original_labels.size());
        original_labels.clear();
        loose_pre_recognized = true;
        write_log(true,
          "[OpenOFC FANTASY V552] new_deal=CURRENT_SCREEN prior=%d current=%d "
          "occupied=0 lineage=RESET replan=1\n",
          prior_count, static_cast<int>(loose.size()));
      }

      if (!loose_pre_recognized) {
        std::vector<string> expected_arrangement;
        for (size_t i = 0; i < original_labels.size(); ++i) {
          if (loose_labels.find(original_labels[i]) == loose_labels.end())
            expected_arrangement.push_back(original_labels[i]);
        }
        if (expected_arrangement.size() != static_cast<size_t>(occupied_hint)) {
          write_log(k_always_log_errors,
            "[OpenOFC FANTASY V552] lineage partition mismatch prior=%d occupied=%d loose=%d expected_arranged=%d terminal=0\n",
            static_cast<int>(original_labels.size()), occupied_hint,
            static_cast<int>(loose.size()), static_cast<int>(expected_arrangement.size()));
          return false;
        }
        if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
              _entire_window_cur, arrangement_rects, expected_arrangement,
              &occupied, &arrangement_cards, &recognition_error)) {
          write_log(k_always_log_errors,
            "[OpenOFC FANTASY V552] expected arrangement rejected count=%d error=%s terminal=0\n",
            text_count, recognition_error.c_str());
          return false;
        }
        loose_pre_recognized = true;
        write_log(true,
          "[OpenOFC FANTASY V552] count=%d score=%.3f identity=TABLEMAP_T7 occupied=%d\n",
          text_count, count_score, occupied_hint);
      }
'''
    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        old,
        new,
        "current-screen re-Fantasy lineage rollover",
    )

    old = r'''      if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
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
'''
    new = r'''      if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlotsAgainstExpected(
            _entire_window_cur, arrangement_rects, original_labels,
            &occupied, &arrangement_cards, &recognition_error)) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY V552] final arrangement lineage verification failed error=%s terminal=0\n",
          recognition_error.c_str());
        return false;
      }
      write_log(true,
        "[OpenOFC FANTASY V552] count=FINAL_COMPLEMENT occupied=13 "
        "identity=LINEAGE_SUBSET count_detail=%s\n",
        count_error.c_str());
'''
    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        old,
        new,
        "final 13-card lineage-subset recognition",
    )


def patch_lineage_subset_matcher() -> None:
    replace_once(
        "OpenHoldem/COFCFantasy15PixelRecognizer.cpp",
        '''  if (occupied_count != static_cast<int>(expected.size())) {
    return Fail(error, "occupied arrangement count disagrees with expected physical set");
  }
''',
        '''  const int unused_count = static_cast<int>(expected.size()) - occupied_count;
  if (occupied_count > static_cast<int>(expected.size())
      || unused_count < 0 || unused_count > 4) {
    return Fail(error, "occupied arrangement is not a safe subset of expected lineage");
  }
''',
        "allow final 13-card subset of 14..17 lineage",
    )
    replace_once(
        "OpenHoldem/COFCFantasy15PixelRecognizer.cpp",
        '''    if (slot_indices.size() != expected_indices.size()) {
      return Fail(error, "expected-arrangement suit cardinality mismatch");
    }
''',
        '''    if (slot_indices.size() > expected_indices.size()) {
      return Fail(error, "expected-arrangement suit cardinality exceeds lineage");
    }
''',
        "allow unused same-suit lineage candidates",
    )
    replace_once(
        "OpenHoldem/COFCFantasy15PixelRecognizer.cpp",
        '''  for (size_t i = 0; i < expected_used.size(); ++i)
    if (!expected_used[i]) return Fail(error, "expected physical card was not assigned");
  return true;
}
''',
        '''  int assigned_count = 0;
  for (size_t i = 0; i < cards->size(); ++i)
    if ((*cards)[i].valid) ++assigned_count;
  if (assigned_count != occupied_count)
    return Fail(error, "not every occupied arrangement slot matched the lineage");
  return true;
}
''',
        "verify occupied slots while permitting 1..4 unused lineage cards",
    )

    replace_once(
        "OpenHoldem/COFCFantasy15PixelRecognizer.h",
        '''  // Final 13-card arrangement matcher. It constrains the upright glyphs to an
  // exact physical-card set (original Fantasy15 minus the two recognized
  // unused cards), resolving weak T/5 upright glyphs by a minimum-distance
  // one-to-one assignment instead of inventing a duplicate identity.
''',
        '''  // Lineage-constrained arrangement matcher. The expected vector may be the
  // exact occupied set or the complete 14..17-card Fantasy lineage. In the
  // latter case 1..4 unused candidates are permitted, while every occupied
  // glyph still receives a one-to-one physical identity from that lineage.
''',
        "document exact-set and final lineage-subset contract",
    )


def patch_visual_row_verification_and_pacing() -> None:
    old = r'''vector<int> CurrentRowCards(const COFCState &state, EOFCRow row) {
  vector<int> values;
  for (int i = 0; i < kOFCMaxIncomingCards; ++i) {
    if (!state.pending[i].active || state.pending[i].row != row) continue;
    const int incoming_index = state.pending[i].incoming_index;
    if (incoming_index < 0 || incoming_index >= state.hero_incoming_count) continue;
    const int value = state.hero_incoming[incoming_index].value;
    if (value >= 0 && value <= kOFCCardJoker2) values.push_back(value);
  }
  sort(values.begin(), values.end());
  return values;
}
'''
    new = r'''vector<int> CurrentVisualRowCards(
    const COFCVisualObservation &observation, EOFCRow row) {
  vector<int> values;
  if (!observation.valid
      || observation.hero_chair < 0
      || observation.hero_chair >= observation.player_count) return values;
  const COFCPlayerBoard &board =
    observation.players[observation.hero_chair].visual_board;
  const COFCCard *cards = NULL;
  int count = 0;
  switch (row) {
    case kOFCRowTop: cards = board.top; count = kOFCTopCards; break;
    case kOFCRowMiddle: cards = board.middle; count = kOFCMiddleCards; break;
    case kOFCRowBottom: cards = board.bottom; count = kOFCBottomCards; break;
    default: return values;
  }
  for (int i = 0; i < count; ++i) {
    // UNKNOWN/BACK are deliberately retained as non-target sentinels. They
    // prove the visual row is occupied but can never equal a physical target.
    if (cards[i].value != kOFCCardNoCard) values.push_back(cards[i].value);
  }
  sort(values.begin(), values.end());
  return values;
}
'''
    replace_once(
        "OpenHoldem/COFCFantasyBatchExecutor.cpp",
        old,
        new,
        "derive row evidence from raw visual board",
    )

    replace_once(
        "OpenHoldem/COFCFantasyBatchExecutor.cpp",
        '''bool COFCFantasyBatchExecutor::RowMatchesTarget(
    const COFCState &state, EOFCRow row) const {
  return CurrentRowCards(state, row) == TargetRowCards(plan_, row);
}

bool COFCFantasyBatchExecutor::RowEmpty(
    const COFCState &state, EOFCRow row) const {
  return CurrentRowCards(state, row).empty();
}
''',
        '''bool COFCFantasyBatchExecutor::RowMatchesTarget(
    const COFCVisualObservation &observation, EOFCRow row) const {
  return CurrentVisualRowCards(observation, row) == TargetRowCards(plan_, row);
}

bool COFCFantasyBatchExecutor::RowEmpty(
    const COFCVisualObservation &observation, EOFCRow row) const {
  return CurrentVisualRowCards(observation, row).empty();
}
''',
        "require exact raw visual row match",
    )
    replace_all(
        "OpenHoldem/COFCFantasyBatchExecutor.cpp",
        "RowEmpty(state, row)",
        "RowEmpty(observation, row)",
        2,
        "use visual emptiness in build/repair selection",
    )
    replace_all(
        "OpenHoldem/COFCFantasyBatchExecutor.cpp",
        "RowMatchesTarget(state, row)",
        "RowMatchesTarget(observation, row)",
        2,
        "use visual target match in build/repair selection",
    )
    replace_all(
        "OpenHoldem/COFCFantasyBatchExecutor.cpp",
        "RowMatchesTarget(state, waiting_row_)",
        "RowMatchesTarget(observation, waiting_row_)",
        1,
        "verify committed row from fresh visual observation",
    )
    replace_all(
        "OpenHoldem/COFCFantasyBatchExecutor.cpp",
        "RowEmpty(state, waiting_row_)",
        "RowEmpty(observation, waiting_row_)",
        2,
        "verify clear/no-op from fresh visual observation",
    )
    replace_once(
        "OpenHoldem/COFCFantasyBatchExecutor.cpp",
        '''  const int gap_ms = p_tablemap == NULL
    ? 110 : max(60, p_tablemap->GetTMSymbol("ofc_fantasy_select_gap_ms", 110));
''',
        '''  // Field pacing: each selection remains visible and tolerates one slow
  // presentation frame. ClickRectsSafely still enforces its bounded 250 ms cap.
  const int gap_ms = p_tablemap == NULL
    ? 250 : max(250, p_tablemap->GetTMSymbol("ofc_fantasy_select_gap_ms", 250));
''',
        "raise Fantasy selection cadence to 250 ms",
    )
    replace_once(
        "OpenHoldem/COFCFantasyBatchExecutor.cpp",
        r'''        "[OpenOFC FANTASY V5] verify=ROW_COMMIT_OK row=%s\n",
        RowName(waiting_row_));
''',
        r'''        "[OpenOFC FANTASY V552] verify=ROW_COMMIT_OK row=%s evidence=RAW_VISUAL_EXACT\n",
        RowName(waiting_row_));
''',
        "log exact visual commit evidence",
    )

    replace_once(
        "OpenHoldem/COFCFantasyBatchExecutor.h",
        '''  bool RowMatchesTarget(const COFCState &state, EOFCRow row) const;
  bool RowEmpty(const COFCState &state, EOFCRow row) const;
''',
        '''  bool RowMatchesTarget(
      const COFCVisualObservation &observation, EOFCRow row) const;
  bool RowEmpty(
      const COFCVisualObservation &observation, EOFCRow row) const;
''',
        "declare visual row verification contract",
    )


def patch_paired_ui_and_screen_order() -> None:
    replace_once(
        "OpenHoldem/COpenHoldemStatusbar.cpp",
        '''    const bool counted_text_ok =
      p_tablemap->GetTMSymbol("openofc_fantasy_tablemap_text_by_count", 0) == 1;
    const bool paired_tablemap_ok = contract_ok && counted_text_ok;
''',
        '''    const bool counted_text_ok =
      p_tablemap->GetTMSymbol("openofc_fantasy_tablemap_text_by_count", 0) == 1;
    const bool live_recovery_ok =
      p_tablemap->GetTMSymbol("openofc_fantasy_live_recovery", 0) == 1;
    const bool paired_tablemap_ok =
      contract_ok && counted_text_ok && live_recovery_ok;
''',
        "require v5.5.2 live-recovery TableMap",
    )
    replace_once(
        "OpenHoldem/COpenHoldemStatusbar.cpp",
        '''    } else if (!counted_text_ok) {
      actor = "TM V551 REQUIRED";
    }
''',
        '''    } else if (!counted_text_ok || !live_recovery_ok) {
      actor = "TM V552 REQUIRED";
    }
''',
        "identify required v5.5.2 pair",
    )

    replace_once(
        "OpenHoldem/OpenHoldemView.cpp",
        '''    const bool counted_text_ok =
      p_tablemap->GetTMSymbol("openofc_fantasy_tablemap_text_by_count", 0) == 1;
    const bool paired_tablemap_ok = contract_ok && counted_text_ok;
''',
        '''    const bool counted_text_ok =
      p_tablemap->GetTMSymbol("openofc_fantasy_tablemap_text_by_count", 0) == 1;
    const bool live_recovery_ok =
      p_tablemap->GetTMSymbol("openofc_fantasy_live_recovery", 0) == 1;
    const bool paired_tablemap_ok =
      contract_ok && counted_text_ok && live_recovery_ok;
''',
        "gate main view on v5.5.2 pair",
    )
    replace_once(
        "OpenHoldem/OpenHoldemView.cpp",
        r'''      view += "TABLEMAP  PAIRED V551=OK\r\n";
''',
        r'''      view += "TABLEMAP  PAIRED V552=OK\r\n";
''',
        "show v5.5.2 pair",
    )
    replace_once(
        "OpenHoldem/OpenHoldemView.cpp",
        r'''    } else {
      view += "TABLEMAP  BLOCKED: COUNTED-TEXT V551 SYMBOL MISSING\r\n";
    }
''',
        r'''    } else {
      view += "TABLEMAP  BLOCKED: V552 LIVE-RECOVERY SYMBOL MISSING\r\n";
    }
''',
        "explain stale paired TableMap",
    )

    old = '''    if (state != NULL && state->valid) {
      line.Format("\\r\\nINCOMING  %s\\r\\n",
        COFCInspectorSnapshot::CardsText(
          state->hero_incoming, state->hero_incoming_count).GetString());
      view += line;
      line.Format("DISCARDS  %s  |  prepare=%d confirm=%d pending=%d\\r\\n",
        COFCInspectorSnapshot::CardsText(
          state->hero_discards, state->hero_discard_count).GetString(),
        state->hero_can_prepare ? 1 : 0, state->hero_can_confirm ? 1 : 0,
        state->hero_incoming_count);
      view += line;
    }
'''
    new = '''    if (state != NULL && state->valid) {
      const bool hero_fantasy = state->hero_chair >= 0
        && state->hero_chair < state->player_count
        && state->players[state->hero_chair].fantasy;
      if (hero_fantasy) {
        bool fresh_screen_order = raw != NULL && raw->valid
          && raw->hero_chair == state->hero_chair;
        if (fresh_screen_order) {
          for (int i = 0; i < raw->hero_loose_count; ++i)
            if (!raw->hero_loose_sources[i].valid) fresh_screen_order = false;
        }
        if (fresh_screen_order) {
          line.Format("\\r\\nFANTASY SCREEN ORDER  %s\\r\\n",
            COFCInspectorSnapshot::CardsText(
              raw->hero_loose_cards, raw->hero_loose_count).GetString());
          view += line;
          line.Format("FANTASY LINEAGE SET   %s\\r\\n",
            COFCInspectorSnapshot::CardsText(
              state->hero_incoming, state->hero_incoming_count).GetString());
          view += line;
        } else {
          view += "\\r\\nFANTASY SCREEN ORDER  REACQUIRING CURRENT DEAL\\r\\n";
        }
      } else {
        line.Format("\\r\\nINCOMING  %s\\r\\n",
          COFCInspectorSnapshot::CardsText(
            state->hero_incoming, state->hero_incoming_count).GetString());
        view += line;
      }
      line.Format("DISCARDS  %s  |  prepare=%d confirm=%d pending=%d\\r\\n",
        COFCInspectorSnapshot::CardsText(
          state->hero_discards, state->hero_discard_count).GetString(),
        state->hero_can_prepare ? 1 : 0, state->hero_can_confirm ? 1 : 0,
        state->hero_incoming_count);
      view += line;
    }
'''
    replace_once(
        "OpenHoldem/OpenHoldemView.cpp",
        old,
        new,
        "show Fantasy loose cards in physical screen order",
    )


def main() -> None:
    patch_refantasy_rollover()
    patch_lineage_subset_matcher()
    patch_visual_row_verification_and_pacing()
    patch_paired_ui_and_screen_order()
    print(
        "OPENOFC_FANTASY_LIVE_RECOVERY_V552_MATERIALIZATION=PASS "
        "refantasy=CURRENT_SCREEN_RESET final=LINEAGE_SUBSET "
        "row_verify=RAW_VISUAL_EXACT click_gap_ms=250 ui=SCREEN_ORDER"
    )


if __name__ == "__main__":
    main()
