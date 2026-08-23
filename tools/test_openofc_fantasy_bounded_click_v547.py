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
        "Sleep(30)",
        "gap_ms > 250",
        "visual_verification=NEXT_SCRAPE",
    ):
        assert required in bounded, f"bounded primitive missing contract: {required}"
    for forbidden in (
        "_dll_mouse_click",
        "MoveMouseHuman",
        "while (",
        "while(",
        "WaitForSingleObject",
    ):
        assert forbidden not in bounded, f"unbounded/legacy primitive leaked: {forbidden}"
    # The only loop is count-bounded and count itself is hard-capped at 16.
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
    assert "fantasy_confirm_click" in confirm
    assert "? p_casino_interface->ClickRectBoundedOFC(rect)" in confirm
    assert ": p_casino_interface->ClickRectSafely(rect)" in confirm
    assert "bounded Fantasy Confirm click" in confirm
    # This proves normal Confirm retained its old path while only Fantasy was
    # rerouted around mouse.dll.
    assert confirm.count("ClickRectBoundedOFC") == 1
    assert confirm.count("ClickRectSafely") == 1

    print(
        "OPENOFC_FANTASY_BOUNDED_CLICK_V547_REGRESSION=PASS "
        "clear=BOUNDED select=BOUNDED fantasy_confirm=BOUNDED normal_confirm=UNCHANGED "
        "mouse_dll_click=ABSENT_FROM_BOUNDED_PATH max_targets=16 gap_cap_ms=250"
    )


if __name__ == "__main__":
    main()
