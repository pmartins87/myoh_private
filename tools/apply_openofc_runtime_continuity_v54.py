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
        raise RuntimeError(f"{rel}: expected one target, got {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def regex_once(rel: str, pattern: str, replacement: str, flags=re.S):
    path, text, eol, bom = read_source(rel)
    new, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(
            f"{rel}: regex expected one target, got {count}: {pattern[:140]}"
        )
    write_source(path, new, eol, bom)
    print(f"patched {rel}")


def patch_current_screen_reconstructor():
    rel = "OpenHoldem/COFCReconstructor.h"
    replace_once(
        rel,
        '''  // Reconstruct one canonical state. `previous` may be NULL only for a normal
  // round-0 attachment. Failure is fail-closed and leaves `out` reset/invalid.
  static bool Reconstruct(
      const COFCVisualObservation &observation,
      const COFCState *previous,
      COFCState *out,
      std::string *error);

''',
        '''  // Reconstruct one canonical state from normal lineage when available.
  // Active Fantasy is self-contained; normal continuation ordinarily uses
  // `previous` to distinguish committed from tentative Hero row cards.
  static bool Reconstruct(
      const COFCVisualObservation &observation,
      const COFCState *previous,
      COFCState *out,
      std::string *error);

  // OPENOFC_CURRENT_SCREEN_RECONSTRUCTION_V54. Recovery/bootstrap entry point.
  // It deliberately ignores process memory. It is authoritative only where the
  // current screen is self-describing: Fantasy 14..17, normal round 0, or a
  // later normal round with all three current cards still loose. Partially
  // arranged later rounds remain a separate hypothesis-recovery gate; guessing
  // which row cards are tentative is forbidden.
  static bool ReconstructCurrentScreen(
      const COFCVisualObservation &observation,
      COFCState *out,
      std::string *error);

''')

    rel = "OpenHoldem/COFCReconstructor.cpp"
    marker = '''string COFCReconstructor::DiagnosticSnapshot(const COFCState &state) {'''
    path, text, eol, bom = read_source(rel)
    if text.count(marker) != 1:
        raise RuntimeError(f"{rel}: DiagnosticSnapshot insertion marker missing")
    method = r'''bool COFCReconstructor::ReconstructCurrentScreen(
    const COFCVisualObservation &observation,
    COFCState *out,
    string *error) {
  if (out == NULL) return false;
  out->Reset();
  if (error != NULL) error->clear();

  if (!observation.valid) {
    return Fail(out, error, "current-screen reconstruction received invalid raw observation");
  }
  if (observation.hero_chair < 0
      || observation.hero_chair >= observation.player_count) {
    return Fail(out, error, "current-screen reconstruction has invalid Hero chair");
  }

  // Fantasy is a one-shot 14..17-card state and is already self-contained.
  // Normal R0 is also self-contained because no Hero card is committed yet.
  if (observation.players[observation.hero_chair].fantasy
      || observation.round_index == 0) {
    return Reconstruct(observation, NULL, out, error);
  }

  if (observation.round_index < 1 || observation.round_index > 4) {
    return Fail(out, error,
      "current-screen normal reconstruction requires round 0..4");
  }

  // In R1..R4 the current screen is unambiguous when all three current cards
  // are still loose: every Hero row card is committed. Once one of the three
  // has been dragged into a row, a single frame cannot prove which visible row
  // card is current-round tentative, so v5.4.2A refuses to guess.
  if (observation.hero_loose_count != 3) {
    ostringstream oss;
    oss << "current-screen normal round " << observation.round_index
        << " is partially arranged; expected all 3 current cards loose, got "
        << observation.hero_loose_count;
    return Fail(out, error, oss.str());
  }

  const COFCPlayerBoard &hero_visual =
    observation.players[observation.hero_chair].visual_board;
  const int expected_committed = 3 + 2 * observation.round_index;
  if (hero_visual.CountKnownCards() != expected_committed) {
    ostringstream oss;
    oss << "current-screen normal round " << observation.round_index
        << " expected " << expected_committed
        << " committed Hero row cards with all three current cards loose; got "
        << hero_visual.CountKnownCards();
    return Fail(out, error, oss.str());
  }

  set<int> current = CardArraySet(
    observation.hero_loose_cards, observation.hero_loose_count);
  if (current.size() != 3) {
    return Fail(out, error,
      "current-screen normal recovery requires three unique known loose cards");
  }

  // Build a synthetic same-round lineage whose committed Hero board is exactly
  // the visible board. Feeding that through the ordinary reconstructor keeps
  // one canonical validation path instead of maintaining a permissive recovery
  // clone. Unknown pre-restart Hero discards remain unknown and are logged by
  // the caller; inventing their identities would be worse than information loss.
  COFCState seed;
  seed.Reset();
  seed.schema_version = kOFCStateSchemaVersion;
  seed.player_count = observation.player_count;
  seed.hero_chair = observation.hero_chair;
  seed.dealer_chair = observation.dealer_chair;
  seed.acting_chair = observation.acting_chair;
  seed.round_index = observation.round_index;
  seed.hero_can_prepare = observation.hero_can_prepare;
  seed.hero_can_confirm = false;
  seed.action_required = false;

  string validation_error;
  for (int p = 0; p < observation.player_count; ++p) {
    seed.players[p].occupied = observation.players[p].occupied;
    seed.players[p].source_chair = observation.players[p].source_chair;
    seed.players[p].fantasy = observation.players[p].fantasy;
    seed.players[p].sitting_out = observation.players[p].sitting_out;
    seed.players[p].hidden_incoming_count =
      observation.players[p].hidden_incoming_count;
    seed.players[p].hidden_discard_count =
      observation.players[p].hidden_discard_count;
    if (!NormalizeBoard(
          observation.players[p].visual_board,
          &seed.players[p].board, &validation_error)) {
      return Fail(out, error, "current-screen seed: " + validation_error);
    }
  }

  CopySortedValuesToCards(
    current, seed.hero_incoming, kOFCMaxIncomingCards,
    &seed.hero_incoming_count);
  seed.hero_discard_count = 0;
  seed.valid = true;

  if (!Reconstruct(observation, &seed, out, error)) {
    return false;
  }
  return true;
}

'''
    text = text.replace(marker, method + marker, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_lazy_scraper_reacquisition():
    rel = "OpenHoldem/CLazyScraper.cpp"
    path, text, eol, bom = read_source(rel)

    anchor = '''  static unsigned long deepofc_cycle = 0;
'''
    if text.count(anchor) != 1:
        raise RuntimeError(f"{rel}: deepofc_cycle anchor missing")
    text = text.replace(
        anchor,
        anchor + '''  // OPENOFC_REACQUIRE_DEBOUNCE_V54: a history-breaking current-screen
  // candidate must remain semantically stable across two heartbeats before it
  // replaces canonical lineage. While this candidate is pending, an identical
  // bitmap is intentionally re-evaluated once; persistence in time is evidence
  // that the frame is not a one-heartbeat drag/deal animation.
  static bool deepofc_reacquire_candidate_pending = false;
  static std::string deepofc_reacquire_candidate_snapshot;
  static int deepofc_reacquire_candidate_hits = 0;
''',
        1)

    # The first identical-bitmap branch belongs to the OpenOFC cache block.
    old = '''    if (identical_bitmap) {
      // Recognition is a pure function of this captured bitmap plus the
'''
    new = '''    if (identical_bitmap && !deepofc_reacquire_candidate_pending) {
      // Recognition is a pure function of this captured bitmap plus the
'''
    if text.count(old) != 1:
        raise RuntimeError(f"{rel}: OpenOFC identical-cache branch not unique")
    text = text.replace(old, new, 1)

    old_log = '''    write_log(true,
      "[DeepOFC CYCLE] id=%lu bitmap=CHANGED previous_canonical_valid=%d\\n",
      deepofc_cycle, p_table_state->OFCState()->valid ? 1 : 0);
'''
    new_log = '''    if (identical_bitmap && deepofc_reacquire_candidate_pending) {
      write_log(true,
        "[OpenOFC REACQUIRE] id=%lu bitmap=IDENTICAL_STABILITY_RECHECK candidate_hits=%d terminal=0\\n",
        deepofc_cycle, deepofc_reacquire_candidate_hits);
    }
    write_log(true,
      "[DeepOFC CYCLE] id=%lu bitmap=%s previous_canonical_valid=%d\\n",
      deepofc_cycle,
      identical_bitmap ? "IDENTICAL_RECHECK" : "CHANGED",
      p_table_state->OFCState()->valid ? 1 : 0);
'''
    if text.count(old_log) != 1:
        raise RuntimeError(f"{rel}: changed-bitmap log anchor missing")
    text = text.replace(old_log, new_log, 1)

    pattern = r'''  // DeepOFC R9 canonical reconstruction path\. Joker Ultimate never falls\n  // through to legacy Hold'em hole/community/betting semantics\.\n  if \(openofc_mode\) \{.*?\n    return;\n  \}\n\tp_scraper->ScrapeLimits\(\);'''
    replacement = r'''  // DeepOFC R9 canonical reconstruction path. Joker Ultimate never falls
  // through to legacy Hold'em hole/community/betting semantics.
  if (openofc_mode) {
    COFCState previous_state = *p_table_state->OFCState();
    if (!p_scraper->ScrapeOFCVisualObservation()) {
      // OPENOFC_NEVER_TERMINAL_PERCEPTION_V54: a rejected scrape is an event,
      // not a runtime state. Keep lineage only as a reconstruction hint and
      // immediately try again on future heartbeats.
      deepofc_reacquire_candidate_pending = false;
      deepofc_reacquire_candidate_snapshot.clear();
      deepofc_reacquire_candidate_hits = 0;
      *p_table_state->OFCState() = previous_state;
      write_log(k_always_log_errors,
        "[OpenOFC FAULT] id=%lu stage=RAW_SCRAPE terminal=0 action=SUPPRESSED_THIS_FRAME lineage=%s continue_scraping=1\n",
        deepofc_cycle, previous_state.valid ? "PRESERVED_HINT" : "EMPTY");
      return;
    }

    COFCVisualObservation *raw = p_table_state->OFCVisualObservation();
    const COFCState *previous = previous_state.valid ? &previous_state : NULL;
    if (raw->round_index == 0 && previous_state.valid &&
        (previous_state.round_index > 0 ||
         (previous_state.hero_chair >= 0 &&
          previous_state.hero_chair < previous_state.player_count &&
          previous_state.players[previous_state.hero_chair].fantasy))) {
      previous = NULL;
    }

    COFCState rebuilt;
    std::string reconstruction_error;
    if (COFCReconstructor::Reconstruct(
          *raw, previous, &rebuilt, &reconstruction_error)) {
      *p_table_state->OFCState() = rebuilt;
      deepofc_reacquire_candidate_pending = false;
      deepofc_reacquire_candidate_snapshot.clear();
      deepofc_reacquire_candidate_hits = 0;
      std::string snapshot = COFCReconstructor::DiagnosticSnapshot(rebuilt);
      write_log(true,
        "[DeepOFC CYCLE] id=%lu result=CANONICAL_VALID source=LINEAGE\n",
        deepofc_cycle);
      write_log(true, "[DeepOFC SNAPSHOT v1] %s\n", snapshot.c_str());
      return;
    }

    // History is advisory, not an absorbing dependency. Ask the independent
    // current-screen entry point whether this frame is self-describing.
    COFCState current_screen;
    std::string current_screen_error;
    if (COFCReconstructor::ReconstructCurrentScreen(
          *raw, &current_screen, &current_screen_error)) {
      const std::string snapshot =
        COFCReconstructor::DiagnosticSnapshot(current_screen);
      if (deepofc_reacquire_candidate_pending
          && snapshot == deepofc_reacquire_candidate_snapshot) {
        ++deepofc_reacquire_candidate_hits;
      } else {
        deepofc_reacquire_candidate_pending = true;
        deepofc_reacquire_candidate_snapshot = snapshot;
        deepofc_reacquire_candidate_hits = 1;
      }

      if (deepofc_reacquire_candidate_hits >= 2) {
        *p_table_state->OFCState() = current_screen;
        deepofc_reacquire_candidate_pending = false;
        deepofc_reacquire_candidate_snapshot.clear();
        deepofc_reacquire_candidate_hits = 0;
        const int unknown_prior_discards =
          (!current_screen.players[current_screen.hero_chair].fantasy
           && current_screen.round_index > 1)
          ? current_screen.round_index - 1 : 0;
        write_log(k_always_log_errors,
          "[OpenOFC REACQUIRE_ACCEPT] id=%lu source=CURRENT_SCREEN round=%d fantasy=%d incoming=%d unknown_prior_discards=%d replaced_stale_lineage=1\n",
          deepofc_cycle, current_screen.round_index,
          current_screen.players[current_screen.hero_chair].fantasy ? 1 : 0,
          current_screen.hero_incoming_count, unknown_prior_discards);
        write_log(true, "[DeepOFC SNAPSHOT v1] %s\n", snapshot.c_str());
        return;
      }

      raw->valid = false;
      *p_table_state->OFCState() = previous_state;
      write_log(k_always_log_errors,
        "[OpenOFC REACQUIRE_CANDIDATE] id=%lu stable=%d/2 history_error=\"%s\" terminal=0 action=SUPPRESSED_THIS_FRAME\n",
        deepofc_cycle, deepofc_reacquire_candidate_hits,
        reconstruction_error.c_str());
      return;
    }

    // Neither lineage nor the current screen is yet sufficient. Log both
    // reasons and continue scraping; no permanent blocked state is created.
    deepofc_reacquire_candidate_pending = false;
    deepofc_reacquire_candidate_snapshot.clear();
    deepofc_reacquire_candidate_hits = 0;
    raw->valid = false;
    *p_table_state->OFCState() = previous_state;
    write_log(k_always_log_errors,
      "[OpenOFC REACQUIRE_REJECT] id=%lu history_error=\"%s\" current_screen_error=\"%s\" terminal=0 continue_scraping=1\n",
      deepofc_cycle, reconstruction_error.c_str(),
      current_screen_error.c_str());
    return;
  }
	p_scraper->ScrapeLimits();'''
    new_text, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{rel}: could not replace OpenOFC reconstruction block")
    write_source(path, new_text, eol, bom)
    print(f"patched {rel}")


def patch_runtime_controller_recovery():
    hrel = "OpenHoldem/COFCRuntimeController.h"
    path, text, eol, bom = read_source(hrel)
    if text.count("    kBlocked,\n") != 1:
        raise RuntimeError(f"{hrel}: expected one kBlocked enum entry")
    text = text.replace(
        "    kBlocked,\n",
        "    kReacquire,\n",
        1)
    if text.count("  void Block(const std::string &message);\n") != 1:
        raise RuntimeError(f"{hrel}: Block declaration missing")
    text = text.replace(
        "  void Block(const std::string &message);\n",
        "  void Recover(const std::string &message);\n",
        1)
    if text.count("  static std::string IncomingSignature(const COFCState &state);\n") != 1:
        raise RuntimeError(f"{hrel}: IncomingSignature declaration missing")
    text = text.replace(
        "  static std::string IncomingSignature(const COFCState &state);\n",
        "  static std::string IncomingSignature(const COFCState &state);\n"
        "  static std::string StateFingerprint(const COFCState &state);\n",
        1)
    if text.count("  std::string hand_signature_;\n") != 1:
        raise RuntimeError(f"{hrel}: hand_signature_ member missing")
    text = text.replace(
        "  std::string hand_signature_;\n",
        "  std::string hand_signature_;\n"
        "  std::string current_fingerprint_;\n"
        "  std::string recovery_fingerprint_;\n"
        "  int reacquire_stable_cycles_;\n"
        "  bool recovery_requires_change_;\n",
        1)
    write_source(path, text, eol, bom)
    print(f"patched {hrel}")

    rel = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_source(rel)

    # Constructor: preserve whatever earlier patch chain added to the
    # initializer list and initialize only the v5.4 continuity members here.
    constructor_pattern = r'''(COFCRuntimeController::COFCRuntimeController\(\)\n\s*:[^\{]+)\{\}'''
    constructor_replacement = r'''\1{
  reacquire_stable_cycles_ = 0;
  recovery_requires_change_ = false;
}'''
    text, count = re.subn(
        constructor_pattern,
        lambda m: m.group(1) + '''{
  reacquire_stable_cycles_ = 0;
  recovery_requires_change_ = false;
}''',
        text,
        count=1,
        flags=re.S)
    if count != 1:
        raise RuntimeError(f"{rel}: constructor patch failed")

    # Add a Hero-transaction-only fingerprint. Opponent animation/timer changes
    # must never be enough to authorize a duplicate Hero drag/Confirm.
    marker = '''bool COFCRuntimeController::IsKnownNewHand(const COFCState &state) const {'''
    if text.count(marker) != 1:
        raise RuntimeError(f"{rel}: IsKnownNewHand marker missing")
    helper = r'''string COFCRuntimeController::StateFingerprint(const COFCState &state) {
  if (!state.valid || state.hero_chair < 0
      || state.hero_chair >= state.player_count) return "INVALID";
  ostringstream out;
  out << IncomingSignature(state)
      << "|R" << state.round_index
      << "|P" << PendingSignature(state)
      << "|HB";
  const COFCPlayerBoard &board = state.players[state.hero_chair].board;
  for (int i = 0; i < kOFCTopCards; ++i)
    if (board.top[i].IsKnownPhysicalCard()) out << board.top[i].value << ',';
  out << '/';
  for (int i = 0; i < kOFCMiddleCards; ++i)
    if (board.middle[i].IsKnownPhysicalCard()) out << board.middle[i].value << ',';
  out << '/';
  for (int i = 0; i < kOFCBottomCards; ++i)
    if (board.bottom[i].IsKnownPhysicalCard()) out << board.bottom[i].value << ',';
  return out.str();
}

'''
    text = text.replace(marker, helper + marker, 1)

    if text.count("    && state.hero_incoming_count == 15;\n") != 1:
        raise RuntimeError(f"{rel}: hardcoded Fantasy15 new-hand condition missing")
    text = text.replace(
        "    && state.hero_incoming_count == 15;\n",
        "    && state.hero_incoming_count >= 14\n"
        "    && state.hero_incoming_count <= 17;\n",
        1)

    reset_old = '''  hand_signature_ = IncomingSignature(state);
  phase_ = kIdle;
'''
    reset_new = '''  hand_signature_ = IncomingSignature(state);
  current_fingerprint_ = StateFingerprint(state);
  recovery_fingerprint_.clear();
  reacquire_stable_cycles_ = 0;
  recovery_requires_change_ = false;
  phase_ = kIdle;
'''
    if text.count(reset_old) != 1:
        raise RuntimeError(f"{rel}: ResetForKnownNewHand tail missing")
    text = text.replace(reset_old, reset_new, 1)

    block_pattern = r'''void COFCRuntimeController::Block\(const string &message\) \{.*?\n\}\n\nbool COFCRuntimeController::SendConfirm'''
    recover_method = r'''void COFCRuntimeController::Recover(const string &message) {
  // OPENOFC_NEVER_TERMINAL_RUNTIME_V54. A runtime fault suppresses only the
  // current unsafe action attempt. The controller immediately becomes a
  // perception/reacquisition consumer; there is no absorbing BLOCKED phase.
  recovery_fingerprint_ = current_fingerprint_;
  recovery_requires_change_ =
    phase_ == kArranging || phase_ == kConfirmSent;
  reacquire_stable_cycles_ = 0;
  orchestrator_.ResetForKnownNewHand();
  fantasy_executor_.Reset();
  plan_.Reset();
  provisional_ = false;
  phase_ = kReacquire;
  write_log(k_always_log_errors,
    "[OpenOFC FAULT] stage=RUNTIME reason=\"%s\" terminal=0 next=REACQUIRE require_hero_state_change=%d continue_scraping=1\n",
    message.c_str(), recovery_requires_change_ ? 1 : 0);
}

bool COFCRuntimeController::SendConfirm'''
    text, count = re.subn(
        block_pattern, lambda _m: recover_method, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{rel}: Block method replacement failed")

    # Rename all controller call sites. Internal orchestrator blocking remains
    # local to that transaction object and is cleared by Recover().
    text = text.replace("Block(", "Recover(")

    confirm_pattern = r'''  CString region = state\.players\[state\.hero_chair\]\.fantasy\n    \? CString\("ofc_fantasy15_confirm_button"\)\n    : CString\("ofc_confirm_button"\);\n  RECT rect;\n  if \(!ReadRegion\(region, &rect\)\) \{\n    Recover\("missing calibrated Confirm button region"\);\n    return false;\n  \}'''
    confirm_replacement = r'''  const bool fantasy = state.players[state.hero_chair].fantasy;
  CString region = fantasy
    ? CString("ofc_fantasy_confirm_button")
    : CString("ofc_confirm_button");
  RECT rect;
  if (!ReadRegion(region, &rect)) {
    // Temporary package-compatibility alias only. Generic FANTASY is the
    // v5.4 runtime concept; a legacy Fantasy15 region name must not decide the
    // game mode or card count.
    if (fantasy
        && ReadRegion(CString("ofc_fantasy15_confirm_button"), &rect)) {
      region = CString("ofc_fantasy15_confirm_button");
      write_log(k_always_log_errors,
        "[OpenOFC DEPRECATION] legacy_region=ofc_fantasy15_confirm_button generic_region=ofc_fantasy_confirm_button continue=1\n");
    } else {
      Recover("missing calibrated Confirm button region");
      return false;
    }
  }'''
    text, count = re.subn(
        confirm_pattern, lambda _m: confirm_replacement,
        text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{rel}: generic Fantasy Confirm patch failed")

    # Fantasy batch Start may already have emitted UI input before reporting a
    # failure. Mark the transaction arranging first so Recover() requires a
    # Hero-state change before any retry of the same semantic state.
    fantasy_start = '''  if (state.players[state.hero_chair].fantasy) {
    bool fantasy_complete = false;
'''
    if text.count(fantasy_start) != 1:
        raise RuntimeError(f"{rel}: Fantasy batch start marker missing")
    text = text.replace(
        fantasy_start,
        '''  if (state.players[state.hero_chair].fantasy) {
    phase_ = kArranging;
    bool fantasy_complete = false;
''',
        1)

    # Track the current Hero semantic state even when the raw observation later
    # becomes invalid; Recover() fingerprints the last valid transaction state.
    invalid_anchor = '''  if (!state.valid || !observation.valid) {
'''
    if text.count(invalid_anchor) < 1:
        raise RuntimeError(f"{rel}: Tick invalid-perception anchor missing")
    # Patch the last occurrence, which is the main Tick guard after all phase
    # patches. Earlier helper guards keep their original semantics.
    idx = text.rfind(invalid_anchor)
    text = (
        text[:idx]
        + '''  if (state.valid) current_fingerprint_ = StateFingerprint(state);
  if (!state.valid || !observation.valid) {
'''
        + text[idx + len(invalid_anchor):]
    )

    blocked_pattern = r'''  if \(phase_ == kReacquire\) \{\n    write_log\(true, "\[DeepOFC TICK\] action=NONE reason=RUNTIME_BLOCKED\\n"\);\n    return;\n  \}'''
    reacquire_block = r'''  if (phase_ == kReacquire) {
    if (!state.valid || !observation.valid) {
      write_log(true,
        "[OpenOFC REACQUIRE] result=WAIT reason=INVALID_PERCEPTION terminal=0 continue_scraping=1\n");
      return;
    }
    const string now = StateFingerprint(state);
    const bool hero_state_changed = now != recovery_fingerprint_;
    if (!hero_state_changed && recovery_requires_change_) {
      write_log(true,
        "[OpenOFC REACQUIRE] result=WAIT reason=SAME_HERO_TRANSACTION_STATE terminal=0 duplicate_input_suppressed=1\n");
      return;
    }
    if (!hero_state_changed) {
      ++reacquire_stable_cycles_;
      if (reacquire_stable_cycles_ < 2) {
        write_log(true,
          "[OpenOFC REACQUIRE] result=WAIT stable=%d/2 reason=SAFE_RETRY_DEBOUNCE terminal=0\n",
          reacquire_stable_cycles_);
        return;
      }
    }

    orchestrator_.ResetForKnownNewHand();
    fantasy_executor_.Reset();
    plan_.Reset();
    confirm_before_.Reset();
    provisional_ = false;
    phase_ = kIdle;
    recovery_fingerprint_.clear();
    reacquire_stable_cycles_ = 0;
    recovery_requires_change_ = false;
    write_log(k_always_log_errors,
      "[OpenOFC REACQUIRE_ACCEPT] source=RUNTIME_CONTROLLER hero_state_changed=%d next=IDLE terminal=0\n",
      hero_state_changed ? 1 : 0);
  }'''
    text, count = re.subn(
        blocked_pattern, lambda _m: reacquire_block,
        text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{rel}: RUNTIME_BLOCKED Tick branch replacement failed")

    # The legacy word is a hard CI sentinel in this file: no future patch may
    # silently restore the absorbing controller phase.
    if "kBlocked" in text or "AUTOMATION BLOCKED until a known new hand" in text:
        raise RuntimeError(f"{rel}: absorbing runtime block survived v5.4 patch")

    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_contract_version():
    rel = "OpenHoldem/CHeartbeatThread.cpp"
    path, text, eol, bom = read_source(rel)
    matches = re.findall(r"const int kOpenOFCContractVersion = (\d+);", text)
    if len(matches) != 1:
        raise RuntimeError(f"{rel}: contract version declaration not unique: {matches}")
    # v5.3 chain reaches contract 4; v5.4 continuity is a breaking runtime/TM
    # contract even though the temporary v5.3 tablemap is still used only for CI.
    text = re.sub(
        r"const int kOpenOFCContractVersion = \d+;",
        "const int kOpenOFCContractVersion = 5;",
        text,
        count=1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def source_contract_assertions():
    checks = {
        "OpenHoldem/COFCRuntimeController.cpp": [
            "OPENOFC_NEVER_TERMINAL_RUNTIME_V54",
            "[OpenOFC REACQUIRE_ACCEPT]",
            "ofc_fantasy_confirm_button",
            "state.hero_incoming_count >= 14",
            "state.hero_incoming_count <= 17",
        ],
        "OpenHoldem/CLazyScraper.cpp": [
            "OPENOFC_REACQUIRE_DEBOUNCE_V54",
            "COFCReconstructor::ReconstructCurrentScreen",
            "[OpenOFC REACQUIRE_CANDIDATE]",
            "[OpenOFC REACQUIRE_REJECT]",
            "terminal=0",
        ],
        "OpenHoldem/COFCReconstructor.cpp": [
            "COFCReconstructor::ReconstructCurrentScreen",
            "partially arranged",
            "expected all 3 current cards loose",
        ],
    }
    for rel, needles in checks.items():
        _path, text, _eol, _bom = read_source(rel)
        for needle in needles:
            if needle not in text:
                raise RuntimeError(f"{rel}: v5.4 contract marker missing: {needle}")
    _path, runtime, _eol, _bom = read_source("OpenHoldem/COFCRuntimeController.cpp")
    _path, header, _eol, _bom = read_source("OpenHoldem/COFCRuntimeController.h")
    if "kBlocked" in runtime or "kBlocked" in header:
        raise RuntimeError("absorbing kBlocked controller phase remains")
    print("OpenOFC v5.4 source continuity contract assertions passed")


def main():
    patch_current_screen_reconstructor()
    patch_lazy_scraper_reacquisition()
    patch_runtime_controller_recovery()
    patch_contract_version()
    source_contract_assertions()
    print("OpenOFC v5.4 runtime continuity patch applied successfully")


if __name__ == "__main__":
    main()
