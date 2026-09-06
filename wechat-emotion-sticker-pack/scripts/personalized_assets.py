#!/usr/bin/env python3
"""Create personalized companion art for a WeChat sticker submission.

The layouts reuse visual cues from the supplied photograph (palette, scene
geometry and prop silhouettes) without copying store labels, trademarks or
background text.  No companion asset contains typography.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


FALLBACK_PALETTES = {
    "minimal-line": {"cream": "#F7F0E4", "gold": "#DCA85A", "navy": "#315B54", "olive": "#97A58D", "coral": "#D97862"},
    "pixel": {"cream": "#E8E2D5", "gold": "#F2B84B", "navy": "#182234", "olive": "#71845B", "coral": "#D66C55"},
    "cute-cartoon": {"cream": "#FFF1D5", "gold": "#F4B400", "navy": "#17304A", "olive": "#9BA34D", "coral": "#E96F62"},
    "chibi": {"cream": "#F8EED8", "gold": "#E9AC4A", "navy": "#294457", "olive": "#8E9D6C", "coral": "#DF8065"},
    "3d": {"cream": "#EEF2F3", "gold": "#D7A145", "navy": "#30465E", "olive": "#889A7F", "coral": "#CB7568"},
}


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _hex(color: np.ndarray | tuple[int, int, int]) -> str:
    return "#" + "".join(f"{int(channel):02X}" for channel in color)


def _blend(first: str, second: str, amount: float) -> tuple[int, int, int]:
    a, b = _rgb(first), _rgb(second)
    return tuple(round(a[index] * (1.0 - amount) + b[index] * amount) for index in range(3))


def _alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    box = image.convert("RGBA").getchannel("A").point(lambda value: 255 if value >= 8 else 0).getbbox()
    if box is None:
        raise ValueError("角色源图没有可见主体")
    return box


def _cutout(image: Image.Image, extent: tuple[int, int]) -> Image.Image:
    crop = image.convert("RGBA").crop(_alpha_bbox(image))
    scale = min(extent[0] / crop.width, extent[1] / crop.height)
    size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    return crop.resize(size, Image.Resampling.LANCZOS)


def _shadowed_subject(source: Image.Image, extent: tuple[int, int], opacity: int = 72) -> Image.Image:
    subject = _cutout(source, extent)
    alpha = subject.getchannel("A")
    shadow_alpha = alpha.filter(ImageFilter.GaussianBlur(max(2, round(min(extent) * 0.025))))
    shadow_alpha = shadow_alpha.point(lambda value: round(value * opacity / 255))
    shadow = Image.new("RGBA", subject.size, (35, 42, 45, 0))
    shadow.putalpha(shadow_alpha)
    layer = Image.new("RGBA", (subject.width + 18, subject.height + 20), (0, 0, 0, 0))
    layer.alpha_composite(shadow, (9, 13))
    layer.alpha_composite(subject, (4, 2))
    return layer


def _gradient(size: tuple[int, int], start: str, end: str) -> Image.Image:
    first, second = _rgb(start), _rgb(end)
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        color = tuple(round(first[channel] * (1 - t) + second[channel] * t) for channel in range(3))
        draw.line((0, y, size[0], y), fill=color)
    return image.convert("RGBA")


def _extract_palette(reference_photo: Path | None, style: str) -> tuple[dict[str, str], dict[str, Any]]:
    palette = dict(FALLBACK_PALETTES[style])
    meta: dict[str, Any] = {"reference_used": False, "reference_photo": None}
    if reference_photo is None:
        return palette, meta
    path = reference_photo.expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"个性化参考照片不存在：{path}")
    with Image.open(path) as opened:
        photo = opened.convert("RGB")
    photo.thumbnail((180, 180), Image.Resampling.LANCZOS)
    pixels = np.asarray(photo, dtype=np.float32).reshape(-1, 3)
    red, green, blue = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    saturation = pixels.max(axis=1) - pixels.min(axis=1)
    golden = pixels[(red > 150) & (green > 85) & (blue < 155) & (saturation > 55)]
    dark_cool = pixels[(blue >= red * 0.82) & (green >= red * 0.72) & (pixels.mean(axis=1) < 95)]
    natural = pixels[(green > red * 0.72) & (green > blue * 0.95) & (red > 70) & (pixels.mean(axis=1) < 180)]
    if len(golden) >= 12:
        palette["gold"] = _hex(np.clip(np.median(golden, axis=0), 0, 255).astype(np.uint8))
    if len(dark_cool) >= 12:
        navy = np.median(dark_cool, axis=0)
        navy = np.clip(navy * 0.82, 18, 110).astype(np.uint8)
        palette["navy"] = _hex(navy)
    if len(natural) >= 12:
        olive = np.median(natural, axis=0)
        palette["olive"] = _hex(np.clip(olive, 55, 190).astype(np.uint8))
    meta.update({"reference_used": True, "reference_photo": str(path)})
    return palette, meta


def _aa_layer(size: tuple[int, int], factor: int = 3) -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    layer = Image.new("RGBA", (size[0] * factor, size[1] * factor), (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer, "RGBA"), factor


def _downsample(layer: Image.Image, size: tuple[int, int]) -> Image.Image:
    return layer.resize(size, Image.Resampling.LANCZOS)


def _line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], factor: int,
          fill: tuple[int, int, int, int] | str, width: float) -> None:
    draw.line([(round(x * factor), round(y * factor)) for x, y in points], fill=fill,
              width=max(1, round(width * factor)), joint="curve")


def _cart(draw: ImageDraw.ImageDraw, factor: int, x: float, y: float, scale: float,
          palette: dict[str, str], alpha: int = 220) -> None:
    navy = (*_rgb(palette["navy"]), alpha)
    gold = (*_rgb(palette["gold"]), min(255, alpha + 20))
    basket = [(x, y), (x + 76 * scale, y), (x + 65 * scale, y + 45 * scale), (x + 10 * scale, y + 45 * scale)]
    draw.polygon([(round(px * factor), round(py * factor)) for px, py in basket], fill=(*_rgb(palette["cream"]), 145), outline=gold)
    for offset in (19, 38, 57):
        _line(draw, [(x + offset * scale, y + 3 * scale), (x + (offset - 4) * scale, y + 41 * scale)], factor, gold, 1.6 * scale)
    _line(draw, [(x, y), (x - 10 * scale, y - 14 * scale), (x - 24 * scale, y - 14 * scale)], factor, navy, 3.0 * scale)
    _line(draw, [(x + 12 * scale, y + 49 * scale), (x + 62 * scale, y + 49 * scale)], factor, navy, 2.4 * scale)
    radius = max(2, round(5 * scale * factor))
    for wheel_x in (x + 18 * scale, x + 57 * scale):
        draw.ellipse((round(wheel_x * factor - radius), round((y + 56 * scale) * factor - radius),
                      round(wheel_x * factor + radius), round((y + 56 * scale) * factor + radius)), fill=navy)


def _groceries(draw: ImageDraw.ImageDraw, factor: int, x: float, y: float, scale: float,
               palette: dict[str, str], alpha: int = 230) -> None:
    cream = (*_rgb(palette["cream"]), alpha)
    coral = (*_rgb(palette["coral"]), alpha)
    olive = (*_rgb(palette["olive"]), alpha)
    navy = (*_rgb(palette["navy"]), alpha)
    draw.rounded_rectangle((round(x * factor), round(y * factor), round((x + 22 * scale) * factor),
                            round((y + 34 * scale) * factor)), radius=max(2, round(4 * scale * factor)), fill=cream, outline=navy,
                           width=max(1, round(1.5 * scale * factor)))
    draw.polygon([(round((x + 3 * scale) * factor), round(y * factor)),
                  (round((x + 10 * scale) * factor), round((y - 8 * scale) * factor)),
                  (round((x + 21 * scale) * factor), round(y * factor))], fill=cream, outline=navy)
    apple_x, apple_y = x + 33 * scale, y + 20 * scale
    radius = 10 * scale * factor
    draw.ellipse((round(apple_x * factor - radius), round(apple_y * factor - radius),
                  round(apple_x * factor + radius), round(apple_y * factor + radius)), fill=coral)
    _line(draw, [(apple_x, apple_y - 10 * scale), (apple_x + 1.5 * scale, apple_y - 16 * scale)], factor, navy, 1.8 * scale)
    draw.ellipse((round((apple_x + 5 * scale) * factor), round((apple_y - 17 * scale) * factor),
                  round((apple_x + 12 * scale) * factor), round((apple_y - 12 * scale) * factor)), fill=olive)


def _star(draw: ImageDraw.ImageDraw, factor: int, x: float, y: float, size: float,
          color: str, alpha: int = 210) -> None:
    fill = (*_rgb(color), alpha)
    _line(draw, [(x - size, y), (x + size, y)], factor, fill, max(1.2, size * 0.20))
    _line(draw, [(x, y - size), (x, y + size)], factor, fill, max(1.2, size * 0.20))


def _heart(draw: ImageDraw.ImageDraw, factor: int, x: float, y: float, size: float,
           color: str, alpha: int = 210) -> None:
    points: list[tuple[int, int]] = []
    for step in range(33):
        angle = 2 * np.pi * step / 32
        hx = 16 * np.sin(angle) ** 3
        hy = 13 * np.cos(angle) - 5 * np.cos(2 * angle) - 2 * np.cos(3 * angle) - np.cos(4 * angle)
        points.append((round((x + hx * size / 32) * factor), round((y - hy * size / 32) * factor)))
    draw.polygon(points, fill=(*_rgb(color), alpha))


def _leaf(draw: ImageDraw.ImageDraw, factor: int, x: float, y: float, size: float,
          color: str, alpha: int = 190) -> None:
    fill = (*_rgb(color), alpha)
    draw.ellipse((round((x - size) * factor), round((y - size * 0.55) * factor),
                  round((x + size) * factor), round((y + size * 0.55) * factor)), fill=fill)
    _line(draw, [(x - size * 0.72, y + size * 0.20), (x + size * 0.72, y - size * 0.20)],
          factor, (*_rgb(color), min(255, alpha + 35)), max(1.0, size * 0.10))


def _shelves(draw: ImageDraw.ImageDraw, factor: int, width: int, y: float,
             palette: dict[str, str], alpha: int = 125) -> None:
    navy = (*_rgb(palette["navy"]), alpha)
    cream = (*_rgb(palette["cream"]), min(245, alpha + 85))
    colors = [palette["coral"], palette["olive"], palette["gold"], palette["cream"]]
    _line(draw, [(24, y), (width - 24, y)], factor, navy, 3.0)
    for index, x in enumerate(range(38, width - 30, 42)):
        box_w, box_h = 25 + (index % 2) * 5, 30 + (index % 3) * 6
        draw.rounded_rectangle((x * factor, round((y - box_h) * factor), round((x + box_w) * factor), round(y * factor)),
                               radius=round(4 * factor), fill=(*_rgb(colors[index % len(colors)]), alpha), outline=cream,
                               width=max(1, round(1.3 * factor)))


def _paste_center(canvas: Image.Image, subject: Image.Image, center: tuple[int, int]) -> None:
    canvas.alpha_composite(subject, (round(center[0] - subject.width / 2), round(center[1] - subject.height / 2)))


def _cover(source: Image.Image, palette: dict[str, str], theme: str) -> Image.Image:
    size = (240, 240)
    layer, draw, factor = _aa_layer(size)
    draw.ellipse((24 * factor, 18 * factor, 218 * factor, 218 * factor), fill=(*_rgb(palette["cream"]), 255))
    draw.ellipse((42 * factor, 35 * factor, 205 * factor, 205 * factor),
                 fill=(*_blend(palette["cream"], palette["gold"], 0.20), 255))
    if theme == "shopping":
        _cart(draw, factor, 146, 148, 0.62, palette, 210)
        _groceries(draw, factor, 23, 155, 0.72, palette, 235)
    elif theme == "nature":
        _leaf(draw, factor, 38, 164, 13, palette["olive"], 190)
        _leaf(draw, factor, 196, 163, 11, palette["olive"], 155)
    else:
        _heart(draw, factor, 36, 166, 17, palette["coral"], 145)
    _star(draw, factor, 48, 44, 7, palette["gold"])
    _star(draw, factor, 198, 55, 5, palette["coral"])
    canvas = _downsample(layer, size)
    subject = _shadowed_subject(source, (165, 190), 52)
    _paste_center(canvas, subject, (119, 132))
    return canvas


def _icon(source: Image.Image, palette: dict[str, str]) -> Image.Image:
    size = (50, 50)
    layer, draw, factor = _aa_layer(size, 4)
    draw.ellipse((1 * factor, 1 * factor, 49 * factor, 49 * factor), fill=(*_rgb(palette["gold"]), 245))
    draw.ellipse((4 * factor, 4 * factor, 46 * factor, 46 * factor), fill=(*_rgb(palette["cream"]), 255),
                 outline=(*_rgb(palette["navy"]), 235), width=round(1.6 * factor))
    canvas = _downsample(layer, size)
    # A complete, calm silhouette is more robust than a guessed head crop:
    # tails, raised ears and unconventional animal poses otherwise make a
    # rectangular crop sever the neck or show the back instead of the face.
    miniature = _cutout(source, (40, 40))
    _paste_center(canvas, miniature, (25, 26))
    return canvas


def _banner(sources: list[Image.Image], palette: dict[str, str], theme: str) -> Image.Image:
    size = (750, 400)
    canvas = _gradient(size, palette["cream"], palette["gold"])
    layer, draw, factor = _aa_layer(size, 2)
    draw.ellipse((-150 * factor, 205 * factor, 905 * factor, 610 * factor), fill=(255, 247, 225, 188))
    if theme == "shopping":
        _shelves(draw, factor, size[0], 94, palette, 90)
        _cart(draw, factor, 584, 267, 1.35, palette, 170)
        _groceries(draw, factor, 58, 281, 1.25, palette, 205)
    elif theme == "nature":
        for x, y, leaf_size in ((68, 102, 24), (675, 118, 28), (616, 305, 20), (120, 311, 18)):
            _leaf(draw, factor, x, y, leaf_size, palette["olive"], 135)
    else:
        for x, y, heart_size in ((77, 126, 20), (669, 137, 24)):
            _heart(draw, factor, x, y, heart_size, palette["coral"], 105)
    for x, y, star_size, color in ((55, 52, 8, "coral"), (701, 51, 7, "navy"), (635, 145, 5, "olive"), (130, 175, 5, "gold")):
        _star(draw, factor, x, y, star_size, palette[color], 170)
    canvas.alpha_composite(_downsample(layer, size))
    arrangements = ((sources[5], (155, 255), (125, 243)), (sources[0], (235, 326), (376, 223)), (sources[7], (168, 272), (610, 238)))
    for source, extent, center in arrangements:
        _paste_center(canvas, _shadowed_subject(source, extent, 62), center)
    return canvas


def _guide(source: Image.Image, palette: dict[str, str], theme: str) -> Image.Image:
    size = (750, 560)
    canvas = _gradient(size, palette["cream"], "#F6DCA6")
    layer, draw, factor = _aa_layer(size, 2)
    if theme == "shopping":
        _shelves(draw, factor, size[0], 76, palette, 72)
    draw.rounded_rectangle((52 * factor, 340 * factor, 698 * factor, 542 * factor), radius=42 * factor,
                           fill=(255, 248, 230, 198), outline=(*_rgb(palette["gold"]), 80), width=2 * factor)
    if theme == "shopping":
        _groceries(draw, factor, 92, 255, 1.12, palette, 178)
        _cart(draw, factor, 575, 259, 1.05, palette, 155)
    elif theme == "nature":
        _leaf(draw, factor, 118, 279, 24, palette["olive"], 150)
        _leaf(draw, factor, 628, 281, 21, palette["olive"], 130)
    _heart(draw, factor, 170, 158, 28, palette["coral"], 130)
    _heart(draw, factor, 592, 148, 22, palette["coral"], 105)
    canvas.alpha_composite(_downsample(layer, size))
    _paste_center(canvas, _shadowed_subject(source, (305, 326), 58), (375, 211))
    return canvas


def _thanks(source: Image.Image, palette: dict[str, str], theme: str) -> Image.Image:
    size = (750, 750)
    canvas = _gradient(size, palette["cream"], "#F3C36C")
    layer, draw, factor = _aa_layer(size, 2)
    draw.ellipse((112 * factor, 82 * factor, 638 * factor, 608 * factor), fill=(255, 247, 224, 205),
                 outline=(*_rgb(palette["gold"]), 110), width=4 * factor)
    if theme == "shopping":
        _cart(draw, factor, 493, 550, 1.42, palette, 180)
        _groceries(draw, factor, 105, 575, 1.45, palette, 210)
    elif theme == "nature":
        _leaf(draw, factor, 142, 601, 34, palette["olive"], 170)
        _leaf(draw, factor, 613, 599, 30, palette["olive"], 145)
    for x, y, heart_size, alpha in ((118, 178, 38, 185), (640, 194, 31, 155), (173, 505, 24, 125)):
        _heart(draw, factor, x, y, heart_size, palette["coral"], alpha)
    for x, y, star_size, color in ((88, 91, 13, "gold"), (669, 94, 10, "navy"), (616, 471, 8, "olive")):
        _star(draw, factor, x, y, star_size, palette[color], 175)
    canvas.alpha_composite(_downsample(layer, size))
    _paste_center(canvas, _shadowed_subject(source, (385, 455), 64), (375, 368))
    return canvas


def build_companion_set(
    sources: list[Image.Image],
    style: str,
    reference_photo: Path | None = None,
    theme: str = "portrait",
) -> tuple[dict[str, Image.Image], dict[str, Any]]:
    palette, reference_meta = _extract_palette(reference_photo, style)
    effective_theme = theme if theme != "portrait" else "photo-derived"
    assets = {
        "cover": _cover(sources[0], palette, theme),
        # The first sticker may be a play-bow or another low feline pose whose
        # tail reaches above the head.  Cropping its upper half can therefore
        # turn the tiny tray icon into a tail/back silhouette.  The gratitude
        # pose is intentionally calm and front-facing across the pack spec, so
        # it produces a much more legible face icon at 50 px.
        "tray_icon": _icon(sources[6], palette),
        "banner": _banner(sources, palette, theme),
        "appreciation_guide": _guide(sources[6], palette, theme),
        "appreciation_thanks": _thanks(sources[6], palette, theme),
    }
    metadata = {
        **reference_meta,
        "enabled": True,
        "theme": effective_theme,
        "visual_cues": ["reference-palette", "scene-geometry", "prop-silhouettes"],
        "motifs": (
            ["shopping-cart", "grocery-basket", "apple", "milk-carton", "shelf-shapes", "stars", "hearts"]
            if theme == "shopping"
            else ["leaves", "organic-badge", "stars", "hearts"]
            if theme == "nature"
            else ["organic-badge", "stars", "hearts"]
        ),
        "palette": palette,
        "contains_text": False,
        "brand_marks_copied": False,
    }
    return assets, metadata


__all__ = ["build_companion_set"]
