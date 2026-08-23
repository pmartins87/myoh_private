from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / "OpenHoldem" / "COFCRuntimeController.cpp"
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    marker = "  if (!state.valid || !observation.valid) {\n"
    start = text.rfind(marker)
    if start < 0:
        raise RuntimeError("v5.4.5 pre-normalizer: main Tick invalid-perception guard missing")
    ret = text.find("    return;\n  }\n", start)
    if ret < 0:
        raise RuntimeError("v5.4.5 pre-normalizer: Tick invalid-perception guard terminator missing")
    end = ret + len("    return;\n  }\n")

    old = text[start:end]
    if "INVALID_PERCEPTION" not in old:
        raise RuntimeError(
            "v5.4.5 pre-normalizer: last invalid-state guard is not INVALID_PERCEPTION"
        )

    canonical = '''  if (!state.valid || !observation.valid) {
    write_log(true, "[DeepOFC TICK] action=NONE reason=INVALID_PERCEPTION\\n");
    return;
  }
'''
    text = text[:start] + canonical + text[end:]

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)

    verify = path.read_text(encoding="utf-8-sig")
    if verify.count(canonical) != 1:
        raise RuntimeError("v5.4.5 pre-normalizer: canonical Tick guard not unique after rewrite")
    print("OpenOFC v5.4.5 PRE Tick invalid-perception input normalization: PASS")


if __name__ == "__main__":
    main()
