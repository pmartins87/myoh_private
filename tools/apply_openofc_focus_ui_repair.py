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


def insert_once(rel: str, anchor: str, insertion: str):
    path, text, eol, bom = read_source(rel)
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"{rel}: expected exactly one insertion anchor, got {count}")
    text = text.replace(anchor, anchor + insertion, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_focus_handoff():
    rel = "OpenHoldem/CCasinoInterface.cpp"
    anchor = "CCasinoInterface *p_casino_interface = NULL;\n"
    helper = r'''

// OpenOFC focus handoff.
//
// Clicking the OpenOFC toolbar to enable the autoplayer necessarily makes the
// OpenOFC window foreground. The old Hold'em safety rule then refused the very
// first OFC drag because the attached simulator was no longer foreground. In
// OFC mode we may safely hand focus back only when the foreground window belongs
// to this OpenOFC process. We never steal focus from an unrelated application.
static bool OpenOFCEnsureAttachedTableForeground(HWND attached_hwnd) {
  if (attached_hwnd == NULL || !IsWindow(attached_hwnd)) return false;
  if (GetForegroundWindow() == attached_hwnd) return true;
  if (p_tablemap == NULL || !p_tablemap->SupportsOFCJokerUltimate()) return false;

  HWND foreground = GetForegroundWindow();
  if (foreground == NULL) return false;
  DWORD foreground_pid = 0;
  GetWindowThreadProcessId(foreground, &foreground_pid);
  if (foreground_pid != GetCurrentProcessId()) {
    write_log(k_always_log_errors,
      "[OpenOFC FOCUS] recovery_refused reason=UNRELATED_FOREGROUND pid=%lu self=%lu\n",
      static_cast<unsigned long>(foreground_pid),
      static_cast<unsigned long>(GetCurrentProcessId()));
    return false;
  }

  if (IsIconic(attached_hwnd)) ShowWindow(attached_hwnd, SW_RESTORE);
  BringWindowToTop(attached_hwnd);
  const BOOL requested = SetForegroundWindow(attached_hwnd);
  for (int i = 0; i < 8 && GetForegroundWindow() != attached_hwnd; ++i) {
    Sleep(25);
  }
  const bool ok = GetForegroundWindow() == attached_hwnd;
  write_log(true,
    "[OpenOFC FOCUS] source=OPENOFC_UI requested=%d result=%s attached=%p\n",
    requested ? 1 : 0, ok ? "FOREGROUND" : "FAILED", attached_hwnd);
  return ok;
}
'''
    insert_once(rel, anchor, helper)

    old_drag = r'''  // Unlike legacy button clicks, an OFC drag can mutate a multi-card
  // arrangement. Never steal focus and drag if the connected table is not
  // already the foreground window; the higher transaction layer will stop.
  if (TableLostFocus()) {
    write_log(k_always_log_errors,
      "[DeepOFC R10] Refusing drag because attached table lost focus\n");
    return false;
  }
'''
    new_drag = r'''  // A click on the OpenOFC toolbar is a benign focus transition. Hand the
  // foreground back to the attached simulator only when OpenOFC itself owns
  // the foreground; unrelated applications remain a hard stop.
  if (GetForegroundWindow() != hwnd
      && !OpenOFCEnsureAttachedTableForeground(hwnd)) {
    TableLostFocus();  // durable diagnostic with both window titles
    write_log(k_always_log_errors,
      "[DeepOFC R10] Refusing drag because attached table focus could not be recovered safely\n");
    return false;
  }
'''
    replace_once(rel, old_drag, new_drag)

    old_click = r'''  if (!rect_ok || TableLostFocus()) {
    write_log(k_always_log_errors,
      "[DeepOFC FP0] Refusing Confirm click outside client bounds or without focus\n");
    return false;
  }
'''
    new_click = r'''  if (!rect_ok) {
    write_log(k_always_log_errors,
      "[DeepOFC FP0] Refusing Confirm click outside attached client bounds\n");
    return false;
  }
  if (GetForegroundWindow() != hwnd
      && !OpenOFCEnsureAttachedTableForeground(hwnd)) {
    TableLostFocus();
    write_log(k_always_log_errors,
      "[DeepOFC FP0] Refusing Confirm because attached table focus could not be recovered safely\n");
    return false;
  }
'''
    replace_once(rel, old_click, new_click)


def patch_openofc_main_view():
    rel = "OpenHoldem/OpenHoldemView.cpp"
    include_anchor = '#include "CCasinoInterface.h"\n'
    insert_once(rel, include_anchor, '#include "COFCInspectorSnapshot.h"\n')

    old_start = '''void COpenHoldemView::UpdateDisplay(const bool update_all) {
\tbool\t\tupdate_it = false;
\tCDC\t\t\t*pDC = GetDC();

\tCString sym_handnumber = p_handreset_detector->GetHandNumber();
'''
    new_start = '''void COpenHoldemView::UpdateDisplay(const bool update_all) {
\tbool\t\tupdate_it = false;
\tCDC\t\t\t*pDC = GetDC();

  // OPENOFC_NATIVE_MAIN_VIEW: OFC mode never touches the legacy Hold'em table
  // renderer. This branch executes before handnumber/blinds/pot/FCKRA/community
  // card UI or Hold'em player-seat symbols are queried.
  if (p_tablemap != NULL && p_tablemap->SupportsOFCJokerUltimate()) {
    GetClientRect(&_client_rect);
    const COFCVisualObservation *raw = p_table_state->OFCVisualObservation();
    const COFCState *state = p_table_state->OFCState();
    const int contract = p_tablemap->GetTMSymbol("openofc_contract", 0);

    CString view;
    CString line;
    const char *read_text = (raw != NULL && raw->valid) ? "OK" : "REJECT";
    const char *state_text = (state != NULL && state->valid) ? "OK" : "REJECT";
    line.Format("OpenOFC  |  KKPoker Joker Ultimate  |  TMv%d\\r\\n", contract);
    view += line;
    line.Format("PERCEPTION  READ=%s  STATE=%s", read_text, state_text);
    if (state != NULL && state->valid) {
      CString action = state->action_required ? "HERO ACTION" : "WAIT";
      line.AppendFormat("  |  Round %d/5  |  H%d A%d D%d  |  %s",
        state->round_index + 1, state->hero_chair, state->acting_chair,
        state->dealer_chair, action.GetString());
    }
    view += line + "\\r\\n\\r\\n";

    if (raw != NULL && raw->valid) {
      for (int p = 0; p < raw->player_count && p < kOFCMaxPlayers; ++p) {
        const COFCPlayerBoard &board = raw->players[p].visual_board;
        line.Format("P%d%s  TOP     %s\\r\\n",
          p, p == raw->hero_chair ? " HERO" : "",
          COFCInspectorSnapshot::CardsText(board.top, kOFCTopCards).GetString());
        view += line;
        line.Format("        MIDDLE  %s\\r\\n",
          COFCInspectorSnapshot::CardsText(board.middle, kOFCMiddleCards).GetString());
        view += line;
        line.Format("        BOTTOM  %s\\r\\n",
          COFCInspectorSnapshot::CardsText(board.bottom, kOFCBottomCards).GetString());
        view += line;
      }
    }

    if (state != NULL && state->valid) {
      line.Format("\\r\\nINCOMING  %s\\r\\n",
        COFCInspectorSnapshot::CardsText(
          state->hero_incoming, state->hero_incoming_count).GetString());
      view += line;
      line.Format("DISCARDS  %s  |  prepare=%d confirm=%d pending=%d\\r\\n",
        COFCInspectorSnapshot::CardsText(
          state->hero_discards, state->hero_discard_count).GetString(),
        state->hero_can_prepare ? 1 : 0, state->hero_can_confirm ? 1 : 0,
        state->hero_incoming_count);
      view += line;
    }

    static CString last_openofc_view;
    if (!update_all && view == last_openofc_view) {
      ReleaseDC(pDC);
      return;
    }
    last_openofc_view = view;

    CBrush backBrush(RGB(36, 39, 43));
    CBrush *oldBrush = pDC->SelectObject(&backBrush);
    pDC->PatBlt(_client_rect.left, _client_rect.top,
      _client_rect.right - _client_rect.left,
      _client_rect.bottom - _client_rect.top, PATCOPY);
    pDC->SelectObject(oldBrush);
    pDC->SetBkMode(TRANSPARENT);
    pDC->SetTextColor(RGB(235, 238, 240));

    LOGFONT ofc_font = _logfont;
    ofc_font.lfHeight = -14;
    ofc_font.lfWeight = FW_NORMAL;
    strcpy_s(ofc_font.lfFaceName, 32, "Consolas");
    CFont font;
    font.CreateFontIndirect(&ofc_font);
    CFont *oldFont = pDC->SelectObject(&font);
    RECT text_rect = _client_rect;
    text_rect.left += 12;
    text_rect.top += 10;
    text_rect.right -= 10;
    text_rect.bottom -= 8;
    pDC->DrawText(view, &text_rect, DT_LEFT | DT_TOP | DT_NOPREFIX);
    pDC->SelectObject(oldFont);
    ReleaseDC(pDC);
    return;
  }

\tCString sym_handnumber = p_handreset_detector->GetHandNumber();
'''
    replace_once(rel, old_start, new_start)


def main():
    patch_focus_handoff()
    patch_openofc_main_view()
    print("OpenOFC focus/UI repair applied successfully")


if __name__ == "__main__":
    main()
