#!/usr/bin/env python3
"""Render every GIF frame on a checkerboard contact sheet for visual review."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def checkerboard(size: tuple[int, int], cell: int = 12) -> Image.Image:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle((x, y, min(size[0], x + cell), min(size[1], y + cell)), fill="#E8E8E8")
    return image


def render(gif_path: Path, output_path: Path, columns: int = 4) -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []
    with Image.open(gif_path) as gif:
        for index in range(getattr(gif, "n_frames", 1)):
            gif.seek(index)
            frames.append(gif.convert("RGBA").copy())
            durations.append(int(gif.info.get("duration", 0)))
    tile_width, tile_height = frames[0].width, frames[0].height + 24
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (tile_width * columns, tile_height * rows), "#D8D8D8")
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        tile = checkerboard(frame.size)
        tile.paste(frame.convert("RGB"), mask=frame.getchannel("A"))
        sheet.paste(tile, (x, y))
        draw.text((x + 8, y + frame.height + 5), f"frame {index + 1} · {durations[index]}ms", fill="#222222")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gif_or_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()
    inputs = sorted(args.gif_or_directory.glob("*.gif")) if args.gif_or_directory.is_dir() else [args.gif_or_directory]
    if not inputs:
        raise SystemExit("没有找到GIF")
    for gif_path in inputs:
        render(gif_path, args.output_directory / f"{gif_path.stem}-frames.png", max(1, args.columns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
