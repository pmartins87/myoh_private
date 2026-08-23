from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "OpenHoldem" / "COFCBaselinePolicy.cpp"
SELFTEST = ROOT / "OpenHoldem" / "COFCBaselinePolicySelftest.cpp"


def replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8-sig")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one target, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {path.relative_to(ROOT)}: {label}")


def main() -> None:
    # The real OpenHoldem runtime uses pokereval/include/deck_std.h:
    #   rank = index % 13, suit = index / 13,
    #   card = suit * 13 + rank.
    # The historical standalone test shim accidentally used a rank-major /4
    # layout. That made old standalone tests self-consistent but not bit-for-bit
    # representative of the production card values consumed by OpenOFC.
    replace_exact(
        POLICY,
        "#define StdDeck_RANK(card) ((card) >> 2)\n#define StdDeck_SUIT(card) ((card) & 0x03)\n",
        "#define StdDeck_RANK(card) ((card) % 13)\n#define StdDeck_SUIT(card) ((card) / 13)\n",
        "standalone StdDeck mapping matches production deck_std.h",
    )

    replace_exact(
        SELFTEST,
        "int Card(int rank, int suit) {\n  return (rank - 2) * 4 + suit;\n}\n",
        "int Card(int rank, int suit) {\n  return suit * 13 + (rank - 2);\n}\n",
        "standalone selftest Card() uses production runtime values",
    )

    print("OpenOFC C++ parity materialization: PASS")


if __name__ == "__main__":
    main()
