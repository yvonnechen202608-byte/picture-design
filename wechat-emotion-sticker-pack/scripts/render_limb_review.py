#!/usr/bin/env python3
"""Render enlarged shoulder-to-hand crops from sticker GIFs for limb QA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def _absolute_point(
    point: dict[str, float],
    subject_bbox: tuple[float, float, float, float],
) -> tuple[float, float]:
    left, top, right, bottom = subject_bbox
    return (
        left + float(point["x"]) * (right - left),
        top + float(point["y"]) * (bottom - top),
    )


def _limb_box(
    root: Path,
    stem: str,
    size: tuple[int, int],
    side: str,
) -> tuple[int, int, int, int]:
    rig = json.loads((root / "animation-rig.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    points = rig["expressions"][stem]["points"]
    record = next(item for item in manifest["expressions"] if str(item["number"]) == stem)
    subject_bbox = tuple(record["motion"]["subject_bbox"])
    names = [f"{side}_shoulder", f"{side}_wrist", f"{side}_paw"]
    missing = [name for name in names if name not in points]
    if missing:
        raise ValueError(f"{stem} 缺少肢体绑定点: {', '.join(missing)}")
    anchors = [_absolute_point(points[name], subject_bbox) for name in names]
    xs = [point[0] for point in anchors]
    ys = [point[1] for point in anchors]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 20.0)
    margin = max(16.0, span * 0.34)
    x0 = max(0, round(min(xs) - margin))
    y0 = max(0, round(min(ys) - margin))
    x1 = min(size[0], round(max(xs) + margin))
    y1 = min(size[1], round(max(ys) + margin))
    return x0, y0, x1, y1


def render(
    gif_path: Path,
    output_path: Path,
    side: str = "left",
    scale: int = 5,
    columns: int = 4,
) -> None:
    root = gif_path.parent.parent
    frames: list[Image.Image] = []
    durations: list[int] = []
    with Image.open(gif_path) as gif:
        box = _limb_box(root, gif_path.stem, gif.size, side)
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
    parser.add_argument("gif_or_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--side", choices=("left", "right"), default="left")
    parser.add_argument("--scale", type=int, default=5)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()
    inputs = sorted(args.gif_or_directory.glob("*.gif")) if args.gif_or_directory.is_dir() else [args.gif_or_directory]
    if not inputs:
        raise SystemExit("没有找到GIF")
    for gif_path in inputs:
        render(
            gif_path,
            args.output_directory / f"{gif_path.stem}-{args.side}-limb.png",
            args.side,
            max(1, args.scale),
            max(1, args.columns),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
