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


def patch_header():
    rel = "OpenHoldem/COFCRuntimeController.h"
    path, text, eol, bom = read_source(rel)
    if "kBlocked" in text:
        raise RuntimeError("v5.4.3H requires non-absorbing v5.4.3 runtime")
    if "recovery_requires_change_" not in text or "fantasy_executor_" not in text:
        raise RuntimeError("v5.4.3H requires materialized v5.4/v5 Fantasy runtime")

    include_anchor = '#include "COFCConfirmVerifier.h"\n'
    if text.count(include_anchor) != 1:
        raise RuntimeError("runtime ConfirmVerifier include anchor missing")
    text = text.replace(
        include_anchor,
        include_anchor + '#include "COFCFantasyConfirmFence.h"\n',
        1)

    marker = "  bool recovery_requires_change_;\n"
    if text.count(marker) != 1:
        raise RuntimeError("runtime recovery member anchor missing")
    text = text.replace(
        marker,
        marker
        + "  // OPENOFC_FANTASY_CONFIRM_FENCE_V543H. The pure fence is armed only\\n"
          "  // after ClickRectSafely has actually invoked the mouse DLL. Recovery\\n"
          "  // never clears it; only a known new hand resets the transaction fence.\\n"
          "  COFCFantasyConfirmFence fantasy_confirm_fence_;\\n".replace("\\n", "\n"),
        1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_cpp():
    rel = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_source(rel)
    executor = (ROOT / "OpenHoldem" / "COFCFantasyBatchExecutor.cpp").read_text(
        encoding="utf-8-sig")
    if "OPENOFC_FANTASY_SOURCE_IDENTITY_V543G" not in executor:
        raise RuntimeError("v5.4.3H must be applied after v5.4.3G")

    include_anchor = '#include "COFCBaselinePolicy.h"\n'
    if text.count(include_anchor) != 1:
        raise RuntimeError("runtime include anchor missing")
    text = text.replace(
        include_anchor,
        include_anchor + '#include "COFCFantasyConfirmGuard.h"\n',
        1)

    # Reset the fence only on an independently recognized new hand. Recover()
    # deliberately preserves it after a dispatched-but-unacknowledged Confirm.
    reset_anchor = "  confirm_before_.Reset();\n"
    start = text.find("void COFCRuntimeController::ResetForKnownNewHand(")
    end = text.find("\n}\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("ResetForKnownNewHand method not found")
    block = text[start:end + 3]
    if block.count(reset_anchor) != 1:
        raise RuntimeError("ResetForKnownNewHand confirm reset anchor not unique")
    block = block.replace(
        reset_anchor,
        reset_anchor + "  fantasy_confirm_fence_.ResetForNewHand();\n",
        1)
    text = text[:start] + block + text[end + 3:]

    sig = "bool COFCRuntimeController::SendConfirm(const COFCState &state) {\n"
    if text.count(sig) != 1:
        raise RuntimeError("SendConfirm signature not unique")
    guard = r'''bool COFCRuntimeController::SendConfirm(const COFCState &state) {
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
    text = text.replace(sig, guard, 1)

    refusal_old = '''  if (p_casino_interface == NULL || !p_casino_interface->ClickRectSafely(rect)) {
    Recover("safe Confirm click was refused after transaction start");
    return false;
  }
  confirm_before_ = state;
'''
    refusal_new = '''  if (p_casino_interface == NULL || !p_casino_interface->ClickRectSafely(rect)) {
    Recover("safe Confirm click was refused before mouse dispatch");
    // ClickRectSafely returns false only before invoking the mouse DLL. A fresh
    // stable replan may therefore retry without creating a duplicate click.
    if (fantasy_confirm) recovery_requires_change_ = false;
    return false;
  }
  if (fantasy_confirm) {
    // The mouse DLL has now been invoked. From this point onward the same Hero
    // transaction fingerprint is fenced even if acknowledgement never arrives.
    fantasy_confirm_fence_.MarkDispatched(confirm_fingerprint);
    write_log(true,
      "[OpenOFC FANTASY CONFIRM] physical_dispatch=1 fingerprint=%s fence=ARMED\n",
      confirm_fingerprint.c_str());
  }
  confirm_before_ = state;
'''
    if text.count(refusal_old) != 1:
        raise RuntimeError("SendConfirm dispatch/refusal block shape changed")
    text = text.replace(refusal_old, refusal_new, 1)

    same_old = '''  // Never resend Confirm. A still-identical actionable state is simply a wait.
  if (state.round_index == confirm_before_.round_index
      && state.acting_chair == state.hero_chair
      && state.hero_can_confirm) return true;
'''
    same_new = '''  // Never resend Confirm. For Fantasy, bound the acknowledgement wait so the
  // controller cannot retain stale executor/plan state forever. Timeout enters
  // reacquisition while the pure dispatch fence remains armed; physical retry
  // on the same Hero transaction is still forbidden.
  if (state.round_index == confirm_before_.round_index
      && state.acting_chair == state.hero_chair
      && state.hero_can_confirm) {
    const bool fantasy_wait = confirm_before_.valid
      && confirm_before_.hero_chair >= 0
      && confirm_before_.hero_chair < confirm_before_.player_count
      && confirm_before_.players[confirm_before_.hero_chair].fantasy;
    if (!fantasy_wait) return true;
    const int kFantasyConfirmAckWaitCycles = 20;
    const COFCFantasyConfirmFence::AckDecision decision =
      fantasy_confirm_fence_.ObserveUnchangedAfterDispatch(
        kFantasyConfirmAckWaitCycles);
    if (decision == COFCFantasyConfirmFence::kAckWait) {
      write_log(true,
        "[OpenOFC FANTASY CONFIRM] ack=WAIT cycle=%d/%d duplicate_input_suppressed=1\n",
        fantasy_confirm_fence_.ack_wait_cycles(), kFantasyConfirmAckWaitCycles);
      return true;
    }
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY CONFIRM] ack=TIMEOUT physical_retry=0 next=REACQUIRE fence=PRESERVED\n");
    Recover("Fantasy Confirm acknowledgement not observed; physical retry forbidden");
    return true;
  }
  fantasy_confirm_fence_.ObserveChangedState();
'''
    if text.count(same_old) != 1:
        raise RuntimeError("HandlePostConfirm unchanged-state block shape changed")
    text = text.replace(same_old, same_new, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def source_contract():
    runtime = (ROOT / "OpenHoldem" / "COFCRuntimeController.cpp").read_text(
        encoding="utf-8-sig")
    header = (ROOT / "OpenHoldem" / "COFCRuntimeController.h").read_text(
        encoding="utf-8-sig")
    required_runtime = [
        "COFCFantasyConfirmGuard::Validate",
        "fantasy_confirm_fence_.CanDispatch",
        "fantasy_confirm_fence_.MarkDispatched",
        "ObserveUnchangedAfterDispatch",
        "physical_dispatch=1",
        "duplicate_input_suppressed=1",
        "ack=TIMEOUT",
        "physical retry forbidden",
    ]
    missing = [x for x in required_runtime if x not in runtime]
    if missing:
        raise RuntimeError(f"v5.4.3H runtime markers missing: {missing}")
    if "COFCFantasyConfirmFence fantasy_confirm_fence_" not in header:
        raise RuntimeError("v5.4.3H pure confirm fence member missing")
    if "kBlocked" in runtime or "kBlocked" in header:
        raise RuntimeError("absorbing runtime state survived v5.4.3H")
    print("OpenOFC v5.4.3H Fantasy Confirm source contract passed")


def main():
    patch_header()
    patch_cpp()
    source_contract()
    print("OpenOFC v5.4.3H Fantasy Confirm hardening applied successfully")


if __name__ == "__main__":
    main()
