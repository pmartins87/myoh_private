from __future__ import annotations

from pathlib import Path

SCRAPER = Path("OpenHoldem/COFCScraper.cpp")
MARKER = "OPENOFC_FANTASY_OPPONENT_OCCLUSION_V549"
FUNCTION = "bool CScraper::ScrapeOFCFantasyVisualObservation(int player_count, int hero_chair) {"
BOUNDARY = "  const int row_counts[3] = {3, 5, 5};"

REPLACEMENT = r'''  // OPENOFC_FANTASY_OPPONENT_OCCLUSION_V549
  // Live KKPoker evidence proves that normal opponent-row TableMap geometry is
  // not authoritative while Hero is in Fantasy. The Fantasy presentation can
  // cover those rectangles with the FANTASY plaque / card-back-like artwork;
  // feeding those pixels through normal row transforms produced false cards,
  // false Jokers and BACK classifications, rejecting an otherwise detected
  // 15-card Hero Fantasy fan before the native Fantasy recognizer could run.
  //
  // Treat the opponent board as unobservable for the pre-Confirm Hero Fantasy
  // decision. This is deliberately stronger than "ignore only BACK": a frame
  // can manufacture plausible rank/suit identities from the overlay, so a
  // partially accepted opponent board would contaminate uniqueness and policy.
  // Hero Fantasy cards, arrangement geometry, dealer/actor and Confirm remain
  // independently fail-closed below. Normal-game scraping is untouched.
  const int opponent = 1 - hero_chair;
  CString base;
  obs->players[opponent].visual_board.Reset();
  obs->players[opponent].hidden_incoming_count = 0;
  obs->players[opponent].hidden_discard_count = 0;
  write_log(true,
    "[OpenOFC FANTASY OPPONENT] visibility=OCCLUDED "
    "source=NORMAL_TABLEMAP action=IGNORE_OPPONENT_BOARD "
    "hero_fantasy_nonblocking=1 contamination_guard=RESET_WHOLE_BOARD\\n");

'''


def main() -> None:
    if not SCRAPER.exists():
        raise SystemExit(f"materialized source missing: {SCRAPER}")
    text = SCRAPER.read_text(encoding="utf-8")
    if MARKER in text:
        print("COFCScraper.cpp: v5.4.9 Fantasy opponent occlusion already materialized")
        return

    function_start = text.find(FUNCTION)
    if function_start < 0 or text.count(FUNCTION) != 1:
        raise SystemExit("v5.4.9 Fantasy scraper function anchor is missing/non-unique")

    comments = (
        "  // Opponent board geometry is stable while Hero arranges Fantasy.\n",
        "  // Opponent board geometry does not move while Hero arranges Fantasy.\n",
    )
    starts = [text.find(comment, function_start) for comment in comments]
    starts = [pos for pos in starts if pos >= 0]
    if len(starts) != 1:
        raise SystemExit(
            f"v5.4.9 expected one post-generic Fantasy opponent block, got {len(starts)}"
        )
    start = starts[0]
    end = text.find(BOUNDARY, start)
    if end < 0:
        raise SystemExit("v5.4.9 could not find row-count boundary after opponent block")

    old = text[start:end]
    required_old = (
        "const int opponent = 1 - hero_chair;",
        'base.Format("ofc_p%d_top%d", opponent, i);',
        'base.Format("ofc_p%d_middle%d", opponent, i);',
        'base.Format("ofc_p%d_bottom%d", opponent, i);',
        "ScrapeOFCSlot(base,",
        "|| back) return false;",
    )
    for needle in required_old:
        if needle not in old:
            raise SystemExit(f"v5.4.9 opponent block shape changed: missing {needle!r}")

    text = text[:start] + REPLACEMENT + text[end:]
    SCRAPER.write_text(text, encoding="utf-8")
    print(
        "OPENOFC_FANTASY_OPPONENT_OCCLUSION_V549_MATERIALIZATION=PASS "
        "opponent_rows=UNOBSERVABLE hero_fantasy=NONBLOCKING normal_game=UNCHANGED"
    )


if __name__ == "__main__":
    main()
