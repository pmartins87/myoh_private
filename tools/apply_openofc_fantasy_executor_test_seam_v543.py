from __future__ import print_function

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'OpenHoldem' / 'COFCFantasyBatchExecutor.cpp'


def require_once(text, old, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit('%s: expected one target, got %d' % (label, count))
    return text.replace(old, '', 1)


def main():
    text = PATH.read_text(encoding='utf-8-sig')

    # The execution gate must exercise the v5.4.3 non-absorbing transaction
    # semantics, never the older kBlocked executor.
    if 'kBlocked' in text:
        raise SystemExit('execution test seam requires v5.4.3 generic non-absorbing executor')
    if 'OPENOFC_FANTASY_SOURCE_IDENTITY_V543G' not in text:
        raise SystemExit('execution test seam requires v5.4.3G source-identity hardening')

    text = text.replace(
        '#include "StdAfx.h"\n',
        '#include <Windows.h>\n\nstatic const bool k_always_log_errors = true;\n'
        'static void write_log(bool, const char *, ...) {}\n',
        1)
    text = text.replace('#include "CCasinoInterface.h"\n', '', 1)
    text = text.replace('#include "..\\CTablemap\\CTablemap.h"\n', '', 1)

    anchor = 'using namespace std;\n\n'
    hooks = '''using namespace std;\n\n// Test-only transaction boundary. Production logic above this boundary is not\n// changed; CI substitutes only mouse/TableMap I/O so no real cursor can move.\nextern bool DeepOFCTestFantasyResolveRowActionRect(EOFCRow row, RECT *out);\nextern bool DeepOFCTestFantasyClickRect(RECT rect);\nextern bool DeepOFCTestFantasyClickRects(const std::vector<RECT> &rects, int gap_ms);\nextern int DeepOFCTestFantasySelectGapMs();\n\n'''
    if text.count(anchor) != 1:
        raise SystemExit('using-namespace seam anchor missing')
    text = text.replace(anchor, hooks, 1)

    pattern = re.compile(
        r'bool COFCFantasyBatchExecutor::ResolveRowActionRect\(\n'
        r'    EOFCRow row, RECT \*out, string \*error\) const \{.*?\n\}\n\n'
        r'bool COFCFantasyBatchExecutor::ResolveLooseSource',
        re.S)
    replacement = '''bool COFCFantasyBatchExecutor::ResolveRowActionRect(\n    EOFCRow row, RECT *out, string *error) const {\n  if (out == NULL || !DeepOFCTestFantasyResolveRowActionRect(row, out)) {\n    if (error != NULL) *error = "test seam could not resolve Fantasy row-action rectangle";\n    return false;\n  }\n  if (out->right <= out->left || out->bottom <= out->top) {\n    if (error != NULL) *error = "Fantasy row-action rectangle is empty";\n    return false;\n  }\n  return true;\n}\n\nbool COFCFantasyBatchExecutor::ResolveLooseSource'''
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise SystemExit('ResolveRowActionRect test seam replacement failed')

    for old, label in [
        ('''  if (p_casino_interface == NULL) {\n    return Fail(error, "casino interface unavailable for Fantasy row clear");\n  }\n''', 'clear casino guard'),
        ('''  if (p_casino_interface == NULL) {\n    return Fail(error, "casino interface unavailable for Fantasy row batch");\n  }\n''', 'batch casino guard')]:
        count = text.count(old)
        if count != 1:
            raise SystemExit('%s: expected one target, got %d' % (label, count))
        text = text.replace(old, '', 1)

    old = '  SetRectEmpty(out);\n'
    new = '  out->left = out->top = out->right = out->bottom = 0;\n'
    if text.count(old) != 1:
        raise SystemExit('SetRectEmpty seam anchor missing')
    text = text.replace(old, new, 1)

    old = '  if (!p_casino_interface->ClickRectSafely(action)) {\n'
    new = '  if (!DeepOFCTestFantasyClickRect(action)) {\n'
    if text.count(old) != 1:
        raise SystemExit('single-click seam anchor missing')
    text = text.replace(old, new, 1)

    old = '''  const int gap_ms = p_tablemap == NULL\n    ? 110 : max(60, p_tablemap->GetTMSymbol("ofc_fantasy_select_gap_ms", 110));\n'''
    new = '''  const int gap_ms = max(60, DeepOFCTestFantasySelectGapMs());\n'''
    if text.count(old) != 1:
        raise SystemExit('select-gap seam anchor missing')
    text = text.replace(old, new, 1)

    old = '  if (!p_casino_interface->ClickRectsSafely(clicks, gap_ms)) {\n'
    new = '  if (!DeepOFCTestFantasyClickRects(clicks, gap_ms)) {\n'
    if text.count(old) != 1:
        raise SystemExit('batch-click seam anchor missing')
    text = text.replace(old, new, 1)

    if 'p_casino_interface' in text or 'p_tablemap' in text:
        raise SystemExit('real mouse/TableMap dependency survived test seam')

    PATH.write_text(text, encoding='utf-8')
    print('OpenOFC Fantasy execution test seam installed; real cursor I/O disabled')


if __name__ == '__main__':
    main()
