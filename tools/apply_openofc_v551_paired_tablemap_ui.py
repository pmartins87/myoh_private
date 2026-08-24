from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{relative}: expected exactly one UI patch target, got {count}"
        )
    text = text.replace(old, new, 1)
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print(f"patched {relative}")


def patch_statusbar() -> None:
    old = '''    const int contract = p_tablemap->GetTMSymbol("openofc_contract", 0);
    const bool contract_ok = contract == 1;

    CString round = "Round: ?";
    CString actor = contract_ok ? "Actor: ?" : "TM BLOCKED";
    CString action = contract_ok ? LastAction() : "OFC BLOQUEADO";
'''
    new = '''    const int contract = p_tablemap->GetTMSymbol("openofc_contract", 0);
    const bool contract_ok = contract == 5;
    const bool counted_text_ok =
      p_tablemap->GetTMSymbol("openofc_fantasy_tablemap_text_by_count", 0) == 1;
    const bool paired_tablemap_ok = contract_ok && counted_text_ok;

    CString round = "Round: ?";
    CString actor = "Actor: ?";
    CString action = LastAction();
    if (!contract_ok) {
      actor.Format("TM CONTRACT %d/5", contract);
      action = "OFC BLOQUEADO";
    } else if (!counted_text_ok) {
      actor = "TM V551 REQUIRED";
      action = "OFC BLOQUEADO";
    }
'''
    replace_once("OpenHoldem/COpenHoldemStatusbar.cpp", old, new)
    replace_once(
        "OpenHoldem/COpenHoldemStatusbar.cpp",
        "      if (contract_ok) {\n",
        "      if (paired_tablemap_ok) {\n",
    )


def patch_main_view() -> None:
    old = '''    const int contract = p_tablemap->GetTMSymbol("openofc_contract", 0);

    CString view;
'''
    new = '''    const int contract = p_tablemap->GetTMSymbol("openofc_contract", 0);
    const bool contract_ok = contract == 5;
    const bool counted_text_ok =
      p_tablemap->GetTMSymbol("openofc_fantasy_tablemap_text_by_count", 0) == 1;
    const bool paired_tablemap_ok = contract_ok && counted_text_ok;

    CString view;
'''
    replace_once("OpenHoldem/OpenHoldemView.cpp", old, new)

    old = '''    line.Format("OpenOFC  |  KKPoker Joker Ultimate  |  TMv%d\\r\\n", contract);
    view += line;
    line.Format("PERCEPTION  READ=%s  STATE=%s\\r\\n", read_text, state_text);
'''
    new = '''    line.Format("OpenOFC  |  KKPoker Joker Ultimate  |  TMv%d\\r\\n", contract);
    view += line;
    if (paired_tablemap_ok) {
      view += "TABLEMAP  PAIRED V551=OK\\r\\n";
    } else if (!contract_ok) {
      line.Format("TABLEMAP  BLOCKED: CONTRACT=%d EXPECTED=5\\r\\n", contract);
      view += line;
    } else {
      view += "TABLEMAP  BLOCKED: COUNTED-TEXT V551 SYMBOL MISSING\\r\\n";
    }
    line.Format("PERCEPTION  READ=%s  STATE=%s\\r\\n", read_text, state_text);
'''
    replace_once("OpenHoldem/OpenHoldemView.cpp", old, new)


def main() -> None:
    patch_statusbar()
    patch_main_view()
    print(
        "OPENOFC_V551_PAIRED_TABLEMAP_UI=PASS "
        "contract=5 counted_text_optin=REQUIRED stale_contract1=REMOVED"
    )


if __name__ == "__main__":
    main()
