#!/usr/bin/env python3
"""Render an enlarged frame sheet around rigged details such as tails or tears."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def _feature_box(
    root: Path,
    stem: str,
    size: tuple[int, int],
    part_names: list[str],
    pad: float,
    extend_bottom: float,
) -> tuple[int, int, int, int]:
    rig = json.loads((root / "animation-rig.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    points = rig["expressions"][stem]["points"]
    record = next(item for item in manifest["expressions"] if str(item["number"]) == stem)
    left, top, right, bottom = tuple(record["motion"]["subject_bbox"])
    subject_width, subject_height = right - left, bottom - top
    subject_long_edge = max(subject_width, subject_height)
    missing = [name for name in part_names if name not in points]
    if missing:
        raise ValueError(f"{stem} 缺少绑定点: {', '.join(missing)}")

    bounds: list[tuple[float, float, float]] = []
    for name in part_names:
        point = points[name]
        bounds.append((
            left + float(point["x"]) * subject_width,
            top + float(point["y"]) * subject_height,
            float(point.get("r", 0.06)) * subject_long_edge,
        ))
    x0 = min(x - radius for x, _, radius in bounds) - pad
    y0 = min(y - radius for _, y, radius in bounds) - pad
    x1 = max(x + radius for x, _, radius in bounds) + pad
    y1 = max(y + radius for _, y, radius in bounds) + pad + extend_bottom
    return (
        max(0, round(x0)),
        max(0, round(y0)),
        min(size[0], round(x1)),
        min(size[1], round(y1)),
    )


def render(
    gif_path: Path,
    output_path: Path,
    part_names: list[str],
    scale: int,
    columns: int,
    pad: float,
    extend_bottom: float,
) -> None:
    root = gif_path.parent.parent
    frames: list[Image.Image] = []
    durations: list[int] = []
    with Image.open(gif_path) as gif:
        box = _feature_box(root, gif_path.stem, gif.size, part_names, pad, extend_bottom)
        for index in range(getattr(gif, "n_frames", 1)):
            gif.seek(index)
            crop = gif.convert("RGBA").crop(box)
            frames.append(crop.resize(
                (crop.width * scale, crop.height * scale),
                Image.Resampling.NEAREST,
            ))
            durations.append(int(gif.info.get("duration", 0)))

    tile_width, tile_height = frames[0].width, frames[0].height + 22
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (tile_width * columns, tile_height * rows), "#D8D8D8")
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        background = Image.new("RGB", frame.size, "#F2F2F2")
        background.paste(frame.convert("RGB"), mask=frame.getchannel("A"))
        sheet.paste(background, (x, y))
        draw.text((x + 6, y + frame.height + 4), f"{index + 1} / {durations[index]}ms", fill="#222222")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gif", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--parts", required=True, help="逗号分隔的绑定点名称")
    parser.add_argument("--scale", type=int, default=6)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--pad", type=float, default=14.0)
    parser.add_argument("--extend-bottom", type=float, default=0.0)
    args = parser.parse_args()
    parts = [part.strip() for part in args.parts.split(",") if part.strip()]
    if not parts:
        raise SystemExit("--parts 至少需要一个绑定点")
    render(
        args.gif,
        args.output,
        parts,
        max(1, args.scale),
        max(1, args.columns),
        max(0.0, args.pad),
        max(0.0, args.extend_bottom),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
