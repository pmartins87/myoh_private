from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem" / "COFCFantasy15PixelRecognizer.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one target, got {count}")
    return text.replace(old, new, 1)


def main():
    raw = PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    # These constants are stored as float in the frozen generated model. A 1e-9
    # double comparison rejects the literal 0.15f/3.20f representation even when
    # the frozen model is byte-for-byte unchanged. Keep the checksum guard, but
    # compare float thresholds with a tolerance appropriate to their storage.
    old_thresholds = '''  if (std::fabs(deepofc_f15_model::kStandardMaxDistance - 2.25) > 1e-9
      || std::fabs(deepofc_f15_model::kStandardMinMargin - 0.15) > 1e-9
      || std::fabs(deepofc_f15_model::kJokerMinDistance - 3.20) > 1e-9) {
'''
    new_thresholds = '''  if (std::fabs(deepofc_f15_model::kStandardMaxDistance - 2.25) > 1e-6
      || std::fabs(deepofc_f15_model::kStandardMinMargin - 0.15) > 1e-6
      || std::fabs(deepofc_f15_model::kJokerMinDistance - 3.20) > 1e-6) {
'''
    text = replace_once(text, old_thresholds, new_thresholds, "frozen float tolerance")

    old_rank = '''  COFCRecognitionResult rank = COFCFantasyRecognitionCore::ClassifyRank(
    rows,
    upright ? kDeepOFCUprightLargeRankTemplates
            : kDeepOFCFantasy15FanRankTemplates,
    13,
    2,
    upright ? 0.36 : kDeepOFCFanRankMaxDistance,
    upright ? 0.04 : kDeepOFCFanRankMinMargin);
  if (!rank.accepted && !upright && allow_ten_fallback) {
    const COFCRecognitionResult fallback =
      COFCFantasyRecognitionCore::ClassifyRank(
        rows, kDeepOFCUprightLargeRankTemplates, 13, 2, 0.51, 0.10);
    if (fallback.accepted && fallback.label == 'T') rank = fallback;
  }
'''
    new_rank = '''  // KKPoker renders Ten as the two-glyph string "10" in the fanned/reflow
  // layout. Across the supplied real replay corpus, that rank is uniquely a
  // wide+dense rank component (19..24 x 18..24, area 200..280). Single-glyph
  // ranks stay narrower; merged rank+suit columns are taller. Recognize this
  // structural invariant before the one-glyph template bank instead of
  // weakening global distance/margin thresholds for every rank.
  const bool structural_ten = !upright
    && width >= 19 && width <= 24
    && height >= 18 && height <= 24
    && area >= 200 && area <= 280;

  COFCRecognitionResult rank;
  rank.Reset();
  if (structural_ten) {
    rank.accepted = true;
    rank.label = 'T';
    rank.best_distance = COFCFantasyRecognitionCore::AlignedBinaryDistance(
      rows, kDeepOFCFantasy15FanRankTemplates[8].rows, 2);
    rank.second_distance = DBL_MAX;
    rank.margin = 0.0;
    rank.reason = kOFCRecognitionAccepted;
  } else {
    rank = COFCFantasyRecognitionCore::ClassifyRank(
      rows,
      upright ? kDeepOFCUprightLargeRankTemplates
              : kDeepOFCFantasy15FanRankTemplates,
      13,
      2,
      upright ? 0.36 : kDeepOFCFanRankMaxDistance,
      upright ? 0.04 : kDeepOFCFanRankMinMargin);
    if (!rank.accepted && !upright && allow_ten_fallback) {
      const COFCRecognitionResult fallback =
        COFCFantasyRecognitionCore::ClassifyRank(
          rows, kDeepOFCUprightLargeRankTemplates, 13, 2, 0.51, 0.10);
      if (fallback.accepted && fallback.label == 'T') rank = fallback;
    }
  }
'''
    text = replace_once(text, old_rank, new_rank, "structural Ten recognition")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    PATH.write_bytes(data)
    print("applied OpenOFC v5.4.3E real-pixel recognizer fixes")


if __name__ == "__main__":
    main()
