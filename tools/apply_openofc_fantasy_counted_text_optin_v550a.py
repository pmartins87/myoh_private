from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = Path("OpenHoldem/COFCScraper.cpp")


def main() -> None:
    path = ROOT / REL
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    signature = (
        "bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {\n"
    )
    old = signature + '''  if (!p_tablemap->OFCFantasyRecognizerCalibrated()) {\n'''
    new = signature + r'''  // OPENOFC_FANTASY_COUNTED_TEXT_V550A: this runtime build is paired with
  // a count-specific TableMap. Never silently interpret an older TableMap using
  // the new region namespace. Missing opt-in is a safe perception failure, not
  // permission to guess geometry/identity.
  if (p_tablemap == NULL
      || p_tablemap->GetTMSymbol("openofc_fantasy_tablemap_text_by_count", 0) != 1) {
    write_log(k_always_log_errors,
      "[OpenOFC FANTASY V550] counted-text TableMap opt-in missing terminal=0\n");
    return false;
  }

  if (!p_tablemap->OFCFantasyRecognizerCalibrated()) {
'''
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"v5.5.0A expected one Fantasy function start, got {count}")
    text = text.replace(old, new, 1)

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print(
        "OPENOFC_FANTASY_COUNTED_TEXT_V550A=PASS "
        "tablemap_opt_in=EXPLICIT missing=FAIL_CLOSED"
    )


if __name__ == "__main__":
    main()
