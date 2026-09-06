#!/usr/bin/env python3
"""Remove a light rendered transparency grid connected to the image border."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageDraw
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("Pillow is required: python3 -m pip install Pillow") from exc


def _enclosed_grid_components(
    candidate: Image.Image,
    rgba: Image.Image,
    min_area: int = 180,
    min_neutral_ratio: float = 0.55,
) -> Image.Image:
    """Find rendered checkerboard islands enclosed by limbs or the body.

    The main border flood fill cannot enter spaces surrounded by a pose (for
    example, between a raised arm and the head).  Checkerboard pixels are much
    more often exactly neutral than warm white clothing, so only sufficiently
    large enclosed components with a strong exact-neutral ratio are accepted.
    """

    width, height = candidate.size
    mask = candidate.load()
    pixels = rgba.convert("RGB").load()
    visited = bytearray(width * height)
    enclosed = Image.new("L", candidate.size, 0)
    enclosed_pixels = enclosed.load()

    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or mask[x, y] == 0:
                continue
            stack = [(x, y)]
            visited[index] = 1
            points: list[tuple[int, int]] = []
            touches_edge = False
            exactly_neutral = 0
            while stack:
                current_x, current_y = stack.pop()
                points.append((current_x, current_y))
                if current_x in (0, width - 1) or current_y in (0, height - 1):
                    touches_edge = True
                rgb = pixels[current_x, current_y]
                if max(rgb) - min(rgb) <= 1:
                    exactly_neutral += 1
                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    next_index = next_y * width + next_x
                    if not visited[next_index] and mask[next_x, next_y]:
                        visited[next_index] = 1
                        stack.append((next_x, next_y))

            neutral_ratio = exactly_neutral / len(points)
            if not touches_edge and len(points) >= min_area and neutral_ratio >= min_neutral_ratio:
                for point_x, point_y in points:
                    enclosed_pixels[point_x, point_y] = 255
    return enclosed


def _largest_foreground(alpha: Image.Image) -> Image.Image:
    """Keep the largest connected visible component while preserving soft alpha."""

    width, height = alpha.size
    visible = alpha.point(lambda value: 255 if value else 0)
    pixels = visible.load()
    visited = bytearray(width * height)
    largest: list[tuple[int, int]] = []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or pixels[x, y] == 0:
                continue
            stack = [(x, y)]
            visited[index] = 1
            points: list[tuple[int, int]] = []
            while stack:
                current_x, current_y = stack.pop()
                points.append((current_x, current_y))
                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    next_index = next_y * width + next_x
                    if not visited[next_index] and pixels[next_x, next_y]:
                        visited[next_index] = 1
                        stack.append((next_x, next_y))
            if len(points) > len(largest):
                largest = points

    component = Image.new("L", alpha.size, 0)
    component_pixels = component.load()
    for x, y in largest:
        component_pixels[x, y] = 255
    return ImageChops.multiply(alpha, component)


def repair(
    source: Path,
    output: Path,
    min_channel: int,
    max_chroma: int,
    remove_enclosed_grid: bool,
    seeds: list[tuple[int, int]],
    largest_foreground: bool,
) -> tuple[float, tuple[int, int, int, int]]:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
    red, green, blue, original_alpha = rgba.split()
    darkest = ImageChops.darker(ImageChops.darker(red, green), blue)
    lightest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    chroma = ImageChops.subtract(lightest, darkest)
    bright = darkest.point(lambda value: 255 if value >= min_channel else 0)
    neutral = chroma.point(lambda value: 255 if value <= max_chroma else 0)
    candidate = ImageChops.multiply(bright, neutral)

    connected = candidate.copy()
    if connected.getpixel((0, 0)) == 0:
        raise ValueError("左上角不是浅色网格，拒绝自动移除；请使用定向图像编辑")
    ImageDraw.floodfill(connected, (0, 0), 128, thresh=0)
    background = connected.point(lambda value: 255 if value == 128 else 0)
    if remove_enclosed_grid:
        enclosed = _enclosed_grid_components(candidate, rgba)
        background = ImageChops.lighter(background, enclosed)
    for seed in seeds:
        if not (0 <= seed[0] < rgba.width and 0 <= seed[1] < rgba.height):
            raise ValueError(f"定向种子超出画布：{seed}")
        if candidate.getpixel(seed) == 0:
            raise ValueError(f"定向种子不在浅色网格上：{seed}")
        seeded = candidate.copy()
        ImageDraw.floodfill(seeded, seed, 128, thresh=0)
        region = seeded.point(lambda value: 255 if value == 128 else 0)
        background = ImageChops.lighter(background, region)
    foreground = ImageChops.invert(background)
    alpha = ImageChops.multiply(original_alpha, foreground)
    if largest_foreground:
        alpha = _largest_foreground(alpha)
    visible = alpha.getbbox()
    if visible is None:
        raise ValueError("修复结果没有可见主体")

    total = rgba.width * rgba.height
    values = background.get_flattened_data() if hasattr(background, "get_flattened_data") else background.getdata()
    removed = sum(1 for value in values if value) / total
    if removed < 0.05 or removed > 0.95:
        raise ValueError(f"边缘连通背景占比 {removed:.1%}，超出安全范围")

    clean_rgb = Image.new("RGB", rgba.size, (0, 0, 0))
    clean_rgb.paste(rgba.convert("RGB"), mask=alpha)
    result = clean_rgb.convert("RGBA")
    result.putalpha(alpha)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"输出已存在，拒绝覆盖：{output}")
    result.save(output, format="PNG", optimize=True, compress_level=9)
    return removed, visible


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--min-channel", type=int, default=230)
    parser.add_argument("--max-chroma", type=int, default=14)
    parser.add_argument(
        "--remove-enclosed-grid",
        action="store_true",
        help="also remove strongly neutral checkerboard islands enclosed by the subject",
    )
    parser.add_argument(
        "--seed",
        action="append",
        default=[],
        metavar="X,Y",
        help="remove one enclosed checkerboard region using a precise pixel seed; repeat as needed",
    )
    parser.add_argument(
        "--largest-foreground",
        action="store_true",
        help="discard disconnected edge specks after alpha repair",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        seeds = [tuple(int(value) for value in item.split(",", 1)) for item in args.seed]
        removed, visible = repair(
            args.source,
            args.output,
            args.min_channel,
            args.max_chroma,
            args.remove_enclosed_grid,
            seeds,
            args.largest_foreground,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK: removed={removed:.1%}, visible_bbox={visible}, output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
