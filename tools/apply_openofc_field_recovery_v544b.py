from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "OpenHoldem" / "COFCReconstructor.cpp"


def main():
    raw = PATH.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    old = '''  const set<int> committed = KnownBoardSet(
    p_table_state == NULL ? COFCPlayerBoard()
      : COFCPlayerBoard());
  (void)committed;
'''
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            "v5.4.4B expected one temporary p_table_state dependency, got %d" % count)
    text = text.replace(old, "", 1)

    if "p_table_state == NULL ? COFCPlayerBoard()" in text:
        raise RuntimeError("temporary standalone dependency survived v5.4.4B")

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    PATH.write_bytes(data)
    print("OpenOFC v5.4.4B reconstructor standalone cleanup: PASS")


if __name__ == "__main__":
    main()
