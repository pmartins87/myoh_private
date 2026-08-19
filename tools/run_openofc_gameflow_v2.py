from __future__ import annotations

import re

import tools.apply_openofc_gameflow_v2 as gameflow


def regex_once_literal(rel: str, pattern: str, replacement: str, flags=re.S):
    """Apply generated C/C++ replacement literally.

    Python re.sub normally interprets backslash escapes in replacement strings.
    The OpenOFC generator intentionally contains C++ string literals such as
    "\\n"; using a callable replacement preserves those bytes exactly instead
    of turning them into physical newlines inside C++ constants.
    """
    path, text, eol, bom = gameflow.read_source(rel)
    new, count = re.subn(
        pattern,
        lambda _match: replacement,
        text,
        count=1,
        flags=flags,
    )
    if count != 1:
        raise RuntimeError(
            f"{rel}: regex expected one target, got {count}: {pattern[:100]}"
        )
    gameflow.write_source(path, new, eol, bom)
    print(f"patched {rel}")


gameflow.regex_once = regex_once_literal

if __name__ == "__main__":
    gameflow.main()
