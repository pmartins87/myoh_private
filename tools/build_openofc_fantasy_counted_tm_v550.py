#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import math
import re
from pathlib import Path


COUNTS = (6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17)

# Same count templates compiled into OpenOFC v5.5.0. Counts 6..16 are
# field-measured; count 17 is an interpolation and remains runtime-disabled.
TEMPLATES = {
    6: [(129.0, 667.5), (160.0, 664.0), (194.0, 661.5), (226.5, 661.0), (259.0, 662.0), (292.0, 664.0)],
    7: [(113.5, 671.0), (145.0, 666.0), (177.5, 662.0), (210.5, 660.5), (243.0, 660.5), (275.0, 663.0), (308.0, 666.0)],
    8: [(97.0, 674.0), (128.0, 668.0), (161.0, 664.0), (194.0, 661.5), (226.5, 661.0), (259.0, 662.0), (292.0, 664.0), (323.5, 668.5)],
    9: [(81.5, 678.0), (113.0, 670.5), (144.5, 666.0), (177.0, 662.0), (210.5, 660.5), (242.5, 661.0), (275.5, 663.0), (306.5, 666.0), (340.0, 672.0)],
    11: [(50.5, 686.5), (80.5, 677.0), (112.0, 671.0), (145.0, 666.0), (177.5, 661.5), (210.5, 661.0), (243.0, 661.0), (274.5, 663.0), (308.0, 666.0), (339.5, 671.5), (373.0, 678.5)],
    12: [(35.0, 691.5), (66.0, 681.5), (96.5, 673.5), (128.5, 668.0), (161.5, 664.0), (194.0, 660.5), (226.5, 660.5), (259.5, 662.0), (290.5, 664.5), (324.5, 669.0), (355.5, 675.0), (388.5, 682.5)],
    13: [(29.5, 693.0), (59.5, 683.5), (87.5, 676.0), (118.0, 670.0), (150.0, 667.0), (179.5, 662.5), (210.0, 660.5), (241.5, 661.0), (271.5, 663.0), (301.5, 665.5), (333.5, 670.0), (362.5, 676.5), (394.0, 684.0)],
    14: [(29.5, 693.5), (55.5, 684.5), (83.0, 677.0), (110.5, 671.0), (138.5, 666.0), (168.0, 663.0), (196.0, 661.5), (224.5, 660.5), (253.0, 662.0), (281.5, 663.5), (307.5, 669.0), (337.0, 671.0), (366.0, 677.0), (394.0, 684.0)],
    15: [(29.5, 693.5), (55.0, 685.5), (79.5, 678.5), (105.0, 672.0), (131.0, 668.0), (157.0, 664.0), (183.5, 662.0), (210.5, 661.0), (237.0, 661.0), (263.5, 661.5), (289.5, 664.5), (316.0, 667.0), (341.5, 672.0), (368.5, 677.0), (392.5, 684.0)],
    16: [(29.5, 693.0), (53.5, 685.5), (75.5, 678.5), (100.0, 673.0), (124.0, 669.0), (148.5, 665.5), (173.0, 662.5), (197.5, 661.5), (222.5, 661.0), (247.5, 661.0), (270.5, 663.0), (295.5, 665.0), (321.0, 668.0), (345.5, 672.0), (368.5, 678.0), (394.0, 684.0)],
    17: [(29.5, 693.0), (52.0, 685.969), (72.75, 679.375), (95.406, 674.031), (118.0, 670.0), (140.844, 666.594), (163.812, 663.625), (186.781, 661.938), (210.0, 661.25), (233.438, 661.0), (256.125, 661.75), (278.312, 663.625), (301.875, 665.75), (325.594, 668.75), (348.375, 672.75), (370.094, 678.375), (394.0, 684.0)],
}

REGION_RE = re.compile(
    r"^r\$(ofc_fantasy(\d{2})_(\d{2})(rank|suit))\s+"
    r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+.*$"
)


def iround(value: float) -> int:
    return int(math.floor(value + 0.5))


def interpolate(values: list[float], position: float) -> float:
    if position <= 0:
        return values[0]
    if position >= len(values) - 1:
        return values[-1]
    lo = int(math.floor(position))
    hi = lo + 1
    fraction = position - lo
    return values[lo] * (1.0 - fraction) + values[hi] * fraction


def parse_verified_15(text: str):
    result: dict[tuple[int, str], tuple[int, int, int, int]] = {}
    for line in text.splitlines():
        match = REGION_RE.match(line)
        if not match or int(match.group(2)) != 15:
            continue
        index = int(match.group(3))
        kind = match.group(4)
        result[(index, kind)] = tuple(map(int, match.groups()[4:8]))
    expected = {(i, kind) for i in range(15) for kind in ("rank", "suit")}
    if set(result) != expected:
        missing = sorted(expected - set(result))
        raise SystemExit(f"source TM lacks verified Fantasy-15 fields: {missing}")
    return result


def source_offsets(verified_15, kind: str):
    offsets = [[], [], [], []]
    for i, (cx, cy) in enumerate(TEMPLATES[15]):
        rect = verified_15[(i, kind)]
        offsets[0].append(rect[0] - cx)
        offsets[1].append(rect[1] - cy)
        offsets[2].append(rect[2] - cx)
        offsets[3].append(rect[3] - cy)
    return offsets


def derived_rect(count: int, index: int, kind: str, verified_15, offsets):
    if count == 15:
        return verified_15[(index, kind)]
    cx, cy = TEMPLATES[count][index]
    position = 0.0 if count == 1 else index * 14.0 / (count - 1)
    return (
        iround(cx + interpolate(offsets[kind][0], position)),
        iround(cy + interpolate(offsets[kind][1], position)),
        iround(cx + interpolate(offsets[kind][2], position)),
        iround(cy + interpolate(offsets[kind][3], position)),
    )


def counted_region_block(verified_15) -> str:
    offsets = {
        kind: source_offsets(verified_15, kind) for kind in ("rank", "suit")
    }
    lines = [
        "//",
        "// OpenOFC v5.5.0 counted Fantasy text regions",
        "// 06..16: field-measured fan centers; T7 boxes inherit the verified",
        "// Fantasy-15 rotation envelope. 17 is interpolated and fail-closed.",
        "//",
        "",
    ]
    for count in COUNTS:
        lines.append(f"// loose count {count:02d}")
        for index in range(count):
            for kind in ("rank", "suit"):
                left, top, right, bottom = derived_rect(
                    count, index, kind, verified_15, offsets
                )
                lines.append(
                    f"r$ofc_fantasy{count:02d}_{index:02d}{kind} "
                    f"{left:3d} {top:3d} {right:3d} {bottom:3d} "
                    "ffffffff -260 T7 1   0 0   0 -1"
                )
        lines.append("")
    return "\n".join(lines)


def replace_symbol(text: str, name: str, value: str) -> str:
    pattern = re.compile(rf"^s\${re.escape(name)}\s+.*$", re.MULTILINE)
    line = f"s${name:<28} {value}"
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    anchor = "s$openofc_fantasy_dynamic_sources 1"
    if anchor not in text:
        raise SystemExit(f"string insertion anchor missing for {name}")
    return text.replace(anchor, anchor + "\n" + line, 1)


def build(source: Path, output: Path) -> None:
    raw = source.read_bytes()
    had_crlf = b"\r\n" in raw
    text = raw.decode("ascii").replace("\r\n", "\n")
    verified_15 = parse_verified_15(text)

    text = replace_symbol(text, "openofc_fantasy_tablemap_text_by_count", "1")
    text = replace_symbol(text, "openofc_fantasy17_calibrated", "0")
    text = replace_symbol(text, "ofc_tablemap_stage", "openofc_v5_5_0_counted_text_field_test")
    text = replace_symbol(text, "openofc_field_revision", "55")

    lines = text.splitlines()
    filtered = [line for line in lines if not REGION_RE.match(line)]
    insertion_index = next(
        i for i, line in enumerate(filtered)
        if line.startswith("r$ofc_fantasy15_arrange_bottom0 ")
    )
    block = counted_region_block(verified_15).splitlines()
    filtered[insertion_index:insertion_index] = block
    output_text = "\n".join(filtered) + "\n"

    # Structural fail-closed audit.
    found: dict[tuple[int, int, str], tuple[int, int, int, int]] = {}
    names: set[str] = set()
    for line in output_text.splitlines():
        match = REGION_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        if name in names:
            raise SystemExit(f"duplicate counted region: {name}")
        names.add(name)
        key = (int(match.group(2)), int(match.group(3)), match.group(4))
        found[key] = tuple(map(int, match.groups()[4:8]))
    expected = {
        (count, index, kind)
        for count in COUNTS
        for index in range(count)
        for kind in ("rank", "suit")
    }
    if set(found) != expected:
        raise SystemExit(
            f"counted region mismatch missing={sorted(expected-set(found))} "
            f"extra={sorted(set(found)-expected)}"
        )
    for (count, index, kind), rect in found.items():
        left, top, right, bottom = rect
        if not (0 <= left <= right < 450 and 0 <= top <= bottom < 830):
            raise SystemExit(f"out-of-bounds region {(count,index,kind)}={rect}")
    for i in range(15):
        for kind in ("rank", "suit"):
            if found[(15, i, kind)] != verified_15[(i, kind)]:
                raise SystemExit(f"verified Fantasy-15 region changed: {i}/{kind}")
    if output_text.count("s$openofc_fantasy_tablemap_text_by_count 1") != 1:
        raise SystemExit("counted-text opt-in missing/duplicated")
    if output_text.count("s$openofc_fantasy17_calibrated 0") != 1:
        raise SystemExit("Fantasy 17 must remain exactly once and disabled")

    final = output_text.replace("\n", "\r\n") if had_crlf else output_text
    output.write_bytes(final.encode("ascii"))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(
        "OPENOFC_V550_COUNTED_TM=PASS "
        f"regions={len(found)} counts={','.join(map(str, COUNTS))} "
        "fantasy15=BYTE_COORDINATES_PRESERVED fantasy17=FAIL_CLOSED "
        f"sha256={digest}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source, args.output)


if __name__ == "__main__":
    main()
