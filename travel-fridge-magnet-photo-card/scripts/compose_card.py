#!/usr/bin/env python3
"""Compose a 3:4 travel fridge-magnet photo card without repainting the photo."""

from __future__ import annotations

import argparse
import colorsys
from pathlib import Path
import sys

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError as exc:  # pragma: no cover - depends on host runtime
    raise SystemExit(
        "Pillow is required. In Codex Desktop, call load_workspace_dependencies "
        "and run this script with its bundled Python executable."
    ) from exc


PALETTE_ANCHORS = (
    "#F496A8",  # rose pink
    "#FCDE7F",  # butter yellow
    "#C6D2A8",  # sage green
    "#3677CC",  # postcard blue
    "#1A203E",  # night navy
    "#FCD491",  # almond apricot
)
LIGHT_TEXT = "#F4EBD7"
DARK_TEXT = "#5B4938"
OUTLINE = "#F7F2E8"


def parse_hex(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        raise argparse.ArgumentTypeError("Color must use six-digit hex, for example #3677CC")
    try:
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Color must use six-digit hexadecimal digits") from exc


def rgb_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    # Hue leads the mapping so warm brown stays in the yellow/apricot family instead
    # of drifting toward a similarly dark but unrelated blue anchor.
    ah, asat, aval = colorsys.rgb_to_hsv(*(channel / 255 for channel in a))
    bh, bsat, bval = colorsys.rgb_to_hsv(*(channel / 255 for channel in b))
    hue_delta = min(abs(ah - bh), 1 - abs(ah - bh))
    return hue_delta * 240 + abs(asat - bsat) * 24 + abs(aval - bval) * 18


def dominant_memory_color(photo: Image.Image) -> tuple[int, int, int]:
    sample = photo.convert("RGB")
    sample.thumbnail((160, 160), Image.Resampling.LANCZOS)
    quantized = sample.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    candidates: list[tuple[float, tuple[int, int, int]]] = []
    for count, index in quantized.getcolors(maxcolors=256) or []:
        rgb = tuple(palette[index * 3 : index * 3 + 3])
        if len(rgb) != 3:
            continue
        _, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
        if value < 0.10 or value > 0.98 or saturation < 0.12:
            continue
        score = count * (0.55 + saturation) * (0.75 + min(value, 0.85) * 0.25)
        candidates.append((score, rgb))
    if not candidates:
        return parse_hex("#FCD491")
    return max(candidates, key=lambda item: item[0])[1]


def auto_background(photo: Image.Image) -> tuple[int, int, int]:
    source = dominant_memory_color(photo)
    anchors = [parse_hex(value) for value in PALETTE_ANCHORS]
    return min(anchors, key=lambda anchor: color_distance(source, anchor))


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(channel) for channel in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def cover_crop(image: Image.Image, size: tuple[int, int], focus: tuple[float, float]) -> Image.Image:
    return ImageOps.fit(
        ImageOps.exif_transpose(image).convert("RGB"),
        size,
        method=Image.Resampling.LANCZOS,
        centering=focus,
    )


def load_transparent_sticker(path: Path) -> Image.Image:
    sticker = ImageOps.exif_transpose(Image.open(path)).convert("RGBA")
    alpha = sticker.getchannel("A")
    extrema = alpha.getextrema()
    if extrema == (255, 255):
        raise SystemExit(
            "Sticker image is fully opaque. Regenerate it with a genuinely transparent background."
        )
    bbox = alpha.getbbox()
    if bbox is None:
        raise SystemExit("Sticker image is fully transparent.")
    return sticker.crop(bbox)


def fit_sticker(sticker: Image.Image, width: int, top_height: int, scale: float) -> Image.Image:
    max_width = int(width * 0.42 * scale)
    max_height = int(top_height * 0.38 * scale)
    ratio = min(max_width / sticker.width, max_height / sticker.height)
    size = (max(1, round(sticker.width * ratio)), max(1, round(sticker.height * ratio)))
    return sticker.resize(size, Image.Resampling.LANCZOS)


def add_die_cut(sticker: Image.Image, width: int) -> Image.Image:
    outline_px = max(5, round(width * 0.010))
    blur_px = max(5, round(width * 0.010))
    offset_x = max(4, round(width * 0.010))
    offset_y = max(5, round(width * 0.012))
    pad = outline_px + blur_px * 3 + max(offset_x, offset_y)

    base = Image.new("RGBA", (sticker.width + pad * 2, sticker.height + pad * 2), (0, 0, 0, 0))
    alpha = Image.new("L", base.size, 0)
    alpha.paste(sticker.getchannel("A"), (pad, pad))
    filter_size = outline_px * 2 + 1
    expanded = alpha.filter(ImageFilter.MaxFilter(filter_size))

    shadow_mask = Image.new("L", base.size, 0)
    shadow_mask.paste(expanded, (offset_x, offset_y))
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(blur_px)).point(lambda value: value * 0.42)
    shadow = Image.new("RGBA", base.size, (28, 24, 22, 0))
    shadow.putalpha(shadow_mask)
    base.alpha_composite(shadow)

    outline = Image.new("RGBA", base.size, (*parse_hex(OUTLINE), 255))
    outline.putalpha(expanded)
    base.alpha_composite(outline)
    base.alpha_composite(sticker, (pad, pad))
    return base


def find_font(size: int, explicit: Path | None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        explicit,
        Path("/System/Library/Fonts/Supplemental/AmericanTypewriter.ttc"),
        Path("/System/Library/Fonts/Supplemental/Baskerville.ttc"),
        Path("/System/Library/Fonts/Palatino.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def tracked_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, tracking: int) -> float:
    if not text:
        return 0
    return sum(draw.textlength(char, font=font) for char in text) + tracking * (len(text) - 1)


def draw_centered_label(
    image: Image.Image,
    label: str,
    top_height: int,
    color: tuple[int, int, int],
    font_path: Path | None,
) -> None:
    draw = ImageDraw.Draw(image)
    max_width = image.width * 0.78
    font_size = max(18, round(image.width * 0.038))
    tracking = max(1, round(image.width * 0.0015))
    while font_size > 18:
        font = find_font(font_size, font_path)
        if tracked_width(draw, label, font, tracking) <= max_width:
            break
        font_size -= 1
    else:
        font = find_font(font_size, font_path)

    x = (image.width - tracked_width(draw, label, font, tracking)) / 2
    center_y = top_height * 0.80
    bbox = draw.textbbox((0, 0), label or " ", font=font)
    y = center_y - (bbox[3] - bbox[1]) / 2 - bbox[1]
    for char in label:
        draw.text((round(x), round(y)), char, font=font, fill=color)
        x += draw.textlength(char, font=font) + tracking


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photo", required=True, type=Path, help="Source photo for the lower half")
    parser.add_argument("--sticker", required=True, type=Path, help="Transparent sticker artwork")
    parser.add_argument("--label", required=True, help="Exact one-line label")
    parser.add_argument("--bg", default="auto", help="Six-digit hex color or 'auto'")
    parser.add_argument("--focus-x", type=float, default=0.5, help="Horizontal photo crop focus, 0 to 1")
    parser.add_argument("--focus-y", type=float, default=0.5, help="Vertical photo crop focus, 0 to 1")
    parser.add_argument("--sticker-scale", type=float, default=1.0, help="Sticker scale, normally 0.85 to 1.15")
    parser.add_argument("--font", type=Path, help="Optional font file")
    parser.add_argument("--width", type=int, default=1080, help="Output width; height is always width × 4/3")
    parser.add_argument("--output", required=True, type=Path, help="Output PNG or JPEG path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.photo.is_file():
        raise SystemExit(f"Photo not found: {args.photo}")
    if not args.sticker.is_file():
        raise SystemExit(f"Sticker not found: {args.sticker}")
    if not (0 <= args.focus_x <= 1 and 0 <= args.focus_y <= 1):
        raise SystemExit("focus-x and focus-y must be between 0 and 1")
    if not (0.70 <= args.sticker_scale <= 1.30):
        raise SystemExit("sticker-scale must be between 0.70 and 1.30")
    if args.width < 480:
        raise SystemExit("width must be at least 480 pixels")

    height = round(args.width * 4 / 3)
    top_height = height // 2
    photo = Image.open(args.photo)
    bg = auto_background(photo) if args.bg.lower() == "auto" else parse_hex(args.bg)
    canvas = Image.new("RGB", (args.width, height), bg)
    lower = cover_crop(photo, (args.width, height - top_height), (args.focus_x, args.focus_y))
    canvas.paste(lower, (0, top_height))

    sticker = fit_sticker(load_transparent_sticker(args.sticker), args.width, top_height, args.sticker_scale)
    sticker = add_die_cut(sticker, args.width)
    center_x = args.width // 2
    center_y = round(top_height * 0.44)
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.alpha_composite(sticker, (center_x - sticker.width // 2, center_y - sticker.height // 2))

    text_color = parse_hex(DARK_TEXT if relative_luminance(bg) > 0.42 else LIGHT_TEXT)
    draw_centered_label(canvas_rgba, args.label, top_height, text_color, args.font)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    suffix = args.output.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        canvas_rgba.convert("RGB").save(args.output, quality=95, subsampling=0)
    else:
        canvas_rgba.save(args.output, format="PNG", optimize=True)
    print(f"output: {args.output.resolve()}")
    print(f"size: {args.width}x{height}")
    print(f"background: {rgb_hex(bg)}")
    print(f"label: {args.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
