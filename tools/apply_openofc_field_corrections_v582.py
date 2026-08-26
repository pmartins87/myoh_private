from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> tuple[Path, str, str, bytes]:
    path = ROOT / relative
    raw = path.read_bytes()
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    body = raw[len(bom):]
    text = body.decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    return path, text.replace("\r\n", "\n"), eol, bom


def write_text(path: Path, text: str, eol: str, bom: bytes) -> None:
    normalized = text.replace("\r\n", "\n")
    if eol == "\r\n":
        normalized = normalized.replace("\n", "\r\n")
    path.write_bytes(bom + normalized.encode("utf-8"))


def patch_count_alignment() -> None:
    relative = "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    path, text, eol, bom = read_text(relative)
    marker = "OPENOFC_V582_BOUNDED_COUNT_ALIGNMENT"
    if marker in text:
        print(f"{relative}: v5.8.2 count alignment already materialized")
        return

    start = text.find("static double CountTemplateScoreWithSkips(")
    end = text.find("\n\n}  // namespace", start)
    if start < 0 or end < 0:
        raise RuntimeError("v5.5 counted-Fantasy score helpers not found")

    replacement = r'''// OPENOFC_V582_BOUNDED_COUNT_ALIGNMENT
// Field replay 2026-08-25 proved that a real FANTASY 15 fan can yield only
// fourteen rank anchors.  The old selector made any expected_count > observed
// impossible, so one missed rank component permanently suppressed the hand.
// Keep the measured templates and thresholds; change only the correspondence
// problem to an order-preserving bounded alignment: <=1 missed expected anchor
// and <=2 spurious observed anchors.  This is a perception tolerance, not a
// strategic/card-identity guess; T7 still has to identify every selected card.
static const int kFantasyCountMaxMissingAnchors = 1;
static const int kFantasyCountMaxExtraAnchors = 2;
static const double kFantasyCountMissingPenalty = 2.5;
static const double kFantasyCountExtraPenalty = 6.0;

static double BestCountTemplateScore(
    const std::vector<COFCFantasyRankAnchor> &anchors,
    const double (*expected)[2], int expected_count) {
  const int observed = static_cast<int>(anchors.size());
  if (observed <= 0 || observed > 22 || expected_count <= 0 || expected_count > 22)
    return 1e100;

  const double inf = 1e100;
  double dp[23][23][kFantasyCountMaxMissingAnchors + 1]
           [kFantasyCountMaxExtraAnchors + 1];
  for (int a = 0; a <= 22; ++a)
    for (int e = 0; e <= 22; ++e)
      for (int m = 0; m <= kFantasyCountMaxMissingAnchors; ++m)
        for (int x = 0; x <= kFantasyCountMaxExtraAnchors; ++x)
          dp[a][e][m][x] = inf;
  dp[0][0][0][0] = 0.0;

  for (int a = 0; a <= observed; ++a) {
    for (int e = 0; e <= expected_count; ++e) {
      for (int missing = 0; missing <= kFantasyCountMaxMissingAnchors; ++missing) {
        for (int extra = 0; extra <= kFantasyCountMaxExtraAnchors; ++extra) {
          const double current = dp[a][e][missing][extra];
          if (!std::isfinite(current) || current >= inf) continue;
          if (a < observed && e < expected_count) {
            const double dx = anchors[a].CenterX() - expected[e][0];
            const double dy = anchors[a].CenterY() - expected[e][1];
            const double next = current + dx * dx + 0.5 * dy * dy;
            dp[a + 1][e + 1][missing][extra] = std::min(
              dp[a + 1][e + 1][missing][extra], next);
          }
          if (e < expected_count && missing < kFantasyCountMaxMissingAnchors) {
            dp[a][e + 1][missing + 1][extra] = std::min(
              dp[a][e + 1][missing + 1][extra], current);
          }
          if (a < observed && extra < kFantasyCountMaxExtraAnchors) {
            dp[a + 1][e][missing][extra + 1] = std::min(
              dp[a + 1][e][missing][extra + 1], current);
          }
        }
      }
    }
  }

  double best = inf;
  for (int missing = 0; missing <= kFantasyCountMaxMissingAnchors; ++missing) {
    for (int extra = 0; extra <= kFantasyCountMaxExtraAnchors; ++extra) {
      const double squared = dp[observed][expected_count][missing][extra];
      const int matched = expected_count - missing;
      if (!std::isfinite(squared) || squared >= inf || matched <= 0
          || matched != observed - extra) continue;
      const double score = std::sqrt(squared / matched)
        + kFantasyCountMissingPenalty * missing
        + kFantasyCountExtraPenalty * extra;
      best = std::min(best, score);
    }
  }
  return best;
}
'''
    text = text[:start] + replacement + text[end:]
    write_text(path, text, eol, bom)
    print(f"patched {relative}: bounded order-preserving count alignment")


def patch_fresh_fantasy_bootstrap() -> None:
    relative = "OpenHoldem/COFCScraper.cpp"
    path, text, eol, bom = read_text(relative)
    marker = "OPENOFC_V582_EMPTY_ARRANGEMENT_BOOTSTRAP"
    if marker in text:
        print(f"{relative}: v5.8.2 empty-arrangement bootstrap already materialized")
        return

    old = r'''  } else {
    if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
          _entire_window_cur, arrangement_rects,
          &occupied, &arrangement_cards, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V550] initial arrangement rejected error=%s terminal=0\n",
        recognition_error.c_str());
      return false;
    }
  }
'''
    new = r'''  } else {
    // OPENOFC_V582_EMPTY_ARRANGEMENT_BOOTSTRAP
    // Fresh Fantasy starts with an empty 3/5/5 board.  Requiring thirteen
    // rank identities before reading the fan made harmless animation/background
    // ink in an empty slot fatal.  Occupancy is the only fact needed here.
    if (!COFCFantasyPixelRecognizer::RecognizeArrangementOccupancy(
          _entire_window_cur, arrangement_rects,
          &occupied, &recognition_error)) {
      write_log(k_always_log_errors,
        "[OpenOFC FANTASY V582] bootstrap occupancy rejected error=%s terminal=0\n",
        recognition_error.c_str());
      return false;
    }
    int bootstrap_occupied = 0;
    for (size_t i = 0; i < occupied.size(); ++i)
      if (occupied[i]) ++bootstrap_occupied;
    if (bootstrap_occupied == 0) {
      arrangement_cards.assign(
        arrangement_rects.size(), COFCFantasyPixelCard());
      write_log(true,
        "[OpenOFC FANTASY V582] bootstrap arrangement=EMPTY identity_scan=SKIPPED\n");
    } else {
      // A non-empty board without lineage remains strict/fail-closed.  We only
      // relax the visually empty fresh-hand case proven by the field replay.
      if (!COFCFantasyPixelRecognizer::RecognizeArrangementSlots(
            _entire_window_cur, arrangement_rects,
            &occupied, &arrangement_cards, &recognition_error)) {
        write_log(k_always_log_errors,
          "[OpenOFC FANTASY V582] nonempty bootstrap arrangement rejected error=%s terminal=0\n",
          recognition_error.c_str());
        return false;
      }
    }
  }
'''
    if text.count(old) != 1:
        raise RuntimeError("v5.5 fresh Fantasy arrangement bootstrap block not found")
    text = text.replace(old, new, 1)
    write_text(path, text, eol, bom)
    print(f"patched {relative}: occupancy-first fresh Fantasy bootstrap")


def patch_runtime_new_hand_release() -> None:
    relative = "OpenHoldem/COFCRuntimeController.cpp"
    path, text, eol, bom = read_text(relative)
    marker = "OPENOFC_V582_FANTASY_NEW_HAND_RELEASE"
    if marker in text:
        print(f"{relative}: v5.8.2 Fantasy new-hand release already materialized")
        return

    old = r'''  const bool initial_fantasy = state.players[state.hero_chair].fantasy
    && state.round_index == -1 && PendingCount(state) == 0
    && state.hero_incoming_count == 15;
'''
    new = r'''  // OPENOFC_V582_FANTASY_NEW_HAND_RELEASE
  // A reconstructed fresh Fantasy state can already contain the 13 pending
  // target placements.  PendingCount==0 therefore made an old blocked/result
  // transaction absorb the next Fantasy hand.  New-hand identity comes from
  // an empty Hero board + a legal 14..17 Fantasy packet + changed incoming
  // signature; pending work is deliberately not part of the gate.
  const int fantasy_count = state.hero_incoming_count;
  const bool initial_fantasy = state.players[state.hero_chair].fantasy
    && state.round_index == -1
    && state.players[state.hero_chair].board.CountKnownCards() == 0
    && fantasy_count >= 14 && fantasy_count <= 17;
'''
    if text.count(old) != 1:
        raise RuntimeError("runtime fresh-Fantasy new-hand gate not found")
    text = text.replace(old, new, 1)
    write_text(path, text, eol, bom)
    print(f"patched {relative}: stale runtime transaction releases on fresh F14..F17")


def main() -> None:
    patch_count_alignment()
    patch_fresh_fantasy_bootstrap()
    patch_runtime_new_hand_release()
    print(
        "OPENOFC_V582_MATERIALIZATION=PASS "
        "count_alignment=MISSING1_EXTRA2 "
        "bootstrap=EMPTY_OCCUPANCY_FIRST "
        "runtime_new_fantasy=F14_17_SEMANTIC_RELEASE "
        "tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
