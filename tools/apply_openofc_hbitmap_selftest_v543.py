from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "OPENOFC_HBITMAP_STANDALONE_PCH_SHIM_V543"


def read_source(path: Path):
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool):
    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def patch_standalone_pch_shim():
    """Make the existing StdAfx include safe for the isolated pixel build.

    The production OpenHoldem project is built with /YuStdAfx.h. Wrapping the
    *include site* in COFCFantasy15PixelRecognizer.cpp inside #ifdef/#else is
    unsafe under MSVC PCH semantics: source before the /Yu include is skipped,
    so the compiler can resume at an unmatched #endif (C1020). Keep the
    recognizer's canonical, unconditional `#include "StdAfx.h"` intact.

    Instead, make StdAfx.h itself expose a tiny Windows-only branch when the
    standalone pixel-test macro is defined. Production never defines that macro
    and therefore sees the byte-for-byte normal OpenHoldem header body.
    """
    recognizer = ROOT / "OpenHoldem/COFCFantasy15PixelRecognizer.cpp"
    rtext, _, _ = read_source(recognizer)
    canonical_include = '#include "StdAfx.h"\n'
    if rtext.count(canonical_include) != 1:
        raise RuntimeError(
            "COFCFantasy15PixelRecognizer.cpp must retain exactly one unconditional StdAfx include"
        )
    if "#ifdef DEEPOFC_FANTASY_PIXEL_STANDALONE" in rtext:
        raise RuntimeError(
            "legacy recognizer-level standalone PCH wrapper survived; production /Yu would be unsafe"
        )

    path = ROOT / "OpenHoldem/stdafx.h"
    text, eol, bom = read_source(path)
    if MARKER in text:
        print("standalone pixel PCH shim already present")
        return

    top_anchor = "#define INC_STDAFX_H\n"
    if text.count(top_anchor) != 1:
        raise RuntimeError("stdafx.h include-guard opening is not unique")
    top = (
        top_anchor
        + "\n// " + MARKER + "\n"
        + "// Isolated real-pixel selftests need only Win32 types. Keeping this\n"
        + "// branch inside StdAfx.h preserves the unconditional /Yu include site\n"
        + "// used by the production OpenHoldem translation unit.\n"
        + "#ifdef DEEPOFC_FANTASY_PIXEL_STANDALONE\n"
        + "#include <Windows.h>\n"
        + "#else\n"
    )
    text = text.replace(top_anchor, top, 1)

    bottom_anchor = "#endif //INC_STDAFX_H"
    if text.count(bottom_anchor) != 1:
        raise RuntimeError("stdafx.h include-guard closing is not unique")
    bottom = (
        "#endif // DEEPOFC_FANTASY_PIXEL_STANDALONE\n\n"
        + bottom_anchor
    )
    text = text.replace(bottom_anchor, bottom, 1)
    write_source(path, text, eol, bom)

    verify, _, _ = read_source(path)
    if MARKER not in verify:
        raise RuntimeError("standalone PCH shim marker missing after write")
    if verify.count("#ifdef DEEPOFC_FANTASY_PIXEL_STANDALONE") != 1:
        raise RuntimeError("standalone PCH shim opening is not unique")
    if verify.count("#endif // DEEPOFC_FANTASY_PIXEL_STANDALONE") != 1:
        raise RuntimeError("standalone PCH shim closing is not unique")
    print("patched StdAfx PCH boundary for isolated HBITMAP/pixel selftests")


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

    recognizer = (ROOT / "OpenHoldem/COFCFantasy15PixelRecognizer.cpp").read_text(
        encoding="utf-8-sig", errors="strict")
    if recognizer.count('#include "StdAfx.h"') != 1:
        raise RuntimeError("production recognizer lost canonical StdAfx include")
    if "#ifdef DEEPOFC_FANTASY_PIXEL_STANDALONE" in recognizer:
        raise RuntimeError("production recognizer contains unsafe PCH include wrapper")

    stdafx = (ROOT / "OpenHoldem/stdafx.h").read_text(
        encoding="utf-8-sig", errors="strict")
    if MARKER not in stdafx:
        raise RuntimeError("StdAfx standalone pixel shim marker missing")

    print("OpenOFC v5.4.3 HBITMAP harness/PCH source contract passed")


if __name__ == "__main__":
    patch_standalone_pch_shim()
    assert_fixture_harness_source()
