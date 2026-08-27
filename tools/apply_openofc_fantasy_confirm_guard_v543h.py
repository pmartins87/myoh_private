from __future__ import annotations

from pathlib import Path

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


def replace_once_text(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one target, got {count}: {old[:160]!r}")
    return text.replace(old, new, 1)


def patch_header():
    rel = "OpenHoldem/COFCRuntimeController.h"
    path, text, eol, bom = read_source(rel)
    if "kBlocked" in text:
        raise RuntimeError("v5.4.3H requires non-absorbing v5.4.3 runtime")
    if "recovery_requires_change_" not in text or "fantasy_executor_" not in text:
        raise RuntimeError("v5.4.3H requires materialized v5.4/v5 Fantasy runtime")

    include_anchor = '#include "COFCConfirmVerifier.h"\n'
    text = replace_once_text(
        text,
        include_anchor,
        include_anchor + '#include "COFCFantasyConfirmFence.h"\n',
        rel + " include")

    marker = "  bool recovery_requires_change_;\n"
    text = replace_once_text(
        text,
        marker,
        marker
        + "  // OPENOFC_FANTASY_CONFIRM_FENCE_V543H. The pure fence is armed only\n"
          "  // after ClickRectSafely has actually invoked the mouse DLL. Recovery\n"
          "  // never clears it; only a known new hand resets the transaction fence.\n"
          "  COFCFantasyConfirmFence fantasy_confirm_fence_;\n",
        rel + " recovery member")
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_cpp():
    rel = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_source(rel)
    executor = (ROOT / "OpenHoldem" / "COFCFantasyBatchExecutor.cpp").read_text(
        encoding="utf-8-sig")
    if "OPENOFC_FANTASY_SOURCE_IDENTITY_V543G" not in executor:
        raise RuntimeError("v5.4.3H must be applied after v5.4.3G")
    if "OPENOFC_PHASE_ENGINE_V4" not in text:
        raise RuntimeError("v5.4.3H requires the materialized v4 phase engine")

    include_anchor = '#include "COFCBaselinePolicy.h"\n'
    text = replace_once_text(
        text,
        include_anchor,
        include_anchor + '#include "COFCFantasyConfirmGuard.h"\n',
        rel + " include")

    start = text.find("void COFCRuntimeController::ResetForKnownNewHand(")
    end = text.find("\n}\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("ResetForKnownNewHand method not found")
    block = text[start:end + 3]
    block = replace_once_text(
        block,
        "  confirm_before_.Reset();\n",
        "  confirm_before_.Reset();\n  fantasy_confirm_fence_.ResetForNewHand();\n",
        "ResetForKnownNewHand confirm reset")
    text = text[:start] + block + text[end + 3:]

    sig = "bool COFCRuntimeController::SendConfirm(const COFCState &state) {\n"
    if text.count(sig) != 1:
        raise RuntimeError("SendConfirm signature not unique")
    prefix = r'''bool COFCRuntimeController::SendConfirm(const COFCState &state) {
  // OPENOFC_FANTASY_CONFIRM_GUARD_V543H
  const bool fantasy_confirm = state.valid
    && state.hero_chair >= 0 && state.hero_chair < state.player_count
    && state.players[state.hero_chair].fantasy;
  const string confirm_fingerprint = fantasy_confirm
    ? StateFingerprint(state) : string();

  if (fantasy_confirm) {
    string confirm_guard_error;
    if (!COFCFantasyConfirmGuard::Validate(state, plan_, &confirm_guard_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY CONFIRM] guard=REJECT reason=\"%s\" physical_dispatch=0\n",
        confirm_guard_error.c_str());
      Recover("Fantasy Confirm guard rejected: " + confirm_guard_error);
      return false;
    }
    if (!fantasy_confirm_fence_.CanDispatch(confirm_fingerprint)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY CONFIRM] duplicate_input_suppressed=1 physical_dispatch=0 fingerprint=%s\n",
        confirm_fingerprint.c_str());
      recovery_fingerprint_ = confirm_fingerprint;
      recovery_requires_change_ = true;
      reacquire_stable_cycles_ = 0;
      phase_ = kReacquire;
      return true;
    }
  }
'''
    text = text.replace(sig, prefix, 1)

    refusal_old = '''  if (p_casino_interface == NULL || !p_casino_interface->ClickRectSafely(rect)) {
    Recover("safe Confirm click was refused after transaction start");
    return false;
  }
  confirm_before_ = state;
'''
    refusal_new = r'''  if (p_casino_interface == NULL || !p_casino_interface->ClickRectSafely(rect)) {
    Recover("safe Confirm click was refused before mouse dispatch");
    // ClickRectSafely returns false only before invoking the mouse DLL. A fresh
    // stable replan may therefore retry without creating a duplicate click.
    if (fantasy_confirm) recovery_requires_change_ = false;
    return false;
  }
  if (fantasy_confirm) {
    // The mouse DLL has now been invoked. From this point onward no second
    // physical Confirm is allowed in this Fantasy hand.
    fantasy_confirm_fence_.MarkDispatched(confirm_fingerprint);
    // Keep the acknowledgement-stability baseline explicit. The regular Tick
    // current_fingerprint_ update occurs after the kConfirmSent branch, so the
    // dispatch boundary must seed it here.
    current_fingerprint_ = confirm_fingerprint;
    write_log(true,
      "[OpenOFC FANTASY CONFIRM] physical_dispatch=1 fingerprint=%s fence=ARMED\n",
      confirm_fingerprint.c_str());
  }
  confirm_before_ = state;
'''
    text = replace_once_text(
        text, refusal_old, refusal_new, "SendConfirm dispatch/refusal block")

    wait_old = '''  if (phase_ == kConfirmSent) {
    if (confirm_before_.players[confirm_before_.hero_chair].fantasy
        || confirm_before_.round_index == 4) {
      if (state.valid && observation.valid && IsKnownNewHand(state)) {
        ResetForKnownNewHand(state);
      } else {
        write_log(true,
          "[OpenOFC FLOW] phase=WAIT_RESULT animation_or_result_pending=1 raw_valid=%d state_valid=%d\\n",
          observation.valid ? 1 : 0, state.valid ? 1 : 0);
        return;
      }
    } else {
'''
    wait_new = '''  if (phase_ == kConfirmSent) {
    const bool confirm_was_fantasy =
      confirm_before_.valid
      && confirm_before_.hero_chair >= 0
      && confirm_before_.hero_chair < confirm_before_.player_count
      && confirm_before_.players[confirm_before_.hero_chair].fantasy;
    if (confirm_was_fantasy || confirm_before_.round_index == 4) {
      if (state.valid && observation.valid && IsKnownNewHand(state)) {
        ResetForKnownNewHand(state);
      } else {
        if (confirm_was_fantasy && fantasy_confirm_fence_.HasAnyDispatch()) {
          bool count_wait = !state.valid || !observation.valid;
          if (state.valid && observation.valid) {
            const string now = StateFingerprint(state);
            if (now != current_fingerprint_) {
              current_fingerprint_ = now;
              fantasy_confirm_fence_.ObserveChangedState();
              count_wait = false;
              write_log(true,
                "[OpenOFC FANTASY CONFIRM] ack=STATE_CHANGED baseline=UPDATED physical_retry=0 fence=PRESERVED\\n");
            } else {
              count_wait = true;
            }
          }
          if (count_wait) {
            const int kFantasyConfirmAckWaitCycles = 20;
            const COFCFantasyConfirmFence::AckDecision decision =
              fantasy_confirm_fence_.ObserveUnchangedAfterDispatch(
                kFantasyConfirmAckWaitCycles);
            if (decision == COFCFantasyConfirmFence::kAckWait) {
              write_log(true,
                "[OpenOFC FANTASY CONFIRM] ack=WAIT cycle=%d/%d duplicate_input_suppressed=1\\n",
                fantasy_confirm_fence_.ack_wait_cycles(),
                kFantasyConfirmAckWaitCycles);
            } else {
              write_log(k_always_log_errors,
                "[OpenOFC FANTASY CONFIRM] ack=TIMEOUT physical_retry=0 next=REACQUIRE fence=PRESERVED\\n");
              Recover("Fantasy Confirm acknowledgement not observed; physical retry forbidden");
              return;
            }
          }
        }
        write_log(true,
          "[OpenOFC FLOW] phase=WAIT_RESULT animation_or_result_pending=1 raw_valid=%d state_valid=%d\\n",
          observation.valid ? 1 : 0, state.valid ? 1 : 0);
        return;
      }
    } else {
'''
    text = replace_once_text(
        text, wait_old, wait_new, "Tick Fantasy kConfirmSent wait-result branch")

    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def source_contract():
    runtime = (ROOT / "OpenHoldem" / "COFCRuntimeController.cpp").read_text(
        encoding="utf-8-sig")
    header = (ROOT / "OpenHoldem" / "COFCRuntimeController.h").read_text(
        encoding="utf-8-sig")
    required_runtime = [
        "OPENOFC_FANTASY_CONFIRM_GUARD_V543H",
        "COFCFantasyConfirmGuard::Validate",
        "fantasy_confirm_fence_.CanDispatch",
        "fantasy_confirm_fence_.MarkDispatched",
        "fantasy_confirm_fence_.HasAnyDispatch",
        "ObserveUnchangedAfterDispatch",
        "confirm_was_fantasy",
        "baseline=UPDATED",
        "current_fingerprint_ = confirm_fingerprint",
        "physical_dispatch=1",
        "duplicate_input_suppressed=1",
        "ack=TIMEOUT",
        "physical retry forbidden",
    ]
    missing = [x for x in required_runtime if x not in runtime]
    if missing:
        raise RuntimeError(f"v5.4.3H runtime markers missing: {missing}")
    if "COFCFantasyConfirmFence fantasy_confirm_fence_" not in header:
        raise RuntimeError("v5.4.3H pure Confirm fence member missing")
    if "kBlocked" in runtime or "kBlocked" in header:
        raise RuntimeError("absorbing runtime state survived v5.4.3H")
    print("OpenOFC v5.4.3H Fantasy Confirm source contract passed")


def main():
    patch_header()
    patch_cpp()
    source_contract()
    print("OpenOFC v5.4.3H Fantasy Confirm hardening applied successfully")
    # v5.4.4 uses source-shape-sensitive assertions. Normalize the upgrader
    # after frozen v5.4.3H semantics are materialized and before field recovery.
    from apply_openofc_field_recovery_v544a import main as normalize_v544_state
    normalize_v544_state()
    from apply_openofc_field_recovery_v544aa import main as harden_v544_tick
    harden_v544_tick()


if __name__ == "__main__":
    main()
