from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_source(relative: str):
    path = ROOT / relative
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")
    eol = "\r\n" if b"\r\n" in raw else "\n"
    return path, text, eol, bom


def write_source(path: Path, text: str, eol: str, bom: bool) -> None:
    output = text if eol == "\n" else text.replace("\n", "\r\n")
    data = output.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path, text, eol, bom = read_source(relative)
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{relative}: {label} expected exactly one target, got {count}"
        )
    write_source(path, text.replace(old, new, 1), eol, bom)
    print(f"patched {relative}: {label}", flush=True)


def main() -> None:
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        "engine=HYBRID_EXACT_R4_V560",
        "engine=EXACT_FANTASY_R4_V570",
        "publish v5.7.0 composed policy engine",
    )
    replace_once(
        "OpenHoldem/COFCRuntimeController.cpp",
        """  if (policy_report.exact_r4_attempted) {
""",
        """  if (policy_report.exact_fantasy_attempted) {
    write_log(true,
      "[OpenOFC EXACT FANTASY] available=%d applied=%d incoming=%d "
      "mask_pairs=%llu legal=%llu universal=%llu "
      "baseline_royalties=%d selected_royalties=%d "
      "baseline_refantasy=%d selected_refantasy=%d reason=\\\"%s\\\"\\n",
      policy_report.exact_fantasy.exact_available ? 1 : 0,
      policy_report.exact_fantasy.applied ? 1 : 0,
      policy_report.exact_fantasy.incoming_count,
      policy_report.exact_fantasy.mask_pairs,
      policy_report.exact_fantasy.legal_boards,
      policy_report.exact_fantasy.universal_improvements,
      policy_report.exact_fantasy.baseline_royalties,
      policy_report.exact_fantasy.selected_royalties,
      policy_report.exact_fantasy.baseline_refantasy ? 1 : 0,
      policy_report.exact_fantasy.selected_refantasy ? 1 : 0,
      policy_report.exact_fantasy_reason.c_str());
  }
  if (policy_report.exact_r4_attempted) {
""",
        "add exact Fantasy search telemetry",
    )
    print(
        "OPENOFC_EXACT_FANTASY_V570_APPLY=PASS "
        "engine=EXACT_FANTASY_R4_V570 tablemap=UNCHANGED"
    )


if __name__ == "__main__":
    main()
