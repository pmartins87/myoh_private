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

    old = r'''  COFCFantasyGridFit fit;
  std::string regular_grid_error;
  if (!COFCFantasyDynamicGeometry::FitRegularGrid(
        anchors, &fit, &regular_grid_error)) {
    bool geometry_recovered = false;
    if (!upright && anchors.size() == 15) {
      std::string fan_error;
      geometry_recovered =
        COFCFantasyDynamicGeometry::FitMeasuredInitialFan15(
          anchors, &fit, &fan_error);
      if (!geometry_recovered && error != NULL)
        *error = regular_grid_error + "; fan15=" + fan_error;
    }
    if (!geometry_recovered && !upright && !original_fantasy_cards.empty()) {
      // Once the exact deal lineage is known, geometry is only a source-object
      // locator. Identity still has to be unique and a subset of the exact
      // physical deal, so a small residual allowance does not create cards.
      geometry_recovered =
        COFCFantasyDynamicGeometry::FitRegularGrid(
          anchors, &fit, error, 24.0, 42.0, 5.5);
    }
    if (!geometry_recovered) {
      if (error != NULL && error->empty()) *error = regular_grid_error;
      return false;
    }
  }

  std::vector<std::string> labels;
'''
    new = r'''  COFCFantasyGridFit fit;
  // OPENOFC_FANTASY_SINGLE_LOOSE_V5 lineage preserved: one remaining loose
  // card is a valid 14-card Fantasy end-state and needs no grid fit.
  if (anchors.size() == 1) {
    fit.valid = true;
    fit.count = 1;
    fit.center = anchors[0].CenterX();
    fit.pitch = 0.0;
    fit.maximum_residual = 0.0;
  } else {
    std::string regular_grid_error;
    if (!COFCFantasyDynamicGeometry::FitRegularGrid(
          anchors, &fit, &regular_grid_error)) {
      bool geometry_recovered = false;
      if (!upright && anchors.size() == 15) {
        std::string fan_error;
        geometry_recovered =
          COFCFantasyDynamicGeometry::FitMeasuredInitialFan15(
            anchors, &fit, &fan_error);
        if (!geometry_recovered && error != NULL)
          *error = regular_grid_error + "; fan15=" + fan_error;
      }
      if (!geometry_recovered && !upright && !original_fantasy_cards.empty()) {
        // Once the exact deal lineage is known, geometry is only a source-object
        // locator. Identity still has to be unique and a subset of the exact
        // physical deal, so a small residual allowance does not create cards.
        geometry_recovered =
          COFCFantasyDynamicGeometry::FitRegularGrid(
            anchors, &fit, error, 24.0, 42.0, 5.5);
      }
      if (!geometry_recovered) {
        if (error != NULL && error->empty()) *error = regular_grid_error;
        return false;
      }
    }
  }

  std::vector<std::string> labels;
'''
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"v5.4.10D expected one patched geometry block, got {count}")
    text = text.replace(old, new, 1)

    out = text if eol == "\n" else text.replace("\n", "\r\n")
    data = out.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    print("OPENOFC_FANTASY_V5410D=PASS single_anchor=RESTORED fan15=PROFILE_FALLBACK")


if __name__ == "__main__":
    main()
