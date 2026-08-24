from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REL = Path("OpenHoldem/COFCFantasy15PixelRecognizer.cpp")


def main() -> None:
    path = ROOT / REL
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"

    # Fantasy v5 added a one-anchor special case around the original regular
    # grid call. v5.4.10's geometry patch is deliberately written against the
    # canonical original call, so normalize the source shape temporarily and
    # restore the one-anchor semantics after the new geometry contract is in.
    old = r'''  COFCFantasyGridFit fit;
  if (anchors.size() == 1) {
    fit.valid = true;
    fit.count = 1;
    fit.center = anchors[0].CenterX();
    fit.pitch = 0.0;
    fit.maximum_residual = 0.0;
  } else if (!COFCFantasyDynamicGeometry::FitRegularGrid(anchors, &fit, error)) {
    return false;
  }

  std::vector<std::string> labels;
'''
    new = r'''  COFCFantasyGridFit fit;
  if (!COFCFantasyDynamicGeometry::FitRegularGrid(anchors, &fit, error)) return false;

  std::vector<std::string> labels;
'''
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"v5.4.10 PRE expected one Fantasy-v5 grid shape, got {count}")
    text = text.replace(old, new, 1)

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print("OPENOFC_FANTASY_V5410_PRE_GRID_SHAPE=PASS single_anchor=TEMP_NORMALIZED")


if __name__ == "__main__":
    main()
