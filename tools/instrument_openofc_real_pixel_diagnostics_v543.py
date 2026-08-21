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

    helper_marker = "bool CardFromFeature(\n"
    helper = r'''std::string RankCandidateDiagnostic(
    const uint16_t rows[kDeepOFCGlyphHeight],
    bool upright) {
  const COFCRankTemplate *templates = upright
    ? kDeepOFCUprightLargeRankTemplates
    : kDeepOFCFantasy15FanRankTemplates;
  int best_index = -1;
  int second_index = -1;
  double best = std::numeric_limits<double>::infinity();
  double second = std::numeric_limits<double>::infinity();
  for (int i = 0; i < 13; ++i) {
    const double distance = COFCFantasyRecognitionCore::AlignedBinaryDistance(
      rows, templates[i].rows, 2);
    if (distance < best) {
      second = best;
      second_index = best_index;
      best = distance;
      best_index = i;
    } else if (distance < second) {
      second = distance;
      second_index = i;
    }
  }
  std::ostringstream oss;
  if (best_index >= 0) {
    oss << " best_candidate=" << templates[best_index].label
        << " best_distance=" << best;
  }
  if (second_index >= 0) {
    oss << " second_candidate=" << templates[second_index].label
        << " second_distance=" << second
        << " candidate_margin=" << (second - best);
  }
  return oss.str();
}

bool CardFromFeature(
'''
    text = replace_once(text, helper_marker, helper, "rank diagnostic helper")

    old_reject = '''  if (!rank.accepted) {
    std::ostringstream oss;
    oss << "Fantasy rank rejected distance=" << rank.best_distance
        << " margin=" << rank.margin;
    return Fail(error, oss.str());
  }
'''
    new_reject = '''  if (!rank.accepted) {
    std::ostringstream oss;
    oss << "Fantasy rank rejected distance=" << rank.best_distance
        << " margin=" << rank.margin
        << RankCandidateDiagnostic(rows, upright);
    return Fail(error, oss.str());
  }
'''
    text = replace_once(text, old_reject, new_reject, "rank reject diagnostic")

    old_caller = '''      if (!CardFromFeature(
            rows, r, g, b,
            static_cast<int>(rank_points.size()),
            anchor.bounds.Width(),
            anchor.bounds.Height(),
            false, true, &card, &card_error)) {
        return Fail(error, "reflow loose Fantasy card rejected: " + card_error);
      }
'''
    new_caller = '''      if (!CardFromFeature(
            rows, r, g, b,
            static_cast<int>(rank_points.size()),
            anchor.bounds.Width(),
            anchor.bounds.Height(),
            false, true, &card, &card_error)) {
        std::ostringstream oss;
        oss << "reflow loose Fantasy card rejected"
            << " anchor_index=" << i
            << " bounds=" << anchor.bounds.left << "," << anchor.bounds.top
            << "," << anchor.bounds.right << "," << anchor.bounds.bottom
            << " center_x=" << anchor.CenterX()
            << " rank_area=" << rank_points.size()
            << " grid_count=" << fit.count
            << " grid_pitch=" << fit.pitch
            << " grid_residual=" << fit.maximum_residual
            << ": " << card_error;
        return Fail(error, oss.str());
      }
'''
    text = replace_once(text, old_caller, new_caller, "dynamic caller diagnostic")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    PATH.write_bytes(data)
    print("instrumented real-pixel rank/anchor diagnostics")


if __name__ == "__main__":
    main()
