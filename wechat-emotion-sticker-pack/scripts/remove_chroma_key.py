#!/usr/bin/env python3
"""Convert a uniform vivid-green sticker background to transparent alpha."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageFilter
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("Pillow is required: python3 -m pip install Pillow") from exc


def remove_key(source: Path, output: Path, soft: int, hard: int) -> tuple[float, tuple[int, int, int, int]]:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")

    red, green, blue, original_alpha = rgba.split()
    max_red_blue = ImageChops.lighter(red, blue)
    dominance = ImageChops.subtract(green, max_red_blue)
    enough_green = green.point(lambda value: 255 if value >= 100 else 0)
    keyed_alpha = dominance.point(
        lambda value: 0
        if value >= hard
        else 255
        if value <= soft
        else round((hard - value) * 255 / (hard - soft))
    )
    keyed_alpha = Image.composite(keyed_alpha, Image.new("L", rgba.size, 255), enough_green)
    alpha = ImageChops.multiply(original_alpha, keyed_alpha)
    visible = alpha.getbbox()
    if visible is None:
        raise ValueError("抠图结果没有可见主体")

    corner_dominance = dominance.getpixel((0, 0))
    if corner_dominance < hard:
        raise ValueError("左上角不是足够鲜艳的绿色，拒绝自动键控")

    # Remove green spill only where the key creates partial/zero transparency.
    edge_mask = keyed_alpha.point(lambda value: 255 if value < 255 else 0)
    clean_green = green.copy()
    clean_green.paste(ImageChops.darker(green, max_red_blue), mask=edge_mask)
    clean_rgb = Image.merge("RGB", (red, clean_green, blue))

    # Chroma-background relighting can leave thin yellow-green lines that are
    # still technically opaque.  Neutralize only green/yellow pixels in a
    # narrow band inside the silhouette; warm skin and white cloth stay intact.
    visible_mask = alpha.point(lambda value: 255 if value else 0)
    eroded_mask = visible_mask.filter(ImageFilter.MinFilter(7))
    inner_edge = ImageChops.subtract(visible_mask, eroded_mask)
    clean_pixels = clean_rgb.load()
    edge_pixels = inner_edge.load()
    for y in range(clean_rgb.height):
        for x in range(clean_rgb.width):
            if edge_pixels[x, y] == 0:
                continue
            red_value, green_value, blue_value = clean_pixels[x, y]
            looks_like_spill = (
                green_value > 30
                and blue_value * 5 < green_value * 3
                and green_value * 100 > red_value * 85
            )
            if looks_like_spill:
                clean_pixels[x, y] = (
                    red_value,
                    min(green_value, max(blue_value, round(red_value * 0.72))),
                    blue_value,
                )
    clean_rgb.putalpha(alpha)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"输出已存在，拒绝覆盖：{output}")
    clean_rgb.save(output, format="PNG", optimize=True, compress_level=9)

    total = rgba.width * rgba.height
    flattened = alpha.get_flattened_data() if hasattr(alpha, "get_flattened_data") else alpha.getdata()
    transparent = sum(1 for value in flattened if value == 0) / total
    if transparent < 0.05 or transparent > 0.95:
        raise ValueError(f"透明区域占比 {transparent:.1%}，超出安全范围")
    return transparent, visible


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--soft", type=int, default=24, help="green dominance where feathering begins")
    parser.add_argument("--hard", type=int, default=82, help="green dominance that becomes fully transparent")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        transparent, visible = remove_key(args.source, args.output, args.soft, args.hard)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: transparent={transparent:.1%}, visible_bbox={visible}, output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
