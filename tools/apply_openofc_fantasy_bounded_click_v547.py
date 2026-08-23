from __future__ import annotations

from pathlib import Path

HEADER = Path("OpenHoldem/CCasinoInterface.h")
CPP = Path("OpenHoldem/CCasinoInterface.cpp")
BATCH = Path("OpenHoldem/COFCFantasyBatchExecutor.cpp")
RUNTIME = Path("OpenHoldem/COFCRuntimeController.cpp")

MARKER = "OPENOFC_FANTASY_BOUNDED_CLICK_V547"

HEADER_DECL = r'''  // OPENOFC_FANTASY_BOUNDED_CLICK_V547: Fantasy click actions must never
  // enter mouse.dll's user-motion wait/restart loop. These primitives keep the
  // legacy named mouse mutex, but the actual click transaction is bounded and
  // uses direct Win32 input. Normal-game ClickRectSafely remains unchanged.
  bool ClickRectBoundedOFC(RECT rect);
  bool ClickRectsBoundedOFC(const RECT *rects, int count, int gap_ms);
'''

CPP_IMPL = r'''// OPENOFC_FANTASY_BOUNDED_CLICK_V547
//
// The legacy mouse.dll click path intentionally waits/restarts when it thinks
// the physical cursor was moved by the user. That is useful for generic OH
// interaction, but it is unsafe inside the synchronous OpenOFC heartbeat: a
// Fantasy CLEAR_ROW/SELECT/CONFIRM action can hold Tick for an unbounded time.
//
// This OFC-specific primitive preserves the same inter-instance named mutex,
// validates every target before touching the mouse, and then performs a fixed,
// bounded direct Win32 click sequence. There is no user-motion arbitration and
// no retry loop here. Visual acceptance is proved later by the existing fresh-
// scrape Fantasy state machine (ROW_CLEAR_OK / ROW_COMMIT_OK / Confirm state).
bool CCasinoInterface::ClickRectsBoundedOFC(
    const RECT *rects, int count, int gap_ms) {
  if (p_autoconnector == NULL || rects == NULL || count <= 0 || count > 16) {
    write_log(k_always_log_errors,
      "[OpenOFC BOUNDED_CLICK] result=REFUSED reason=BAD_ARGUMENT count=%d\n",
      count);
    return false;
  }
  HWND hwnd = p_autoconnector->attached_hwnd();
  if (hwnd == NULL || !IsWindow(hwnd)) {
    write_log(k_always_log_errors,
      "[OpenOFC BOUNDED_CLICK] result=REFUSED reason=BAD_WINDOW\n");
    return false;
  }
  RECT client;
  if (!GetClientRect(hwnd, &client)) return false;
  for (int i = 0; i < count; ++i) {
    const RECT &rect = rects[i];
    const bool rect_ok = rect.right > rect.left && rect.bottom > rect.top
      && rect.left >= client.left && rect.top >= client.top
      && rect.right <= client.right && rect.bottom <= client.bottom;
    if (!rect_ok) {
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=REFUSED reason=OUT_OF_BOUNDS index=%d rect=%ld,%ld,%ld,%ld client=%ld,%ld,%ld,%ld\n",
        i, rect.left, rect.top, rect.right, rect.bottom,
        client.left, client.top, client.right, client.bottom);
      return false;
    }
  }

  // CMyMutex has its own finite 5-second timeout. Keeping it here preserves
  // cross-instance cursor arbitration without reintroducing mouse.dll's
  // indefinite user-motion wait/restart behavior.
  CMyMutex mouse_mutex;
  if (!mouse_mutex.IsLocked()) {
    write_log(k_always_log_errors,
      "[OpenOFC BOUNDED_CLICK] result=REFUSED reason=MUTEX_TIMEOUT\n");
    return false;
  }

  if (gap_ms < 40) gap_ms = 40;
  if (gap_ms > 250) gap_ms = 250;
  const DWORD started = GetTickCount();
  SetForegroundWindow(hwnd);
  SetFocus(hwnd);
  SetActiveWindow(hwnd);

  write_log(true,
    "[OpenOFC BOUNDED_CLICK] begin count=%d gap_ms=%d max_targets=16 path=DIRECT_WIN32\n",
    count, gap_ms);
  for (int i = 0; i < count; ++i) {
    POINT point;
    point.x = rects[i].left + (rects[i].right - rects[i].left) / 2;
    point.y = rects[i].top + (rects[i].bottom - rects[i].top) / 2;
    if (!ClientToScreen(hwnd, &point) || !SetCursorPos(point.x, point.y)) {
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=FAIL reason=CURSOR_POSITION index=%d\n", i);
      return false;
    }
    Sleep(20);

    INPUT down;
    ZeroMemory(&down, sizeof(INPUT));
    down.type = INPUT_MOUSE;
    down.mi.dwFlags = MOUSEEVENTF_LEFTDOWN;
    if (SendInput(1, &down, sizeof(INPUT)) != 1) {
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=FAIL reason=LEFTDOWN index=%d\n", i);
      return false;
    }

    Sleep(30);
    INPUT up;
    ZeroMemory(&up, sizeof(INPUT));
    up.type = INPUT_MOUSE;
    up.mi.dwFlags = MOUSEEVENTF_LEFTUP;
    if (SendInput(1, &up, sizeof(INPUT)) != 1) {
      // One fixed emergency release attempt; never loop while a button may be
      // held. The state machine will fail closed because this call returns false.
      Sleep(10);
      SendInput(1, &up, sizeof(INPUT));
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=FAIL reason=LEFTUP index=%d emergency_release=1\n",
        i);
      return false;
    }
    if (i + 1 < count) Sleep(gap_ms);
  }

  const DWORD elapsed = GetTickCount() - started;
  write_log(true,
    "[OpenOFC BOUNDED_CLICK] result=OK count=%d elapsed_ms=%lu visual_verification=NEXT_SCRAPE\n",
    count, static_cast<unsigned long>(elapsed));
  p_engine_container->symbol_engine_time()->UpdateOnAutoPlayerAction();
  return true;
}

bool CCasinoInterface::ClickRectBoundedOFC(RECT rect) {
  return ClickRectsBoundedOFC(&rect, 1, 40);
}

'''


def require_once(text: str, needle: str, label: str) -> None:
    count = text.count(needle)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, got {count}: {needle!r}")


def patch_header() -> None:
    text = HEADER.read_text(encoding="utf-8")
    if MARKER in text:
        print("CCasinoInterface.h: v5.4.7 already materialized")
        return
    anchor = "  bool ClickRectSafely(RECT rect);\n"
    require_once(text, anchor, "CCasinoInterface.h")
    text = text.replace(anchor, anchor + HEADER_DECL, 1)
    HEADER.write_text(text, encoding="utf-8")
    print("CCasinoInterface.h: added bounded OFC click API")


def patch_cpp() -> None:
    text = CPP.read_text(encoding="utf-8")
    if MARKER in text:
        print("CCasinoInterface.cpp: v5.4.7 already materialized")
        return
    anchor = "bool CCasinoInterface::ClickButtonSequence("
    require_once(text, anchor, "CCasinoInterface.cpp")
    text = text.replace(anchor, CPP_IMPL + anchor, 1)
    CPP.write_text(text, encoding="utf-8")
    print("CCasinoInterface.cpp: added direct bounded Win32 click implementation")


def patch_batch() -> None:
    text = BATCH.read_text(encoding="utf-8")
    if "bounded Fantasy row-clear click" in text:
        print("COFCFantasyBatchExecutor.cpp: v5.4.7 already materialized")
        return

    old_clear = "if (!p_casino_interface->ClickRectSafely(action)) {\n    return Fail(error, \"safe Fantasy row-clear click was refused\");\n  }"
    new_clear = "if (!p_casino_interface->ClickRectBoundedOFC(action)) {\n    return Fail(error, \"bounded Fantasy row-clear click was refused\");\n  }"
    require_once(text, old_clear, "COFCFantasyBatchExecutor.cpp clear")
    text = text.replace(old_clear, new_clear, 1)

    old_select = "if (!p_casino_interface->ClickRectsSafely(clicks, gap_ms)) {\n    return Fail(error, \"atomic Fantasy select-and-check sequence was refused\");\n  }"
    new_select = "if (clicks.empty() || !p_casino_interface->ClickRectsBoundedOFC(\n        &clicks[0], static_cast<int>(clicks.size()), gap_ms)) {\n    return Fail(error, \"bounded Fantasy select-and-check sequence was refused\");\n  }"
    require_once(text, old_select, "COFCFantasyBatchExecutor.cpp select")
    text = text.replace(old_select, new_select, 1)

    BATCH.write_text(text, encoding="utf-8")
    print("COFCFantasyBatchExecutor.cpp: clear/select now use bounded clicks")


def patch_runtime_confirm() -> None:
    text = RUNTIME.read_text(encoding="utf-8")
    if "confirm_click_dispatched" in text:
        print("COFCRuntimeController.cpp: v5.4.7 already materialized")
        return

    old_condition = "  if (p_casino_interface == NULL || !p_casino_interface->ClickRectSafely(rect)) {\n"
    new_condition = '''  const bool confirm_click_dispatched = p_casino_interface != NULL
    && (fantasy_confirm
      ? p_casino_interface->ClickRectBoundedOFC(rect)
      : p_casino_interface->ClickRectSafely(rect));
  if (!confirm_click_dispatched) {
'''
    require_once(text, old_condition, "COFCRuntimeController.cpp confirm condition")
    text = text.replace(old_condition, new_condition, 1)

    old_recover = '    Recover("safe Confirm click was refused before mouse dispatch");\n'
    new_recover = '''    Recover(fantasy_confirm
      ? "bounded Fantasy Confirm click was refused before physical dispatch"
      : "safe Confirm click was refused before mouse dispatch");
'''
    require_once(text, old_recover, "COFCRuntimeController.cpp confirm refusal")
    text = text.replace(old_recover, new_recover, 1)

    old_comment = '''    // ClickRectSafely returns false only before invoking the mouse DLL. A fresh
    // stable replan may therefore retry without creating a duplicate click.
'''
    new_comment = '''    // Both click APIs return false before a successful physical dispatch. A
    // fresh stable replan may therefore retry without creating a duplicate click.
'''
    require_once(text, old_comment, "COFCRuntimeController.cpp confirm refusal comment")
    text = text.replace(old_comment, new_comment, 1)

    RUNTIME.write_text(text, encoding="utf-8")
    print("COFCRuntimeController.cpp: Fantasy Confirm bounded; normal Confirm/fence semantics preserved")


def main() -> None:
    for path in (HEADER, CPP, BATCH, RUNTIME):
        if not path.exists():
            raise SystemExit(f"required materialized source missing: {path}")
    patch_header()
    patch_cpp()
    patch_batch()
    patch_runtime_confirm()
    print("OPENOFC_FANTASY_BOUNDED_CLICK_V547_MATERIALIZATION=PASS")


if __name__ == "__main__":
    main()
