from __future__ import annotations

from pathlib import Path

HEADER = Path("OpenHoldem/CCasinoInterface.h")
CPP = Path("OpenHoldem/CCasinoInterface.cpp")
BATCH = Path("OpenHoldem/COFCFantasyBatchExecutor.cpp")
RUNTIME = Path("OpenHoldem/COFCRuntimeController.cpp")


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"missing function signature: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise AssertionError(f"missing opening brace: {signature}")
    depth = 0
    i = brace
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    raise AssertionError(f"unclosed function: {signature}")


def main() -> None:
    header = HEADER.read_text(encoding="utf-8")
    cpp = CPP.read_text(encoding="utf-8")
    batch = BATCH.read_text(encoding="utf-8")
    runtime = RUNTIME.read_text(encoding="utf-8")

    assert "OPENOFC_FANTASY_BOUNDED_CLICK_V547" in header
    assert "ClickRectBoundedOFC(RECT rect)" in header
    assert "ClickRectsBoundedOFC(const RECT *rects, int count, int gap_ms)" in header

    bounded = function_body(cpp, "bool CCasinoInterface::ClickRectsBoundedOFC(")
    for required in (
        "count > 16",
        "CMyMutex mouse_mutex",
        "MUTEX_TIMEOUT",
        "SetCursorPos",
        "SendInput(1, &down",
        "SendInput(1, &up",
        "Sleep(20)",
        "gap_ms > 250",
        "visual_verification=NEXT_SCRAPE",
    ):
        assert required in bounded, f"bounded primitive missing contract: {required}"

    # v5.4.7 originally held LEFTDOWN for 30 ms. v5.4.8 intentionally shortens
    # that bounded hold to 15 ms so it can perform an interference check before
    # LEFTUP. Accept exactly the timing that belongs to the materialized lineage;
    # do not force a stale v5.4.7 literal after the v5.4.8 safety upgrade.
    if "OPENOFC_FANTASY_BOUNDED_INPUT_GUARD_V548" in bounded:
        assert "Sleep(15)" in bounded, "v5.4.8 guarded hold timing missing"
    else:
        assert "Sleep(30)" in bounded, "v5.4.7 bounded hold timing missing"

    for forbidden in (
        "_dll_mouse_click",
        "MoveMouseHuman",
        "while (",
        "while(",
        "WaitForSingleObject",
    ):
        assert forbidden not in bounded, f"unbounded/legacy primitive leaked: {forbidden}"
    # The only loops are finite count-bounded loops and count itself is capped at 16.
    assert bounded.count("for (") == 2, "expected validation + click loops only"

    clear = function_body(batch, "bool COFCFantasyBatchExecutor::SendClearRow(")
    select = function_body(batch, "bool COFCFantasyBatchExecutor::SendBuildRowBatch(")
    assert "ClickRectBoundedOFC(action)" in clear
    assert "ClickRectSafely" not in clear
    assert "ClickRectsBoundedOFC(" in select
    assert "ClickRectsSafely" not in select
    assert "bounded Fantasy row-clear click" in clear
    assert "bounded Fantasy select-and-check sequence" in select

    confirm = function_body(runtime, "bool COFCRuntimeController::SendConfirm(")
    # v5.4.3H owns Fantasy double-confirm protection. v5.4.7 is allowed to
    # replace only the physical dispatch primitive selected inside that guarded
    # transaction; the fence/guard semantics must survive byte-semantically.
    for guard_marker in (
        "OPENOFC_FANTASY_CONFIRM_GUARD_V543H",
        "COFCFantasyConfirmGuard::Validate",
        "fantasy_confirm_fence_.CanDispatch",
        "fantasy_confirm_fence_.MarkDispatched",
        "physical_dispatch=1",
    ):
        assert guard_marker in confirm, f"Fantasy Confirm guard lost: {guard_marker}"
    assert "const bool confirm_click_dispatched" in confirm
    assert "fantasy_confirm" in confirm
    assert "? p_casino_interface->ClickRectBoundedOFC(rect)" in confirm
    assert ": p_casino_interface->ClickRectSafely(rect)" in confirm
    assert "bounded Fantasy Confirm click" in confirm
    # Normal Confirm retains the legacy safe path; only Fantasy bypasses the
    # potentially unbounded mouse.dll click loop.
    assert confirm.count("ClickRectBoundedOFC") == 1
    assert confirm.count("ClickRectSafely") == 1

    print(
        "OPENOFC_FANTASY_BOUNDED_CLICK_V547_REGRESSION=PASS "
        "clear=BOUNDED select=BOUNDED fantasy_confirm=BOUNDED normal_confirm=UNCHANGED "
        "fantasy_confirm_fence=PRESERVED mouse_dll_click=ABSENT_FROM_BOUNDED_PATH "
        "max_targets=16 gap_cap_ms=250"
    )


if __name__ == "__main__":
    main()
