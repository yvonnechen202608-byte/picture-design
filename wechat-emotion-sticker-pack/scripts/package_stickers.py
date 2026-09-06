#!/usr/bin/env python3
"""Build animated WeChat submission assets from eight transparent emotion PNGs."""

from __future__ import annotations

import argparse
import colorsys
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("Pillow is required: python3 -m pip install Pillow") from exc

from animated_text import DEFAULT_LABELS, add_animated_text, resolve_font
from personalized_assets import build_companion_set
from pose_preserving_animation import ENGINE_NAME, build_pose_preserving_frames, load_animation_rig, merged_rig
from validate_pack import validate_pack


EXPRESSIONS = [
    ("01", "开心", "happy", "bounce"),
    ("02", "生气", "angry", "shake"),
    ("03", "伤心", "sad", "sink"),
    ("04", "大笑", "laugh", "squash"),
    ("05", "惊讶", "surprised", "pop"),
    ("06", "害羞", "shy", "sway"),
    ("07", "感谢", "thanks", "bow"),
    ("08", "再见", "bye", "wave"),
]

STYLE_PALETTES = {
    "minimal-line": ("#F3EBDD", "#D9E7DF", "#315B54"),
    "pixel": ("#182234", "#314A67", "#F2B84B"),
    "cute-cartoon": ("#FFF0EC", "#FFD9CC", "#EF7B72"),
    "chibi": ("#F7F1E7", "#DDEBE4", "#E48B64"),
    "3d": ("#E9EEF5", "#C9D7E7", "#6D83A5"),
}

def rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def resample_for(style: str) -> Image.Resampling:
    return Image.Resampling.NEAREST if style == "pixel" else Image.Resampling.LANCZOS


def rotation_resample_for(style: str) -> Image.Resampling:
    return Image.Resampling.NEAREST if style == "pixel" else Image.Resampling.BICUBIC


def discover_sources(source_dir: Path) -> list[Path]:
    if not source_dir.is_dir():
        raise ValueError(f"母图目录不存在：{source_dir}")
    files: list[Path] = []
    for index in range(1, 9):
        prefix = f"{index:02d}"
        candidates = sorted(
            path for path in source_dir.iterdir()
            if path.is_file() and path.stem.startswith(prefix) and path.suffix.lower() in {".png", ".webp"}
        )
        if len(candidates) != 1:
            raise ValueError(f"编号 {prefix} 需要且只能有一张PNG/WEBP母图，找到 {len(candidates)} 张")
        files.append(candidates[0])
    return files


def load_transparent(path: Path) -> Image.Image:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    lo, hi = alpha.getextrema()
    if lo == 255:
        raise ValueError(f"{path.name} 没有真实透明像素")
    if hi == 0:
        raise ValueError(f"{path.name} 完全透明")
    return rgba


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    mask = image.getchannel("A").point(lambda value: 255 if value >= 8 else 0)
    box = mask.getbbox()
    if box is None:
        raise ValueError("图片没有可见主体")
    return box


def clean_rgba(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    red, green, blue, alpha = image.split()
    base = Image.new("RGB", image.size, (0, 0, 0))
    base.paste(Image.merge("RGB", (red, green, blue)), mask=alpha)
    result = base.convert("RGBA")
    result.putalpha(alpha)
    return result


def contain_subject(
    image: Image.Image,
    canvas_size: tuple[int, int],
    max_extent: tuple[int, int],
    style: str,
    offset: tuple[int, int] = (0, 0),
) -> Image.Image:
    cropped = image.crop(alpha_bbox(image))
    scale = min(max_extent[0] / cropped.width, max_extent[1] / cropped.height)
    new_size = (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale)))
    resized = cropped.resize(new_size, resample_for(style))
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x = (canvas_size[0] - new_size[0]) // 2 + offset[0]
    y = (canvas_size[1] - new_size[1]) // 2 + offset[1]
    canvas.alpha_composite(resized, (x, y))
    return clean_rgba(canvas)


def add_white_outline(image: Image.Image, radius: int = 2) -> Image.Image:
    alpha = image.getchannel("A")
    expanded = alpha.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    edge = ImageChops.subtract(expanded, alpha)
    outline = Image.new("RGBA", image.size, (255, 255, 255, 0))
    outline.putalpha(edge)
    outline.alpha_composite(image)
    return clean_rgba(outline)


def _vivid_palette_anchors(frame: Image.Image, limit: int = 5) -> list[tuple[int, int, int]]:
    """Keep small identity colours (eyes, accessories, accents) in tiny GIF palettes.

    Median-cut naturally favours the large neutral areas in a sticker.  That is
    especially destructive for heterochromia: two small irises can disappear
    when a black subject is compressed to 12–16 colours.  Pick one representative
    high-chroma colour from each occupied hue sector and give those colours a
    small training swatch during quantisation.  The swatches never enter the
    delivered frame; only their palette entries do.
    """

    sample = frame.convert("RGBA").resize((96, 96), Image.Resampling.LANCZOS)
    hue_bins: dict[int, list[tuple[float, int, int, int]]] = {}
    pixels = sample.get_flattened_data() if hasattr(sample, "get_flattened_data") else sample.getdata()
    for red, green, blue, alpha in pixels:
        if alpha < 128:
            continue
        hue, saturation, value = colorsys.rgb_to_hsv(red / 255.0, green / 255.0, blue / 255.0)
        if saturation < 0.28 or value < 0.22:
            continue
        sector = int(hue * 12.0) % 12
        hue_bins.setdefault(sector, []).append((saturation * value, red, green, blue))

    ranked = sorted(hue_bins.values(), key=len, reverse=True)[:limit]
    anchors: list[tuple[int, int, int]] = []
    for candidates in ranked:
        candidates.sort(reverse=True)
        _, red, green, blue = candidates[max(0, len(candidates) // 8)]
        anchors.append((red, green, blue))
    return anchors


def gif_palette_frame(frame: Image.Image, colors: int) -> Image.Image:
    alpha = frame.getchannel("A")
    flattened = Image.new("RGB", frame.size, (255, 255, 255))
    flattened.paste(frame.convert("RGB"), mask=alpha)
    anchors = _vivid_palette_anchors(frame, limit=max(2, min(5, colors // 3)))
    if anchors:
        strip_height = max(len(anchors), 10)
        training = Image.new("RGB", (frame.width, frame.height + strip_height), (255, 255, 255))
        training.paste(flattened, (0, 0))
        draw = ImageDraw.Draw(training)
        for index, color in enumerate(anchors):
            left = round(index * frame.width / len(anchors))
            right = round((index + 1) * frame.width / len(anchors))
            draw.rectangle((left, frame.height, right, frame.height + strip_height - 1), fill=color)
        trained = training.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        paletted = trained.crop((0, 0, frame.width, frame.height))
    else:
        paletted = flattened.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette = paletted.getpalette() or []
    palette = (palette + [0] * 768)[:768]
    palette[765:768] = [255, 255, 255]
    paletted.putpalette(palette)
    transparent_mask = alpha.point(lambda value: 255 if value < 128 else 0)
    paletted.paste(255, mask=transparent_mask)
    return paletted


def _shared_gif_palette(frames: list[Image.Image], colors: int) -> Image.Image:
    """Train one palette for the whole loop so tiny identity colours stay stable.

    A palette chosen independently for every frame makes small blue/gold irises
    flicker between coloured and grey even when the artwork itself is unchanged.
    The shared thumbnail sheet represents every pose, while deliberately larger
    hue swatches reserve entries for small but semantically important accents.
    """

    thumb_size = 72
    columns = min(4, max(1, len(frames)))
    rows = (len(frames) + columns - 1) // columns
    sheet_width = columns * thumb_size
    sheet_height = rows * thumb_size
    training = Image.new("RGB", (sheet_width, sheet_height + 36), (255, 255, 255))

    hue_candidates: dict[int, list[tuple[float, tuple[int, int, int]]]] = {}
    for index, frame in enumerate(frames):
        alpha = frame.getchannel("A")
        flattened = Image.new("RGB", frame.size, (255, 255, 255))
        flattened.paste(frame.convert("RGB"), mask=alpha)
        thumb = flattened.resize((thumb_size, thumb_size), Image.Resampling.LANCZOS)
        training.paste(thumb, ((index % columns) * thumb_size, (index // columns) * thumb_size))
        for color in _vivid_palette_anchors(frame, limit=8):
            hue, saturation, value = colorsys.rgb_to_hsv(*(channel / 255.0 for channel in color))
            sector = int(hue * 16.0) % 16
            hue_candidates.setdefault(sector, []).append((saturation * value, color))

    anchor_limit = max(4, min(6, colors // 2))
    ranked_sectors = sorted(
        hue_candidates.values(),
        key=lambda candidates: (len(candidates), max(score for score, _ in candidates)),
        reverse=True,
    )[:anchor_limit]
    anchors = [max(candidates, key=lambda item: item[0])[1] for candidates in ranked_sectors]
    draw = ImageDraw.Draw(training)
    if anchors:
        for index, color in enumerate(anchors):
            left = round(index * sheet_width / len(anchors))
            right = round((index + 1) * sheet_width / len(anchors))
            draw.rectangle((left, sheet_height, right, sheet_height + 35), fill=color)

    palette = training.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    palette_values = (palette.getpalette() or [] + [0] * 768)[:768]
    palette_values = (palette_values + [0] * 768)[:768]
    # Keep the unused palette entries far from the artwork so opaque pixels do
    # not accidentally map to the reserved transparency index 255.
    for index in range(colors, 256):
        palette_values[index * 3 : index * 3 + 3] = [0, 255, 0]
    palette.putpalette(palette_values)
    return palette


def gif_palette_frames(frames: list[Image.Image], colors: int) -> list[Image.Image]:
    palette = _shared_gif_palette(frames, colors)
    output: list[Image.Image] = []
    for frame in frames:
        alpha = frame.getchannel("A")
        flattened = Image.new("RGB", frame.size, (255, 255, 255))
        flattened.paste(frame.convert("RGB"), mask=alpha)
        paletted = flattened.quantize(palette=palette, dither=Image.Dither.NONE)
        transparent_mask = alpha.point(lambda value: 255 if value < 128 else 0)
        paletted.paste(255, mask=transparent_mask)
        paletted.info["transparency"] = 255
        output.append(paletted)
    return output


def encode_gif(frames: list[Image.Image], max_kb: int, durations: list[int]) -> tuple[bytes, dict[str, int]]:
    plans = [
        (16, 48), (16, 40), (16, 32), (16, 24), (16, 20), (16, 16), (16, 14), (16, 12),
        (14, 40), (14, 32), (14, 24), (14, 20), (14, 16), (14, 14), (14, 12),
        (12, 32), (12, 24), (12, 20), (12, 16), (12, 14), (12, 12),
    ]
    best: tuple[bytes, dict[str, int]] | None = None
    for frame_count, colors in plans:
        indices = [round(i * (len(frames) - 1) / (frame_count - 1)) for i in range(frame_count)]
        rgba_selected = [frames[index] for index in indices]
        selected = gif_palette_frames(rgba_selected, colors)
        selected_durations = [durations[index] for index in indices]
        buffer = io.BytesIO()
        selected[0].save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=selected[1:],
            duration=selected_durations,
            loop=0,
            disposal=2,
            transparency=255,
            optimize=True,
        )
        payload = buffer.getvalue()
        # GIF encoders may coalesce an identical loop-closing frame into the
        # previous duration. Record the actual stored count, not the requested
        # sample count, so validation describes the delivered file precisely.
        with Image.open(io.BytesIO(payload)) as encoded:
            actual_frame_count = getattr(encoded, "n_frames", frame_count)
        metadata = {
            "frames": actual_frame_count,
            "requested_frames": frame_count,
            "colors": colors,
            "bytes": len(payload),
            "duration_ms": sum(selected_durations),
        }
        if best is None or len(payload) < len(best[0]):
            best = (payload, metadata)
        if len(payload) <= max_kb * 1000:
            return payload, metadata
    assert best is not None
    raise ValueError(f"GIF压缩后仍为 {len(best[0]) / 1000:.1f}KB，超过 {max_kb}KB；请简化母图纹理")


def save_png_limited(image: Image.Image, path: Path, max_kb: int) -> dict[str, int]:
    image = clean_rgba(image)
    for colors in (0, 256, 128, 96, 64, 48, 32, 24, 16):
        candidate = image
        if colors:
            alpha = image.getchannel("A")
            candidate = image.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).convert("RGBA")
            candidate.putalpha(alpha)
            candidate = clean_rgba(candidate)
        buffer = io.BytesIO()
        candidate.save(buffer, format="PNG", optimize=True, compress_level=9)
        payload = buffer.getvalue()
        if len(payload) <= max_kb * 1000:
            path.write_bytes(payload)
            return {"colors": colors or 16777216, "bytes": len(payload)}
    raise ValueError(f"PNG压缩后仍超过 {max_kb}KB：{path.name}")


def save_jpeg_limited(image: Image.Image, path: Path, max_kb: int) -> dict[str, int]:
    opaque = image.convert("RGB")
    for quality in (90, 82, 74, 66, 58, 50, 42, 34, 26):
        buffer = io.BytesIO()
        opaque.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=False, subsampling=2)
        payload = buffer.getvalue()
        if len(payload) <= max_kb * 1000:
            path.write_bytes(payload)
            return {"quality": quality, "bytes": len(payload)}
    raise ValueError(f"JPEG压缩后仍超过 {max_kb}KB：{path.name}")


def gradient(size: tuple[int, int], start: str, end: str) -> Image.Image:
    first, second = rgb(start), rgb(end)
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        color = tuple(round(first[i] * (1 - t) + second[i] * t) for i in range(3))
        draw.line((0, y, size[0], y), fill=color)
    return image.convert("RGBA")


def draw_sparkles(image: Image.Image, accent: str, points: list[tuple[int, int, int]]) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    color = (*rgb(accent), 150)
    for x, y, radius in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
        draw.line((x - radius * 2, y, x + radius * 2, y), fill=color, width=max(1, radius // 2))
        draw.line((x, y - radius * 2, x, y + radius * 2), fill=color, width=max(1, radius // 2))


def make_icon(source: Image.Image, style: str) -> Image.Image:
    left, top, right, bottom = alpha_bbox(source)
    height = bottom - top
    head_bottom = min(bottom, top + max(1, round(height * 0.62)))
    head = source.crop((left, top, right, head_bottom))
    return contain_subject(head, (50, 50), (42, 42), style)


def make_banner(sources: list[Image.Image], style: str) -> Image.Image:
    start, end, accent = STYLE_PALETTES[style]
    canvas = gradient((750, 400), start, end)
    draw_sparkles(canvas, accent, [(72, 72, 9), (678, 90, 7), (610, 330, 6), (130, 322, 5)])
    placements = [((205, 255), (120, 80)), ((245, 315), (252, 36)), ((205, 255), (462, 82))]
    for source, (extent, offset) in zip((sources[1], sources[0], sources[7]), placements):
        cutout = contain_subject(source, (extent[0], extent[1]), extent, style)
        canvas.alpha_composite(cutout, offset)
    return canvas


def make_appreciation(source: Image.Image, style: str, thanks: bool) -> Image.Image:
    start, end, accent = STYLE_PALETTES[style]
    size = (750, 750) if thanks else (750, 560)
    canvas = gradient(size, start, end)
    if thanks:
        subject = contain_subject(source, (360, 410), (330, 380), style)
        canvas.alpha_composite(subject, (195, 155))
        draw_sparkles(canvas, accent, [(145, 180, 10), (610, 170, 8), (125, 585, 7), (625, 590, 10)])
    else:
        subject = contain_subject(source, (300, 300), (270, 270), style)
        canvas.alpha_composite(subject, (225, 40))
        draw_sparkles(canvas, accent, [(150, 110, 9), (610, 120, 8), (105, 350, 6), (650, 350, 6)])
    return canvas


def safe_output_path(path: Path, source_dir: Path) -> Path:
    resolved = path.expanduser().resolve()
    source = source_dir.expanduser().resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve()}
    if resolved in forbidden or len(resolved.parts) < 3:
        raise ValueError(f"拒绝使用过宽的输出目录：{resolved}")
    if resolved == source or resolved in source.parents or source in resolved.parents:
        raise ValueError("输出目录不能与母图目录相同，也不能互为父子目录")
    return resolved


def build(args: argparse.Namespace) -> dict[str, object]:
    sources_paths = discover_sources(args.source_dir)
    sources = [load_transparent(path) for path in sources_paths]
    rig_profiles = load_animation_rig(args.rig)
    labels = dict(DEFAULT_LABELS)
    if args.labels_json:
        supplied_labels = json.loads(args.labels_json.read_text(encoding="utf-8"))
        if not isinstance(supplied_labels, dict):
            raise ValueError("labels JSON根节点必须是对象")
        for number, label in supplied_labels.items():
            if number not in labels or not isinstance(label, str) or not 1 <= len(label) <= 4:
                raise ValueError(f"无效表情文字：{number}={label!r}")
            labels[number] = label
    text_enabled = args.text_mode == "handwritten"
    font_path = resolve_font(args.font) if text_enabled else None
    output = safe_output_path(args.output_dir, args.source_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"输出目录已存在：{output}。请选择新目录；只有用户明确要求覆盖时才使用 --overwrite")

    build_records: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="wechat-stickers-", dir=output.parent) as temp_name:
        stage = Path(temp_name) / "pack"
        main_dir = stage / "表情主图"
        thumb_dir = stage / "表情缩略图"
        main_dir.mkdir(parents=True)
        thumb_dir.mkdir(parents=True)

        used_rig: dict[str, dict[str, object]] = {}
        for source, (number, meaning, english, motion) in zip(sources, EXPRESSIONS):
            extent = (190, 176) if text_enabled else (198, 198)
            offset = (0, 18) if text_enabled else (0, 0)
            main_base = contain_subject(source, (240, 240), extent, args.style, offset)
            rig_entry = rig_profiles.get(number)
            frames, animation_meta = build_pose_preserving_frames(
                main_base, english, rig_entry, args.style, outline_radius=2
            )
            animation_meta["subject_bbox"] = list(alpha_bbox(main_base))
            text_meta: dict[str, object] = {"enabled": False}
            if text_enabled:
                assert font_path is not None
                frames, text_meta = add_animated_text(frames, labels[number], english, font_path)
            gif_bytes, gif_meta = encode_gif(frames, 100, animation_meta["durations_ms"])
            main_path = main_dir / f"{number}.gif"
            main_path.write_bytes(gif_bytes)
            used_rig[number] = {"points": merged_rig(rig_entry), "semantic_motion": motion}
            if isinstance(rig_entry, dict) and isinstance(rig_entry.get("motion_policy"), dict):
                used_rig[number]["motion_policy"] = rig_entry["motion_policy"]

            thumb = contain_subject(source, (120, 120), (102, 102), args.style)
            thumb_meta = save_png_limited(thumb, thumb_dir / f"{number}.png", 50)
            build_records.append({
                "number": number,
                "meaning": meaning,
                "english": english,
                "label": labels[number] if text_enabled else "",
                "source": sources_paths[int(number) - 1].name,
                "motion": {**animation_meta, "preset": motion, "encoded_frames": gif_meta["frames"]},
                "dynamic_text": text_meta,
                "main": gif_meta,
                "thumbnail": thumb_meta,
            })

        rig_document = {
            "version": 2,
            "coordinate_space": "subject-bbox-normalized",
            "animation_model": ENGINE_NAME,
            "expressions": used_rig,
        }
        (stage / "animation-rig.json").write_text(
            json.dumps(rig_document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        companion, companion_meta = build_companion_set(
            sources,
            args.style,
            args.reference_photo,
            args.companion_theme,
        )
        cover_meta = save_png_limited(companion["cover"], stage / "表情封面图.png", 80)
        icon_meta = save_png_limited(companion["tray_icon"], stage / "聊天面板图标.png", 30)
        banner_meta = save_jpeg_limited(companion["banner"], stage / "详情页横幅.jpg", 80)
        guide_meta = save_png_limited(companion["appreciation_guide"], stage / "赞赏引导图.png", args.appreciation_max_kb)
        thanks_meta = save_png_limited(companion["appreciation_thanks"], stage / "赞赏致谢图.png", args.appreciation_max_kb)

        manifest = {
            "title": args.title,
            "style": args.style,
            "source_directory": str(args.source_dir.resolve()),
            "animation_engine": ENGINE_NAME,
            "animation_rig": "animation-rig.json",
            "dynamic_text": {
                "enabled": text_enabled,
                "style": args.text_mode,
                "font": font_path.name if font_path else None,
                "font_size_range_px": [23, 26] if text_enabled else None,
                "stroke_width_px": 1 if text_enabled else None,
                "placement": "adaptive-top-empty-space" if text_enabled else None,
                "labels": labels if text_enabled else {},
            },
            "expressions": build_records,
            "assets": {
                "cover": cover_meta,
                "tray_icon": icon_meta,
                "banner": banner_meta,
                "appreciation_guide": guide_meta,
                "appreciation_thanks": thanks_meta,
            },
            "companion_design": companion_meta,
            "spec_profile": "wechat-cartoon-conservative-2026-09-05",
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        staged_report = validate_pack(stage, args.appreciation_max_kb)
        if not staged_report["ok"]:
            failed = [item["message"] for item in staged_report["checks"] if not item["ok"]]
            raise ValueError("生成结果未通过规格检查：" + "；".join(failed[:6]))

        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(stage), str(output))

    final_report = validate_pack(output, args.appreciation_max_kb)
    (output / "validation-report.json").write_text(json.dumps(final_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output": str(output), "ok": final_report["ok"], "summary": final_report["summary"]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="8张透明情绪母图所在目录；文件名以01到08开头")
    parser.add_argument("output_dir", type=Path, help="新的输出目录")
    parser.add_argument("--style", choices=sorted(STYLE_PALETTES), default="chibi")
    parser.add_argument("--rig", type=Path, help="按主体包围盒归一化标注的五官与肢体动画绑定JSON")
    parser.add_argument("--text-mode", choices=("handwritten", "none"), default="handwritten")
    parser.add_argument("--font", type=Path, help="支持中文的本地手写字体；不指定时自动查找")
    parser.add_argument("--labels-json", type=Path, help="以01到08为键的1–4字自定义文案JSON")
    parser.add_argument("--reference-photo", type=Path, help="用于提取色彩、场景几何和道具剪影的原始照片")
    parser.add_argument(
        "--companion-theme",
        choices=("portrait", "shopping", "nature", "celebration"),
        default="portrait",
        help="配套图个性化主题；只抽象参考元素，不复制照片中品牌或文字",
    )
    parser.add_argument("--title", default="微信动态表情包")
    parser.add_argument("--appreciation-max-kb", type=int, default=500)
    parser.add_argument("--overwrite", action="store_true", help="明确允许替换已有输出目录")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build(args)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
