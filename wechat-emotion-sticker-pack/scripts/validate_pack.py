#!/usr/bin/env python3
"""Validate a packaged WeChat sticker set against the skill's pinned limits."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - environment dependent
    raise SystemExit("Pillow is required: python3 -m pip install Pillow") from exc


MAIN_DIR = "表情主图"
THUMB_DIR = "表情缩略图"
STATIC_SPECS = {
    "表情封面图.png": ((240, 240), "PNG", 80, True),
    "聊天面板图标.png": ((50, 50), "PNG", 30, True),
    "详情页横幅.jpg": ((750, 400), "JPEG", 80, False),
    "赞赏引导图.png": ((750, 560), "PNG", None, False),
    "赞赏致谢图.png": ((750, 750), "PNG", None, False),
}
FACE_PARTS = {"head", "left_eye", "right_eye", "mouth", "left_ear", "right_ear", "left_tear", "right_tear"}
BODY_PARTS = {
    "left_paw", "right_paw", "left_wrist", "right_wrist", "left_shoulder", "right_shoulder",
    "body", "left_foot", "right_foot", "tail_base", "tail_mid", "tail",
}
EXPECTED_ENGINE = "pose-preserving-intact-silhouette-v10"


def size_kb(path: Path) -> float:
    return path.stat().st_size / 1000.0


def has_transparency(image: Image.Image) -> bool:
    rgba = image.convert("RGBA")
    lo, hi = rgba.getchannel("A").getextrema()
    return lo < 255 and hi > 0


def add_check(checks: list[dict[str, Any]], path: Path, ok: bool, message: str) -> None:
    checks.append({"path": str(path), "ok": ok, "message": message})


def load_json(path: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    if not path.is_file():
        add_check(checks, path, False, "缺少文件")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        add_check(checks, path, False, f"JSON无法读取：{exc}")
        return {}
    if not isinstance(value, dict):
        add_check(checks, path, False, "JSON根节点必须是对象")
        return {}
    add_check(checks, path, True, "JSON可读取")
    return value


def locally_animated_parts(
    frames: list[Image.Image],
    rig_entry: dict[str, Any],
    candidates: set[str],
    declared_subject_box: list[int] | None = None,
) -> list[str]:
    if not frames:
        return []
    subject_box = tuple(declared_subject_box) if declared_subject_box and len(declared_subject_box) == 4 else None
    if subject_box is None:
        first_alpha = frames[0].getchannel("A").point(lambda value: 255 if value >= 8 else 0)
        subject_box = first_alpha.getbbox()
    if subject_box is None:
        return []
    left, top, right, bottom = subject_box
    width, height = right - left, bottom - top
    extent = max(width, height)
    points = rig_entry.get("points", {}) if isinstance(rig_entry, dict) else {}
    changed: list[str] = []
    for name in sorted(candidates):
        point = points.get(name)
        if not isinstance(point, dict) or "x" not in point or "y" not in point:
            continue
        cx = left + float(point["x"]) * width
        cy = top + float(point["y"]) * height
        radius = max(4, round(float(point.get("r", 0.1)) * extent * 0.72))
        box = (
            max(0, round(cx - radius)),
            max(0, round(cy - radius)),
            min(frames[0].width, round(cx + radius)),
            min(frames[0].height, round(cy + radius)),
        )
        signatures = {
            frame.crop(box).resize((16, 16), Image.Resampling.BILINEAR).tobytes()
            for frame in frames
        }
        if len(signatures) >= 2:
            changed.append(name)
    return changed


def top_band_text_state(frames: list[Image.Image], band_height: int = 72) -> tuple[bool, bool]:
    if not frames:
        return False, False
    crops = [frame.crop((0, 0, frame.width, band_height)) for frame in frames]
    visible = any(crop.getchannel("A").getbbox() is not None for crop in crops)
    signatures = {crop.resize((60, 12), Image.Resampling.BILINEAR).tobytes() for crop in crops}
    return visible, len(signatures) >= 2


def face_alpha_coverage(
    frames: list[Image.Image],
    rig_entry: dict[str, Any],
    declared_subject_box: list[int] | None,
) -> float:
    """Return minimum opaque coverage in the eye-to-mouth facial core.

    This catches transparent seams introduced when a raised-arm extraction mask
    accidentally reaches into the cheek or central face.
    """

    if not frames or not declared_subject_box or len(declared_subject_box) != 4:
        return 0.0
    points = rig_entry.get("points", {}) if isinstance(rig_entry, dict) else {}
    required = [points.get(name) for name in ("left_eye", "right_eye", "mouth")]
    if any(not isinstance(point, dict) or "x" not in point or "y" not in point for point in required):
        return 0.0
    left, top, right, bottom = declared_subject_box
    width, height = right - left, bottom - top
    left_eye, right_eye, mouth = required
    eye_x = sorted((left + float(left_eye["x"]) * width, left + float(right_eye["x"]) * width))
    eye_y = (top + float(left_eye["y"]) * height + top + float(right_eye["y"]) * height) / 2.0
    mouth_y = top + float(mouth["y"]) * height
    spacing = max(5.0, eye_x[1] - eye_x[0])
    box = (
        max(0, round(eye_x[0] - spacing * 0.22)),
        max(0, round(eye_y - spacing * 0.20)),
        min(frames[0].width, round(eye_x[1] + spacing * 0.22)),
        min(frames[0].height, round(mouth_y + spacing * 0.20)),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return 0.0
    coverages = []
    for frame in frames:
        alpha = frame.getchannel("A").crop(box)
        histogram = alpha.histogram()
        opaque = sum(histogram[96:])
        coverages.append(opaque / max(1, alpha.width * alpha.height))
    return min(coverages)


def limb_segment_core_coverage(
    frames: list[Image.Image],
    rig_entry: dict[str, Any],
    declared_subject_box: list[int] | None,
    side: str,
    start_part: str,
    end_part: str,
) -> float:
    """Measure alpha continuity along a named segment of a rigged limb."""

    if not frames or not declared_subject_box or len(declared_subject_box) != 4:
        return 0.0
    points = rig_entry.get("points", {}) if isinstance(rig_entry, dict) else {}
    start_point = points.get(f"{side}_{start_part}")
    end_point = points.get(f"{side}_{end_part}")
    if not isinstance(start_point, dict) or not isinstance(end_point, dict):
        return 0.0
    left, top, right, bottom = declared_subject_box
    width, height = right - left, bottom - top
    start = (left + float(start_point["x"]) * width, top + float(start_point["y"]) * height)
    end = (left + float(end_point["x"]) * width, top + float(end_point["y"]) * height)
    coverages: list[float] = []
    for frame in frames:
        alpha = frame.getchannel("A")
        for fraction in (0.18, 0.34, 0.50, 0.66, 0.82):
            x = round(start[0] * (1.0 - fraction) + end[0] * fraction)
            y = round(start[1] * (1.0 - fraction) + end[1] * fraction)
            crop = alpha.crop((max(0, x - 2), max(0, y - 2), min(alpha.width, x + 3), min(alpha.height, y + 3)))
            histogram = crop.histogram()
            coverages.append(sum(histogram[96:]) / max(1, crop.width * crop.height))
    return min(coverages) if coverages else 0.0


def proximal_limb_core_coverage(
    frames: list[Image.Image],
    rig_entry: dict[str, Any],
    declared_subject_box: list[int] | None,
    side: str,
) -> float:
    return limb_segment_core_coverage(frames, rig_entry, declared_subject_box, side, "shoulder", "wrist")


def distal_limb_core_coverage(
    frames: list[Image.Image],
    rig_entry: dict[str, Any],
    declared_subject_box: list[int] | None,
    side: str,
) -> float:
    return limb_segment_core_coverage(frames, rig_entry, declared_subject_box, side, "wrist", "paw")


def inspect_image(
    path: Path,
    expected_size: tuple[int, int],
    expected_format: str,
    max_kb: int | None,
    require_transparency: bool,
    checks: list[dict[str, Any]],
) -> None:
    if not path.is_file():
        add_check(checks, path, False, "缺少文件")
        return
    try:
        with Image.open(path) as image:
            ok_size = image.size == expected_size
            add_check(checks, path, ok_size, f"尺寸 {image.size[0]}×{image.size[1]}，要求 {expected_size[0]}×{expected_size[1]}")
            ok_format = image.format == expected_format
            add_check(checks, path, ok_format, f"格式 {image.format}，要求 {expected_format}")
            if require_transparency:
                transparent = has_transparency(image)
                add_check(checks, path, transparent, "包含真实透明像素" if transparent else "缺少真实透明像素")
            elif path.name == "详情页横幅.jpg":
                add_check(checks, path, image.mode in {"RGB", "L"}, f"横幅为不透明模式 {image.mode}")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, path, False, f"无法读取图片：{exc}")
        return
    if max_kb is not None:
        actual = size_kb(path)
        add_check(checks, path, actual <= max_kb, f"体积 {actual:.1f}KB，上限 {max_kb}KB")


def validate_pack(root: Path, appreciation_max_kb: int = 500) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    main_dir = root / MAIN_DIR
    thumb_dir = root / THUMB_DIR
    manifest = load_json(root / "manifest.json", checks)
    rig_document = load_json(root / "animation-rig.json", checks)
    add_check(
        checks,
        root / "manifest.json",
        manifest.get("animation_engine") == EXPECTED_ENGINE,
        f"动画引擎 {manifest.get('animation_engine')}，要求 {EXPECTED_ENGINE}",
    )
    add_check(
        checks,
        root / "animation-rig.json",
        rig_document.get("animation_model") == EXPECTED_ENGINE,
        f"绑定动画模型 {rig_document.get('animation_model')}，要求 {EXPECTED_ENGINE}",
    )
    companion = manifest.get("companion_design", {}) if isinstance(manifest, dict) else {}
    add_check(checks, root / "manifest.json", companion.get("enabled") is True, "已启用个性化配套图设计")
    motifs = companion.get("motifs", []) if isinstance(companion, dict) else []
    add_check(checks, root / "manifest.json", isinstance(motifs, list) and bool(motifs), f"配套图视觉母题：{motifs}")
    add_check(checks, root / "manifest.json", companion.get("contains_text") is False, "配套图未添加文字")
    add_check(checks, root / "manifest.json", companion.get("brand_marks_copied") is False, "未复制原图品牌标识")
    rig_expressions = rig_document.get("expressions", {}) if isinstance(rig_document, dict) else {}
    manifest_expressions = {
        str(item.get("number")): item
        for item in manifest.get("expressions", [])
        if isinstance(item, dict) and item.get("number") is not None
    }
    text_config = manifest.get("dynamic_text", {}) if isinstance(manifest, dict) else {}
    text_enabled = bool(text_config.get("enabled")) if isinstance(text_config, dict) else False

    main_files = sorted(main_dir.glob("*.gif")) if main_dir.is_dir() else []
    thumb_files = sorted(thumb_dir.glob("*.png")) if thumb_dir.is_dir() else []
    add_check(checks, main_dir, len(main_files) == 8, f"主图数量 {len(main_files)}，要求 8")
    add_check(checks, thumb_dir, len(thumb_files) == 8, f"缩略图数量 {len(thumb_files)}，要求 8")

    for index in range(1, 9):
        stem = f"{index:02d}"
        main = main_dir / f"{stem}.gif"
        thumb = thumb_dir / f"{stem}.png"
        if not main.is_file():
            add_check(checks, main, False, "缺少主图")
        else:
            try:
                with Image.open(main) as image:
                    add_check(checks, main, image.size == (240, 240), f"尺寸 {image.size[0]}×{image.size[1]}，要求 240×240")
                    add_check(checks, main, image.format == "GIF", f"格式 {image.format}，要求 GIF")
                    frames = getattr(image, "n_frames", 1)
                    add_check(checks, main, frames >= 2, f"动画帧数 {frames}，要求至少 2")
                    add_check(checks, main, frames >= 12, f"精细动画质量门槛：帧数 {frames}，要求至少 12")
                    signatures = set()
                    rgba_frames: list[Image.Image] = []
                    for frame_index in range(frames):
                        image.seek(frame_index)
                        rgba = image.convert("RGBA").copy()
                        rgba_frames.append(rgba)
                        sample = rgba.resize((24, 24), Image.Resampling.NEAREST)
                        signatures.add(sample.tobytes())
                    add_check(checks, main, len(signatures) >= 2, f"可区分动画帧 {len(signatures)}，要求至少 2")
                    add_check(checks, main, image.info.get("loop") == 0, f"循环值 {image.info.get('loop')}，要求永久循环 0")
                    add_check(checks, main, has_transparency(image), "包含真实透明像素" if has_transparency(image) else "缺少真实透明像素")
                    record = manifest_expressions.get(stem, {})
                    motion = record.get("motion", {}) if isinstance(record, dict) else {}
                    add_check(
                        checks,
                        main,
                        motion.get("source_frames", 0) >= 16,
                        f"动画源帧数 {motion.get('source_frames')}，要求至少 16",
                    )
                    add_check(
                        checks,
                        main,
                        motion.get("encoded_frames") == frames,
                        f"实际帧数 {frames}，与清单记录 {motion.get('encoded_frames')} 一致",
                    )
                    add_check(checks, main, motion.get("detail_level") == "fine", "已声明精细动画级别")
                    facial_details = motion.get("facial_details", [])
                    detail_profile = motion.get("detail_profile", {})
                    accents = motion.get("decorative_accents", [])
                    limb_chains = motion.get("rigid_limb_chains", [])
                    add_check(checks, main, isinstance(facial_details, list) and bool(facial_details), f"五官动画细节：{facial_details}")
                    add_check(checks, main, isinstance(detail_profile, dict) and bool(detail_profile), f"解剖细节策略：{detail_profile}")
                    add_check(checks, main, isinstance(accents, list) and bool(accents), f"情绪装饰动效：{accents}")
                    add_check(checks, main, isinstance(limb_chains, list), f"刚性肢体链：{limb_chains}")
                    add_check(
                        checks,
                        main,
                        motion.get("geometry_preserving") is True,
                        "头脸与身体使用姿态保持变换，不叠加高斯拉伸",
                    )
                    add_check(
                        checks,
                        main,
                        motion.get("nonuniform_face_or_body_scale") is False,
                        "未对头脸或身体使用非等比缩放",
                    )
                    if stem == "08":
                        add_check(
                            checks,
                            main,
                            motion.get("rigid_arm_chain") is True
                            or motion.get("raised_forelimb_no_separation") is True,
                            "再见使用肩根重叠刚性链，或完整轮廓的整体肩背摆动",
                        )
                    active_parts = set(motion.get("active_parts", [])) if isinstance(motion, dict) else set()
                    face_declared = active_parts & FACE_PARTS
                    body_declared = active_parts & BODY_PARTS
                    add_check(checks, main, bool(face_declared), f"声明的面部动画部位：{sorted(face_declared)}")
                    add_check(checks, main, bool(body_declared), f"声明的身体/肢体动画部位：{sorted(body_declared)}")
                    rig_entry = rig_expressions.get(stem, {}) if isinstance(rig_expressions, dict) else {}
                    subject_box = motion.get("subject_bbox") if isinstance(motion, dict) else None
                    face_coverage = face_alpha_coverage(rgba_frames, rig_entry, subject_box)
                    add_check(checks, main, face_coverage >= 0.97, f"脸部核心区最低不透明覆盖率 {face_coverage:.3f}，要求≥0.970")
                    if stem == "01":
                        natural_happy_blink = (
                            detail_profile.get("blink_mode") == "partial-upper-lid-microblink"
                            and detail_profile.get("blink_timing") == "three-frame-down-peak-up"
                            and int(detail_profile.get("blink_duration_ms", 999)) <= 200
                            and detail_profile.get("eyelid_rim_line") is False
                            and detail_profile.get("eyelid_volume_band") is False
                            and detail_profile.get("pupil_lower_crescent_visible") is True
                            and detail_profile.get("skin_fill") == "local-two-tone-gradient"
                            and detail_profile.get("decoration_occluded_by_subject") is True
                            and 0.32 <= float(detail_profile.get("max_eye_cover", 1.0)) <= 0.44
                        )
                        add_check(checks, main, natural_happy_blink, f"开心使用保留瞳孔下缘的快速部分眨眼：{detail_profile}")
                        separated_happy_hands = (
                            detail_profile.get("limb_articulation") == "distal-wrist-overlap"
                            and detail_profile.get("opening_bilateral_wrist_wave") is True
                            and detail_profile.get("erase_proximal_arm") is False
                            and detail_profile.get("joint_overlap") is True
                            and int(detail_profile.get("limb_mask_max_width_px", 999)) <= 22
                            and motion.get("opening_bilateral_wrist_wave") is True
                            and motion.get("joint_overlap_applied") is True
                            and motion.get("proximal_arm_erased") is False
                            and motion.get("limb_articulations", {}).get("left") == "distal-wrist-overlap"
                            and motion.get("limb_articulations", {}).get("right") == "distal-wrist-overlap"
                        )
                        grounded_happy_paws = (
                            detail_profile.get("limb_articulation") == "none-intact-silhouette"
                            and detail_profile.get("grounded_forepaws_no_separation") is True
                            and detail_profile.get("opening_bilateral_wrist_wave") is False
                            and int(detail_profile.get("limb_mask_max_width_px", 999)) == 0
                            and motion.get("intact_subject_silhouette") is True
                            and motion.get("grounded_forepaws_no_separation") is True
                            and motion.get("rigid_limb_chains") == []
                        )
                        add_check(
                            checks,
                            main,
                            separated_happy_hands or grounded_happy_paws,
                            f"开心使用安全腕部链，或猫式贴地前爪完整轮廓：{detail_profile}",
                        )
                        for side, label in (("left", "左"), ("right", "右")):
                            proximal_coverage = proximal_limb_core_coverage(rgba_frames, rig_entry, subject_box, side)
                            add_check(
                                checks,
                                main,
                                proximal_coverage >= 0.92,
                                f"开心{label}肩—腕近端核心最低alpha连续率 {proximal_coverage:.3f}，要求≥0.920",
                            )
                            distal_coverage = distal_limb_core_coverage(rgba_frames, rig_entry, subject_box, side)
                            add_check(
                                checks,
                                main,
                                distal_coverage >= 0.92,
                                f"开心{label}腕—爪远端核心最低alpha连续率 {distal_coverage:.3f}，要求≥0.920",
                            )
                    elif stem == "02":
                        lively_angry = (
                            detail_profile.get("blink_mode") == "partial-upper-lid-focus-blink"
                            and detail_profile.get("body_motion") == "short-feline-weight-shift"
                            and float(detail_profile.get("body_travel_px", 0)) >= 1.5
                            and 0.20 <= float(detail_profile.get("max_eye_cover", 0)) <= 0.34
                        )
                        add_check(checks, main, lively_angry, f"生气包含短促猫式重心变化和聚焦眨眼：{detail_profile}")
                    elif stem == "03":
                        natural_tears = (
                            detail_profile.get("tear_mode") == "source-tears-plus-falling-tapered-drops"
                            and detail_profile.get("white_outline") is False
                            and float(detail_profile.get("max_added_radius_px", 99)) <= 2.4
                            and float(detail_profile.get("tear_travel_px", 0)) >= 16.0
                            and int(detail_profile.get("tear_visible_frames", 0)) >= 5
                        )
                        add_check(checks, main, natural_tears, f"伤心保留母图泪痕并添加真实下落的无白边小水滴：{detail_profile}")
                    elif stem == "04":
                        lively_laugh = (
                            detail_profile.get("detail_mode") == "closed-eye-corner-pulse"
                            and detail_profile.get("body_motion") == "side-lying-rock-and-belly-bounce"
                            and float(detail_profile.get("body_travel_px", 0)) >= 2.0
                            and float(detail_profile.get("body_rock_max_deg", 0)) >= 1.2
                        )
                        add_check(checks, main, lively_laugh, f"大笑包含侧躺摇摆、身体弹动和闭眼眼角细节：{detail_profile}")
                    elif stem == "05":
                        natural_tail_tremor = (
                            detail_profile.get("tail_motion") == "base-and-mid-stable-tip-tremor"
                            and 1.5 <= float(detail_profile.get("tail_amplitude_deg", 0)) <= 3.5
                            and int(detail_profile.get("tail_cycles", 0)) >= 2
                            and detail_profile.get("tail_joint_overlap") is True
                            and motion.get("rigid_tail_chain") is True
                            and motion.get("tail_tremor_applied") is True
                        )
                        add_check(checks, main, natural_tail_tremor, f"惊讶使用尾根封口、尾梢快速细颤：{detail_profile}")
                    elif stem == "06":
                        natural_blush = (
                            detail_profile.get("blush_mode") == "outer-lower-cheek-hatching"
                            and detail_profile.get("eye_overlay") is False
                            and int(detail_profile.get("max_alpha", 999)) <= 80
                            and detail_profile.get("blink_mode") == "partial-upper-lid-slow-blink"
                            and float(detail_profile.get("body_travel_px", 0)) >= 1.0
                        )
                        add_check(checks, main, natural_blush, f"害羞使用猫式揣手呼吸、侧摆慢眨与眼外腮红线：{detail_profile}")
                    elif stem == "07":
                        natural_thanks = (
                            detail_profile.get("blink_mode") == "partial-upper-lid-affectionate-slow-blink"
                            and detail_profile.get("body_motion") == "seated-head-tilt-and-bow"
                            and float(detail_profile.get("body_travel_px", 0)) >= 2.0
                        )
                        add_check(checks, main, natural_thanks, f"感谢使用坐姿歪头、慢眨和轻鞠躬：{detail_profile}")
                    elif stem == "08":
                        protected_bye_face = (
                            detail_profile.get("blink_mode") == "none"
                            and detail_profile.get("decoration_occluded_by_subject") is True
                            and motion.get("proximal_arm_erased") is False
                            and (
                                (
                                    detail_profile.get("face_guard") is True
                                    and motion.get("face_guard_applied") is True
                                    and detail_profile.get("limb_articulation") == "full-chain-shoulder-overlap"
                                    and detail_profile.get("joint_overlap") is True
                                    and int(detail_profile.get("limb_mask_max_width_px", 999)) <= 30
                                    and motion.get("joint_overlap_applied") is True
                                    and motion.get("limb_articulations", {}).get("left") == "full-chain-shoulder-overlap"
                                )
                                or (
                                    detail_profile.get("limb_articulation") == "whole-body-sway-intact-silhouette"
                                    and detail_profile.get("raised_forelimb_no_separation") is True
                                    and int(detail_profile.get("limb_mask_max_width_px", 999)) == 0
                                    and motion.get("intact_subject_silhouette") is True
                                    and motion.get("raised_forelimb_no_separation") is True
                                    and motion.get("rigid_limb_chains") == []
                                )
                            )
                        )
                        add_check(checks, main, protected_bye_face, f"再见使用无裂缝抬爪策略且轨迹线位于主体后方：{detail_profile}")
                        proximal_coverage = proximal_limb_core_coverage(rgba_frames, rig_entry, subject_box, "left")
                        add_check(
                            checks,
                            main,
                            proximal_coverage >= 0.92,
                            f"挥手肩—腕近端核心最低alpha连续率 {proximal_coverage:.3f}，要求≥0.920",
                        )
                        distal_coverage = distal_limb_core_coverage(rgba_frames, rig_entry, subject_box, "left")
                        add_check(
                            checks,
                            main,
                            distal_coverage >= 0.92,
                            f"挥手腕—爪远端核心最低alpha连续率 {distal_coverage:.3f}，要求≥0.920",
                        )
                    face_changed = locally_animated_parts(rgba_frames, rig_entry, face_declared, subject_box)
                    body_changed = locally_animated_parts(rgba_frames, rig_entry, body_declared, subject_box)
                    add_check(checks, main, bool(face_changed), f"检测到面部区域位姿变化：{face_changed}")
                    add_check(checks, main, bool(body_changed), f"检测到身体/肢体区域位姿变化：{body_changed}")
                    if text_enabled:
                        label = record.get("label", "") if isinstance(record, dict) else ""
                        text_record = record.get("dynamic_text", {}) if isinstance(record, dict) else {}
                        add_check(checks, main, isinstance(label, str) and 1 <= len(label) <= 4, f"动态文案：{label!r}")
                        add_check(checks, main, bool(text_record.get("enabled")), "已声明动态手写文字")
                        font_size = text_record.get("font_size")
                        add_check(
                            checks,
                            main,
                            isinstance(font_size, int) and 23 <= font_size <= 26,
                            f"动态文字字号 {font_size}，要求 23–26px",
                        )
                        add_check(
                            checks,
                            main,
                            text_record.get("stroke_width") == 1,
                            f"动态文字白描边 {text_record.get('stroke_width')}px，要求 1px",
                        )
                        add_check(
                            checks,
                            main,
                            text_record.get("region") in {"top-left", "top-center", "top-right"},
                            f"动态文字自适应位置：{text_record.get('region')}",
                        )
                        anchor = text_record.get("anchor")
                        natural_anchor = (
                            isinstance(anchor, list)
                            and len(anchor) == 2
                            and all(isinstance(value, int) for value in anchor)
                            and 0 <= anchor[0] <= 235
                            and 0 <= anchor[1] <= 62
                        )
                        add_check(checks, main, natural_anchor, f"动态文字锚点：{anchor}")
                        text_visible, text_moves = top_band_text_state(rgba_frames)
                        add_check(checks, main, text_visible, "顶部72px文字区域包含可见像素")
                        add_check(checks, main, text_moves, "顶部72px文字区域在帧间发生变化")
            except Exception as exc:  # noqa: BLE001
                add_check(checks, main, False, f"无法读取GIF：{exc}")
            actual = size_kb(main)
            add_check(checks, main, actual <= 100, f"体积 {actual:.1f}KB，上限 100KB")
        inspect_image(thumb, (120, 120), "PNG", 50, True, checks)

    for filename, (dimensions, image_format, max_kb, transparent) in STATIC_SPECS.items():
        limit = appreciation_max_kb if filename.startswith("赞赏") else max_kb
        inspect_image(root / filename, dimensions, image_format, limit, transparent, checks)

    failures = [item for item in checks if not item["ok"]]
    return {
        "ok": not failures,
        "root": str(root.resolve()),
        "summary": {"checks": len(checks), "passed": len(checks) - len(failures), "failed": len(failures)},
        "checks": checks,
        "manual_review": [
            "确认八张角色身份与画风一致，动作轮廓具有足够差异。",
            "逐帧确认眼距、脸宽高比、下颌线、颈肩宽度和躯干比例稳定；五官不漂移、头耳连接不撕裂、四肢不呈贴片感、承重点不无故滑动且循环首尾自然。",
            "重点检查开心的快速部分眨眼：仅用约3个连续帧完成下压—峰值—回弹，峰值仍能看到两只瞳孔圆润的下缘，不得出现横向阴影带、整眼消失或一条线式闭眼；伤心泪滴应跨至少5帧向下移动，害羞与感谢有自然慢眨，惊讶尾梢应细颤，再见挥爪轨迹不得压在爪上。",
            "开心主动作爪必须10倍放大检查：人物安全腕链应保持腕口相交；猫的落地承重爪优先保持完整主体轮廓。两种策略都不能出现裂缝、亮色笔画穿爪、双影、贴片边或循环跳动。",
            "再见主动作爪必须10倍放大检查：安全刚性链要保持关节重叠；深色猫可改用完整轮廓的肩背整体摆动。两种策略都不能出现白/透明月牙、彩色轨迹穿爪、双影或贴片边。",
            "对生气、大笑、害羞和感谢逐帧确认身体重心、眼睑或眼角细节确实变化；只动文字或装饰、主体视觉上静止时仍判为不合格。",
            "对惊讶单独放大尾巴：尾根和尾中段稳定且连续，仅尾梢小幅快速颤动；不得整条尾巴脱离身体或像橡皮弯折。",
            "确认手写文字无缺字、乱码、断笔或遮挡角色，并与对应情绪含义一致。",
            "确认装饰物与情绪或原图主题有关，通常仅1–3个；高亮装饰用主体alpha反向遮罩，不得跨过五官、四肢、关节、尾巴、文字或动作轮廓。",
            "确认封面、聊天面板图标、横幅和赞赏图已抽象使用原图色彩、场景或道具特征，不复制品牌文字与商标。",
            "区域变化机检与姿态保持元数据不能代替对结构稳定性、动作节奏与情绪语义的人工判断。",
            "确认表情主图主体有约2px白色描边，其他透明素材没有白描边。",
            "确认详情页横幅没有文字、二维码、网址、水印或近白背景。",
            "确认照片、角色、字体和其他素材的版权或肖像授权。",
            "提交前以微信表情开放平台后台显示的动态规格为准。",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack_dir", type=Path, help="打包后的表情素材目录")
    parser.add_argument("--appreciation-max-kb", type=int, default=500, help="两张赞赏图的工程体积上限")
    parser.add_argument("--no-write", action="store_true", help="只打印报告，不写 validation-report.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_pack(args.pack_dir, args.appreciation_max_kb)
    if not args.no_write:
        report_path = args.pack_dir / "validation-report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
