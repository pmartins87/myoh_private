#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from PIL import Image

from calibrate_openofc_fantasy_t7_v550 import foreground_mask, load_tm, t7_text


BEGIN = "// BEGIN OPENOFC_V550_STABLE_REPLAY_T7"
END = "// END OPENOFC_V550_STABLE_REPLAY_T7"

# Only stable, visually audited frames are allowed here. Captures that still
# show the previous loose-card count are deliberately absent.
CALIBRATION = [
    (6, "06 cards/frame000015.bmp", ["Kd", "Qh", "9d", "6h", "4s", "3d"]),
    (6, "06 cards/frame000040.bmp", ["Kh", "Jd", "Tc", "9c", "6h", "5h"]),
    (7, "07 cards/frame000014.bmp", ["As", "Kd", "Qh", "9d", "6h", "4s", "3d"]),
    (7, "07 cards/frame000020.bmp", ["Ad", "Kd", "Tc", "7d", "6s", "3c", "2c"]),
    (8, "08 cards/frame000013.bmp", ["As", "Kd", "Qh", "9d", "6h", "4s", "3d", "2s"]),
    (8, "08 cards/frame000037.bmp", ["Kh", "Jd", "Tc", "9c", "6h", "5h", "3c", "2s"]),
    (9, "09 cards/frame000012.bmp", ["As", "Kd", "Qh", "9d", "6h", "4s", "3d", "2s", "2h"]),
    (9, "09 cards/frame000018.bmp", ["Ad", "Qd", "8h", "7d", "6s", "5h", "5d", "4s", "4h"]),
    (11, "11 cards/frame000009.bmp", ["As", "Kd", "Qh", "9d", "8s", "8h", "6h", "4s", "3d", "2s", "2h"]),
    (12, "12 cards/frame000008.bmp", ["As", "Ac", "Kd", "Qh", "9d", "8s", "8h", "6h", "4s", "3d", "2s", "2h"]),
    (13, "13 cards/frame000007.bmp", ["As", "Ac", "Kd", "Qh", "9c", "9d", "8s", "8h", "6h", "4s", "3d", "2s", "2h"]),
    (14, "14 cards/frame000002.bmp", ["Ad", "Kc", "Qs", "Qc", "Js", "Jh", "Jd", "7h", "6d", "4c", "4d", "3d", "2c", "2d"]),
    (14, "14 cards/frame000027.bmp", ["Ts", "7s", "6s", "3s", "2s", "Ah", "Qh", "2h", "Jc", "6c", "3c", "Ad", "Jd", "2d"]),
    (15, "15 cards/frame000000.bmp", ["JK1", "JK2", "Jh", "Ts", "9s", "9h", "9c", "9d", "8s", "8c", "7h", "7c", "6c", "5h", "3c"]),
    (15, "15 cards/frame000032.bmp", ["Ah", "Ac", "Kh", "Js", "Jd", "Tc", "9s", "9c", "7s", "6s", "6h", "5h", "3s", "3c", "2s"]),
    (15, "15 cards/frame000052.bmp", ["JK1", "JK2", "Ac", "Kd", "Qc", "Qd", "Js", "9s", "9h", "7s", "6h", "4s", "4c", "3s", "2c"]),
    (15, "15 cards/frame000056.bmp", ["JK2", "As", "Ad", "Kd", "Td", "9s", "9h", "9c", "8c", "5h", "4h", "3s", "3h", "2s", "2d"]),
    (15, "15 cards/frame000060.bmp", ["Ac", "Ad", "Qd", "Tc", "8c", "7h", "7c", "6d", "5c", "4h", "4d", "3s", "3c", "3d", "2s"]),
    (16, "16 cards/frame000003.bmp", ["As", "Ac", "Kd", "Qh", "9c", "9d", "8s", "8h", "6h", "5c", "4s", "4c", "3c", "3d", "2s", "2h"]),
]


def normalized_pattern(image: Image.Image, rect) -> tuple[int, ...]:
    mask = foreground_mask(image, rect)
    ys, xs = mask.nonzero()
    if len(xs) == 0:
        raise SystemExit(f"empty T7 calibration crop: {rect}")
    left, right = int(xs.min()), int(xs.max())
    top, bottom = int(ys.min()), int(ys.max())
    if bottom - top > 32:
        top = bottom - 32
    result = []
    for x in range(left, right + 1):
        value = 0
        for y in range(bottom, top - 1, -1):
            if mask[y, x]:
                value |= 1 << (bottom - y)
        result.append(value)
    if len(result) > 31:
        raise SystemExit(f"T7 calibration glyph wider than 31 columns: {rect}")
    return tuple(result)


def card_chars(label: str):
    if label.startswith("JK"):
        return "X", None
    return label[0], label[1]


def collect_patterns(tm: Path, frames_root: Path):
    _, _, regions = load_tm(tm)
    generated: dict[tuple[int, ...], str] = {}
    observations = 0
    for count, relative, labels in CALIBRATION:
        if len(labels) != count:
            raise SystemExit(f"manifest cardinality mismatch: {relative}")
        image = Image.open(frames_root / relative).convert("RGB")
        for index, label in enumerate(labels):
            rank, suit = card_chars(label)
            items = [("rank", rank)]
            if suit is not None:
                items.append(("suit", suit))
            for kind, char in items:
                name = f"ofc_fantasy{count:02d}_{index:02d}{kind}"
                if name not in regions:
                    raise SystemExit(f"missing calibration region: {name}")
                pattern = normalized_pattern(image, regions[name])
                prior = generated.get(pattern)
                if prior is not None and prior != char:
                    raise SystemExit(
                        f"T7 exact-pattern label collision {prior!r}/{char!r} "
                        f"at {relative}:{name}"
                    )
                generated[pattern] = char
                observations += 1
    return generated, observations


def enrich(source: Path, frames_root: Path, output: Path) -> None:
    raw = source.read_bytes()
    had_crlf = b"\r\n" in raw
    text = raw.decode("ascii").replace("\r\n", "\n")
    if BEGIN in text or END in text:
        text = re.sub(
            rf"\n?{re.escape(BEGIN)}.*?{re.escape(END)}\n?",
            "\n",
            text,
            flags=re.DOTALL,
        )
    generated, observations = collect_patterns(source, frames_root)

    existing: dict[tuple[int, ...], str] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"t7\$(.)\s+(.+)", line)
        if match:
            existing[tuple(int(value, 16) for value in match.group(2).split())] = match.group(1)

    additions = []
    reused = 0
    for pattern, char in sorted(generated.items(), key=lambda item: (item[1], item[0])):
        prior = existing.get(pattern)
        if prior is not None:
            if prior != char:
                raise SystemExit(
                    f"new stable replay pattern conflicts with existing T7 {prior!r}/{char!r}"
                )
            reused += 1
            continue
        additions.append(f"t7${char} " + " ".join(f"{value:x}" for value in pattern))

    block = "\n".join(
        [
            BEGIN,
            "// Exact stable-replay glyphs; global T7 tolerance remains 0.75.",
            *additions,
            END,
            "",
        ]
    )
    anchor = "//\n// points\n//"
    if text.count(anchor) != 1:
        raise SystemExit("TableMap points-section anchor missing/duplicated")
    text = text.replace(anchor, block + "\n" + anchor, 1)

    final = text.replace("\n", "\r\n") if had_crlf else text
    output.write_bytes(final.encode("ascii"))

    # Replay-gate the actual fuzzy T7 scan after inserting the new records.
    _, fonts, regions = load_tm(output)
    decoded = 0
    for count, relative, labels in CALIBRATION:
        image = Image.open(frames_root / relative).convert("RGB")
        for index, label in enumerate(labels):
            expected_rank, expected_suit = card_chars(label)
            rank_name = f"ofc_fantasy{count:02d}_{index:02d}rank"
            rank_text, _, _ = t7_text(image, regions[rank_name], fonts)
            if rank_text != expected_rank:
                raise SystemExit(
                    f"T7 replay rank mismatch {relative}:{rank_name} "
                    f"expected={expected_rank} got={rank_text!r}"
                )
            decoded += 1
            if expected_suit is None:
                continue
            suit_name = f"ofc_fantasy{count:02d}_{index:02d}suit"
            suit_text, _, _ = t7_text(image, regions[suit_name], fonts)
            if suit_text != expected_suit:
                raise SystemExit(
                    f"T7 replay suit mismatch {relative}:{suit_name} "
                    f"expected={expected_suit} got={suit_text!r}"
                )
            decoded += 1

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(
        "OPENOFC_V550_STABLE_REPLAY_T7=PASS "
        f"frames={len(CALIBRATION)} observations={observations} "
        f"unique_patterns={len(generated)} added={len(additions)} reused={reused} "
        f"decoded_fields={decoded} tolerance=UNCHANGED_0.75 sha256={digest}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("frames_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    enrich(args.source, args.frames_root, args.output)


if __name__ == "__main__":
    main()
