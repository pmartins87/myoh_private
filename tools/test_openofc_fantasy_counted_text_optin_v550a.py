from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    assert start >= 0, signature
    brace = text.find('{', start)
    assert brace >= 0
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError('unclosed function')


def main() -> None:
    scraper = (ROOT / 'OpenHoldem/COFCScraper.cpp').read_text(encoding='utf-8-sig')
    fantasy = function_body(
        scraper, 'bool CScraper::ScrapeOFCFantasyVisualObservation(')
    assert 'OPENOFC_FANTASY_COUNTED_TEXT_V550A' in fantasy
    assert 'openofc_fantasy_tablemap_text_by_count' in fantasy
    assert 'counted-text TableMap opt-in missing terminal=0' in fantasy
    optin = fantasy.find('openofc_fantasy_tablemap_text_by_count')
    first_identity = fantasy.find('ofc_fantasy%02d_%02d')
    assert optin >= 0 and first_identity > optin
    print(
        'OPENOFC_FANTASY_COUNTED_TEXT_V550A_REGRESSION=PASS '
        'tablemap_opt_in=EXPLICIT missing=FAIL_CLOSED'
    )


if __name__ == '__main__':
    main()
