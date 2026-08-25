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
    output = text if eol == "\n" else text.replace("\n", "\r\n")
    data = output.encode("utf-8")
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


def patch_observation() -> None:
    replace_once(
        "OpenHoldem/COFCVisualObservation.h",
        """};

class COFCVisualObservation {
""",
        r''' };

// OPENOFC_ACTIVE_IDENTITY_RECOVERY_V580.  This payload is diagnostic evidence,
// not a valid card observation.  It survives a fail-closed Fantasy scrape so
// the runtime can perform one bounded, reversible identity probe.
struct COFCIdentityProbeEvidence {
  bool anomaly_detected;
  bool candidate_available;
  int fantasy_card_count;
  int candidate_index;
  int staging_row;
  COFCVisualCardSource candidate_source;
  int known_values[kOFCMaxIncomingCards];
  int known_count;
  char reason[128];

  void Reset() {
    anomaly_detected = false;
    candidate_available = false;
    fantasy_card_count = 0;
    candidate_index = -1;
    staging_row = -1;
    candidate_source.Reset();
    known_count = 0;
    for (int i = 0; i < kOFCMaxIncomingCards; ++i)
      known_values[i] = kOFCCardNoCard;
    reason[0] = 0;
  }
};

class COFCVisualObservation {
''',
        "add fail-closed identity-probe evidence",
    )
    replace_once(
        "OpenHoldem/COFCVisualObservation.h",
        """    opponent_result_fantasy = false;
    for (int i = 0; i < kOFCMaxPlayers; ++i) {
""",
        """    opponent_result_fantasy = false;
    identity_probe.Reset();
    for (int i = 0; i < kOFCMaxPlayers; ++i) {
""",
        "reset identity-probe evidence",
    )
    replace_once(
        "OpenHoldem/COFCVisualObservation.h",
        """  bool opponent_result_fantasy;

  COFCVisualPlayerObservation players[kOFCMaxPlayers];
""",
        """  bool opponent_result_fantasy;

  COFCIdentityProbeEvidence identity_probe;
  COFCVisualPlayerObservation players[kOFCMaxPlayers];
""",
        "store identity-probe evidence",
    )


def patch_scraper() -> None:
    replace_once(
        "OpenHoldem/COFCScraper.cpp",
        '#include "COFCFantasyPixelRecognizer.h"\n',
        '#include "COFCFantasyPixelRecognizer.h"\n'
        '#include "COFCIdentityRecoveryCache.h"\n',
        "include exact identity-recovery cache",
    )
    path, text, eol, bom = read_source("OpenHoldem/COFCScraper.cpp")
    marker = "  std::string recognition_error;\n"
    if text.count(marker) != 1:
        raise SystemExit("COFCScraper.cpp: diagnostic occupancy marker mismatch")
    text = text.replace(
        marker,
        "  std::string recognition_error;\n"
        "  int diagnostic_row_occupied[3] = {-1, -1, -1};\n",
        1,
    )
    start = text.index("  auto scrape_text_loose = [&](int loose_count,")
    end = text.index("\n  if (!original_labels.empty()) {", start)
    replacement = r'''  auto scrape_text_loose = [&](int loose_count,
      std::vector<COFCFantasyPixelObject> *out,
      std::string *text_error) -> bool {
    if (out == NULL) return false;
    out->clear();
    const bool supported =
      (loose_count >= 6 && loose_count <= 9)
      || (loose_count >= 11 && loose_count <= 17);
    if (!supported) {
      if (text_error != NULL) *text_error = "loose count has no stable text-map family";
      return false;
    }
    if (loose_count == 17
        && p_tablemap->GetTMSymbol("openofc_fantasy17_calibrated", 0) != 1) {
      if (text_error != NULL) *text_error = "17-card Fantasy text geometry is not field-calibrated";
      return false;
    }

    std::set<std::string> labels;
    std::vector<int> observed_values;
    int invalid_count = 0;
    int invalid_index = -1;
    bool duplicate_identity = false;
    std::string first_failure;

    for (int i = 0; i < loose_count; ++i) {
      CString base;
      base.Format("ofc_fantasy%02d_%02d", loose_count, i);
      const CString rank_region = base + "rank";
      const CString suit_region = base + "suit";
      if (!DeepOFCRegionExists(rank_region) || !DeepOFCRegionExists(suit_region)) {
        if (text_error != NULL) *text_error = "missing count-specific Fantasy rank/suit region";
        out->clear();
        return false;
      }

      RECT rank_rect;
      RECT suit_rect;
      if (!DeepOFCReadRegionRect(rank_region, &rank_rect)
          || !DeepOFCReadRegionRect(suit_region, &suit_rect)) {
        if (text_error != NULL) *text_error = "Fantasy T7 source rectangles missing";
        out->clear();
        return false;
      }

      COFCFantasyPixelObject object;
      object.valid = false;
      object.fresh_from_current_bitmap = true;
      object.detected_layout_count = loose_count;
      object.geometry_residual = 0.0;
      object.source_rect.left = std::min(rank_rect.left, suit_rect.left);
      object.source_rect.top = std::min(rank_rect.top, suit_rect.top);
      object.source_rect.right = std::max(rank_rect.right, suit_rect.right);
      object.source_rect.bottom = std::max(rank_rect.bottom, suit_rect.bottom);
      object.drag_anchor.x = (object.source_rect.left + object.source_rect.right) / 2;
      object.drag_anchor.y = (object.source_rect.top + object.source_rect.bottom) / 2;

      bool identity_ok = true;
      std::string local_failure;
      CString rank_text;
      CString suit_text;
      if (!EvaluateRegion(rank_region, &rank_text)) {
        identity_ok = false;
        local_failure = "Fantasy T7 rank transform failed";
      } else {
        rank_text.Trim();
        rank_text.MakeUpper();
        if (rank_text == "X") {
          int joker_id = 0;
          std::string joker_error;
          if (!COFCFantasyPixelRecognizer::ClassifyFanJokerAtRect(
                _entire_window_cur, rank_rect, &joker_id, &joker_error)) {
            identity_ok = false;
            local_failure = joker_error;
          } else {
            object.card.valid = true;
            object.card.joker_id = joker_id;
          }
        } else if (!EvaluateRegion(suit_region, &suit_text)) {
          identity_ok = false;
          local_failure = "Fantasy T7 suit transform failed";
        } else {
          suit_text.Trim();
          suit_text.MakeLower();
          char rank = 0;
          if (rank_text == "10") rank = 'T';
          else if (rank_text.GetLength() == 1) rank = rank_text[0];
          const std::string ranks = "23456789TJQKA";
          if (rank == 0 || ranks.find(rank) == std::string::npos
              || !IsSuitString(suit_text)) {
            identity_ok = false;
            local_failure = "Fantasy T7 rank/suit result is invalid";
          } else {
            object.card.valid = true;
            object.card.rank = rank;
            object.card.suit = static_cast<char>(tolower(suit_text[0]));
          }
        }
      }

      int value = identity_ok ? DeepOFCPixelCardValue(object.card)
                              : kOFCCardUnknown;
      if (identity_ok) {
        const std::string label = object.card.PhysicalLabel();
        if (label == "AMBIGUOUS" || !labels.insert(label).second) {
          duplicate_identity = true;
          if (first_failure.empty())
            first_failure = "Fantasy T7 returned duplicate/ambiguous physical card";
        }
        object.valid = true;
      } else {
        ++invalid_count;
        invalid_index = i;
        if (first_failure.empty()) first_failure = local_failure;
      }
      observed_values.push_back(value);
      out->push_back(object);
    }

    // A previously probed card may still be unreadable in the fan. Reuse is
    // permitted only for that same Fantasy physical set. Full-fan recovery is
    // exact set subtraction; partial-fan recovery remains subject to the exact
    // lineage/arrangement verification later in this same scrape.
    if (invalid_count == 1 && !duplicate_identity
        && g_openofc_identity_recovery_cache.valid()) {
      int recovered = kOFCCardNoCard;
      std::vector<int> completed;
      std::string cache_error;
      const int expected_total = !original_labels.empty()
        ? static_cast<int>(original_labels.size()) : loose_count;
      bool cache_ok = false;
      if (loose_count == expected_total) {
        cache_ok = g_openofc_identity_recovery_cache.CompleteOneUnknown(
          expected_total, observed_values, &completed, &recovered, &cache_error);
      } else {
        cache_ok =
          g_openofc_identity_recovery_cache.SuggestProbedCardForSingleUnknownSubset(
            expected_total, observed_values, &recovered, &cache_error);
        completed = observed_values;
        if (cache_ok) completed[invalid_index] = recovered;
      }
      if (cache_ok) {
        COFCFantasyPixelCard recovered_pixel;
        if (card_from_label(DeepOFCPhysicalLabel(recovered), &recovered_pixel)) {
          (*out)[invalid_index].card = recovered_pixel;
          (*out)[invalid_index].valid = true;
          observed_values = completed;
          invalid_count = 0;
          write_log(k_always_log_errors,
            "[OpenOFC IDENTITY V580] mode=FANTASY cache=APPLIED "
            "count=%d loose=%d index=%d card=%s authority=%s\n",
            expected_total, loose_count, invalid_index,
            DeepOFCPhysicalLabel(recovered).c_str(),
            loose_count == expected_total
              ? "EXACT_SET_SUBTRACTION" : "PROBED_IDENTITY_PLUS_LINEAGE");
        }
      } else {
        write_log(true,
          "[OpenOFC IDENTITY V580] mode=FANTASY cache=REFUSED reason=\"%s\"\n",
          cache_error.c_str());
      }
    }

    if (invalid_count != 0 || duplicate_identity) {
      COFCIdentityProbeEvidence *evidence = &obs->identity_probe;
      evidence->anomaly_detected = true;
      evidence->fantasy_card_count = !original_labels.empty()
        ? static_cast<int>(original_labels.size()) : loose_count;
      evidence->known_count = 0;
      std::set<int> known_unique;
      for (size_t i = 0; i < observed_values.size(); ++i) {
        if (observed_values[i] < 0
            || !known_unique.insert(observed_values[i]).second) continue;
        if (evidence->known_count < kOFCMaxIncomingCards)
          evidence->known_values[evidence->known_count++] = observed_values[i];
      }
      const std::string reason = first_failure.empty()
        ? "Fantasy identity ambiguity" : first_failure;
      strncpy_s(evidence->reason, sizeof(evidence->reason),
        reason.c_str(), _TRUNCATE);

      // Exactly one transform failure has one physical source rectangle.
      // Duplicate identities have two possible sources and stay fail-closed.
      int staging_row = -1;
      for (int r = 0; r < 3; ++r) {
        if (diagnostic_row_occupied[r] == 0) {
          staging_row = r;
          break;
        }
      }
      if (invalid_count == 1 && !duplicate_identity && staging_row >= 0) {
        evidence->candidate_available = true;
        evidence->candidate_index = invalid_index;
        evidence->staging_row = staging_row;
        evidence->candidate_source.valid = true;
        evidence->candidate_source.card_value = kOFCCardUnknown;
        evidence->candidate_source.rect = (*out)[invalid_index].source_rect;
      }
      if (text_error != NULL) *text_error = reason;
      write_log(k_always_log_errors,
        "[OpenOFC IDENTITY V580] anomaly=1 candidate=%d count=%d "
        "index=%d known=%d reason=\"%s\" action=%s terminal=0\n",
        evidence->candidate_available ? 1 : 0,
        evidence->fantasy_card_count, evidence->candidate_index,
        evidence->known_count, evidence->reason,
        evidence->candidate_available ? "BOUNDED_PROBE_AVAILABLE" : "FAIL_CLOSED");
      return false;
    }

    if (text_error != NULL) text_error->clear();
    return true;
  };'''
    write_source(path, text[:start] + replacement + text[end:], eol, bom)
    # Bind the reversible staging row to current-bitmap occupancy, including
    # the prior-lineage path where row identities are populated only after the
    # loose fan has been accepted.
    path, text, eol, bom = read_source("OpenHoldem/COFCScraper.cpp")
    old = """    int occupied_hint = 0;
    for (size_t i = 0; i < occupied.size(); ++i)
      if (occupied[i]) ++occupied_hint;

    int text_count = 0;
"""
    new = """    int occupied_hint = 0;
    int occupancy_flat = 0;
    for (int row = 0; row < 3; ++row) {
      diagnostic_row_occupied[row] = 0;
      for (int i = 0; i < row_counts[row]; ++i, ++occupancy_flat) {
        if (occupied[occupancy_flat]) {
          ++occupied_hint;
          ++diagnostic_row_occupied[row];
        }
      }
    }

    int text_count = 0;
"""
    if text.count(old) != 1:
        raise SystemExit("COFCScraper.cpp: prior-lineage occupancy block mismatch")
    text = text.replace(old, new, 1)
    old = """    if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
          _entire_window_cur, arrangement_rects,
          &occupied, &arrangement_cards, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V550] initial arrangement rejected error=%s terminal=0\\n",
        recognition_error.c_str());
      return false;
    }
  }

  int arrangement_count = 0;
"""
    new = """    if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
          _entire_window_cur, arrangement_rects,
          &occupied, &arrangement_cards, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V550] initial arrangement rejected error=%s terminal=0\\n",
        recognition_error.c_str());
      return false;
    }
    int occupancy_flat = 0;
    for (int row = 0; row < 3; ++row) {
      diagnostic_row_occupied[row] = 0;
      for (int i = 0; i < row_counts[row]; ++i, ++occupancy_flat)
        if (occupied[occupancy_flat]) ++diagnostic_row_occupied[row];
    }
  }

  int arrangement_count = 0;
"""
    if text.count(old) != 1:
        raise SystemExit("COFCScraper.cpp: bootstrap occupancy block mismatch")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print("patched OpenHoldem/COFCScraper.cpp: tolerant one-card diagnostic route", flush=True)


def patch_replay() -> None:
    replace_once(
        "OpenHoldem/CSymbolEngineReplayFrameController.h",
        """#include "CVirtualSymbolEngine.h"

class CSymbolEngineReplayFrameController""",
        """#include "CVirtualSymbolEngine.h"

// OpenOFC anomaly capture hook: persists the current BMP + HTML diagnostic.
void RequestOpenOFCReplayFrame(const char *reason);

class CSymbolEngineReplayFrameController""",
        "declare OpenOFC replay request hook",
    )
    path, text, eol, bom = read_source(
        "OpenHoldem/CSymbolEngineReplayFrameController.cpp"
    )
    text += r'''

void RequestOpenOFCReplayFrame(const char *reason) {
  write_log(k_always_log_errors,
    "[OpenOFC IDENTITY REPLAY] capture=REQUESTED reason=\"%s\"\n",
    reason == NULL ? "UNSPECIFIED" : reason);
  if (p_engine_container == NULL
      || p_engine_container->symbol_engine_replayframe_controller() == NULL) {
    write_log(k_always_log_errors,
      "[OpenOFC IDENTITY REPLAY] capture=UNAVAILABLE reason=NO_CONTROLLER\n");
    return;
  }
  p_engine_container->symbol_engine_replayframe_controller()
    ->ShootReplayFrameIfNotYetDone();
}
'''
    write_source(path, text, eol, bom)
    print("patched OpenHoldem/CSymbolEngineReplayFrameController.cpp: anomaly replay hook", flush=True)


def patch_runtime_header() -> None:
    replace_once(
        "OpenHoldem/COFCRuntimeController.h",
        '#include "COFCTurnOrchestrator.h"\n',
        '#include "COFCTurnOrchestrator.h"\n'
        '#include "COFCUnknownCardProbe.h"\n',
        "include UNKNOWN-card probe",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.h",
        """    kConfirmSent,
    kReacquire,
""",
        """    kConfirmSent,
    kIdentityProbe,
    kReacquire,
""",
        "add active identity-probe runtime phase",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.h",
        """  bool DecisionStabilized(const COFCState &state);
  static int UnknownIncomingCount(const COFCState &state);
""",
        """  bool DecisionStabilized(const COFCState &state);
  static int UnknownIncomingCount(const COFCState &state);
  bool MaybeStartIdentityProbe(
      const COFCState &state,
      const COFCVisualObservation &observation);
  bool AdvanceIdentityProbe(
      const COFCState &state,
      const COFCVisualObservation &observation);
""",
        "declare active identity-probe transaction",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.h",
        """  Phase phase_;
  COFCTurnOrchestrator orchestrator_;
""",
        """  Phase phase_;
  COFCUnknownCardProbe identity_probe_;
  std::string active_probe_signature_;
  std::string exhausted_probe_signature_;
  COFCTurnOrchestrator orchestrator_;
""",
        "store bounded identity-probe transaction",
    )


def patch_project() -> None:
    replace_once(
        "OpenHoldem/OpenHoldem.vcxproj",
        """    <ClCompile Include="COFCFantasyExactSolver.cpp">
      <PrecompiledHeader>NotUsing</PrecompiledHeader>
    </ClCompile>
    <ClCompile Include="COFCR4ExactTeacher.cpp">
""",
        """    <ClCompile Include="COFCFantasyExactSolver.cpp">
      <PrecompiledHeader>NotUsing</PrecompiledHeader>
    </ClCompile>
    <ClCompile Include="COFCIdentityRecoveryCache.cpp" />
    <ClCompile Include="COFCUnknownCardProbe.cpp" />
    <ClCompile Include="COFCR4ExactTeacher.cpp">
""",
        "compile active identity-recovery sources in Release",
    )


RUNTIME_METHODS = r'''

bool COFCRuntimeController::MaybeStartIdentityProbe(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  if (phase_ != kIdle && phase_ != kReacquire) return false;
  if (p_tablemap == NULL || p_casino_interface == NULL
      || !p_tablemap->SupportsOFCJokerUltimate()
      || p_tablemap->GetTMSymbol("ofc_executor_enabled", 0) != 1) {
    return false;
  }

  // Fantasy: the scraper retained one exact current source even though the
  // complete fan was rejected. A row must be completely empty because the
  // same contextual button is later used as the reversible red-X clear.
  if (observation.identity_probe.anomaly_detected) {
    ostringstream signature;
    signature << "F:" << observation.identity_probe.fantasy_card_count
      << ':' << observation.identity_probe.candidate_index << ':'
      << observation.identity_probe.candidate_source.rect.left << ':'
      << observation.identity_probe.candidate_source.rect.top << ':'
      << observation.identity_probe.reason;
    const string candidate_signature = signature.str();
    if (candidate_signature == exhausted_probe_signature_) return false;
    if (!observation.identity_probe.candidate_available) {
      exhausted_probe_signature_ = candidate_signature;
      RequestOpenOFCReplayFrame("FANTASY_IDENTITY_AMBIGUITY_NO_UNIQUE_SOURCE");
      write_log(k_always_log_errors,
        "[OpenOFC IDENTITY V580] mode=FANTASY action=NONE "
        "reason=NO_UNIQUE_SOURCE replay=1 terminal=0\n");
      return false;
    }

    const EOFCRow row = static_cast<EOFCRow>(
      observation.identity_probe.staging_row);
    if (row == kOFCRowUndefined) {
      exhausted_probe_signature_ = candidate_signature;
      RequestOpenOFCReplayFrame("FANTASY_IDENTITY_PROBE_NO_EMPTY_REVERSIBLE_ROW");
      return false;
    }

    string error;
    if (!identity_probe_.BeginFantasy(observation, row, &error)) {
      exhausted_probe_signature_ = candidate_signature;
      RequestOpenOFCReplayFrame("FANTASY_IDENTITY_PROBE_PRECONDITION_REJECTED");
      return false;
    }
    RECT action;
    CString action_name;
    action_name.Format("ofc_fantasy_row_action_%s", RowLabel(row));
    if (!ReadRegion(action_name, &action)) {
      identity_probe_.Fail("missing Fantasy diagnostic row-action region");
      exhausted_probe_signature_ = candidate_signature;
      RequestOpenOFCReplayFrame("FANTASY_IDENTITY_PROBE_ACTION_REGION_MISSING");
      return false;
    }
    RECT clicks[2] = {identity_probe_.source_rect(), action};
    const int gap_ms = max(300,
      p_tablemap->GetTMSymbol("ofc_identity_probe_click_gap_ms", 400));
    RequestOpenOFCReplayFrame("FANTASY_IDENTITY_PROBE_BEFORE_INPUT");
    if (!p_casino_interface->ClickRectsBoundedOFC(clicks, 2, gap_ms)) {
      identity_probe_.Fail("Fantasy diagnostic select-and-place was refused");
      exhausted_probe_signature_ = candidate_signature;
      RequestOpenOFCReplayFrame("FANTASY_IDENTITY_PROBE_INPUT_REFUSED");
      return false;
    }
    active_probe_signature_ = candidate_signature;
    phase_ = kIdentityProbe;
    recovery_requires_change_ = true;
    OpenOFCSetUserStatus("RECUPERANDO CARTA FANTASY - verificando no board");
    write_log(k_always_log_errors,
      "[OpenOFC IDENTITY V580] mode=FANTASY action=PROBE_SENT "
      "row=%s source=(%ld,%ld,%ld,%ld) gap_ms=%d replay=1\n",
      RowLabel(row), clicks[0].left, clicks[0].top,
      clicks[0].right, clicks[0].bottom, gap_ms);
    return true;
  }

  // Normal OFC: exactly one UNKNOWN plus one exact loose source is required.
  if (!state.valid || !observation.valid
      || state.hero_chair < 0 || state.hero_chair >= state.player_count
      || state.players[state.hero_chair].fantasy
      || UnknownIncomingCount(state) != 1) return false;
  int unknown_source = -1;
  for (int i = 0; i < observation.hero_loose_count; ++i) {
    if (observation.hero_loose_cards[i].value != kOFCCardUnknown) continue;
    const COFCVisualCardSource &source = observation.hero_loose_sources[i];
    if (!source.valid || source.rect.right <= source.rect.left
        || source.rect.bottom <= source.rect.top) return false;
    if (unknown_source >= 0) return false;
    unknown_source = i;
  }
  if (unknown_source < 0) return false;

  ostringstream signature;
  signature << "N:" << StateFingerprint(state) << ':' << unknown_source << ':'
    << observation.hero_loose_sources[unknown_source].rect.left << ':'
    << observation.hero_loose_sources[unknown_source].rect.top;
  const string candidate_signature = signature.str();
  if (candidate_signature == exhausted_probe_signature_) return false;

  const COFCPlayerBoard &visual =
    observation.players[observation.hero_chair].visual_board;
  EOFCRow row = kOFCRowUndefined;
  int slot = -1;
  for (int r = kOFCRowTop; r <= kOFCRowBottom && slot < 0; ++r) {
    const EOFCRow candidate = static_cast<EOFCRow>(r);
    const COFCCard *cards = candidate == kOFCRowTop ? visual.top
      : (candidate == kOFCRowMiddle ? visual.middle : visual.bottom);
    const int capacity = candidate == kOFCRowTop
      ? kOFCTopCards : kOFCMiddleCards;
    int occupied = 0;
    bool prefix = true;
    for (int i = 0; i < capacity; ++i) {
      if (cards[i].value == kOFCCardNoCard) {
        for (int j = i + 1; j < capacity; ++j)
          if (cards[j].value != kOFCCardNoCard) prefix = false;
        break;
      }
      ++occupied;
    }
    if (prefix && occupied < capacity) {
      row = candidate;
      slot = occupied;
    }
  }
  if (slot < 0) {
    exhausted_probe_signature_ = candidate_signature;
    RequestOpenOFCReplayFrame("NORMAL_IDENTITY_PROBE_NO_SAFE_STAGING_SLOT");
    return false;
  }
  CString target_name;
  target_name.Format("ofc_drop_%s%d", RowLabel(row), slot);
  RECT target;
  if (!ReadRegion(target_name, &target)) {
    exhausted_probe_signature_ = candidate_signature;
    RequestOpenOFCReplayFrame("NORMAL_IDENTITY_PROBE_TARGET_REGION_MISSING");
    return false;
  }
  string error;
  const RECT source = observation.hero_loose_sources[unknown_source].rect;
  if (!identity_probe_.BeginNormal(state, observation, row, source, &error)) {
    exhausted_probe_signature_ = candidate_signature;
    return false;
  }
  const int duration_ms = max(500,
    p_tablemap->GetTMSymbol("ofc_identity_probe_drag_ms", 700));
  RequestOpenOFCReplayFrame("NORMAL_IDENTITY_PROBE_BEFORE_INPUT");
  if (!p_casino_interface->DragRectToRect(source, target, duration_ms)) {
    identity_probe_.Fail("normal diagnostic drag was refused");
    exhausted_probe_signature_ = candidate_signature;
    RequestOpenOFCReplayFrame("NORMAL_IDENTITY_PROBE_INPUT_REFUSED");
    return false;
  }
  active_probe_signature_ = candidate_signature;
  phase_ = kIdentityProbe;
  recovery_requires_change_ = true;
  OpenOFCSetUserStatus("RECUPERANDO CARTA - verificando no board");
  write_log(k_always_log_errors,
    "[OpenOFC IDENTITY V580] mode=NORMAL action=PROBE_SENT "
    "row=%s slot=%d duration_ms=%d replay=1\n",
    RowLabel(row), slot, duration_ms);
  return true;
}

bool COFCRuntimeController::AdvanceIdentityProbe(
    const COFCState &state,
    const COFCVisualObservation &observation) {
  if (phase_ != kIdentityProbe || !identity_probe_.active()) return false;
  const int wait_cycles = p_tablemap == NULL ? 12
    : max(8, p_tablemap->GetTMSymbol("ofc_identity_probe_wait_cycles", 12));
  string event;

  if (identity_probe_.phase() == COFCUnknownCardProbe::kAwaitNormalPlacement
      || identity_probe_.phase() == COFCUnknownCardProbe::kAwaitFantasyPlacement) {
    int resolved = kOFCCardNoCard;
    const bool observed = identity_probe_.ObservePlacement(
      state, observation, wait_cycles, &resolved, &event);
    if (identity_probe_.phase() == COFCUnknownCardProbe::kFailed) {
      exhausted_probe_signature_ = active_probe_signature_;
      RequestOpenOFCReplayFrame("IDENTITY_PROBE_PLACEMENT_TIMEOUT");
      const string reason = identity_probe_.failure_reason();
      identity_probe_.Reset();
      Recover(reason);
      recovery_requires_change_ = true;
      return true;
    }
    if (!observed) {
      write_log(true,
        "[OpenOFC IDENTITY V580] verify=%s raw_valid=%d state_valid=%d\n",
        event.c_str(), observation.valid ? 1 : 0, state.valid ? 1 : 0);
      return true;
    }

    RequestOpenOFCReplayFrame("IDENTITY_PROBE_RESOLVED_ON_BOARD");
    write_log(k_always_log_errors,
      "[OpenOFC IDENTITY V580] resolved=1 card=%s proof=%s mode=%s replay=1\n",
      CardLabel(resolved).c_str(), event.c_str(),
      identity_probe_.fantasy() ? "FANTASY" : "NORMAL");

    if (!identity_probe_.fantasy()) {
      identity_probe_.Reset();
      active_probe_signature_.clear();
      exhausted_probe_signature_.clear();
      orchestrator_.ResetForKnownNewHand();
      fantasy_executor_.Reset();
      plan_.Reset();
      phase_ = kIdle;
      current_fingerprint_ = StateFingerprint(state);
      ArmDecisionStabilization(state, "NORMAL_IDENTITY_RECOVERED");
      OpenOFCSetUserStatus("CARTA RECUPERADA - recalculando");
      return true;
    }

    vector<int> exact_set;
    if (!state.valid || state.hero_incoming_count != identity_probe_.fantasy_card_count()) {
      identity_probe_.Fail("Fantasy post-probe canonical set is unavailable");
    } else {
      for (int i = 0; i < state.hero_incoming_count; ++i)
        exact_set.push_back(state.hero_incoming[i].value);
      string cache_error;
      if (!g_openofc_identity_recovery_cache.RememberFantasySet(
            identity_probe_.fantasy_card_count(), exact_set,
            resolved, &cache_error)) {
        identity_probe_.Fail("Fantasy recovery cache refused exact set: " + cache_error);
      }
    }
    if (identity_probe_.phase() == COFCUnknownCardProbe::kFailed) {
      exhausted_probe_signature_ = active_probe_signature_;
      RequestOpenOFCReplayFrame("FANTASY_IDENTITY_CACHE_REJECTED");
      const string reason = identity_probe_.failure_reason();
      identity_probe_.Reset();
      Recover(reason);
      recovery_requires_change_ = true;
      return true;
    }

    CString action_name;
    action_name.Format("ofc_fantasy_row_action_%s",
      RowLabel(identity_probe_.staging_row()));
    RECT action;
    if (!ReadRegion(action_name, &action)
        || p_casino_interface == NULL
        || !p_casino_interface->ClickRectBoundedOFC(action)) {
      exhausted_probe_signature_ = active_probe_signature_;
      RequestOpenOFCReplayFrame("FANTASY_IDENTITY_CLEAR_REFUSED");
      identity_probe_.Reset();
      Recover("Fantasy diagnostic row-X clear was refused");
      recovery_requires_change_ = true;
      return true;
    }
    identity_probe_.MarkFantasyClearSent();
    OpenOFCSetUserStatus("CARTA FANTASY IDENTIFICADA - limpando teste");
    write_log(k_always_log_errors,
      "[OpenOFC IDENTITY V580] mode=FANTASY action=CLEAR_PROBE_ROW_SENT "
      "row=%s card=%s cache=ARMED\n",
      RowLabel(identity_probe_.staging_row()), CardLabel(resolved).c_str());
    return true;
  }

  if (identity_probe_.phase() == COFCUnknownCardProbe::kAwaitFantasyClear) {
    const bool cleared = identity_probe_.ObserveFantasyClear(
      observation, wait_cycles, &event);
    if (identity_probe_.phase() == COFCUnknownCardProbe::kFailed) {
      exhausted_probe_signature_ = active_probe_signature_;
      RequestOpenOFCReplayFrame("FANTASY_IDENTITY_CLEAR_TIMEOUT");
      const string reason = identity_probe_.failure_reason();
      identity_probe_.Reset();
      Recover(reason);
      recovery_requires_change_ = true;
      return true;
    }
    if (!cleared) {
      write_log(true,
        "[OpenOFC IDENTITY V580] verify=%s raw_valid=%d\n",
        event.c_str(), observation.valid ? 1 : 0);
      return true;
    }
    RequestOpenOFCReplayFrame("FANTASY_IDENTITY_PROBE_COMPLETE");
    identity_probe_.Reset();
    active_probe_signature_.clear();
    exhausted_probe_signature_.clear();
    orchestrator_.ResetForKnownNewHand();
    fantasy_executor_.Reset();
    plan_.Reset();
    phase_ = kIdle;
    current_fingerprint_ = StateFingerprint(state);
    ArmDecisionStabilization(state, "FANTASY_IDENTITY_RECOVERED");
    OpenOFCSetUserStatus("CARTA FANTASY RECUPERADA - recalculando");
    write_log(k_always_log_errors,
      "[OpenOFC IDENTITY V580] mode=FANTASY complete=1 "
      "clear_verified=1 next=FRESH_REPLAN replay=1\n");
    return true;
  }
  return false;
}
'''


def patch_runtime_cpp() -> None:
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '#include "COFCFantasyConfirmGuard.h"\n',
        '#include "COFCFantasyConfirmGuard.h"\n'
        '#include "COFCIdentityRecoveryCache.h"\n'
        '#include "COFCRecoveryLiveness.h"\n'
        '#include "CSymbolEngineReplayFrameController.h"\n',
        "include active-recovery dependencies",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        """void COFCRuntimeController::ResetForKnownNewHand(const COFCState &state) {
""",
        RUNTIME_METHODS
        + """

void COFCRuntimeController::ResetForKnownNewHand(const COFCState &state) {
""",
        "add reversible identity-probe runtime transaction",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        """  fantasy_confirm_fence_.ResetForNewHand();
  pending_before_drag_ = 0;
""",
        """  fantasy_confirm_fence_.ResetForNewHand();
  identity_probe_.Reset();
  active_probe_signature_.clear();
  exhausted_probe_signature_.clear();
  const bool retain_fantasy_recovery = state.valid
    && state.hero_chair >= 0 && state.hero_chair < state.player_count
    && state.players[state.hero_chair].fantasy
    && g_openofc_identity_recovery_cache.valid()
    && g_openofc_identity_recovery_cache.fantasy_card_count()
       == state.fantasy_card_count;
  if (!retain_fantasy_recovery)
    g_openofc_identity_recovery_cache.Reset();
  pending_before_drag_ = 0;
""",
        "reset or retain correctly bound recovery cache",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        """  if (fantasy_confirm) {
    // The mouse DLL has now been invoked. From this point onward no second
""",
        """  if (fantasy_confirm) {
    // No probe cache may cross the Fantasy Confirm/new-deal boundary.
    g_openofc_identity_recovery_cache.Reset();
    // The mouse DLL has now been invoked. From this point onward no second
""",
        "clear recovery cache at Fantasy transaction boundary",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        """  if (state.valid) current_fingerprint_ = StateFingerprint(state);
  if (!state.valid || !observation.valid) {
""",
        """  // Identity recovery is evaluated before generic invalid-perception
  // suppression because Fantasy diagnostic evidence is intentionally carried
  // by an otherwise invalid raw observation.
  if (phase_ == kIdentityProbe) {
    AdvanceIdentityProbe(state, observation);
    return;
  }
  if ((phase_ == kIdle || phase_ == kReacquire)
      && MaybeStartIdentityProbe(state, observation)) {
    return;
  }

  if (state.valid) current_fingerprint_ = StateFingerprint(state);
  if (!state.valid || !observation.valid) {
""",
        "route UNKNOWN evidence before invalid-frame return",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        """  if (phase_ == kReacquire) {
    if (!state.valid || !observation.valid) {
    if (state.valid && !observation.valid)
      OpenOFCSetUserStatus("RECUPERANDO LEITURA - sem agir");
    else
      OpenOFCSetUserStatus("AGUARDANDO ESTADO VALIDO");
    write_log(true, "[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION\\n");
    return;
  }

  }
""",
        r'''  if (phase_ == kReacquire) {
    const string now = StateFingerprint(state);
    const bool hero_state_changed = now != recovery_fingerprint_;
    const COFCRecoveryLivenessDecision recovery =
      EvaluateOFCRecoveryLiveness(
        true, hero_state_changed, recovery_requires_change_,
        reacquire_stable_cycles_);
    reacquire_stable_cycles_ = recovery.stable_cycles;
    write_log(true,
      "[OpenOFC REACQUIRE V580] release=%d reason=%s changed=%d "
      "stable=%d/%d action_may_have_been_sent=%d\n",
      recovery.release ? 1 : 0,
      OFCRecoveryLivenessReasonLabel(recovery.reason),
      hero_state_changed ? 1 : 0,
      recovery.stable_cycles, recovery.required_cycles,
      recovery_requires_change_ ? 1 : 0);
    if (!recovery.release) {
      OpenOFCSetUserStatus("RECUPERANDO LEITURA - sem repetir acao");
      return;
    }
    orchestrator_.ResetForKnownNewHand();
    fantasy_executor_.Reset();
    plan_.Reset();
    confirm_before_.Reset();
    recovery_fingerprint_.clear();
    recovery_requires_change_ = false;
    reacquire_stable_cycles_ = 0;
    phase_ = kIdle;
    current_fingerprint_ = now;
    ArmDecisionStabilization(state, "BOUNDED_REACQUIRE_RELEASE");
    OpenOFCSetUserStatus("LEITURA RECUPERADA - recalculando");
    return;
  }
''',
        "restore non-absorbing reacquire transition",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        """        ResetForKnownNewHand(state);
    ArmDecisionStabilization(state, "NEW_HAND_EDGE");
        ArmDecisionStabilization(state, "NEW_HAND_EDGE");
""",
        """        ResetForKnownNewHand(state);
        ArmDecisionStabilization(state, "NEW_HAND_EDGE");
""",
        "remove duplicate new-hand stabilization arm",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        "engine=EXACT_FANTASY_R4_V570",
        "engine=EXACT_FANTASY_R4_IDREC_V580",
        "publish v5.8.0 composed engine telemetry",
    )


def main() -> None:
    patch_observation()
    patch_scraper()
    patch_replay()
    patch_runtime_header()
    patch_project()
    patch_runtime_cpp()
    print(
        "OPENOFC_ACTIVE_IDENTITY_RECOVERY_V580_APPLY=PASS "
        "normal=BOARD_PROBE fantasy=REVERSIBLE_PROBE replay=BMP_HTML "
        "reacquire=BOUNDED_NONABSORBING tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
