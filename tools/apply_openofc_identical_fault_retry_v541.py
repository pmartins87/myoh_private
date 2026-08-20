from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem/CLazyScraper.cpp"

raw = PATH.read_bytes()
bom = raw.startswith(b"\xef\xbb\xbf")
text = raw.decode("utf-8-sig").replace("\r\n", "\n")
eol = "\r\n" if b"\r\n" in raw else "\n"

old = '''    if (identical_bitmap && !deepofc_reacquire_candidate_pending) {
      // Recognition is a pure function of this captured bitmap plus the
'''
new = '''    const bool deepofc_cached_snapshot_safe =
      p_table_state->OFCVisualObservation()->valid
      && p_table_state->OFCState()->valid;
    if (identical_bitmap
        && !deepofc_reacquire_candidate_pending
        && deepofc_cached_snapshot_safe) {
      // Recognition is a pure function of this captured bitmap plus the
'''
if text.count(old) != 1:
    raise RuntimeError("v5.4 identical-bitmap cache branch not found exactly once")
text = text.replace(old, new, 1)

old_log = '''    if (identical_bitmap && deepofc_reacquire_candidate_pending) {
      write_log(true,
        "[OpenOFC REACQUIRE] id=%lu bitmap=IDENTICAL_STABILITY_RECHECK candidate_hits=%d terminal=0\\n",
        deepofc_cycle, deepofc_reacquire_candidate_hits);
    }
    write_log(true,
      "[DeepOFC CYCLE] id=%lu bitmap=%s previous_canonical_valid=%d\\n",
      deepofc_cycle,
      identical_bitmap ? "IDENTICAL_RECHECK" : "CHANGED",
      p_table_state->OFCState()->valid ? 1 : 0);
'''
new_log = '''    if (identical_bitmap && deepofc_reacquire_candidate_pending) {
      write_log(true,
        "[OpenOFC REACQUIRE] id=%lu bitmap=IDENTICAL_STABILITY_RECHECK candidate_hits=%d terminal=0\\n",
        deepofc_cycle, deepofc_reacquire_candidate_hits);
    } else if (identical_bitmap && !deepofc_cached_snapshot_safe) {
      // OPENOFC_IDENTICAL_FAULT_RETRY_V541. An invalid observation is never a
      // cacheable terminal result. Re-run the scraper even on byte-identical
      // pixels: OCR/recognizer state, startup state and cross-frame hypotheses
      // may recover while the client is waiting for Hero and the screen itself
      // remains unchanged.
      write_log(k_always_log_errors,
        "[OpenOFC FAULT_RETRY] id=%lu bitmap=IDENTICAL previous_raw_valid=%d previous_canonical_valid=%d terminal=0 continue_scraping=1\\n",
        deepofc_cycle,
        p_table_state->OFCVisualObservation()->valid ? 1 : 0,
        p_table_state->OFCState()->valid ? 1 : 0);
    }
    write_log(true,
      "[DeepOFC CYCLE] id=%lu bitmap=%s previous_canonical_valid=%d\\n",
      deepofc_cycle,
      identical_bitmap ? "IDENTICAL_RECHECK" : "CHANGED",
      p_table_state->OFCState()->valid ? 1 : 0);
'''
if text.count(old_log) != 1:
    raise RuntimeError("v5.4 identical-bitmap recheck log block not found exactly once")
text = text.replace(old_log, new_log, 1)

if "OPENOFC_IDENTICAL_FAULT_RETRY_V541" not in text:
    raise RuntimeError("identical-fault retry marker was not materialized")

out = text if eol == "\n" else text.replace("\n", "\r\n")
data = out.encode("utf-8")
if bom:
    data = b"\xef\xbb\xbf" + data
PATH.write_bytes(data)
print("OpenOFC v5.4.1 invalid-identical-frame retry patch applied")
