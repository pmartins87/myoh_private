from __future__ import annotations

from pathlib import Path

CPP = Path("OpenHoldem/CCasinoInterface.cpp")
MARKER = "OPENOFC_FANTASY_BOUNDED_INPUT_GUARD_V548"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one anchor, got {count}: {old[:180]!r}")
    return text.replace(old, new, 1)


def main() -> None:
    if not CPP.exists():
        raise SystemExit(f"materialized source missing: {CPP}")
    text = CPP.read_text(encoding="utf-8")
    if MARKER in text:
        print("CCasinoInterface.cpp: v5.4.8 bounded input guard already materialized")
        return
    if "OPENOFC_FANTASY_BOUNDED_CLICK_V547" not in text:
        raise SystemExit("v5.4.8 requires materialized v5.4.7 bounded Fantasy click primitive")

    focus_old = '''  SetForegroundWindow(hwnd);
  SetFocus(hwnd);
  SetActiveWindow(hwnd);

  write_log(true,
'''
    focus_new = '''  // OPENOFC_FANTASY_BOUNDED_INPUT_GUARD_V548
  // v5.4.7 removed the legacy mouse.dll wait/restart loop. v5.4.8 restores
  // user-interference safety without restoring liveness risk: acquire/check the
  // attached table once, then fail closed immediately if focus is unavailable.
  // The connector normally attaches a top-level table HWND, but guarding its
  // GA_ROOT as well keeps the primitive correct if a child HWND is ever used.
  HWND foreground_target = GetAncestor(hwnd, GA_ROOT);
  if (foreground_target == NULL) foreground_target = hwnd;
  SetForegroundWindow(foreground_target);
  SetFocus(hwnd);
  SetActiveWindow(hwnd);
  Sleep(20);
  if (GetForegroundWindow() != foreground_target) {
    write_log(k_always_log_errors,
      "[OpenOFC BOUNDED_CLICK] result=REFUSED reason=FOREGROUND_NOT_ACQUIRED bounded=1\\n");
    return false;
  }

  write_log(true,
'''
    text = replace_once(text, focus_old, focus_new, "initial foreground guard")

    settle_old = '''    if (!ClientToScreen(hwnd, &point) || !SetCursorPos(point.x, point.y)) {
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=FAIL reason=CURSOR_POSITION index=%d\\n", i);
      return false;
    }
    Sleep(20);

    INPUT down;
'''
    settle_new = '''    if (GetForegroundWindow() != foreground_target) {
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=REFUSED reason=FOREGROUND_LOST index=%d bounded=1\\n",
        i);
      return false;
    }
    if (!ClientToScreen(hwnd, &point) || !SetCursorPos(point.x, point.y)) {
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=FAIL reason=CURSOR_POSITION index=%d\\n", i);
      return false;
    }
    Sleep(20);
    POINT settled = {0, 0};
    if (!GetCursorPos(&settled)
        || settled.x < point.x - 2 || settled.x > point.x + 2
        || settled.y < point.y - 2 || settled.y > point.y + 2) {
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=REFUSED reason=CURSOR_INTERFERENCE_BEFORE_DOWN index=%d expected=%ld,%ld actual=%ld,%ld bounded=1\\n",
        i, point.x, point.y, settled.x, settled.y);
      return false;
    }

    INPUT down;
'''
    text = replace_once(text, settle_old, settle_new, "pre-down cursor guard")

    release_old = '''    Sleep(30);
    INPUT up;
    ZeroMemory(&up, sizeof(INPUT));
    up.type = INPUT_MOUSE;
    up.mi.dwFlags = MOUSEEVENTF_LEFTUP;
    if (SendInput(1, &up, sizeof(INPUT)) != 1) {
'''
    release_new = '''    Sleep(15);
    INPUT up;
    ZeroMemory(&up, sizeof(INPUT));
    up.type = INPUT_MOUSE;
    up.mi.dwFlags = MOUSEEVENTF_LEFTUP;

    POINT before_release;
    const bool release_cursor_ok = GetCursorPos(&before_release) != FALSE
      && before_release.x >= point.x - 2 && before_release.x <= point.x + 2
      && before_release.y >= point.y - 2 && before_release.y <= point.y + 2;
    const bool release_focus_ok = GetForegroundWindow() == foreground_target;
    if (!release_cursor_ok || !release_focus_ok) {
      // LEFTDOWN has already happened. Release exactly once immediately and
      // stop the transaction; never wait/retry while a mouse button may be held.
      SendInput(1, &up, sizeof(INPUT));
      write_log(k_always_log_errors,
        "[OpenOFC BOUNDED_CLICK] result=FAIL reason=INTERFERENCE_WHILE_HELD index=%d focus_ok=%d cursor_ok=%d emergency_release=1 bounded=1\\n",
        i, release_focus_ok ? 1 : 0, release_cursor_ok ? 1 : 0);
      return false;
    }
    if (SendInput(1, &up, sizeof(INPUT)) != 1) {
'''
    text = replace_once(text, release_old, release_new, "held-button interference guard")

    text = text.replace(
        '"[OpenOFC BOUNDED_CLICK] begin count=%d gap_ms=%d max_targets=16 path=DIRECT_WIN32\\n",',
        '"[OpenOFC BOUNDED_CLICK] begin count=%d gap_ms=%d max_targets=16 path=DIRECT_WIN32 guard=FOCUS_CURSOR_FAIL_CLOSED_V548\\n",',
        1,
    )

    CPP.write_text(text, encoding="utf-8")
    print("OPENOFC_FANTASY_BOUNDED_INPUT_GUARD_V548_MATERIALIZATION=PASS")


if __name__ == "__main__":
    main()
