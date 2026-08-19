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
        raise RuntimeError(f"{rel}: expected exactly one target, got {count}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_casino_header():
    old = '''  // DeepOFC R10 low-level client-coordinate drag wrapper. This method performs
  // only physical-window sanity checks and invokes the already-loaded mouse
  // DLL primitive; OFC semantic authorization and post-drag verification stay
  // in the dedicated transaction layer. It is not wired into the live R9 path.
  bool DragRectToRect(RECT source_rect, RECT target_rect, int duration_ms);
  // Bounds/focus checked single click used by the OFC Confirm transaction.
  bool ClickRectSafely(RECT rect);
'''
    new = '''  // OpenOFC physical primitives. They preserve the named OpenHoldem mouse
  // mutex so multiple OH/OpenOFC instances serialize real cursor ownership.
  bool DragRectToRect(RECT source_rect, RECT target_rect, int duration_ms);
  bool ClickRectSafely(RECT rect);
  // Legacy OHReplay is a static bitmap target. OpenOFC uses this only to make
  // input diagnostics visible; it must never expect a board-state transition.
  bool ConnectedToOHReplay() const;
'''
    replace_once("OpenHoldem/CCasinoInterface.h", old, new)


def patch_casino_cpp():
    rel = "OpenHoldem/CCasinoInterface.cpp"
    path, text, eol, bom = read_source(rel)

    marker = '''bool CCasinoInterface::TableLostFocus() {
'''
    if marker not in text:
        raise RuntimeError("TableLostFocus anchor not found")
    helper = '''bool CCasinoInterface::ConnectedToOHReplay() const {
  if (p_autoconnector == NULL) return false;
  HWND hwnd = p_autoconnector->attached_hwnd();
  if (hwnd == NULL || !IsWindow(hwnd)) return false;
  char classname[64] = {0};
  if (GetClassNameA(hwnd, classname, sizeof(classname)) <= 0) return false;
  return strcmp(classname, "OHREPLAY") == 0;
}

'''
    if "bool CCasinoInterface::ConnectedToOHReplay() const" not in text:
        text = text.replace(marker, helper + marker, 1)

    old_drag = '''  // OPENOFC_LEGACY_MOUSE_ARBITRATION: preserve normal OpenHoldem mouse
  // arbitration. The mouse DLL moves the cursor and activates its target;
  // OFC does not require the table to already own foreground focus.
  POINT cursor_before = {0};
  POINT cursor_after = {0};
  const bool have_before = GetCursorPos(&cursor_before) != FALSE;
  write_log(true,
    "[DeepOFC R10] physical drag src=%d,%d,%d,%d dst=%d,%d,%d,%d duration=%d\\n",
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
    new_drag = '''  // OPENOFC_LEGACY_MOUSE_ARBITRATION: preserve the same named mutex used by
  // normal OpenHoldem before taking ownership of the shared physical cursor.
  CMyMutex mouse_mutex;
  if (!mouse_mutex.IsLocked()) {
    write_log(k_always_log_errors,
      "[OpenOFC MOUSE] arbitration=LEGACY result=MUTEX_TIMEOUT\\n");
    return false;
  }

  const bool replay_probe = ConnectedToOHReplay();
  const int physical_duration = replay_probe ? max(duration_ms, 1600) : duration_ms;
  POINT cursor_before = {0};
  POINT cursor_after = {0};
  const bool have_before = GetCursorPos(&cursor_before) != FALSE;
  write_log(true,
    "[DeepOFC R10] physical drag src=%d,%d,%d,%d dst=%d,%d,%d,%d duration=%d replay_probe=%d\\n",
    source_rect.left, source_rect.top, source_rect.right, source_rect.bottom,
    target_rect.left, target_rect.top, target_rect.right, target_rect.bottom,
    physical_duration, replay_probe ? 1 : 0);
  const bool ok = (theApp._dll_mouse_drag_between)(
    hwnd, source_rect, target_rect, physical_duration) != 0;
  const bool have_after = GetCursorPos(&cursor_after) != FALSE;
  write_log(true,
    "[OpenOFC MOUSE] arbitration=LEGACY before=(%ld,%ld) after=(%ld,%ld) dll_result=%d sampled=%d/%d replay_probe=%d\\n",
    cursor_before.x, cursor_before.y, cursor_after.x, cursor_after.y,
    ok ? 1 : 0, have_before ? 1 : 0, have_after ? 1 : 0,
    replay_probe ? 1 : 0);
'''
    if old_drag not in text:
        raise RuntimeError("current OpenOFC drag arbitration block not found")
    text = text.replace(old_drag, new_drag, 1)

    old_click = '''  (theApp._dll_mouse_click)(hwnd, rect, MouseLeft, 1);
  p_engine_container->symbol_engine_time()->UpdateOnAutoPlayerAction();
  return true;
}

bool CCasinoInterface::ClickButtonSequence'''
    new_click = '''  CMyMutex mouse_mutex;
  if (!mouse_mutex.IsLocked()) {
    write_log(k_always_log_errors,
      "[OpenOFC MOUSE] confirm arbitration=LEGACY result=MUTEX_TIMEOUT\\n");
    return false;
  }
  (theApp._dll_mouse_click)(hwnd, rect, MouseLeft, 1);
  p_engine_container->symbol_engine_time()->UpdateOnAutoPlayerAction();
  return true;
}

bool CCasinoInterface::ClickButtonSequence'''
    if old_click not in text:
        raise RuntimeError("ClickRectSafely tail not found")
    text = text.replace(old_click, new_click, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_mouse_dll():
    rel = "Reference Mouse DLL/mousedll.cpp"
    path, text, eol, bom = read_source(rel)

    anchor = '''static bool IsUsableRect(const RECT &rect) {
    return rect.right > rect.left && rect.bottom > rect.top;
}
'''
    helper = '''static bool IsUsableRect(const RECT &rect) {
    return rect.right > rect.left && rect.bottom > rect.top;
}

static bool IsOHReplayWindow(const HWND hwnd) {
    if (hwnd == NULL || !IsWindow(hwnd)) return false;
    char classname[64] = {0};
    if (GetClassNameA(hwnd, classname, sizeof(classname)) <= 0) return false;
    return strcmp(classname, "OHREPLAY") == 0;
}
'''
    if "static bool IsOHReplayWindow" not in text:
        if anchor not in text:
            raise RuntimeError("IsUsableRect anchor not found")
        text = text.replace(anchor, helper, 1)

    old = '''    POINT current;
    if (!GetCursorPos(&current)) return (int)false;
    MoveMouseHuman(current, start, 200 + rand() % 100);

    SetFocus(hwnd);
    SetForegroundWindow(hwnd);
    SetActiveWindow(hwnd);

    const LONG start_x = (LONG)(start.x * (65535.0 / screen_width));
'''
    new = '''    POINT current;
    if (!GetCursorPos(&current)) return (int)false;
    const bool replay_probe = IsOHReplayWindow(hwnd);
    // Real tables preserve normal OH timing. OHReplay is static, so make the
    // exact same physical path deliberately slow and unmistakable on screen.
    const int approach_ms = replay_probe ? 1200 : (200 + rand() % 100);
    MoveMouseHuman(current, start, approach_ms);
    if (replay_probe) Sleep(700);  // visibly dwell over the source card

    SetFocus(hwnd);
    SetForegroundWindow(hwnd);
    SetActiveWindow(hwnd);

    const LONG start_x = (LONG)(start.x * (65535.0 / screen_width));
'''
    if old not in text:
        raise RuntimeError("mouse approach block not found")
    text = text.replace(old, new, 1)

    old2 = '''    Sleep(30 + rand() % 31);
    int held_duration = duration_ms;
    if (held_duration <= 0) held_duration = 350;
    if (held_duration < 100) held_duration = 100;
    if (held_duration > 1500) held_duration = 1500;
    MoveMouseHuman(start, end, held_duration);

    INPUT move;
'''
    new2 = '''    Sleep(replay_probe ? 500 : (30 + rand() % 31));
    int held_duration = duration_ms;
    if (held_duration <= 0) held_duration = 350;
    if (replay_probe && held_duration < 1600) held_duration = 1600;
    if (!replay_probe && held_duration < 100) held_duration = 100;
    if (held_duration > 2000) held_duration = 2000;
    MoveMouseHuman(start, end, held_duration);
    if (replay_probe) Sleep(700);  // visibly dwell over destination before up

    INPUT move;
'''
    if old2 not in text:
        raise RuntimeError("mouse held-duration block not found")
    text = text.replace(old2, new2, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_runtime_header():
    old = '''  enum Phase {
    kIdle,
    kArranging,
    kConfirmSent,
    kBlocked
  };
'''
    new = '''  enum Phase {
    kIdle,
    kArranging,
    kConfirmSent,
    kBlocked,
    kReplayProbeComplete
  };
'''
    replace_once("OpenHoldem/COFCRuntimeController.h", old, new)


def patch_runtime_cpp():
    rel = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_source(rel)

    old = '''  phase_ = kArranging;
  if (complete && ready) return SendConfirm(state);
  return true;
}
'''
    new = '''  // OHReplay is intentionally immutable. It is a perception/input diagnostic,
  // not a transactional simulator. Dispatch exactly one slow physical drag so
  // cursor motion can be observed, then stop without waiting for bitmap change.
  if (p_casino_interface != NULL
      && p_casino_interface->ConnectedToOHReplay()
      && orchestrator_.awaiting_drag_verification()) {
    phase_ = kReplayProbeComplete;
    write_log(true,
      "[OpenOFC REPLAY PROBE] physical_drag_dispatched=1 verification=SKIPPED reason=STATIC_OHREPLAY\\n");
    return true;
  }

  phase_ = kArranging;
  if (complete && ready) {
    if (p_casino_interface != NULL && p_casino_interface->ConnectedToOHReplay()) {
      phase_ = kReplayProbeComplete;
      write_log(true,
        "[OpenOFC REPLAY PROBE] no_drag_required=1 confirm=SKIPPED reason=STATIC_OHREPLAY\\n");
      return true;
    }
    return SendConfirm(state);
  }
  return true;
}
'''
    if old not in text:
        raise RuntimeError("StartDecision phase tail not found")
    text = text.replace(old, new, 1)

    old2 = '''  if (phase_ == kBlocked) {
    write_log(true, "[DeepOFC TICK] action=NONE reason=RUNTIME_BLOCKED\\n");
    return;
  }
  if (phase_ == kConfirmSent) {
'''
    new2 = '''  if (phase_ == kBlocked) {
    write_log(true, "[DeepOFC TICK] action=NONE reason=RUNTIME_BLOCKED\\n");
    return;
  }
  if (phase_ == kReplayProbeComplete) {
    // A static OHReplay can never verify a drag. One visible probe per attached
    // replay state is sufficient; do not retry and do not call it a runtime error.
    return;
  }
  if (phase_ == kConfirmSent) {
'''
    if old2 not in text:
        raise RuntimeError("Tick phase gate not found")
    text = text.replace(old2, new2, 1)

    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def main():
    patch_casino_header()
    patch_casino_cpp()
    patch_mouse_dll()
    patch_runtime_header()
    patch_runtime_cpp()
    print("OpenOFC replay probe v1 applied successfully")


if __name__ == "__main__":
    main()
