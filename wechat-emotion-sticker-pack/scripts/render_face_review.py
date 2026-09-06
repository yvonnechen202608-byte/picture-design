#!/usr/bin/env python3
"""Render enlarged eye-to-mouth crops from sticker GIFs for facial QA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def _face_box(root: Path, stem: str, size: tuple[int, int]) -> tuple[int, int, int, int]:
    rig = json.loads((root / "animation-rig.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    points = rig["expressions"][stem]["points"]
    record = next(item for item in manifest["expressions"] if str(item["number"]) == stem)
    left, top, right, bottom = record["motion"]["subject_bbox"]
    width, height = right - left, bottom - top
    left_eye = (left + points["left_eye"]["x"] * width, top + points["left_eye"]["y"] * height)
    right_eye = (left + points["right_eye"]["x"] * width, top + points["right_eye"]["y"] * height)
    mouth = (left + points["mouth"]["x"] * width, top + points["mouth"]["y"] * height)
    eye_y = (left_eye[1] + right_eye[1]) / 2.0
    spacing = max(8.0, abs(right_eye[0] - left_eye[0]))
    center_x = (left_eye[0] + right_eye[0] + mouth[0]) / 3.0
    crop_width = max(44.0, spacing * 2.15)
    crop_height = max(42.0, mouth[1] - eye_y + spacing * 1.45)
    x0 = max(0, round(center_x - crop_width / 2))
    y0 = max(0, round(eye_y - spacing * 0.72))
    x1 = min(size[0], round(x0 + crop_width))
    y1 = min(size[1], round(y0 + crop_height))
    return x0, y0, x1, y1


def render(gif_path: Path, output_path: Path, scale: int = 4, columns: int = 4) -> None:
    root = gif_path.parent.parent
    frames: list[Image.Image] = []
    durations: list[int] = []
    with Image.open(gif_path) as gif:
        box = _face_box(root, gif_path.stem, gif.size)
        for index in range(getattr(gif, "n_frames", 1)):
            gif.seek(index)
            frames.append(gif.convert("RGBA").crop(box).resize(
                ((box[2] - box[0]) * scale, (box[3] - box[1]) * scale),
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
    parser.add_argument("--scale", type=int, default=4)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()
    inputs = sorted(args.gif_or_directory.glob("*.gif")) if args.gif_or_directory.is_dir() else [args.gif_or_directory]
    if not inputs:
        raise SystemExit("没有找到GIF")
    for gif_path in inputs:
        render(gif_path, args.output_directory / f"{gif_path.stem}-face.png", max(1, args.scale), max(1, args.columns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
