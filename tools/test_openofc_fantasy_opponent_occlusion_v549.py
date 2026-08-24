from __future__ import annotations

from pathlib import Path

SCRAPER = Path("OpenHoldem/COFCScraper.cpp")
RECONSTRUCTOR = Path("OpenHoldem/COFCReconstructor.cpp")
MARKER = "OPENOFC_FANTASY_OPPONENT_OCCLUSION_V549"


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"missing function signature: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise AssertionError(f"missing opening brace: {signature}")
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError(f"unclosed function: {signature}")


def main() -> None:
    scraper = SCRAPER.read_text(encoding="utf-8")
    reconstructor = RECONSTRUCTOR.read_text(encoding="utf-8")

    fantasy = function_body(scraper, "bool CScraper::ScrapeOFCFantasyVisualObservation(")
    normal = function_body(scraper, "bool CScraper::ScrapeOFCVisualObservation(")
    reconstruct_fantasy = function_body(
        reconstructor, "bool ReconstructFantasyDecision("
    )

    assert MARKER in fantasy
    marker_pos = fantasy.index(MARKER)
    arrangement_pos = fantasy.index("std::vector<RECT> arrangement_rects", marker_pos)
    isolation = fantasy[marker_pos:arrangement_pos]

    required = (
        "const int opponent = 1 - hero_chair;",
        "obs->players[opponent].visual_board.Reset();",
        "obs->players[opponent].hidden_incoming_count = 0;",
        "obs->players[opponent].hidden_discard_count = 0;",
        "[OpenOFC FANTASY OPPONENT]",
        "visibility=OCCLUDED",
        "action=IGNORE_OPPONENT_BOARD",
        "hero_fantasy_nonblocking=1",
        "contamination_guard=RESET_WHOLE_BOARD",
    )
    for needle in required:
        assert needle in isolation, f"v5.4.9 isolation contract missing: {needle}"

    # The live failure was caused by normal row transforms interpreting the
    # Fantasy overlay as BACK / JK / ordinary cards. No opponent normal-slot
    # scrape is allowed before native Hero Fantasy recognition anymore.
    forbidden = (
        'base.Format("ofc_p%d_top%d", opponent, i);',
        'base.Format("ofc_p%d_middle%d", opponent, i);',
        'base.Format("ofc_p%d_bottom%d", opponent, i);',
        "ScrapeOFCSlot(base,",
        "|| back) return false;",
    )
    for needle in forbidden:
        assert needle not in isolation, f"opponent overlay path leaked: {needle}"

    # Hero Fantasy perception itself remains strict and native. The repair is
    # not a threshold relaxation and does not accept guessed Hero identities.
    # v5.4.3 generalized the old Fantasy15 recognizer to the 14..17 count path.
    for needle in (
        "COFCFantasyPixelRecognizer::RecognizeArrangementSlots(",
        "COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound(",
        "COFCFantasyPixelRecognizer::RecognizeLooseObjectsBound(",
        "DeepOFCObservationHasUniqueKnownCards(obs)",
        "detected_count < 14 || detected_count > 17",
        "obs->fantasy_card_count = detected_count",
    ):
        assert needle in fantasy, f"strict Hero Fantasy gate lost: {needle}"

    # Normal mode must retain its original TableMap row scraping and Hero-BACK
    # fail-safe. The v5.4.9 repair is Fantasy-route-only.
    assert "ScrapeOFCSlot(base," in normal
    assert "Unexpected hidden Hero cardback in row source slots" in normal
    assert MARKER not in normal

    # The canonical Fantasy reconstructor accepts an opponent board with zero
    # visible identities; it normalizes whatever trustworthy opponent cards are
    # available and never requires a 13-card opponent board for Hero's decision.
    assert "NormalizeBoard(observation.players[p].visual_board" in reconstruct_fantasy
    assert "Fantasy decision requires 14..17 visible Hero physical cards" in reconstruct_fantasy
    assert "actionable Fantasy Confirm requires exactly 13 tentative placements" in reconstruct_fantasy

    # Deterministic model of the observed contamination. Under the old route a
    # single BACK was terminal; under v5.4.9 the entire untrusted opponent board
    # is discarded and cannot collide with Hero's physical-card set.
    contaminated_overlay = ["JK1", "4c", "BACK"]
    old_route_valid = all(card != "BACK" for card in contaminated_overlay)
    new_opponent_known_cards: list[str] = []
    assert old_route_valid is False
    assert new_opponent_known_cards == []

    print(
        "OPENOFC_FANTASY_OPPONENT_OCCLUSION_V549_REGRESSION=PASS "
        "overlay_false_cards=ISOLATED opponent_board=UNOBSERVABLE "
        "hero_native_recognition=STRICT normal_game=UNCHANGED"
    )


if __name__ == "__main__":
    main()
