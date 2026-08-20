from __future__ import annotations

import apply_openofc_fantasy_v5 as v5


_original_replace_once = v5.replace_once


def replace_once_contextual(rel: str, old: str, new: str):
    ambiguous_reset = (
        rel == "OpenHoldem/COFCRuntimeController.cpp"
        and old == "  orchestrator_.ResetForKnownNewHand();\n  plan_.Reset();\n"
    )
    if not ambiguous_reset:
        return _original_replace_once(rel, old, new)

    path, text, eol, bom = v5.read_source(rel)
    function_old = (
        "void COFCRuntimeController::ResetForKnownNewHand(const COFCState &state) {\n"
        "  orchestrator_.ResetForKnownNewHand();\n"
        "  plan_.Reset();\n"
    )
    function_new = (
        "void COFCRuntimeController::ResetForKnownNewHand(const COFCState &state) {\n"
        "  orchestrator_.ResetForKnownNewHand();\n"
        "  fantasy_executor_.Reset();\n"
        "  plan_.Reset();\n"
    )
    count = text.count(function_old)
    if count != 1:
        raise RuntimeError(
            f"{rel}: expected one ResetForKnownNewHand context, got {count}"
        )
    text = text.replace(function_old, function_new, 1)
    v5.write_source(path, text, eol, bom)
    print(f"patched {rel}: Fantasy executor reset bound to new-hand function")


v5.replace_once = replace_once_contextual

if __name__ == "__main__":
    v5.main()
