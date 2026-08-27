from __future__ import annotations

from pathlib import Path

CPP = Path("OpenHoldem/CCasinoInterface.cpp")
RUNTIME = Path("OpenHoldem/COFCRuntimeController.cpp")
BATCH = Path("OpenHoldem/COFCFantasyBatchExecutor.cpp")


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"missing function signature: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise AssertionError(f"missing opening brace: {signature}")
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError(f"unclosed function: {signature}")


def main() -> None:
    cpp = CPP.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")
    batch = BATCH.read_text(encoding="utf-8")

    # v5.4.7 owns the primitive and v5.4.8 rewrites part of its function body.
    # The v5.4.7 lineage marker is intentionally immediately before the
    # function, not necessarily inside the brace-delimited body after a later
    # rewrite. Assert the lineage at translation-unit scope and the v5.4.8
    # contract inside the function itself.
    assert "OPENOFC_FANTASY_BOUNDED_CLICK_V547" in cpp
    bounded = function_body(cpp, "bool CCasinoInterface::ClickRectsBoundedOFC(")
    assert "OPENOFC_FANTASY_BOUNDED_INPUT_GUARD_V548" in bounded
    assert "guard=FOCUS_CURSOR_FAIL_CLOSED_V548" in bounded

    required = (
        "GetAncestor(hwnd, GA_ROOT)",
        "foreground_target",
        "SetForegroundWindow(foreground_target)",
        "GetForegroundWindow() != foreground_target",
        "FOREGROUND_NOT_ACQUIRED",
        "FOREGROUND_LOST",
        "GetCursorPos(&settled)",
        "CURSOR_INTERFERENCE_BEFORE_DOWN",
        "settled.x < point.x - 2",
        "settled.x > point.x + 2",
        "settled.y < point.y - 2",
        "settled.y > point.y + 2",
        "release_cursor_ok",
        "release_focus_ok",
        "GetForegroundWindow() == foreground_target",
        "INTERFERENCE_WHILE_HELD",
        "emergency_release=1",
        "Sleep(15)",
        "SendInput(1, &down",
        "SendInput(1, &up",
        "CMyMutex mouse_mutex",
        "count > 16",
        "gap_ms > 250",
    )
    for marker in required:
        assert marker in bounded, f"v5.4.8 guard missing: {marker}"

    forbidden = (
        "_dll_mouse_click",
        "MoveMouseHuman",
        "WaitForSingleObject",
        "while (",
        "while(",
    )
    for marker in forbidden:
        assert marker not in bounded, f"unbounded/legacy path leaked into v5.4.8: {marker}"

    # Two finite loops only: preflight rectangle validation and bounded click list.
    assert bounded.count("for (") == 2
    # Initial acquisition + per-click pre-down guard + while-held release guard.
    assert bounded.count("GetForegroundWindow()") >= 3

    clear = function_body(batch, "bool COFCFantasyBatchExecutor::SendClearRow(")
    select = function_body(batch, "bool COFCFantasyBatchExecutor::SendBuildRowBatch(")
    confirm = function_body(runtime, "bool COFCRuntimeController::SendConfirm(")
    assert "ClickRectBoundedOFC(action)" in clear
    assert "ClickRectsBoundedOFC(" in select
    assert "? p_casino_interface->ClickRectBoundedOFC(rect)" in confirm
    assert ": p_casino_interface->ClickRectSafely(rect)" in confirm
    for guard_marker in (
        "COFCFantasyConfirmGuard::Validate",
        "fantasy_confirm_fence_.CanDispatch",
        "fantasy_confirm_fence_.MarkDispatched",
    ):
        assert guard_marker in confirm, f"Fantasy Confirm fence lost after v5.4.8: {guard_marker}"

    print(
        "OPENOFC_FANTASY_BOUNDED_INPUT_GUARD_V548_REGRESSION=PASS "
        "focus_root=FAIL_CLOSED cursor_before_down=FAIL_CLOSED "
        "interference_while_held=EMERGENCY_RELEASE_THEN_STOP "
        "mouse_dll=ABSENT loops=FINITE normal_confirm=UNCHANGED"
    )


if __name__ == "__main__":
    main()
