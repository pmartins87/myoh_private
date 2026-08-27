#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


MAX_SINGLE_CHAR_WIDTH = 31
MAX_SINGLE_CHAR_HEIGHT = 32


def load_tm(path: Path):
    text = path.read_text(encoding="ascii", errors="strict")
    fonts: list[tuple[str, list[int]]] = []
    regions: dict[str, tuple[int, int, int, int]] = {}
    for line in text.splitlines():
        m = re.fullmatch(r"t7\$(.)\s+(.+)", line)
        if m:
            fonts.append((m.group(1), [int(x, 16) for x in m.group(2).split()]))
            continue
        m = re.match(
            r"r\$(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+", line
        )
        if m:
            regions[m.group(1)] = tuple(map(int, m.groups()[1:]))
    return text, fonts, regions


def foreground_mask(image: Image.Image, rect: tuple[int, int, int, int]) -> np.ndarray:
    left, top, right, bottom = rect
    rgb = np.asarray(image.convert("RGB"), dtype=np.int32)[top : bottom + 1, left : right + 1]
    delta = 255 - rgb
    # Win32 GetDIBits returns these replay HBITMAP pixels with zeroed alpha.
    # The TableMap center is ffffffff, so alpha contributes 255^2 to the
    # four-dimensional ARGB distance used by CTransform.
    distance_sq = np.sum(delta * delta, axis=2, dtype=np.int32) + 255 * 255
    return distance_sq > 260.0 * 260.0


def shifted_bits(mask: np.ndarray, left: int, width: int) -> list[int]:
    height, total_width = mask.shape
    right = min(total_width, left + width)
    sub = mask[:, left:right]
    ys, xs = np.nonzero(sub)
    if len(xs) == 0:
        return []
    x_begin = int(xs.min())
    x_end = int(xs.max())
    y_begin = int(ys.min())
    y_end = int(ys.max())
    if y_end - y_begin > MAX_SINGLE_CHAR_HEIGHT:
        y_begin = y_end - MAX_SINGLE_CHAR_HEIGHT
    result: list[int] = []
    for x in range(x_begin, x_end + 1):
        value = 0
        for y in range(y_end, y_begin - 1, -1):
            if sub[y, x]:
                value |= 1 << (y_end - y)
        result.append(value)
    return result


def best_font(mask: np.ndarray, left: int, fonts, tolerance: float = 0.75):
    best = None
    max_width = min(MAX_SINGLE_CHAR_WIDTH, mask.shape[1] - left)
    for trial_width in range(1, max_width + 1):
        observed = shifted_bits(mask, left, trial_width)
        for ch, expected in fonts:
            if len(expected) > trial_width:
                continue
            observed_for_compare = observed + [0] * (len(expected) - len(observed))
            distance = sum(
                (a ^ b).bit_count()
                for a, b in zip(expected, observed_for_compare)
            )
            lit = sum(v.bit_count() for v in expected) + 1e-6
            weighted = (distance + 1e-6) / lit
            if weighted < tolerance and (best is None or weighted < best[0]):
                best = (weighted, ch, len(expected), observed)
    return best


def t7_text(image: Image.Image, rect, fonts, tolerance: float = 0.75):
    mask = foreground_mask(image, rect)
    text = ""
    details = []
    left = 0
    while left < mask.shape[1]:
        while left < mask.shape[1] and not mask[:, left].any():
            left += 1
        if left >= mask.shape[1]:
            break
        best = best_font(mask, left, fonts, tolerance)
        if best is None:
            details.append((left, None))
            left += 1
        else:
            weighted, ch, width, observed = best
            text += ch
            details.append((left, ch, weighted, width, observed))
            left += width
    return text, details, mask


def audit_existing(tm: Path, frame: Path, count: int):
    _, fonts, regions = load_tm(tm)
    image = Image.open(frame)
    for i in range(count):
        row = []
        for kind in ("rank", "suit"):
            name = f"ofc_fantasy{count:02d}_{i:02d}{kind}"
            rect = regions[name]
            text, details, _ = t7_text(image, rect, fonts)
            row.append((name, rect, text, details))
        print(row)


def overlay(tm: Path, frame: Path, count: int, output: Path):
    _, _, regions = load_tm(tm)
    image = Image.open(frame).convert("RGB")
    draw = ImageDraw.Draw(image)
    for i in range(count):
        for kind, color in (("rank", "red"), ("suit", "blue")):
            name = f"ofc_fantasy{count:02d}_{i:02d}{kind}"
            if name in regions:
                draw.rectangle(regions[name], outline=color, width=1)
    image.save(output)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tm", type=Path)
    p.add_argument("frame", type=Path)
    p.add_argument("count", type=int)
    p.add_argument("--overlay", type=Path)
    args = p.parse_args()
    audit_existing(args.tm, args.frame, args.count)
    if args.overlay:
        overlay(args.tm, args.frame, args.count, args.overlay)


if __name__ == "__main__":
    main()
