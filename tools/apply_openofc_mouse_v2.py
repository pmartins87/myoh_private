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


def replace_once(rel: str, old: str, new: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{rel}: expected exactly one replacement target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_casino_interface():
    rel = "OpenHoldem/CCasinoInterface.cpp"
    path, text, eol, bom = read_source(rel)

    helper_start = text.find("// OpenOFC focus handoff.\n")
    helper_end = text.find("CCasinoInterface::CCasinoInterface()", helper_start)
    if helper_start < 0 or helper_end <= helper_start:
        raise RuntimeError("OpenOFC focus helper not found")
    text = text[:helper_start] + text[helper_end:]

    old_drag_gate = '''  // A click on the OpenOFC toolbar is a benign focus transition. Hand the
  // foreground back to the attached simulator only when OpenOFC itself owns
  // the foreground; unrelated applications remain a hard stop.
  if (GetForegroundWindow() != hwnd
      && !OpenOFCEnsureAttachedTableForeground(hwnd)) {
    TableLostFocus();  // durable diagnostic with both window titles
    write_log(k_always_log_errors,
      "[DeepOFC R10] Refusing drag because attached table focus could not be recovered safely\\n");
    return false;
  }

  write_log(true,
    "[DeepOFC R10] physical drag src=%d,%d,%d,%d dst=%d,%d,%d,%d duration=%d\\n",
    source_rect.left, source_rect.top, source_rect.right, source_rect.bottom,
    target_rect.left, target_rect.top, target_rect.right, target_rect.bottom, duration_ms);
  const bool ok = (theApp._dll_mouse_drag_between)(
    hwnd, source_rect, target_rect, duration_ms) != 0;
'''
    new_drag_gate = '''  // OPENOFC_LEGACY_MOUSE_ARBITRATION: preserve the normal OpenHoldem mouse
  // model. The mouse DLL itself moves the cursor and activates the target
  // window; OFC must not require the table to already own foreground focus.
  // This keeps multi-table/manual-input coexistence aligned with legacy OH.
  POINT cursor_before = {0};
  POINT cursor_after = {0};
  const bool have_before = GetCursorPos(&cursor_before) != FALSE;
  write_log(true,
    "[DeepOFC R10] physical drag src=%d,%d,%d,%d dst=%d,%d,%d,%d duration=%d arbitration=LEGACY\\n",
    source_rect.left, source_rect.top, source_rect.right, source_rect.bottom,
    target_rect.left, target_rect.top, target_rect.right, target_rect.bottom, duration_ms);
  const bool ok = (theApp._dll_mouse_drag_between)(
    hwnd, source_rect, target_rect, duration_ms) != 0;
  const bool have_after = GetCursorPos(&cursor_after) != FALSE;
  write_log(true,
    "[OpenOFC MOUSE] arbitration=LEGACY before=(%ld,%ld) after=(%ld,%ld) dll_result=%d sampled=%d/%d\\n",
    cursor_before.x, cursor_before.y, cursor_after.x, cursor_after.y,
    ok ? 1 : 0, have_before ? 1 : 0, have_after ? 1 : 0);
'''
    if old_drag_gate not in text:
        raise RuntimeError("legacy focus drag gate not found")
    text = text.replace(old_drag_gate, new_drag_gate, 1)

    old_click_gate = '''  if (!rect_ok) {
    write_log(k_always_log_errors,
      "[DeepOFC FP0] Refusing Confirm click outside attached client bounds\\n");
    return false;
  }
  if (GetForegroundWindow() != hwnd
      && !OpenOFCEnsureAttachedTableForeground(hwnd)) {
    TableLostFocus();
    write_log(k_always_log_errors,
      "[DeepOFC FP0] Refusing Confirm because attached table focus could not be recovered safely\\n");
    return false;
  }
  (theApp._dll_mouse_click)(hwnd, rect, MouseLeft, 1);
'''
    new_click_gate = '''  if (!rect_ok) {
    write_log(k_always_log_errors,
      "[DeepOFC FP0] Refusing Confirm click outside attached client bounds\\n");
    return false;
  }
  // Confirm uses the same normal OpenHoldem click primitive. The mouse DLL
  // owns focus activation/arbitration; no separate OFC foreground gate.
  (theApp._dll_mouse_click)(hwnd, rect, MouseLeft, 1);
'''
    if old_click_gate not in text:
        raise RuntimeError("legacy focus confirm gate not found")
    text = text.replace(old_click_gate, new_click_gate, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_mouse_dll():
    rel = "Reference Mouse DLL/mousedll.cpp"
    path, text, eol, bom = read_source(rel)
    start = text.find("MOUSEDLL_API int MouseDragBetweenRects(")
    if start < 0:
        raise RuntimeError("MouseDragBetweenRects start not found")
    # Function is followed by RandomizeClickLocation in this source.
    end = text.find("const POINT RandomizeClickLocation", start)
    if end < 0:
        raise RuntimeError("MouseDragBetweenRects end anchor not found")

    new_func = r'''MOUSEDLL_API int MouseDragBetweenRects(const HWND hwnd, const RECT source_rect,
                                       const RECT target_rect, const int duration_ms) {
    // OPENOFC_LEGACY_DRAG_ARBITRATION: arbitrary-card drag follows the same
    // movement/focus semantics as the long-proven OpenHoldem MouseClickDrag.
    // In particular, MoveMouseHuman handles concurrent/manual cursor activity.
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
    if (screen_width <= 0 || screen_height <= 0) {
        return (int)false;
    }

    POINT current;
    if (!GetCursorPos(&current)) {
        return (int)false;
    }

    // Exact legacy pre-action arbitration: move to source first, then activate
    // the table, just like MouseClick / MouseClickDrag.
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
    if (SendInput(1, &down, sizeof(INPUT)) != 1) {
        return (int)false;
    }

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
    text = text[:start] + new_func + text[end:]
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_runtime_retry():
    relh = "OpenHoldem/COFCRuntimeController.h"
    path, text, eol, bom = read_source(relh)
    old = '''  int pending_before_drag_;
  std::string pending_signature_before_drag_;
  std::string hand_signature_;
'''
    new = '''  int pending_before_drag_;
  std::string pending_signature_before_drag_;
  int drag_wait_cycles_;
  int drag_retry_count_;
  std::string hand_signature_;
'''
    if old not in text:
        raise RuntimeError("runtime header fields anchor not found")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {relh}")

    rel = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_source(rel)
    old_ctor = '''COFCRuntimeController::COFCRuntimeController()
    : phase_(kIdle), pending_before_drag_(0) {}
'''
    new_ctor = '''COFCRuntimeController::COFCRuntimeController()
    : phase_(kIdle), pending_before_drag_(0), drag_wait_cycles_(0),
      drag_retry_count_(0) {}
'''
    if old_ctor not in text:
        raise RuntimeError("runtime constructor anchor not found")
    text = text.replace(old_ctor, new_ctor, 1)

    old_reset = '''  pending_before_drag_ = 0;
  pending_signature_before_drag_.clear();
  hand_signature_ = IncomingSignature(state);
'''
    new_reset = '''  pending_before_drag_ = 0;
  pending_signature_before_drag_.clear();
  drag_wait_cycles_ = 0;
  drag_retry_count_ = 0;
  hand_signature_ = IncomingSignature(state);
'''
    if old_reset not in text:
        raise RuntimeError("runtime reset anchor not found")
    text = text.replace(old_reset, new_reset, 1)

    old_start = '''  pending_before_drag_ = PendingCount(state);
  pending_signature_before_drag_ = PendingSignature(state);
  if (!orchestrator_.StartTurn(
'''
    new_start = '''  pending_before_drag_ = PendingCount(state);
  pending_signature_before_drag_ = PendingSignature(state);
  drag_wait_cycles_ = 0;
  if (!orchestrator_.StartTurn(
'''
    if old_start not in text:
        raise RuntimeError("runtime start anchor not found")
    text = text.replace(old_start, new_start, 1)

    old_wait = '''  if (orchestrator_.awaiting_drag_verification()
      && PendingSignature(state) == pending_signature_before_drag_) {
    write_log(true,
      "[DeepOFC WAIT] drag not visible yet pending_signature=\"%s\"\\n",
      pending_signature_before_drag_.c_str());
    return true;  // Current frame has not incorporated the drag yet.
  }
'''
    new_wait = '''  if (orchestrator_.awaiting_drag_verification()
      && PendingSignature(state) == pending_signature_before_drag_) {
    ++drag_wait_cycles_;
    const int kOpenOFCDragObservationWaitCycles = 8;
    write_log(true,
      "[DeepOFC WAIT] drag not visible yet pending_signature=\"%s\" wait=%d/%d retry=%d\\n",
      pending_signature_before_drag_.c_str(), drag_wait_cycles_,
      kOpenOFCDragObservationWaitCycles, drag_retry_count_);
    if (drag_wait_cycles_ < kOpenOFCDragObservationWaitCycles) {
      return true;
    }

    // OPENOFC_DRAG_RETRY: an input API success is not proof that the simulator
    // accepted the gesture. Retry the exact fixed strategic placement once,
    // then fail closed with a durable reason instead of waiting forever.
    if (drag_retry_count_ < 1) {
      ++drag_retry_count_;
      drag_wait_cycles_ = 0;
      write_log(k_always_log_errors,
        "[OpenOFC DRAG RETRY] reason=NOT_OBSERVED attempt=%d pending_signature=\"%s\"\\n",
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
    if old_wait not in text:
        raise RuntimeError("runtime wait block not found")
    text = text.replace(old_wait, new_wait, 1)

    old_after = '''  pending_before_drag_ = current_pending;
  pending_signature_before_drag_ = PendingSignature(state);
  if (complete && ready) return SendConfirm(state);
'''
    new_after = '''  pending_before_drag_ = current_pending;
  pending_signature_before_drag_ = PendingSignature(state);
  drag_wait_cycles_ = 0;
  drag_retry_count_ = 0;
  if (complete && ready) return SendConfirm(state);
'''
    if old_after not in text:
        raise RuntimeError("runtime post-fresh anchor not found")
    text = text.replace(old_after, new_after, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_view():
    rel = "OpenHoldem/OpenHoldemView.cpp"
    path, text, eol, bom = read_source(rel)
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
    if old not in text:
        raise RuntimeError("OpenOFC view status block not found")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_ci():
    rel = ".github/workflows/deepofc-fp0-playable-fantasy15.yml"
    path, text, eol, bom = read_source(rel)
    anchor = '''          $autoplayer = Get-Content -Raw 'OpenHoldem/CAutoplayer.cpp'
'''
    if anchor not in text:
        raise RuntimeError("CI anchor not found")
    block = '''          # OFC physical input must preserve legacy OpenHoldem mouse arbitration.
          $casino = Get-Content -Raw 'OpenHoldem/CCasinoInterface.cpp'
          $mouse = Get-Content -Raw 'Reference Mouse DLL/mousedll.cpp'
          $view = Get-Content -Raw 'OpenHoldem/OpenHoldemView.cpp'
          if (($casino -notmatch 'OPENOFC_LEGACY_MOUSE_ARBITRATION') -or
              ($casino -match 'OpenOFCEnsureAttachedTableForeground') -or
              ($casino -match 'Refusing drag because attached table focus')) {
            throw 'OpenOFC still imposes a non-legacy foreground hard gate'
          }
          if (($mouse -notmatch 'OPENOFC_LEGACY_DRAG_ARBITRATION') -or
              ($mouse -notmatch 'MoveMouseHuman\(start, end, held_duration\)')) {
            throw 'OpenOFC arbitrary drag is not using legacy MouseClickDrag arbitration'
          }
          $dragStart = $mouse.IndexOf('MOUSEDLL_API int MouseDragBetweenRects')
          $dragEnd = $mouse.IndexOf('const POINT RandomizeClickLocation', $dragStart)
          if (($dragStart -lt 0) -or ($dragEnd -le $dragStart)) {
            throw 'Could not isolate MouseDragBetweenRects for CI contract'
          }
          $dragBody = $mouse.Substring($dragStart, $dragEnd - $dragStart)
          if ($dragBody -match 'MoveMouseHeldButton') {
            throw 'Custom held-button mouse path remains in active OFC drag'
          }
          if (($runtime -notmatch 'OPENOFC_DRAG_RETRY') -or
              ($runtime -notmatch 'DRAG_NOT_OBSERVED_AFTER_RETRY')) {
            throw 'OpenOFC unobserved-drag retry/bounded wait contract is missing'
          }
          if (($view -notmatch 'ROUND %d/5') -or ($view -notmatch 'ACTION=%s')) {
            throw 'OpenOFC main-view status is not split into unclipped OFC-native lines'
          }

'''
    if "OPENOFC_LEGACY_MOUSE_ARBITRATION" in text:
        raise RuntimeError("CI mouse-v2 assertions already present")
    text = text.replace(anchor, block + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def main():
    patch_casino_interface()
    patch_mouse_dll()
    patch_runtime_retry()
    patch_view()
    patch_ci()
    print("OpenOFC mouse v2 repair applied successfully")


if __name__ == "__main__":
    main()
