from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_source(relative: str):
    path = ROOT / relative
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool) -> None:
    output = text if eol == "\n" else text.replace("\n", "\r\n")
    data = output.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path, text, eol, bom = read_source(relative)
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{relative}: {label} expected exactly one target, got {count}"
        )
    write_source(path, text.replace(old, new, 1), eol, bom)
    print(f"patched {relative}: {label}", flush=True)


def regex_once(relative: str, pattern: str, replacement: str, label: str) -> None:
    path, text, eol, bom = read_source(relative)
    updated, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=re.S | re.M)
    if count != 1:
        raise SystemExit(
            f"{relative}: {label} expected exactly one regex target, got {count}"
        )
    write_source(path, updated, eol, bom)
    print(f"patched {relative}: {label}", flush=True)


def replace_tick_block_near_marker(
    relative: str, marker: str, start_token: str, replacement: str, label: str
) -> None:
    path, text, eol, bom = read_source(relative)
    marker_index = text.find(marker)
    if marker_index < 0:
        raise SystemExit(f"{relative}: {label} marker missing")
    start = text.rfind(start_token, 0, marker_index)
    if start < 0:
        raise SystemExit(f"{relative}: {label} start token missing")
    end = text.find("\n  }", marker_index)
    if end < 0:
        raise SystemExit(f"{relative}: {label} closing brace missing")
    end += len("\n  }")
    write_source(path, text[:start] + replacement + text[end:], eol, bom)
    print(f"patched {relative}: {label}", flush=True)


def patch_versioned_ui() -> None:
    replace_once(
        "OpenHoldem/COpenHoldemStatusbar.cpp",
        '#include "COFCInspectorSnapshot.h"\n',
        '#include "COFCInspectorSnapshot.h"\n#include "COFCBuildInfo.h"\n',
        "include centralized OpenOFC build identity",
    )
    replace_once(
        "OpenHoldem/OpenHoldemView.cpp",
        '#include "COFCInspectorSnapshot.h"\n',
        '#include "COFCInspectorSnapshot.h"\n#include "COFCBuildInfo.h"\n',
        "include centralized OpenOFC build identity",
    )

    replace_once(
        "OpenHoldem/OpenHoldemView.cpp",
        '    line.Format("OpenOFC  |  KKPoker Joker Ultimate  |  TMv%d\\r\\n", contract);\n    view += line;\n',
        '    line.Format("%s  |  KKPoker Joker Ultimate\\r\\n",\n      OPENOFC_PRODUCT_VERSION_LABEL);\n    view += line;\n',
        "show product/runtime version instead of TableMap contract as version",
    )
    replace_once(
        "OpenHoldem/OpenHoldemView.cpp",
        '      view += "TABLEMAP  PAIRED V551=OK\\r\\n";\n',
        '      line.Format(\n        "TABLEMAP ASSET  v%s  |  CONTRACT=%d  |  COUNTED-TEXT=OK\\r\\n",\n        OPENOFC_TABLEMAP_ASSET_VERSION, contract);\n      view += line;\n',
        "separate TableMap asset version from OpenOFC runtime version",
    )
    replace_once(
        "OpenHoldem/OpenHoldemView.cpp",
        '      view += "TABLEMAP  BLOCKED: COUNTED-TEXT V551 SYMBOL MISSING\\r\\n";\n',
        '      line.Format(\n        "TABLEMAP BLOCKED: v%s COUNTED-TEXT SYMBOL MISSING\\r\\n",\n        OPENOFC_TABLEMAP_ASSET_VERSION);\n      view += line;\n',
        "remove stale v5.5.1 branding from TableMap error",
    )
    replace_once(
        "OpenHoldem/COpenHoldemStatusbar.cpp",
        '      actor = "TM V551 REQUIRED";\n',
        '      actor.Format("TM v%s REQUIRED", OPENOFC_TABLEMAP_ASSET_VERSION);\n',
        "label the required TableMap as an asset, not runtime",
    )


def patch_runtime_status_lifecycle() -> None:
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '#include "COFCBaselinePolicy.h"\n',
        '#include "COFCBaselinePolicy.h"\n#include "COFCBuildInfo.h"\n',
        "include centralized build identity in runtime",
    )

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        "namespace {\n\n",
        '''namespace {

// OPENOFC_V583_BLOCK_STATUS: the terminal reason is durable until a semantic
// new-hand reset. The visible status is therefore never left at "calculating"
// after automation has deliberately failed closed.
std::string g_openofc_block_reason;

''',
        "store durable terminal block reason",
    )

    regex_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        r'''void COFCRuntimeController::Block\(const string &message\) \{\n.*?\n\}''',
        '''void COFCRuntimeController::Block(const string &message) {
  g_openofc_block_reason = message.empty() ? "motivo nao informado" : message;
  const string visible = "TRAVADO - " + g_openofc_block_reason;
  OpenOFCSetUserStatus(visible.c_str());
  phase_ = kBlocked;
  write_log(k_always_log_errors,
    "[DeepOFC FP0] AUTOMATION BLOCKED until a known new hand: %s\\n",
    g_openofc_block_reason.c_str());
}''',
        "publish exact fail-closed reason to the UI",
    )

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        'void COFCRuntimeController::ResetForKnownNewHand(const COFCState &state) {\n',
        'void COFCRuntimeController::ResetForKnownNewHand(const COFCState &state) {\n  g_openofc_block_reason.clear();\n',
        "clear terminal reason only at known new hand",
    )

    replace_tick_block_near_marker(
        "OpenHoldem/COFCRuntimeController.cpp",
        '[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION',
        "  if (!state.valid || !observation.valid) {",
        '''  if (!state.valid || !observation.valid) {
    OpenOFCSetUserStatus("LEITURA INVALIDA - aguardando nova leitura; sem agir");
    write_log(true, "[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION\\n");
    return;
  }''',
        "replace stale calculating status on invalid perception",
    )

    replace_tick_block_near_marker(
        "OpenHoldem/COFCRuntimeController.cpp",
        '[DeepOFC TICK] action=NONE reason=RUNTIME_BLOCKED',
        "  if (phase_ == kBlocked) {",
        '''  if (phase_ == kBlocked) {
    const string visible = "TRAVADO - "
      + (g_openofc_block_reason.empty()
          ? string("motivo nao informado") : g_openofc_block_reason);
    OpenOFCSetUserStatus(visible.c_str());
    write_log(true,
      "[DeepOFC TICK] action=NONE reason=RUNTIME_BLOCKED detail=\\"%s\\"\\n",
      g_openofc_block_reason.c_str());
    return;
  }''',
        "reassert exact terminal reason every blocked heartbeat",
    )

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        'bool COFCRuntimeController::StartDecision(\n    const COFCState &state,\n    const COFCVisualObservation &observation) {\n',
        'bool COFCRuntimeController::StartDecision(\n    const COFCState &state,\n    const COFCVisualObservation &observation) {\n  OpenOFCSetUserStatus("CALCULANDO JOGADA");\n',
        "show calculating only while a decision is actually being computed",
    )

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '  if (phase_ == kConfirmSent) {\n    HandlePostConfirm(state);\n    return;\n  }\n',
        '  if (phase_ == kConfirmSent) {\n    OpenOFCSetUserStatus("AGUARDANDO RESULTADO");\n    HandlePostConfirm(state);\n    return;\n  }\n',
        "label post-confirm wait",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare) {\n',
        '  if (state.acting_chair != state.hero_chair || !state.hero_can_prepare) {\n    OpenOFCSetUserStatus("AGUARDANDO VEZ / TRANSICAO");\n',
        "label non-actionable waiting state",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '  if (phase_ == kArranging) AdvanceArrangement(state, observation);\n',
        '  if (phase_ == kArranging) {\n    OpenOFCSetUserStatus("EXECUTANDO JOGADA");\n    AdvanceArrangement(state, observation);\n  }\n',
        "label active arrangement execution",
    )

    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '  write_log(true, "[DeepOFC FP0] known new hand; runtime reset\\n");\n',
        '  write_log(true,\n    "[DeepOFC FP0] known new hand; runtime reset product=%s tablemap_asset=%s\\n",\n    OPENOFC_PRODUCT_VERSION, OPENOFC_TABLEMAP_ASSET_VERSION);\n',
        "log the composed product and paired TableMap versions",
    )


def main() -> None:
    patch_versioned_ui()
    patch_runtime_status_lifecycle()
    print(
        "OPENOFC_V583_FIELD_OBSERVABILITY_APPLY=PASS "
        "product=5.8.3 tablemap_asset=5.5.2 "
        "blocked_reason=DURABLE invalid_read=VISIBLE "
        "status_lifecycle=PHASE_ACCURATE strategy=UNCHANGED"
    )


if __name__ == "__main__":
    main()
