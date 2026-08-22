from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_recognizer_standalone_include():
    path = ROOT / "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    old = '#include "StdAfx.h"\n'
    new = '''#ifdef DEEPOFC_FANTASY_PIXEL_STANDALONE\n#include <Windows.h>\n#else\n#include "StdAfx.h"\n#endif\n'''
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"COFCFantasy15PixelRecognizer.cpp: expected one StdAfx include target, got {count}")
    text = text.replace(old, new, 1)

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print("patched native Fantasy recognizer for isolated HBITMAP selftest build")


def assert_fixture_harness_source():
    test = (ROOT / "OpenHoldem/COFCFantasyHBitmapSelftest.cpp").read_text(
        encoding="utf-8-sig", errors="strict")
    for needle in (
        "RecognizeLooseObjectsUnbound",
        "RecognizeArrangementSlots",
        "ReconstructCurrentScreen",
        "field_frame000000_loose.png",
        "field_frame000005_arrangement.png",
        "field_frame000005_loose.png",
        "previous=NULL",
        "dealer_known=0",
    ):
        if needle not in test:
            raise RuntimeError(f"HBITMAP selftest source marker missing: {needle}")
    print("OpenOFC v5.4.3 HBITMAP harness source contract passed")


if __name__ == "__main__":
    patch_recognizer_standalone_include()
    assert_fixture_harness_source()
