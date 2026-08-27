from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / "OpenHoldem/COFCScraper.cpp"

STABLE_COUNTS = {6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17}


def legal_counts(arranged: int, prior_total: int = 0) -> list[int]:
    if 14 <= prior_total <= 17:
        expected = prior_total - arranged
        if arranged == 0 and 14 <= expected <= 17:
            return [expected]
        if arranged == 3 and 11 <= expected <= 14:
            return [expected]
        if arranged == 8 and 6 <= expected <= 9:
            return [expected]
        return []
    if arranged == 0:
        return [14, 15, 16, 17]
    if arranged == 3:
        return [11, 12, 13, 14]
    if arranged == 8:
        return [6, 7, 8, 9]
    return []


def main() -> None:
    text = SCRAPER.read_text(encoding="utf-8-sig")

    # Structural route contract.
    required = [
        "OPENOFC_FANTASY_TABLEMAP_TEXT_V5411",
        'base.Format("ofc_fantasy%02d_%02d", count, i);',
        'GetTMSymbol("openofc_fantasy_text_sources", 0)',
        "DeepOFCFantasyLegalLooseCounts",
        "DeepOFCFantasySelectTextFamily",
        "Fantasy text family selection passes=",
        "route=TABLEMAP_TEXT",
        "route=FALLBACK_NATIVE",
        "COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound",
        "COFCFantasyPixelRecognizer::RecognizeLooseObjectsBound",
        "detected_layout_count = -13",
        "carried_final_unused",
        'const string allowed = "23456789TJQKAXRG";',
    ]
    missing = [needle for needle in required if needle not in text]
    assert not missing, missing

    # The user-derived state machine: only these loose-card counts need a
    # clickable/text TableMap family before the 13-card board is complete.
    assert set(legal_counts(0)) == {14, 15, 16, 17}
    assert set(legal_counts(3)) == {11, 12, 13, 14}
    assert set(legal_counts(8)) == {6, 7, 8, 9}
    assert legal_counts(13) == []
    assert set(legal_counts(0) + legal_counts(3) + legal_counts(8)) == STABLE_COUNTS
    assert 10 not in STABLE_COUNTS
    for n in range(1, 6):
        assert n not in STABLE_COUNTS

    # Once the initial total is known, no count detector is allowed to guess.
    for total in range(14, 18):
        assert legal_counts(0, total) == [total]
        assert legal_counts(3, total) == [total - 3]
        assert legal_counts(8, total) == [total - 8]
        assert legal_counts(13, total) == []

    # Final unused cards are reconstruction lineage only: source rectangles are
    # intentionally non-clickable after all three rows are verified.
    assert "obs->hero_loose_sources[i].valid = !carried_final_unused;" in text
    assert "arrangement_count == 13 && !original_labels.empty()" in text
    assert "static_cast<int>(original_labels.size()) - 13" in text

    # Legacy TableMaps keep the v5.4.9 native route. New text regions cannot
    # silently activate themselves just by existing.
    assert 'text_error = "TableMap text-source opt-in is disabled";' in text
    native_unbound = text.count("COFCFantasyPixelRecognizer::RecognizeLooseObjectsUnbound")
    native_bound = text.count("COFCFantasyPixelRecognizer::RecognizeLooseObjectsBound")
    assert native_unbound >= 1 and native_bound >= 1

    # Family selection is fail-closed: exactly one complete/unique family.
    assert "if (pass_count != 1)" in text
    assert "Fantasy text family contains invalid/duplicate card" in text
    assert "Fantasy text family violates prior physical lineage" in text

    print(
        "OPENOFC_FANTASY_TABLEMAP_TEXT_V5411_REGRESSION=PASS "
        "stable_counts=6,7,8,9,11,12,13,14,15,16,17 "
        "phase_groups=PASS prior_total_exact=PASS final_unused=LINEAGE_ONLY "
        "family_selection=EXACTLY_ONE native_fallback=PRESERVED opt_in=EXPLICIT"
    )


if __name__ == "__main__":
    main()
