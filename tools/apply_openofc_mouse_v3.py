from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(rel: str):
    p = ROOT / rel
    raw = p.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    return p, text, eol, bom


def save(p: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    p.write_bytes(data)


def replace_one(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f"{label}: expected 1 target, got {n}")
    return text.replace(old, new, 1)


def patch_casino():
    rel = "OpenHoldem/CCasinoInterface.cpp"
    p, s, eol, bom = load(rel)
    a = s.find("// OpenOFC focus handoff.\n")
    b = s.find("CCasinoInterface::CCasinoInterface()", a)
    if a < 0 or b <= a:
        raise RuntimeError("casino: focus helper not found")
    s = s[:a] + s[b:]

    gate_start = s.find("  // A click on the OpenOFC toolbar is a benign focus transition.")
    call_anchor = s.find("  write_log(true,\n    \"[DeepOFC R10] physical drag", gate_start)
    if gate_start < 0 or call_anchor <= gate_start:
        raise RuntimeError("casino: drag focus gate not found")
    # Keep the existing physical-drag log/call but replace the gate with legacy arbitration telemetry.
    prefix = '''  // OPENOFC_LEGACY_MOUSE_ARBITRATION: preserve normal OpenHoldem mouse
  // arbitration. The mouse DLL moves the cursor and activates its target;
  // OFC does not require the table to already own foreground focus.
  POINT cursor_before = {0};
  POINT cursor_after = {0};
  const bool have_before = GetCursorPos(&cursor_before) != FALSE;
'''
    s = s[:gate_start] + prefix + s[call_anchor:]

    old_call = '''  const bool ok = (theApp._dll_mouse_drag_between)(
    hwnd, source_rect, target_rect, duration_ms) != 0;
'''
    new_call = '''  const bool ok = (theApp._dll_mouse_drag_between)(
    hwnd, source_rect, target_rect, duration_ms) != 0;
  const bool have_after = GetCursorPos(&cursor_after) != FALSE;
  write_log(true,
    "[OpenOFC MOUSE] arbitration=LEGACY before=(%ld,%ld) after=(%ld,%ld) dll_result=%d sampled=%d/%d\\n",
    cursor_before.x, cursor_before.y, cursor_after.x, cursor_after.y,
    ok ? 1 : 0, have_before ? 1 : 0, have_after ? 1 : 0);
'''
    s = replace_one(s, old_call, new_call, "casino drag call")

    click_gate = '''  if (GetForegroundWindow() != hwnd
      && !OpenOFCEnsureAttachedTableForeground(hwnd)) {
    TableLostFocus();
    write_log(k_always_log_errors,
      "[DeepOFC FP0] Refusing Confirm because attached table focus could not be recovered safely\\n");
    return false;
  }
'''
    s = replace_one(s, click_gate, "", "casino confirm focus gate")
    save(p, s, eol, bom)
    print("patched", rel)


def patch_mouse():
    rel = "Reference Mouse DLL/mousedll.cpp"
    p, s, eol, bom = load(rel)
    a = s.find("MOUSEDLL_API int MouseDragBetweenRects(")
    b = s.find("\nMOUSEDLL_API void ProcessMessage", a)
    if a < 0 or b <= a:
        raise RuntimeError("mouse: function boundary not found")
    fn = r'''MOUSEDLL_API int MouseDragBetweenRects(const HWND hwnd, const RECT source_rect,
                                       const RECT target_rect, const int duration_ms) {
    // OPENOFC_LEGACY_DRAG_ARBITRATION: arbitrary-card drag follows the same
    // arbitration used by the proven MouseClickDrag path.
    if (hwnd == NULL || !IsUsableRect(source_rect) || !IsUsableRect(target_rect)) {
        return (int)false;
    }
    POINT start = RandomizeInteriorLocation(source_rect);
    POINT end = RandomizeInteriorLocation(target_rect);
    if (!ClientToScreen(hwnd, &start) || !ClientToScreen(hwnd, &end)) {
        return (int)false;
    }
    const double screen_width = ::GetSystemMetrics(SM_CXSCREEN) - 1;
    const double screen_height = ::GetSystemMetrics(SM_CYSCREEN) - 1;
    if (screen_width <= 0 || screen_height <= 0) return (int)false;

    POINT current;
    if (!GetCursorPos(&current)) return (int)false;
    MoveMouseHuman(current, start, 200 + rand() % 100);

    SetFocus(hwnd);
    SetForegroundWindow(hwnd);
    SetActiveWindow(hwnd);

    const LONG start_x = (LONG)(start.x * (65535.0 / screen_width));
    const LONG start_y = (LONG)(start.y * (65535.0 / screen_height));
    const LONG end_x = (LONG)(end.x * (65535.0 / screen_width));
    const LONG end_y = (LONG)(end.y * (65535.0 / screen_height));

    INPUT down;
    ZeroMemory(&down, sizeof(INPUT));
    down.type = INPUT_MOUSE;
    down.mi.dx = start_x;
    down.mi.dy = start_y;
    down.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN;
    if (SendInput(1, &down, sizeof(INPUT)) != 1) return (int)false;

    Sleep(30 + rand() % 31);
    int held_duration = duration_ms;
    if (held_duration <= 0) held_duration = 350;
    if (held_duration < 100) held_duration = 100;
    if (held_duration > 1500) held_duration = 1500;
    MoveMouseHuman(start, end, held_duration);

    INPUT move;
    ZeroMemory(&move, sizeof(INPUT));
    move.type = INPUT_MOUSE;
    move.mi.dx = end_x;
    move.mi.dy = end_y;
    move.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE;
    const bool move_ok = (SendInput(1, &move, sizeof(INPUT)) == 1);

    INPUT up;
    ZeroMemory(&up, sizeof(INPUT));
    up.type = INPUT_MOUSE;
    up.mi.dx = end_x;
    up.mi.dy = end_y;
    up.mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP;
    const bool up_ok = (SendInput(1, &up, sizeof(INPUT)) == 1);
    return (int)(move_ok && up_ok);
}
'''
    s = s[:a] + fn + s[b:]
    save(p, s, eol, bom)
    print("patched", rel)


def patch_runtime():
    relh = "OpenHoldem/COFCRuntimeController.h"
    p, s, eol, bom = load(relh)
    s = replace_one(s,
        "  int pending_before_drag_;\n  std::string pending_signature_before_drag_;\n  std::string hand_signature_;\n",
        "  int pending_before_drag_;\n  std::string pending_signature_before_drag_;\n  int drag_wait_cycles_;\n  int drag_retry_count_;\n  std::string hand_signature_;\n",
        "runtime header fields")
    save(p, s, eol, bom)
    print("patched", relh)

    rel = "OpenHoldem/COFCRuntimeController.cpp"
    p, s, eol, bom = load(rel)
    s = replace_one(s,
        "COFCRuntimeController::COFCRuntimeController()\n    : phase_(kIdle), pending_before_drag_(0) {}\n",
        "COFCRuntimeController::COFCRuntimeController()\n    : phase_(kIdle), pending_before_drag_(0), drag_wait_cycles_(0),\n      drag_retry_count_(0) {}\n",
        "runtime ctor")
    s = replace_one(s,
        "  pending_before_drag_ = 0;\n  pending_signature_before_drag_.clear();\n  hand_signature_ = IncomingSignature(state);\n",
        "  pending_before_drag_ = 0;\n  pending_signature_before_drag_.clear();\n  drag_wait_cycles_ = 0;\n  drag_retry_count_ = 0;\n  hand_signature_ = IncomingSignature(state);\n",
        "runtime new-hand reset")
    s = replace_one(s,
        "  pending_before_drag_ = PendingCount(state);\n  pending_signature_before_drag_ = PendingSignature(state);\n  if (!orchestrator_.StartTurn(\n",
        "  pending_before_drag_ = PendingCount(state);\n  pending_signature_before_drag_ = PendingSignature(state);\n  drag_wait_cycles_ = 0;\n  if (!orchestrator_.StartTurn(\n",
        "runtime decision start")

    a = s.find("  if (orchestrator_.awaiting_drag_verification()")
    b = s.find("  bool complete = false;", a)
    if a < 0 or b <= a:
        raise RuntimeError("runtime wait block boundary not found")
    wait = '''  if (orchestrator_.awaiting_drag_verification()
      && PendingSignature(state) == pending_signature_before_drag_) {
    ++drag_wait_cycles_;
    const int kOpenOFCDragObservationWaitCycles = 8;
    write_log(true,
      "[DeepOFC WAIT] drag not visible yet pending_signature=\\\"%s\\\" wait=%d/%d retry=%d\\n",
      pending_signature_before_drag_.c_str(), drag_wait_cycles_,
      kOpenOFCDragObservationWaitCycles, drag_retry_count_);
    if (drag_wait_cycles_ < kOpenOFCDragObservationWaitCycles) return true;

    // OPENOFC_DRAG_RETRY: API success is not proof that the simulator accepted
    // the gesture. Retry the exact fixed strategic action once, then fail with
    // a bounded durable reason instead of hanging indefinitely.
    if (drag_retry_count_ < 1) {
      ++drag_retry_count_;
      drag_wait_cycles_ = 0;
      write_log(k_always_log_errors,
        "[OpenOFC DRAG RETRY] reason=NOT_OBSERVED attempt=%d pending_signature=\\\"%s\\\"\\n",
        drag_retry_count_ + 1, pending_signature_before_drag_.c_str());
      orchestrator_.ResetForKnownNewHand();
      plan_.Reset();
      phase_ = kIdle;
      return StartDecision(state, observation);
    }
    Block("DRAG_NOT_OBSERVED_AFTER_RETRY");
    return false;
  }
'''
    s = s[:a] + wait + s[b:]
    s = replace_one(s,
        "  pending_before_drag_ = current_pending;\n  pending_signature_before_drag_ = PendingSignature(state);\n  if (complete && ready) return SendConfirm(state);\n",
        "  pending_before_drag_ = current_pending;\n  pending_signature_before_drag_ = PendingSignature(state);\n  drag_wait_cycles_ = 0;\n  drag_retry_count_ = 0;\n  if (complete && ready) return SendConfirm(state);\n",
        "runtime verified progress")
    save(p, s, eol, bom)
    print("patched", rel)


def patch_view():
    rel = "OpenHoldem/OpenHoldemView.cpp"
    p, s, eol, bom = load(rel)
    old = '''    line.Format("PERCEPTION  READ=%s  STATE=%s", read_text, state_text);
    if (state != NULL && state->valid) {
      CString action = state->action_required ? "HERO ACTION" : "WAIT";
      line.AppendFormat("  |  Round %d/5  |  H%d A%d D%d  |  %s",
        state->round_index + 1, state->hero_chair, state->acting_chair,
        state->dealer_chair, action.GetString());
    }
    view += line + "\\r\\n\\r\\n";
'''
    new = '''    line.Format("PERCEPTION  READ=%s  STATE=%s\\r\\n", read_text, state_text);
    view += line;
    if (state != NULL && state->valid) {
      line.Format("ROUND %d/5  |  HERO=P%d  |  ACTOR=P%d  |  DEALER=P%d\\r\\n",
        state->round_index + 1, state->hero_chair, state->acting_chair,
        state->dealer_chair);
      view += line;
      line.Format("ACTION=%s  |  prepare=%d  |  confirm=%d\\r\\n\\r\\n",
        state->action_required ? "HERO" : "WAIT",
        state->hero_can_prepare ? 1 : 0, state->hero_can_confirm ? 1 : 0);
      view += line;
    } else {
      view += "\\r\\n";
    }
'''
    s = replace_one(s, old, new, "OpenOFC multiline view")
    save(p, s, eol, bom)
    print("patched", rel)


def patch_ci():
    rel = ".github/workflows/deepofc-fp0-playable-fantasy15.yml"
    p, s, eol, bom = load(rel)
    if "OPENOFC_LEGACY_MOUSE_ARBITRATION" in s:
        print("CI assertions already present")
        return
    anchor = "          $autoplayer = Get-Content -Raw 'OpenHoldem/CAutoplayer.cpp'\n"
    if anchor not in s:
        raise RuntimeError("CI insertion anchor not found")
    block = r'''          # OFC physical input preserves legacy OpenHoldem mouse arbitration.
          $casino = Get-Content -Raw 'OpenHoldem/CCasinoInterface.cpp'
          $mouse = Get-Content -Raw 'Reference Mouse DLL/mousedll.cpp'
          $view = Get-Content -Raw 'OpenHoldem/OpenHoldemView.cpp'
          if (($casino -notmatch 'OPENOFC_LEGACY_MOUSE_ARBITRATION') -or
              ($casino -match 'OpenOFCEnsureAttachedTableForeground') -or
              ($casino -match 'Refusing drag because attached table focus')) {
            throw 'OpenOFC still imposes a non-legacy foreground hard gate'
          }
          $dragStart = $mouse.IndexOf('MOUSEDLL_API int MouseDragBetweenRects')
          $dragEnd = $mouse.IndexOf('MOUSEDLL_API void ProcessMessage', $dragStart)
          if (($dragStart -lt 0) -or ($dragEnd -le $dragStart)) {
            throw 'Could not isolate MouseDragBetweenRects'
          }
          $dragBody = $mouse.Substring($dragStart, $dragEnd - $dragStart)
          if (($dragBody -notmatch 'OPENOFC_LEGACY_DRAG_ARBITRATION') -or
              ($dragBody -notmatch 'MoveMouseHuman\(start, end, held_duration\)') -or
              ($dragBody -match 'MoveMouseHeldButton')) {
            throw 'OpenOFC arbitrary drag is not using legacy mouse arbitration'
          }
          if (($runtime -notmatch 'OPENOFC_DRAG_RETRY') -or
              ($runtime -notmatch 'DRAG_NOT_OBSERVED_AFTER_RETRY')) {
            throw 'OpenOFC bounded unobserved-drag retry contract is missing'
          }
          if (($view -notmatch 'ROUND %d/5') -or ($view -notmatch 'ACTION=%s')) {
            throw 'OpenOFC main-view state remains vulnerable to clipping'
          }

'''
    s = s.replace(anchor, block + anchor, 1)
    save(p, s, eol, bom)
    print("patched", rel)


def main():
    patch_casino()
    patch_mouse()
    patch_runtime()
    patch_view()
    patch_ci()
    print("OpenOFC mouse v3 repair applied successfully")


if __name__ == "__main__":
    main()
