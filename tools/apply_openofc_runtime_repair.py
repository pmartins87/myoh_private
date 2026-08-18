from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_source(rel: str):
    path = ROOT / rel
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text.replace("\r\n", "\n"), eol, bom


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


def patch_transform():
    old = '''\t\t\t// See if our pixel is in the defined color cube
\t\t\tif (IsInARGBColorCube((region->second.color>>24)&0xff,
\t\t\t\t\t\t\t\t GetRValue(region->second.color), 
\t\t\t\t\t\t\t\t GetGValue(region->second.color), 
\t\t\t\t\t\t\t\t GetBValue(region->second.color), 
\t\t\t\t\t\t\t\t region->second.radius, 
\t\t\t\t\t\t\t\t alpha, 
\t\t\t\t\t\t\t\t red, 
\t\t\t\t\t\t\t\t green,
\t\t\t\t\t\t\t\t blue))
\t\t\t{
\t\t\t\tcharacter[x][y] = true;
\t\t\t}
'''
    new = '''\t\t\t// OPENOFC_RGB_TEXT_TRANSFORM: OpenOFC regions are copied through
\t\t\t// GDI DDBs, whose high/alpha byte is not a stable part of the pixel
\t\t\t// contract. TableMap Tn fonts are defined by RGB foreground colour, so
\t\t\t// OFC text transforms must ignore alpha. Legacy OpenHoldem keeps the
\t\t\t// historical ARGB behaviour unchanged.
\t\t\tconst bool openofc_rgb_text = (p_tablemap != NULL)
\t\t\t\t&& p_tablemap->SupportsOFCJokerUltimate();
\t\t\tconst bool foreground = openofc_rgb_text
\t\t\t\t? IsInRGBColorCube(
\t\t\t\t\tGetRValue(region->second.color),
\t\t\t\t\tGetGValue(region->second.color),
\t\t\t\t\tGetBValue(region->second.color),
\t\t\t\t\tregion->second.radius, red, green, blue)
\t\t\t\t: IsInARGBColorCube((region->second.color>>24)&0xff,
\t\t\t\t\tGetRValue(region->second.color),
\t\t\t\t\tGetGValue(region->second.color),
\t\t\t\t\tGetBValue(region->second.color),
\t\t\t\t\tregion->second.radius, alpha, red, green, blue);
\t\t\tif (foreground)
\t\t\t{
\t\t\t\tcharacter[x][y] = true;
\t\t\t}
'''
    replace_once("CTransform/CTransform.cpp", old, new)


def patch_opponent_discards():
    old = '''    for (int i = 0; i < kOFCMaxDiscards; ++i) {
      base.Format("ofc_p%d_discard%d", p, i);
      COFCCard discard_face;
      bool back = false; int joker_id = 0;
      int rc = ScrapeOFCSlot(base, &discard_face, &back, &joker_id);
      if (rc < 0) { all_slots_ok = false; continue; }
      if (back) {
        ++player->hidden_discard_count;
      } else if (rc > 0) {
        write_log(k_always_log_errors,
          "[DeepOFC] Opponent discard identity visible while R1 D1 unresolved: p=%d slot=%d\\n",
          p, i);
        return false;
      }
    }
'''
    new = '''    // OPPONENT_HIDDEN_DISCARDS_DERIVED_FROM_BOARD: KKPoker does not expose
    // opponent discard identities in this layout. The old draft regions named
    // ofc_pX_discardY were calibration placeholders (some even covered the
    // KKPoker logo), so treating them as physical-card slots poisoned the
    // entire observation. Derive only the hidden discard COUNT from the public
    // board progression; never invent or scrape a hidden card identity.
    const int opponent_known_board = player->visual_board.CountKnownCards();
    if (opponent_known_board == 0) {
      if (player->hidden_incoming_count != 0
          && player->hidden_incoming_count != 5) {
        write_log(k_always_log_errors,
          "[DeepOFC] Invalid opponent initial hidden-incoming count: p=%d backs=%d\\n",
          p, player->hidden_incoming_count);
        all_slots_ok = false;
      }
      player->hidden_discard_count = 0;
    } else if (opponent_known_board >= 5 && opponent_known_board <= 13
        && ((opponent_known_board - 5) % 2 == 0)) {
      player->hidden_discard_count = (opponent_known_board - 5) / 2;
    } else {
      write_log(k_always_log_errors,
        "[DeepOFC] Impossible opponent public-board progression: p=%d known=%d backs=%d\\n",
        p, opponent_known_board, player->hidden_incoming_count);
      all_slots_ok = false;
    }
'''
    replace_once("OpenHoldem/COFCScraper.cpp", old, new)


def patch_capture():
    rel = "OpenHoldem/CScraper.cpp"
    path, text, eol, bom = read_source(rel)
    start = text.find("bool CScraper::IsIdenticalScrape() {")
    end = text.find("\n#undef __HDC_HEADER", start)
    if start < 0 or end <= start:
        raise RuntimeError("could not isolate CScraper::IsIdenticalScrape")
    old = text[start:end]
    if "PrintWindow(hwndTarget" not in old:
        raise RuntimeError("expected legacy PrintWindow capture implementation not found")
    new = '''bool CScraper::IsIdenticalScrape() {
  __HDC_HEADER

  HWND hwndTarget = p_autoconnector->attached_hwnd();
  RECT cr = {0};
  GetClientRect(hwndTarget, &cr);
  const bool openofc_mode = (p_tablemap != NULL)
    && p_tablemap->SupportsOFCJokerUltimate();

  old_bitmap = (HBITMAP) SelectObject(hdcCompatible, _entire_window_cur);
  BOOL capture_ok = FALSE;
  if (openofc_mode) {
    // OPENOFC_DESKTOP_BITBLT: the simulator is visible during diagnostics and
    // can be captured from the desktop client area without asking its window
    // procedure to repaint. Repeated PrintWindow calls caused visible flashing
    // and are unnecessary for this OpenOFC workflow.
    HDC hdcDesktop = GetDC(NULL);
    POINT client_origin = {0, 0};
    if (hdcDesktop != NULL && ClientToScreen(hwndTarget, &client_origin)) {
      capture_ok = BitBlt(hdcCompatible, 0, 0, cr.right, cr.bottom,
        hdcDesktop, client_origin.x, client_origin.y, SRCCOPY);
    }
    if (hdcDesktop != NULL) ReleaseDC(NULL, hdcDesktop);
    static bool logged_openofc_capture = false;
    if (!logged_openofc_capture) {
      write_log(true,
        "[OpenOFC CAPTURE] mode=DESKTOP_BITBLT nonintrusive=1 printwindow=0\\n");
      logged_openofc_capture = true;
    }
  } else {
    capture_ok = PrintWindow(hwndTarget, hdcCompatible, 0x00000002);
    if (!capture_ok) {
      HDC hdcDesktop = GetDC(NULL);
      POINT client_origin = {0, 0};
      if (hdcDesktop != NULL && ClientToScreen(hwndTarget, &client_origin)) {
        capture_ok = BitBlt(hdcCompatible, 0, 0, cr.right, cr.bottom,
          hdcDesktop, client_origin.x, client_origin.y, SRCCOPY);
      }
      if (hdcDesktop != NULL) ReleaseDC(NULL, hdcDesktop);
    }
  }
  SelectObject(hdcCompatible, old_bitmap);

  if (!capture_ok) {
    write_log(k_always_log_errors,
      "[CScraper] Window capture failed; current frame rejected\\n");
    __HDC_FOOTER_ATTENTION_HAS_TO_BE_CALLED_ON_EVERY_FUNCTION_EXIT_OTHERWISE_MEMORY_LEAK
    return false;
  }

  p_table_state->TableTitle()->UpdateTitle();
  if (BitmapsAreEqual(_entire_window_last, _entire_window_cur)
      && !p_table_state->TableTitle()->TitleChangedSinceLastHeartbeat()) {
    write_log(Preferences()->debug_scraper(),
      "[CScraper] IsIdenticalScrape() true\\n");
    __HDC_FOOTER_ATTENTION_HAS_TO_BE_CALLED_ON_EVERY_FUNCTION_EXIT_OTHERWISE_MEMORY_LEAK
    return true;
  }

  // OPENOFC_SINGLE_CAPTURE: update the comparison baseline from the already
  // captured current bitmap. Never recapture the external window merely to
  // populate _entire_window_last.
  HDC hdcCurrent = CreateCompatibleDC(hdcScreen);
  if (hdcCurrent == NULL) {
    write_log(k_always_log_errors,
      "[CScraper] Could not create current-frame memory DC\\n");
    __HDC_FOOTER_ATTENTION_HAS_TO_BE_CALLED_ON_EVERY_FUNCTION_EXIT_OTHERWISE_MEMORY_LEAK
    return false;
  }
  HBITMAP old_current = (HBITMAP) SelectObject(hdcCurrent, _entire_window_cur);
  old_bitmap = (HBITMAP) SelectObject(hdcCompatible, _entire_window_last);
  BitBlt(hdcCompatible, 0, 0, cr.right, cr.bottom,
    hdcCurrent, 0, 0, SRCCOPY);
  SelectObject(hdcCompatible, old_bitmap);
  SelectObject(hdcCurrent, old_current);
  DeleteDC(hdcCurrent);

  write_log(Preferences()->debug_scraper(),
    "[CScraper] IsIdenticalScrape() false\\n");
  __HDC_FOOTER_ATTENTION_HAS_TO_BE_CALLED_ON_EVERY_FUNCTION_EXIT_OTHERWISE_MEMORY_LEAK
  return false;
}
'''
    text = text[:start] + new.rstrip("\n") + text[end:]
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def patch_ci_contract():
    rel = ".github/workflows/deepofc-fp0-playable-fantasy15.yml"
    path, text, eol, bom = read_source(rel)
    anchor = '''          $autoplayer = Get-Content -Raw 'OpenHoldem/CAutoplayer.cpp'
'''
    if anchor not in text:
        raise RuntimeError("workflow assertion anchor not found")
    block = '''          # Perception/capture regressions discovered by the first canonical-TM
          # simulator run must remain impossible.
          if ($scraper -notmatch 'OPPONENT_HIDDEN_DISCARDS_DERIVED_FROM_BOARD') {
            throw 'Opponent hidden discards are not derived from public OFC board progression'
          }
          if ($scraper -match 'base\.Format\("ofc_p%d_discard%d"') {
            throw 'OpenOFC still scrapes fake opponent discard identity regions'
          }
          $transform = Get-Content -Raw 'CTransform/CTransform.cpp'
          if (($transform -notmatch 'OPENOFC_RGB_TEXT_TRANSFORM') -or
              ($transform -notmatch 'SupportsOFCJokerUltimate') -or
              ($transform -notmatch 'IsInRGBColorCube')) {
            throw 'OpenOFC Tn text transforms are not protected from unstable DDB alpha bytes'
          }
          $capture = Get-Content -Raw 'OpenHoldem/CScraper.cpp'
          if (($capture -notmatch 'OPENOFC_DESKTOP_BITBLT') -or
              ($capture -notmatch 'OPENOFC_SINGLE_CAPTURE') -or
              ($capture -notmatch '\[OpenOFC CAPTURE\].*printwindow=0')) {
            throw 'OpenOFC nonintrusive single-capture contract is missing'
          }

'''
    if "OPENOFC_DESKTOP_BITBLT" in text:
        raise RuntimeError("workflow already contains runtime repair assertions")
    text = text.replace(anchor, block + anchor, 1)
    write_source(path, text, eol, bom)
    print(f"patched {rel}")


def main():
    patch_transform()
    patch_opponent_discards()
    patch_capture()
    patch_ci_contract()
    print("OpenOFC runtime repair applied successfully")


if __name__ == "__main__":
    main()
