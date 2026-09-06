#!/usr/bin/env python3
"""Render deterministic animated handwritten labels onto transparent sticker frames."""

from __future__ import annotations

import glob
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


DEFAULT_LABELS = {
    "01": "好开心",
    "02": "哼！",
    "03": "呜呜",
    "04": "哈哈哈",
    "05": "哇！",
    "06": "嘿嘿",
    "07": "谢谢",
    "08": "拜拜",
}

FONT_CANDIDATES = [
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/*.asset/AssetData/Hanzipen.ttc",
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/*.asset/AssetData/Xingkai.ttc",
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/*.asset/AssetData/Kaiti.ttc",
    "/System/Library/Fonts/Supplemental/Kaiti.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "C:/Windows/Fonts/STXINGKA.TTF",
    "C:/Windows/Fonts/simkai.ttf",
]

TEXT_COLORS = {
    "happy": "#7A4631",
    "angry": "#B1472E",
    "sad": "#526F7C",
    "laugh": "#9A4E2E",
    "surprised": "#D06A32",
    "shy": "#B65E65",
    "thanks": "#7A543A",
    "bye": "#5F6E48",
}

def resolve_font(requested: Path | None = None) -> Path:
    if requested is not None:
        path = requested.expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"手写字体不存在：{path}")
        return path
    for pattern in FONT_CANDIDATES:
        for candidate in sorted(glob.glob(pattern)):
            path = Path(candidate)
            if path.is_file():
                return path
    raise ValueError("未找到支持中文的手写或楷体字体；请使用 --font 指定本地字体文件")


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError as exc:
        raise ValueError(f"无法加载字体：{path}") from exc


def render_label(text: str, font_path: Path, fill: str, max_width: int = 150) -> Image.Image:
    # At 240px, a 23–26px handwritten label reads clearly without competing
    # with the character's face.  The previous 29–32px default felt headline-like.
    font_size = 26 if len(text) <= 2 else 25 if len(text) == 3 else 23
    font = _font(font_path, font_size)
    probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    stroke_width = 1
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    padding = 5
    width = bbox[2] - bbox[0] + padding * 2
    height = bbox[3] - bbox[1] + padding * 2
    label = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(label)
    draw.text(
        (padding - bbox[0], padding - bbox[1]),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill="#FFFFFF",
    )
    if label.width > max_width:
        scale = max_width / label.width
        label = label.resize((max_width, max(1, round(label.height * scale))), Image.Resampling.LANCZOS)
    label.info.update({"font_size": font_size, "stroke_width": stroke_width})
    return label


def _find_natural_position(frames: list[Image.Image], label: Image.Image) -> tuple[int, int, str]:
    """Find a quiet top-area pocket instead of forcing every label to top-center."""

    width, height = frames[0].size
    occupied = Image.new("L", (width, height), 0)
    for frame in frames:
        alpha = frame.convert("RGBA").getchannel("A").point(lambda value: 255 if value >= 16 else 0)
        occupied = ImageChops.lighter(occupied, alpha)
    occupied = occupied.filter(ImageFilter.MaxFilter(9))

    margin = 5
    max_y = min(62, height - label.height - margin)
    max_x = width - label.width - margin
    if max_y < margin or max_x < margin:
        return max(margin, (width - label.width) // 2), margin, "top-center"

    best: tuple[float, int, int] | None = None
    for y in range(margin, max_y + 1, 2):
        for x in range(margin, max_x + 1, 2):
            crop = occupied.crop((x, y, x + label.width, y + label.height))
            overlap = crop.histogram()[255]
            center_distance = abs((x + label.width / 2) - width / 2)
            # Overlap dominates; among clear pockets prefer a high, visually
            # balanced placement with breathing room from the canvas edge.
            score = overlap * 1000.0 + y * 2.2 + center_distance * 0.08
            candidate = (score, x, y)
            if best is None or candidate < best:
                best = candidate
    assert best is not None
    _, x, y = best
    center = x + label.width / 2
    if center < width * 0.40:
        zone = "top-left"
    elif center > width * 0.60:
        zone = "top-right"
    else:
        zone = "top-center"
    return x, y, zone


def _motion(emotion: str, index: int, total: int) -> tuple[float, float, float, float]:
    # Continuous curves keep text motion smooth at any frame count and make
    # the first and last frame land on the same neutral pose.
    phase = index / max(1, total - 1)
    wave = math.sin(phase * math.tau)
    pulse = math.sin(phase * math.pi) ** 2
    bow = pulse
    double_wave = math.sin(phase * math.tau * 2.0) * math.sin(phase * math.pi)
    if emotion == "happy":
        return 0.6 * wave, -1.3 * pulse, 0.8 * wave, 1.0 + 0.018 * pulse
    if emotion == "angry":
        jitter = 1.15 * double_wave
        return jitter, 0.3 * abs(jitter), 1.0 * jitter, 1.0
    if emotion == "sad":
        return -0.25 * bow, 1.5 * bow, -0.5 * bow, 1.0 - 0.010 * bow
    if emotion == "laugh":
        return 0.9 * wave, -1.0 * abs(wave), 1.2 * wave, 1.0 + 0.026 * abs(wave)
    if emotion == "surprised":
        return 0.0, -1.4 * pulse, 0.0, 1.0 + 0.045 * pulse
    if emotion == "shy":
        return 0.7 * wave, 0.35 * abs(wave), 0.9 * wave, 1.0
    if emotion == "thanks":
        return 0.0, 1.4 * bow, -0.4 * bow, 1.0 - 0.012 * bow
    if emotion == "bye":
        return 0.9 * wave, -0.45 * abs(wave), 1.2 * wave, 1.0 + 0.012 * abs(wave)
    raise ValueError(f"未知文字动画语义：{emotion}")


def _transform_label(label: Image.Image, dx: float, dy: float, angle: float, scale: float) -> Image.Image:
    transformed = label
    if abs(scale - 1.0) > 0.001:
        transformed = transformed.resize(
            (max(1, round(label.width * scale)), max(1, round(label.height * scale))),
            Image.Resampling.LANCZOS,
        )
    if abs(angle) > 0.01:
        transformed = transformed.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    transformed.info["offset"] = (round(dx), round(dy))
    return transformed


def add_animated_text(
    frames: list[Image.Image],
    text: str,
    emotion: str,
    font_path: Path,
) -> tuple[list[Image.Image], dict[str, Any]]:
    if not 1 <= len(text) <= 4:
        raise ValueError(f"表情文字建议为1–4个字符：{text}")
    label = render_label(text, font_path, TEXT_COLORS[emotion])
    font_size = int(label.info["font_size"])
    stroke_width = int(label.info["stroke_width"])
    anchor_x, anchor_y, placement = _find_natural_position(frames, label)
    output: list[Image.Image] = []
    for index, frame in enumerate(frames):
        dx, dy, angle, scale = _motion(emotion, index, len(frames))
        animated = _transform_label(label, dx, dy, angle, scale)
        offset_x, offset_y = animated.info["offset"]
        x = anchor_x + (label.width - animated.width) // 2 + offset_x
        y = anchor_y + (label.height - animated.height) // 2 + offset_y
        composed = frame.copy()
        composed.alpha_composite(animated, (x, y))
        output.append(composed)
    return output, {
        "enabled": True,
        "text": text,
        "style": "handwritten",
        "font": font_path.name,
        "font_size": font_size,
        "stroke_width": stroke_width,
        "motion": emotion,
        "region": placement,
        "anchor": [anchor_x, anchor_y],
    }
