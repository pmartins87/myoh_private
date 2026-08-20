from __future__ import annotations

from pathlib import Path
import re

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
        raise RuntimeError(f"{rel}: expected one target, got {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_safe_click_sequence():
    replace_once(
        "OpenHoldem/CCasinoInterface.h",
        '#include "CBetSlider.h"\n',
        '#include <vector>\n\n#include "CBetSlider.h"\n',
    )
    replace_once(
        "OpenHoldem/CCasinoInterface.h",
        '''  bool DragRectToRect(RECT source_rect, RECT target_rect, int duration_ms);\n  bool ClickRectSafely(RECT rect);\n''',
        '''  bool DragRectToRect(RECT source_rect, RECT target_rect, int duration_ms);\n  bool ClickRectSafely(RECT rect);\n  // OPENOFC_FANTASY_ATOMIC_CLICK_SEQUENCE_V5: validates every rectangle and\n  // holds the legacy named mouse mutex for the complete select+row-check batch.\n  bool ClickRectsSafely(const std::vector<RECT> &rects, int delay_ms);\n''',
    )

    rel = "OpenHoldem/CCasinoInterface.cpp"
    anchor = '''bool CCasinoInterface::ClickButtonSequence(int first_button, int second_button, int delay_in_milli_seconds) {\n'''
    method = r'''bool CCasinoInterface::ClickRectsSafely(
    const std::vector<RECT> &rects, int delay_ms) {
  if (rects.empty() || theApp._dll_mouse_click == NULL || p_autoconnector == NULL)
    return false;
  HWND hwnd = p_autoconnector->attached_hwnd();
  if (hwnd == NULL || !IsWindow(hwnd)) return false;
  RECT client;
  if (!GetClientRect(hwnd, &client)) return false;
  for (size_t i = 0; i < rects.size(); ++i) {
    const RECT &rect = rects[i];
    const bool ok = rect.right > rect.left && rect.bottom > rect.top
      && rect.left >= client.left && rect.top >= client.top
      && rect.right <= client.right && rect.bottom <= client.bottom;
    if (!ok) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V5] refusing click-sequence rectangle outside client index=%d rect=%d,%d,%d,%d\n",
        static_cast<int>(i), rect.left, rect.top, rect.right, rect.bottom);
      return false;
    }
  }

  CMyMutex mouse_mutex;
  if (!mouse_mutex.IsLocked()) {
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY V5] click-sequence arbitration=LEGACY result=MUTEX_TIMEOUT\n");
    return false;
  }
  const int bounded_delay = max(40, min(delay_ms, 500));
  write_log(true,
    "[OpenOFC FANTASY V5] click-sequence begin count=%d gap_ms=%d\n",
    static_cast<int>(rects.size()), bounded_delay);
  for (size_t i = 0; i < rects.size(); ++i) {
    (theApp._dll_mouse_click)(hwnd, rects[i], MouseLeft, 1);
    p_engine_container->symbol_engine_time()->UpdateOnAutoPlayerAction();
    write_log(true,
      "[OpenOFC FANTASY V5] click-sequence dispatched index=%d rect=%d,%d,%d,%d\n",
      static_cast<int>(i), rects[i].left, rects[i].top,
      rects[i].right, rects[i].bottom);
    if (i + 1 < rects.size()) Sleep(bounded_delay);
  }
  return true;
}

'''
    replace_once(rel, anchor, method + anchor)


def patch_single_loose_card_reflow():
    replace_once(
        "OpenHoldem/COFCFantasy15PixelRecognizer.cpp",
        '''  if (anchors->size() < 2) {\n    return Fail(error, "dynamic Fantasy detector found fewer than two loose cards");\n  }\n''',
        '''  // OPENOFC_FANTASY_SINGLE_LOOSE_V5: a 14-card Fantasy legitimately\n  // leaves exactly one loose card after the 13-card board is arranged. One\n  // anchor is enough to recognize/click that physical card; only grid fitting\n  // requires 2+ anchors.\n  if (anchors->empty()) {\n    return Fail(error, "dynamic Fantasy detector found no loose cards");\n  }\n''',
    )
    replace_once(
        "OpenHoldem/COFCFantasy15PixelRecognizer.cpp",
        '''  COFCFantasyGridFit fit;\n  if (!COFCFantasyDynamicGeometry::FitRegularGrid(anchors, &fit, error)) return false;\n\n  std::vector<std::string> labels;\n''',
        '''  COFCFantasyGridFit fit;\n  if (anchors.size() == 1) {\n    fit.valid = true;\n    fit.count = 1;\n    fit.center = anchors[0].CenterX();\n    fit.pitch = 0.0;\n    fit.maximum_residual = 0.0;\n  } else if (!COFCFantasyDynamicGeometry::FitRegularGrid(anchors, &fit, error)) {\n    return false;\n  }\n\n  std::vector<std::string> labels;\n''',
    )


def patch_runtime_fantasy_batch():
    replace_once(
        "OpenHoldem/COFCRuntimeController.h",
        '#include "COFCConfirmVerifier.h"\n',
        '#include "COFCConfirmVerifier.h"\n#include "COFCFantasyBatchExecutor.h"\n',
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.h",
        '''  COFCTurnOrchestrator orchestrator_;\n  COFCTurnPlan plan_;\n''',
        '''  COFCTurnOrchestrator orchestrator_;\n  COFCFantasyBatchExecutor fantasy_executor_;\n  COFCTurnPlan plan_;\n''',
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        '''  orchestrator_.ResetForKnownNewHand();\n  plan_.Reset();\n''',
        '''  orchestrator_.ResetForKnownNewHand();\n  fantasy_executor_.Reset();\n  plan_.Reset();\n''',
    )

    rel = "OpenHoldem/COFCRuntimeController.cpp"
    old = '''  write_log(true,\n    "[DeepOFC PLAN] target=%d already_correct=%d to_add=%d unused=%d\\n",\n    plan_.target_count, plan_.already_correct_count,\n    plan_.to_add_count, plan_.unused_count);\n  bool complete = false;\n'''
    new = '''  write_log(true,\n    "[DeepOFC PLAN] target=%d already_correct=%d to_add=%d unused=%d\\n",\n    plan_.target_count, plan_.already_correct_count,\n    plan_.to_add_count, plan_.unused_count);\n\n  // OPENOFC_FANTASY_ROW_BATCH_V5: Fantasy uses KKPoker's native select-card +\n  // yellow-row-check interaction. Dynamic source geometry is consumed only for\n  // the current row; after the row commits we rescrape/reflow before the next.\n  if (state.players[state.hero_chair].fantasy) {\n    bool fantasy_complete = false;\n    string fantasy_error;\n    if (!fantasy_executor_.Start(\n          state, observation, plan_, &fantasy_complete, &fantasy_error)) {\n      Block("Fantasy v5 start failed: " + fantasy_error);\n      return false;\n    }\n    phase_ = kArranging;\n    if (fantasy_complete && state.hero_can_confirm) return SendConfirm(state);\n    return true;\n  }\n\n  bool complete = false;\n'''
    replace_once(rel, old, new)

    old2 = '''bool COFCRuntimeController::AdvanceArrangement(\n    const COFCState &state,\n    const COFCVisualObservation &observation) {\n  const int current_pending = PendingCount(state);\n'''
    new2 = '''bool COFCRuntimeController::AdvanceArrangement(\n    const COFCState &state,\n    const COFCVisualObservation &observation) {\n  if (state.hero_chair >= 0 && state.hero_chair < state.player_count\n      && state.players[state.hero_chair].fantasy) {\n    bool fantasy_complete = false;\n    string fantasy_error;\n    if (!fantasy_executor_.AdvanceAfterFreshScrape(\n          state, observation, &fantasy_complete, &fantasy_error)) {\n      Block("Fantasy v5 verification/continuation failed: " + fantasy_error);\n      return false;\n    }\n    if (fantasy_complete) {\n      if (state.hero_can_confirm && state.action_required) {\n        write_log(true,\n          "[OpenOFC FANTASY V5] final_board_verified=1 confirm_visible=1\\n");\n        return SendConfirm(state);\n      }\n      write_log(true,\n        "[OpenOFC FANTASY V5] final_board_verified=1 waiting=CONFIRM_VISIBLE\\n");\n    }\n    return true;\n  }\n\n  const int current_pending = PendingCount(state);\n'''
    replace_once(rel, old2, new2)


def patch_project():
    replace_once(
        "OpenHoldem/OpenHoldem.vcxproj",
        '    <ClCompile Include="COFCActionPlanner.cpp" />\n',
        '    <ClCompile Include="COFCActionPlanner.cpp" />\n    <ClCompile Include="COFCFantasyBatchExecutor.cpp" />\n',
    )


def patch_executor_generic_joker_bridge():
    rel = "OpenHoldem/COFCFantasyBatchExecutor.cpp"
    path, text, eol, bom = read_source(rel)
    text = text.replace('#ifdef kOFCCardJokerGeneric\n', '')
    text = text.replace('#endif\n', '')
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def main():
    patch_safe_click_sequence()
    patch_single_loose_card_reflow()
    patch_runtime_fantasy_batch()
    patch_project()
    patch_executor_generic_joker_bridge()
    print("OpenOFC Fantasy v5 row-batch repair applied successfully")


if __name__ == "__main__":
    main()
