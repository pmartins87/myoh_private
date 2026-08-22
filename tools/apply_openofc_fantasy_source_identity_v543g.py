from __future__ import print_function

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = Path('OpenHoldem') / 'COFCFantasyBatchExecutor.cpp'


def main():
    path = ROOT / REL
    text = path.read_text(encoding='utf-8-sig')
    old = '''  const COFCVisualCardSource &source = observation.hero_loose_sources[index];\n  if (!source.valid || source.rect.right <= source.rect.left\n      || source.rect.bottom <= source.rect.top) {\n    if (error != NULL) *error = "Fantasy loose source has no click-safe fresh rectangle";\n    return false;\n  }\n'''
    new = '''  const COFCVisualCardSource &source = observation.hero_loose_sources[index];\n  // OPENOFC_FANTASY_SOURCE_IDENTITY_V543G: geometry and identity are one\n  // fresh-observation tuple. Never click a rectangle whose source metadata no\n  // longer names the physical card observed at the same index. This matters\n  // especially for the two distinct physical Jokers (JK1/JK2).\n  if (source.card_value != observation.hero_loose_cards[index].value) {\n    if (error != NULL) *error = "Fantasy loose source/card identity metadata mismatch";\n    return false;\n  }\n  if (!source.valid || source.rect.right <= source.rect.left\n      || source.rect.bottom <= source.rect.top) {\n    if (error != NULL) *error = "Fantasy loose source has no click-safe fresh rectangle";\n    return false;\n  }\n'''
    count = text.count(old)
    if count != 1:
        raise SystemExit('expected one ResolveLooseSource identity anchor, got %d' % count)
    text = text.replace(old, new, 1)
    path.write_text(text, encoding='utf-8')

    verify = path.read_text(encoding='utf-8')
    marker = 'OPENOFC_FANTASY_SOURCE_IDENTITY_V543G'
    if marker not in verify:
        raise SystemExit('v5.4.3G source identity marker missing after patch')
    print('OpenOFC v5.4.3G Fantasy source-identity hardening applied successfully')


if __name__ == '__main__':
    main()
