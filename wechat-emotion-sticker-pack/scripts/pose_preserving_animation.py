#!/usr/bin/env python3
"""Fine pose-preserving sticker animation without rubber-like deformation.

The character's face, head, neck and torso share one similarity transform around
an anatomical support pivot. Explicitly rigged, silhouette-separated limbs may
rotate as rigid shoulder-wrist-hand chains. Facial detail is added with small
overlay animation, never by stretching the face.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from part_aware_animation import BODY_PARTS, FACE_PARTS, load_animation_rig, merged_rig, rig_to_pixels


FRAME_COUNT = 16
ENGINE_NAME = "pose-preserving-intact-silhouette-v10"
FRAME_DURATIONS = {
    "happy": [100] + [60] * 14 + [100],
    "angry": [90] + [50] * 14 + [90],
    "sad": [140] + [80] * 14 + [150],
    "laugh": [90] + [50] * 14 + [100],
    "surprised": [120] + [55] * 14 + [130],
    "shy": [120] + [70] * 14 + [130],
    "thanks": [140] + [75] * 14 + [150],
    "bye": [100] + [55] * 14 + [120],
}

ACTIVE_PARTS = {
    "happy": {"head", "left_eye", "right_eye", "mouth", "body", "left_paw", "right_paw"},
    "angry": {"head", "left_eye", "right_eye", "mouth", "body", "left_paw", "right_paw"},
    "sad": {"head", "left_eye", "right_eye", "mouth", "left_tear", "right_tear", "body"},
    "laugh": {"head", "left_eye", "right_eye", "mouth", "body", "left_paw", "right_paw"},
    "surprised": {"head", "left_eye", "right_eye", "mouth", "body", "left_paw", "right_paw", "tail"},
    "shy": {"head", "left_eye", "right_eye", "mouth", "body", "left_paw", "right_paw"},
    "thanks": {"head", "left_eye", "right_eye", "mouth", "body", "left_paw", "right_paw"},
    "bye": {"head", "left_eye", "right_eye", "mouth", "body", "left_shoulder", "left_wrist", "left_paw"},
}

FACIAL_DETAILS = {
    "happy": ["upper-lid-partial-microblink"],
    "angry": ["focused-partial-blink"],
    "sad": ["tear-drop"],
    "laugh": ["closed-eye-corner-pulse", "laugh-lines"],
    "surprised": ["surprise-rays"],
    "shy": ["shy-partial-slow-blink", "outer-cheek-hatching"],
    "thanks": ["affectionate-partial-slow-blink", "warm-heart"],
    "bye": ["smile-hold"],
}

DETAIL_PROFILES = {
    "happy": {
        "blink_mode": "partial-upper-lid-microblink",
        "blink_timing": "three-frame-down-peak-up",
        "blink_duration_ms": 180,
        "max_eye_cover": 0.34,
        "eyelid_rim_line": False,
        "eyelid_volume_band": False,
        "pupil_lower_crescent_visible": True,
        "skin_fill": "local-two-tone-gradient",
        "limb_articulation": "distal-wrist-overlap",
        "opening_bilateral_wrist_wave": True,
        "erase_proximal_arm": False,
        "joint_overlap": True,
        "limb_mask_max_width_px": 22,
        "decoration_occluded_by_subject": True,
    },
    "angry": {
        "blink_mode": "partial-upper-lid-focus-blink",
        "max_eye_cover": 0.30,
        "body_motion": "short-feline-weight-shift",
        "body_travel_px": 1.8,
    },
    "sad": {
        "tear_mode": "source-tears-plus-falling-tapered-drops",
        "white_outline": False,
        "max_added_radius_px": 2.3,
        "tear_travel_px": 18.0,
        "tear_visible_frames": 6,
    },
    "laugh": {
        "detail_mode": "closed-eye-corner-pulse",
        "body_motion": "side-lying-rock-and-belly-bounce",
        "body_travel_px": 2.2,
        "body_rock_max_deg": 1.40,
    },
    "surprised": {
        "detail_mode": "outer-surprise-rays",
        "tail_motion": "base-and-mid-stable-tip-tremor",
        "tail_amplitude_deg": 3.30,
        "tail_cycles": 3,
        "tail_joint_overlap": True,
    },
    "shy": {
        "blink_mode": "partial-upper-lid-slow-blink",
        "max_eye_cover": 0.26,
        "body_motion": "loaf-breath-and-side-sway",
        "body_travel_px": 1.3,
        "blush_mode": "outer-lower-cheek-hatching",
        "max_alpha": 78,
        "eye_overlay": False,
    },
    "thanks": {
        "blink_mode": "partial-upper-lid-affectionate-slow-blink",
        "max_eye_cover": 0.32,
        "body_motion": "seated-head-tilt-and-bow",
        "body_travel_px": 2.8,
        "detail_mode": "outer-warm-heart",
    },
    "bye": {
        "blink_mode": "none",
        "face_guard": True,
        "limb_articulation": "full-chain-shoulder-overlap",
        "erase_proximal_arm": False,
        "joint_overlap": True,
        "limb_mask_max_width_px": 30,
        "decoration_occluded_by_subject": True,
    },
}

DECORATIVE_ACCENTS = {
    "happy": ["sparkles"],
    "angry": ["stress-marks"],
    "sad": ["tear-drops"],
    "laugh": ["laugh-rays"],
    "surprised": ["surprise-rays"],
    "shy": ["blush"],
    "thanks": ["heart"],
    "bye": ["wave-trails"],
}


def _sample_bilinear(array: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    height, width, _ = array.shape
    x0 = np.floor(map_x).astype(np.int32)
    y0 = np.floor(map_y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)
    x0 = np.clip(x0, 0, width - 1)
    y0 = np.clip(y0, 0, height - 1)
    weight_x = (map_x - x0)[..., None]
    weight_y = (map_y - y0)[..., None]
    top = array[y0, x0] * (1.0 - weight_x) + array[y0, x1] * weight_x
    bottom = array[y1, x0] * (1.0 - weight_x) + array[y1, x1] * weight_x
    return top * (1.0 - weight_y) + bottom * weight_y


def _similarity_transform(
    image: Image.Image,
    pivot: tuple[float, float],
    angle: float = 0.0,
    scale: float = 1.0,
    dx: float = 0.0,
    dy: float = 0.0,
) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
    alpha = rgba[..., 3:4]
    premultiplied = np.concatenate((rgba[..., :3] * alpha, alpha), axis=2)
    height, width = rgba.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    pivot_x, pivot_y = pivot
    translated_x = xx - dx - pivot_x
    translated_y = yy - dy - pivot_y
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    map_x = pivot_x + (cosine * translated_x + sine * translated_y) / scale
    map_y = pivot_y + (-sine * translated_x + cosine * translated_y) / scale
    map_x = np.clip(map_x, 0, width - 1)
    map_y = np.clip(map_y, 0, height - 1)
    sampled = _sample_bilinear(premultiplied, map_x, map_y)
    out_alpha = sampled[..., 3:4]
    out_rgb = np.divide(sampled[..., :3], out_alpha, out=np.zeros_like(sampled[..., :3]), where=out_alpha > 1e-5)
    output = np.concatenate((out_rgb, out_alpha), axis=2)
    return Image.fromarray(np.clip(np.rint(output * 255.0), 0, 255).astype(np.uint8), "RGBA")


def _white_outline(image: Image.Image, radius: int) -> Image.Image:
    """Outline the completed posed silhouette, never the pre-cut source parts."""

    if radius <= 0:
        return image
    alpha = image.getchannel("A")
    expanded = alpha.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    edge = ImageChops.subtract(expanded, alpha)
    outline = Image.new("RGBA", image.size, (255, 255, 255, 0))
    outline.putalpha(edge)
    return Image.alpha_composite(outline, image)


def _support_pivot(points: dict[str, dict[str, float]]) -> tuple[float, float]:
    feet = [points[name] for name in ("left_foot", "right_foot") if name in points]
    if feet:
        return (sum(p["x"] for p in feet) / len(feet), sum(p["y"] for p in feet) / len(feet))
    body = points.get("body") or points.get("head")
    return (120.0, 205.0) if body is None else (body["x"], body["y"] + body["r"] * 0.85)


def _timing(index: int) -> tuple[float, float, float, float]:
    t = index / max(1, FRAME_COUNT - 1)
    cycle = math.sin(2.0 * math.pi * t)
    pulse = math.sin(math.pi * t) ** 2
    double_wave = math.sin(4.0 * math.pi * t) * math.sin(math.pi * t)
    return t, cycle, pulse, double_wave


def _motion(
    emotion: str,
    index: int,
    motion_policy: dict[str, Any] | None = None,
) -> tuple[float, float, float, float, dict[str, float]]:
    t, cycle, pulse, double_wave = _timing(index)
    motion_policy = motion_policy or {}
    if emotion == "happy":
        # Two small, slightly offset wrist waves happen only at the opening.
        # The envelope begins and ends at zero, so neither hand snaps when the
        # loop starts or when the body bounce takes over.
        wave_window = 0.0
        left_wave = right_wave = 0.0
        if t <= 0.50:
            wave_t = t / 0.50
            wave_window = math.sin(math.pi * wave_t) ** 2
            left_wave = -5.4 * math.sin(4.0 * math.pi * wave_t) * wave_window
            right_wave = 4.9 * math.sin(4.0 * math.pi * wave_t - 0.24) * wave_window
        grounded = motion_policy.get("forepaws") == "grounded-intact-silhouette"
        body_dx = 0.55 * cycle if grounded else 0.22 * cycle
        return body_dx, -2.0 * pulse, 0.20 * cycle, 1.0 + 0.007 * pulse, {
            "left": left_wave,
            "right": right_wave,
        }
    if emotion == "angry":
        return 0.90 * double_wave, 0.25 * abs(double_wave), 0.92 * double_wave, 1.0 + 0.004 * pulse, {}
    if emotion == "sad":
        return -0.35 * pulse, 1.8 * pulse, -0.22 * pulse, 1.0 - 0.002 * pulse, {}
    if emotion == "laugh":
        return 0.80 * cycle, -2.20 * abs(cycle), 1.40 * cycle, 1.0 + 0.008 * abs(cycle), {}
    if emotion == "surprised":
        tail_tremor = 3.30 * math.sin(6.0 * math.pi * t) * math.sin(math.pi * t) ** 2
        return 0.0, -1.50 * pulse, 0.0, 1.0 + 0.016 * pulse, {"tail": tail_tremor}
    if emotion == "shy":
        return 0.65 * cycle, 0.35 * abs(cycle), 1.05 * cycle, 1.0 + 0.004 * pulse, {}
    if emotion == "thanks":
        return 0.20 * cycle, 2.80 * pulse, 0.72 * cycle - 0.28 * pulse, 1.0 - 0.005 * pulse, {}
    if emotion == "bye":
        intact = motion_policy.get("raised_forelimb") == "whole-body-sway-intact-silhouette"
        if intact:
            # A seated cat waves from the shoulder girdle and balance shift.
            # Keeping the full silhouette intact avoids cutting a dark paw at
            # the wrist or opening a white crescent at the shoulder root.
            return 0.45 * double_wave, -0.25 * pulse, 0.82 * double_wave, 1.0, {"left": 0.0}
        return 0.12 * cycle, 0.0, 0.16 * cycle, 1.0, {"left": 2.40 * double_wave}
    raise ValueError(f"未知动画语义：{emotion}")


def _circle(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float, fill: int) -> None:
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _has_explicit_chain(rig_entry: dict[str, Any] | None, side: str) -> bool:
    supplied = rig_entry.get("points", {}) if isinstance(rig_entry, dict) else {}
    return all(f"{side}_{name}" in supplied for name in ("shoulder", "wrist", "paw"))


def _has_explicit_tail_chain(rig_entry: dict[str, Any] | None) -> bool:
    supplied = rig_entry.get("points", {}) if isinstance(rig_entry, dict) else {}
    return all(name in supplied for name in ("tail_base", "tail_mid", "tail"))


def _face_guard(image: Image.Image, points: dict[str, dict[str, float]]) -> Image.Image:
    guard = Image.new("L", image.size, 0)
    head = points.get("head")
    if head is None:
        return guard
    draw = ImageDraw.Draw(guard)
    draw.ellipse(
        (
            head["x"] - head["r"] * 0.73,
            head["y"] - head["r"] * 0.68,
            head["x"] + head["r"] * 0.73,
            head["y"] + head["r"] * 0.84,
        ),
        fill=255,
    )
    return guard.filter(ImageFilter.GaussianBlur(1.0))


def _limb_masks(
    image: Image.Image,
    points: dict[str, dict[str, float]],
    side: str,
    articulation: str,
) -> tuple[Image.Image, Image.Image] | None:
    names = tuple(f"{side}_{name}" for name in ("shoulder", "wrist", "paw"))
    if any(name not in points for name in names):
        return None
    shoulder, wrist, paw = (points[name] for name in names)
    patch_mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(patch_mask)
    if articulation == "distal-wrist-overlap":
        # Keep the elbow and sleeve completely in the base layer. Only the
        # wrist-to-hand segment moves, with a protected overlap disk at the
        # cuff so the two layers cannot open into a crescent-shaped crack.
        width = max(6, min(18, round(min(wrist["r"], paw["r"]) * 0.55)))
        chain = [(wrist["x"], wrist["y"]), (paw["x"], paw["y"])]
        draw.line(chain, fill=255, width=width, joint="curve")
        _circle(draw, chain[0], min(width * 0.68, wrist["r"] * 0.48), 255)
        _circle(draw, chain[1], min(22.0, max(width * 0.98, paw["r"] * 0.62)), 255)
        patch_mask = patch_mask.filter(ImageFilter.GaussianBlur(0.65))
        erase_mask = patch_mask.copy()
        joint_guard = Image.new("L", image.size, 0)
        joint_draw = ImageDraw.Draw(joint_guard)
        _circle(joint_draw, chain[0], max(5.0, width * 0.78), 255)
        joint_guard = joint_guard.filter(ImageFilter.GaussianBlur(0.85))
        erase_mask = ImageChops.subtract(erase_mask, joint_guard)
    else:
        # Full chains are reserved for silhouettes with clear negative space.
        width = max(8, min(30, round(min(shoulder["r"], wrist["r"], paw["r"]) * 1.18)))
        chain = [(shoulder["x"], shoulder["y"]), (wrist["x"], wrist["y"]), (paw["x"], paw["y"])]
        draw.line(chain, fill=255, width=width, joint="curve")
        _circle(draw, chain[0], min(width * 0.72, shoulder["r"] * 0.70), 255)
        _circle(draw, chain[1], min(width * 0.78, wrist["r"] * 0.82), 255)
        _circle(draw, chain[2], min(26.0, max(width * 1.05, paw["r"] * 0.86)), 255)
        patch_mask = patch_mask.filter(ImageFilter.GaussianBlur(0.75))
        erase_mask = patch_mask.copy()
        if articulation == "full-chain-shoulder-overlap":
            # Keep a stationary shoulder disk in the base.  The rotated limb
            # overlaps this disk on every frame, sealing the joint without a
            # transparent crescent or a colour line that reads as a crack.
            joint_guard = Image.new("L", image.size, 0)
            joint_draw = ImageDraw.Draw(joint_guard)
            _circle(joint_draw, chain[0], max(6.0, width * 0.90), 255)
            joint_guard = joint_guard.filter(ImageFilter.GaussianBlur(0.90))
            erase_mask = ImageChops.subtract(erase_mask, joint_guard)

    guard = _face_guard(image, points)
    patch_mask = ImageChops.subtract(patch_mask, guard)
    erase_mask = ImageChops.subtract(erase_mask, guard)
    alpha = image.getchannel("A")
    empty = Image.new("L", image.size, 0)
    return Image.composite(patch_mask, empty, alpha), Image.composite(erase_mask, empty, alpha)


def _replace_rigid_limb(
    image: Image.Image,
    points: dict[str, dict[str, float]],
    side: str,
    angle: float,
    articulation: str,
) -> tuple[Image.Image, bool]:
    if abs(angle) < 1e-4:
        return image.copy(), False
    masks = _limb_masks(image, points, side, articulation)
    if masks is None:
        return image.copy(), False
    patch_mask, erase_mask = masks
    pivot_name = "wrist" if articulation == "distal-wrist-overlap" else "shoulder"
    pivot = points[f"{side}_{pivot_name}"]
    red, green, blue, alpha = image.convert("RGBA").split()
    inverse_mask = Image.eval(erase_mask, lambda value: 255 - value)
    base_alpha = ImageChops.multiply(alpha, inverse_mask)
    base = Image.merge("RGBA", (red, green, blue, base_alpha))
    patch_alpha = ImageChops.multiply(alpha, patch_mask)
    patch = Image.merge("RGBA", (red, green, blue, patch_alpha))
    rotated_patch = _similarity_transform(patch, (pivot["x"], pivot["y"]), angle=angle)
    return Image.alpha_composite(base, rotated_patch), True


def _replace_rigid_tail(
    image: Image.Image,
    points: dict[str, dict[str, float]],
    angle: float,
) -> tuple[Image.Image, bool]:
    """Rotate only the distal tail around a sealed mid-tail joint.

    A startled cat stabilises the tail base with the pelvis; the visible fine
    tremor travels mainly through the distal half. Keeping base-to-mid fixed
    also avoids opening a transparent wedge where the tail meets the body.
    """

    if abs(angle) < 1e-4 or any(name not in points for name in ("tail_base", "tail_mid", "tail")):
        return image.copy(), False
    _base_point, mid_point, tip_point = (points[name] for name in ("tail_base", "tail_mid", "tail"))
    width = max(10, min(38, round(min(mid_point["r"], tip_point["r"]) * 1.35)))
    patch_mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(patch_mask)
    chain = [(mid_point["x"], mid_point["y"]), (tip_point["x"], tip_point["y"])]
    draw.line(chain, fill=255, width=width, joint="curve")
    _circle(draw, chain[0], width * 0.86, 255)
    _circle(draw, chain[1], width * 0.96, 255)
    patch_mask = patch_mask.filter(ImageFilter.GaussianBlur(0.78))
    erase_mask = patch_mask.copy()
    base_guard = Image.new("L", image.size, 0)
    _circle(ImageDraw.Draw(base_guard), chain[0], width * 1.08, 255)
    base_guard = base_guard.filter(ImageFilter.GaussianBlur(0.95))
    erase_mask = ImageChops.subtract(erase_mask, base_guard)
    alpha = image.getchannel("A")
    empty = Image.new("L", image.size, 0)
    patch_mask = Image.composite(patch_mask, empty, alpha)
    erase_mask = Image.composite(erase_mask, empty, alpha)
    red, green, blue, alpha = image.convert("RGBA").split()
    base_alpha = ImageChops.multiply(alpha, Image.eval(erase_mask, lambda value: 255 - value))
    base = Image.merge("RGBA", (red, green, blue, base_alpha))
    patch_alpha = ImageChops.multiply(alpha, patch_mask)
    patch = Image.merge("RGBA", (red, green, blue, patch_alpha))
    rotated = _similarity_transform(patch, (mid_point["x"], mid_point["y"]), angle=angle)
    return Image.alpha_composite(base, rotated), True


def _transform_xy(xy: tuple[float, float], pivot: tuple[float, float], angle: float, scale: float, dx: float, dy: float) -> tuple[float, float]:
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    px, py = pivot
    x, y = xy[0] - px, xy[1] - py
    return (px + scale * (cosine * x - sine * y) + dx, py + scale * (sine * x + cosine * y) + dy)


def _posed_points(
    points: dict[str, dict[str, float]], pivot: tuple[float, float], angle: float,
    scale: float, dx: float, dy: float, limb_angles: dict[str, float],
    limb_articulations: dict[str, str],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for name, point in points.items():
        xy = (point["x"], point["y"])
        if "tail" in limb_angles and name == "tail":
            tail_mid = points.get("tail_mid")
            if tail_mid is not None:
                xy = _transform_xy(xy, (tail_mid["x"], tail_mid["y"]), limb_angles["tail"], 1.0, 0.0, 0.0)
        for side, limb_angle in limb_angles.items():
            if side == "tail":
                continue
            part = name.split("_", 1)[1] if name.startswith(f"{side}_") else ""
            articulation = limb_articulations.get(side, "full-chain")
            if articulation == "distal-wrist-overlap" and part == "paw":
                wrist = points.get(f"{side}_wrist")
                if wrist is not None:
                    xy = _transform_xy(xy, (wrist["x"], wrist["y"]), limb_angle, 1.0, 0.0, 0.0)
            elif articulation in {"full-chain", "full-chain-shoulder-overlap"} and part in {"wrist", "paw"}:
                shoulder = points.get(f"{side}_shoulder")
                if shoulder is not None:
                    xy = _transform_xy(xy, (shoulder["x"], shoulder["y"]), limb_angle, 1.0, 0.0, 0.0)
        x, y = _transform_xy(xy, pivot, angle, scale, dx, dy)
        result[name] = {"x": x, "y": y, "r": point["r"] * scale}
    return result


def _local_surface_color(image: Image.Image, point: dict[str, float]) -> tuple[int, int, int, int]:
    x, y, radius = point["x"], point["y"], max(3.0, point["r"])
    # Sample cheek skin below the eye; sampling above often catches eyebrow or
    # hair and creates a dark "crack" when used as an eyelid patch.
    box = (max(0, round(x - radius * 0.78)), max(0, round(y + radius * 0.62)),
           min(image.width, round(x + radius * 0.78)), min(image.height, round(y + radius * 1.48)))
    if box[2] <= box[0] or box[3] <= box[1]:
        return (232, 184, 142, 255)
    pixels = np.asarray(image.crop(box).convert("RGBA")).reshape(-1, 4)
    visible = pixels[pixels[:, 3] > 180]
    if len(visible) < 4:
        return (232, 184, 142, 255)
    luminance = visible[:, :3].mean(axis=1)
    usable = visible[luminance >= np.percentile(luminance, 38)]
    color = np.median(usable[:, :3], axis=0).astype(np.uint8)
    return (int(color[0]), int(color[1]), int(color[2]), 255)


def _line(draw: ImageDraw.ImageDraw, coords: list[tuple[float, float]], factor: int,
          color: tuple[int, int, int, int], width: float = 1.8) -> None:
    scaled = [(round(x * factor), round(y * factor)) for x, y in coords]
    draw.line(scaled, fill=(255, 255, 255, min(230, color[3])), width=max(1, round((width + 1.6) * factor)), joint="curve")
    draw.line(scaled, fill=color, width=max(1, round(width * factor)), joint="curve")


def _keyframed_value(t: float, keyframes: tuple[tuple[float, float], ...]) -> float:
    if t <= keyframes[0][0]:
        return keyframes[0][1]
    for (start_t, start_value), (end_t, end_value) in zip(keyframes, keyframes[1:]):
        if t <= end_t:
            progress = (t - start_t) / max(1e-6, end_t - start_t)
            eased = progress * progress * (3.0 - 2.0 * progress)
            return start_value * (1.0 - eased) + end_value * eased
    return keyframes[-1][1]


def _blink_amount(emotion: str, t: float) -> float:
    if emotion == "happy":
        # A quick partial blink survives GIF quantization better than a slow
        # full closure: three delivered frames show down, peak and up while a
        # rounded lower crescent of each pupil remains visible throughout.
        return _keyframed_value(t, (
            (0.00, 0.00),
            (0.60, 0.00),
            (0.67, 0.16),
            (0.73, 0.34),
            (0.80, 0.14),
            (0.86, 0.00),
            (1.00, 0.00),
        ))
    if emotion == "angry":
        return _keyframed_value(t, (
            (0.00, 0.00),
            (0.28, 0.00),
            (0.38, 0.13),
            (0.47, 0.30),
            (0.56, 0.10),
            (0.65, 0.00),
            (1.00, 0.00),
        ))
    if emotion == "shy":
        return _keyframed_value(t, (
            (0.00, 0.00),
            (0.48, 0.00),
            (0.61, 0.11),
            (0.72, 0.26),
            (0.82, 0.08),
            (0.90, 0.00),
            (1.00, 0.00),
        ))
    if emotion == "thanks":
        return _keyframed_value(t, (
            (0.00, 0.00),
            (0.26, 0.00),
            (0.42, 0.14),
            (0.58, 0.32),
            (0.73, 0.12),
            (0.86, 0.00),
            (1.00, 0.00),
        ))
    return 0.0


def _local_skin_gradient(
    image: Image.Image,
    eye: dict[str, float],
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    cx, cy, radius = eye["x"], eye["y"], max(3.0, eye["r"])

    def sample(y0: float, y1: float) -> tuple[int, int, int, int]:
        box = (
            max(0, round(cx - radius * 0.58)),
            max(0, round(cy + radius * y0)),
            min(image.width, round(cx + radius * 0.58)),
            min(image.height, round(cy + radius * y1)),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return _local_surface_color(image, eye)
        pixels = np.asarray(image.crop(box).convert("RGBA")).reshape(-1, 4)
        visible = pixels[pixels[:, 3] > 180]
        if len(visible) < 4:
            return _local_surface_color(image, eye)
        # Sample the median surface colour.  Biasing toward bright pixels can
        # accidentally select sclera/iris on large-eyed animals and paint a
        # pale rectangular patch over otherwise dark fur.
        color = np.median(visible[:, :3], axis=0).astype(np.uint8)
        return int(color[0]), int(color[1]), int(color[2]), 255

    # Both bands sit outside the visible eye aperture.  This works for skin,
    # fur and feathers without borrowing colour from the eyeball itself.
    return sample(-1.90, -1.25), sample(1.08, 1.62)


def _apply_upper_lid_curtain(
    frame: Image.Image,
    points: dict[str, dict[str, float]],
    amount: float,
) -> Image.Image:
    """Lower a softly curved, skin-toned upper lid over each open eye.

    The moving boundary is an area, not a replacement stroke. This partial
    microblink always leaves a rounded lower-eye crescent visible, so the eye
    cannot collapse to a single hard horizontal line.
    """

    if amount < 0.02:
        return frame
    result = frame.copy()
    for name in ("left_eye", "right_eye"):
        eye = points.get(name)
        if eye is None:
            continue
        cx, cy, radius = eye["x"], eye["y"], max(3.0, eye["r"])
        rx, ry = radius * 0.78, radius * 0.50
        factor = 4
        mask_large = Image.new("L", (frame.width * factor, frame.height * factor), 0)
        mask_draw = ImageDraw.Draw(mask_large)
        top = cy - ry * 1.08
        descent = 2.0 * ry * min(0.34, amount)
        boundary: list[tuple[float, float]] = []
        for step in range(17):
            normalized_x = -1.0 + 2.0 * step / 16.0
            x = cx + normalized_x * rx
            # The centre of the upper lid descends slightly farther than the
            # corners, producing a rounded eyelid instead of a ruler-straight line.
            sag = ry * 0.32 * (1.0 - normalized_x * normalized_x) * min(1.0, amount / 0.26)
            boundary.append((x, top + descent + sag))
        polygon = [(cx - rx, top - 1.2 * ry), (cx + rx, top - 1.2 * ry), *reversed(boundary)]
        mask_draw.polygon([(round(x * factor), round(y * factor)) for x, y in polygon], fill=255)
        mask = mask_large.resize(frame.size, Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(0.28))

        upper_skin, lower_skin = _local_skin_gradient(frame, eye)
        lower_lid_shadow = (
            min(255, round(lower_skin[0] * 1.005)),
            max(0, round(lower_skin[1] * 0.985)),
            max(0, round(lower_skin[2] * 0.97)),
            255,
        )
        # Fill the entire masked source with skin colour before adding the
        # vertical gradient. A transparent-black source can quantize into a
        # dark horizontal band at the top edge of an animated GIF.
        patch = Image.new("RGBA", frame.size, upper_skin)
        patch_draw = ImageDraw.Draw(patch)
        gradient_top = max(0, round(top - ry))
        gradient_bottom = min(frame.height - 1, round(cy + ry * 1.15))
        for y in range(gradient_top, gradient_bottom + 1):
            blend = (y - gradient_top) / max(1, gradient_bottom - gradient_top)
            color = tuple(round(upper_skin[channel] * (1.0 - blend) + lower_lid_shadow[channel] * blend) for channel in range(3))
            patch_draw.line((round(cx - rx - 2), y, round(cx + rx + 2), y), fill=(*color, 255))
        patch.putalpha(mask)
        result = Image.alpha_composite(result, patch)
    return result


def _apply_soft_blinks(
    frame: Image.Image,
    points: dict[str, dict[str, float]],
    amount: float,
    emotion: str,
) -> Image.Image:
    if emotion in {"happy", "angry", "shy", "thanks"}:
        return _apply_upper_lid_curtain(frame, points, amount)
    """Lower a feathered upper eyelid for restrained non-happy blinks."""

    if amount < 0.035:
        return frame
    result = frame.copy()
    for name in ("left_eye", "right_eye"):
        eye = points.get(name)
        if eye is None:
            continue
        cx, cy, radius = eye["x"], eye["y"], max(3.0, eye["r"])
        rx, ry = radius * 0.72, radius * 0.43
        skin = _local_surface_color(frame, eye)
        mask = Image.new("L", frame.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
        cover_fraction = 0.14 + 0.78 * min(1.0, amount)
        lid_bottom = cy - ry + 2.0 * ry * cover_fraction
        mask_draw.rectangle((0, lid_bottom, frame.width, frame.height), fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(0.75))
        opacity = min(1.0, amount / 0.54)
        mask = mask.point(lambda value: round(value * opacity))
        patch = Image.new("RGBA", frame.size, skin)
        patch.putalpha(mask)
        result = Image.alpha_composite(result, patch)
    return result


def _draw_eyelid_lines(draw: ImageDraw.ImageDraw, factor: int,
                        points: dict[str, dict[str, float]], amount: float) -> None:
    if amount < 0.28:
        return
    strength = min(1.0, (amount - 0.28) / 0.35)
    for name in ("left_eye", "right_eye"):
        eye = points.get(name)
        if eye is None:
            continue
        cx, cy, radius = eye["x"], eye["y"], max(3.0, eye["r"])
        rx, ry = radius * 0.58, radius * 0.34
        cover_fraction = 0.14 + 0.78 * min(1.0, amount)
        y = cy - ry + 2.0 * ry * cover_fraction
        coords = [(cx - rx, y - 0.25), (cx, y + 0.42), (cx + rx, y - 0.25)]
        draw.line([(round(x * factor), round(py * factor)) for x, py in coords],
                  fill=(88, 54, 39, round(175 * strength)), width=max(1, round(0.9 * factor)), joint="curve")


def _draw_teardrop(draw: ImageDraw.ImageDraw, factor: int, x: float, y: float,
                   radius: float, alpha: int) -> None:
    points = [
        (round(x * factor), round((y - radius * 1.65) * factor)),
        (round((x - radius) * factor), round((y + radius * 0.18) * factor)),
        (round(x * factor), round((y + radius) * factor)),
        (round((x + radius) * factor), round((y + radius * 0.18) * factor)),
    ]
    draw.polygon(points, fill=(91, 169, 207, alpha))
    if alpha > 105:
        dot = max(1, round(0.30 * radius * factor))
        draw.ellipse((round((x - radius * 0.30) * factor) - dot, round((y - radius * 0.28) * factor) - dot,
                      round((x - radius * 0.30) * factor) + dot, round((y - radius * 0.28) * factor) + dot),
                     fill=(226, 247, 255, round(alpha * 0.62)))


def _draw_sparkle(draw: ImageDraw.ImageDraw, factor: int, x: float, y: float,
                  size: float, alpha: int) -> None:
    _line(draw, [(x - size, y), (x + size, y)], factor, (244, 173, 39, alpha), 1.4)
    _line(draw, [(x, y - size), (x, y + size)], factor, (244, 173, 39, alpha), 1.4)


def _draw_heart(draw: ImageDraw.ImageDraw, factor: int, x: float, y: float,
                size: float, alpha: int) -> None:
    points = []
    for step in range(25):
        theta = 2 * math.pi * step / 24
        hx = 16 * math.sin(theta) ** 3
        hy = 13 * math.cos(theta) - 5 * math.cos(2 * theta) - 2 * math.cos(3 * theta) - math.cos(4 * theta)
        points.append((x + hx * size / 32.0, y - hy * size / 32.0))
    _line(draw, points, factor, (224, 93, 105, alpha), 1.6)


def _add_emotion_details(frame: Image.Image, emotion: str,
                         points: dict[str, dict[str, float]], index: int) -> Image.Image:
    t, cycle, pulse, double_wave = _timing(index)
    blink_amount = _blink_amount(emotion, t)
    frame = _apply_soft_blinks(frame, points, blink_amount, emotion)
    factor = 3
    layer = Image.new("RGBA", (frame.width * factor, frame.height * factor), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    if emotion not in {"happy", "angry", "shy", "thanks"}:
        _draw_eyelid_lines(draw, factor, points, blink_amount)
    head = points.get("head", {"x": frame.width / 2, "y": frame.height / 3, "r": 35.0})

    if emotion == "happy":
        alpha = round(70 + 165 * pulse)
        for side, sign in (("left", -1), ("right", 1)):
            paw = points.get(f"{side}_paw")
            if paw:
                _draw_sparkle(draw, factor, paw["x"] + sign * 14, paw["y"] - 13, 3.2 + 1.4 * pulse, alpha)
    elif emotion == "angry":
        alpha = round(90 + 145 * abs(double_wave))
        x, y = head["x"] - head["r"] * 0.86, head["y"] - head["r"] * 0.52
        for offset in (0.0, 5.0, 10.0):
            _line(draw, [(x + offset, y + 5), (x + offset - 2, y)], factor, (190, 64, 48, alpha), 1.7)
    elif emotion == "sad":
        for name, start, end in (("left_tear", 0.12, 0.58), ("right_tear", 0.48, 0.94)):
            tear = points.get(name)
            if tear and start <= t <= end:
                progress = (t - start) / max(1e-6, end - start)
                eased = progress * progress * (3.0 - 2.0 * progress)
                fade_in = min(1.0, progress / 0.15)
                fade_out = min(1.0, (1.0 - progress) / 0.18)
                visibility = max(0.0, min(fade_in, fade_out))
                drift = 1.0 if name == "right_tear" else -1.0
                x = tear["x"] + drift * eased
                y = tear["y"] + 2.0 + 18.0 * eased
                radius = 1.55 + 0.75 * math.sin(math.pi * progress)
                _draw_teardrop(draw, factor, x, y, radius, round(225 * visibility))
    elif emotion == "laugh":
        alpha = round(80 + 150 * abs(cycle))
        for sign in (-1, 1):
            x, y = head["x"] + sign * head["r"] * 0.72, head["y"] + head["r"] * 0.12
            _line(draw, [(x, y - 4), (x + sign * 5, y - 7)], factor, (229, 132, 55, alpha), 1.6)
            _line(draw, [(x, y + 1), (x + sign * 6, y + 1)], factor, (229, 132, 55, alpha), 1.6)
        for name, sign in (("left_eye", -1), ("right_eye", 1)):
            eye = points.get(name)
            if eye:
                corner_x = eye["x"] + sign * eye["r"] * 0.78
                corner_y = eye["y"] + eye["r"] * 0.12
                _line(draw, [(corner_x, corner_y), (corner_x + sign * 3.2, corner_y - 1.2)],
                      factor, (238, 155, 83, round(55 + 135 * abs(cycle))), 1.25)
    elif emotion == "surprised":
        alpha = round(80 + 160 * pulse)
        for ray_angle in (-150, -115, -65, -30):
            radians = math.radians(ray_angle)
            inner, outer = head["r"] * 0.72, head["r"] * 0.72 + 5.0 + 2.0 * pulse
            start = (head["x"] + math.cos(radians) * inner, head["y"] + math.sin(radians) * inner)
            end = (head["x"] + math.cos(radians) * outer, head["y"] + math.sin(radians) * outer)
            _line(draw, [start, end], factor, (228, 133, 48, alpha), 1.7)
    elif emotion == "shy":
        alpha = round(24 + 54 * pulse)
        left_eye, right_eye, mouth = points.get("left_eye"), points.get("right_eye"), points.get("mouth")
        if left_eye and right_eye and mouth:
            eye_line = (left_eye["y"] + right_eye["y"]) / 2.0
            spacing = max(5.0, right_eye["x"] - left_eye["x"])
            cheek_y = eye_line + (mouth["y"] - eye_line) * 0.54
            cheek_centers = (left_eye["x"] - spacing * 0.32, right_eye["x"] + spacing * 0.32)
            for cheek_x in cheek_centers:
                for offset in (-2.1, 0.0, 2.1):
                    coords = [
                        (round((cheek_x + offset - 0.9) * factor), round((cheek_y + 0.8) * factor)),
                        (round((cheek_x + offset + 0.9) * factor), round((cheek_y - 0.8) * factor)),
                    ]
                    draw.line(coords, fill=(224, 118, 103, alpha), width=max(1, round(0.75 * factor)))
    elif emotion == "thanks":
        alpha = round(70 + 165 * pulse)
        paw = points.get("right_paw") or points.get("left_paw")
        if paw:
            _draw_heart(draw, factor, paw["x"] + 17, paw["y"] - 10 - 2 * pulse, 12 + 3 * pulse, alpha)
    elif emotion == "bye":
        alpha = round(80 + 160 * abs(double_wave))
        paw = points.get("left_paw")
        if paw:
            direction = -1 if paw["x"] < frame.width / 2 else 1
            for offset in (0.0, 5.0):
                x, y = paw["x"] + direction * (10 + offset), paw["y"] + offset * 0.7
                _line(draw, [(x, y - 4), (x + direction * 4, y + 1)], factor, (104, 123, 76, alpha), 1.5)

    detail = layer.resize(frame.size, Image.Resampling.LANCZOS)
    if emotion in {"happy", "bye"}:
        # Sparkles and motion trails belong behind/outside the silhouette.
        # Removing their overlap with the cat prevents bright strokes across a
        # dark paw from being perceived as cracks in the limb.
        subject_guard = frame.getchannel("A").filter(ImageFilter.MaxFilter(3))
        detail.putalpha(ImageChops.subtract(detail.getchannel("A"), subject_guard))
    return Image.alpha_composite(frame, detail)


def build_pose_preserving_frames(image: Image.Image, emotion: str,
                                 rig_entry: dict[str, Any] | None,
                                 style: str,
                                 outline_radius: int = 0) -> tuple[list[Image.Image], dict[str, Any]]:
    del style
    points = rig_to_pixels(image, rig_entry)
    pivot = _support_pivot(points)
    frames: list[Image.Image] = []
    used_chains: set[str] = set()
    limb_articulations: dict[str, str] = {}
    tail_chain_used = False
    motion_policy = (
        rig_entry.get("motion_policy", {})
        if isinstance(rig_entry, dict) and isinstance(rig_entry.get("motion_policy", {}), dict)
        else {}
    )
    grounded_forepaws = emotion == "happy" and motion_policy.get("forepaws") == "grounded-intact-silhouette"
    intact_bye_forelimb = (
        emotion == "bye"
        and motion_policy.get("raised_forelimb") == "whole-body-sway-intact-silhouette"
    )
    for index in range(FRAME_COUNT):
        dx, dy, angle, scale, requested_limb_angles = _motion(emotion, index, motion_policy)
        posed = image
        applied_angles: dict[str, float] = {}
        tail_angle = requested_limb_angles.get("tail", 0.0)
        if _has_explicit_tail_chain(rig_entry) and abs(tail_angle) >= 1e-4:
            posed, tail_used = _replace_rigid_tail(posed, points, tail_angle)
            if tail_used:
                tail_chain_used = True
                applied_angles["tail"] = tail_angle
        for side, limb_angle in requested_limb_angles.items():
            if side == "tail":
                continue
            if grounded_forepaws or intact_bye_forelimb:
                continue
            if not _has_explicit_chain(rig_entry, side):
                continue
            articulation = (
                "distal-wrist-overlap"
                if emotion == "happy"
                else "full-chain-shoulder-overlap"
                if emotion == "bye"
                else "full-chain"
            )
            posed, used = _replace_rigid_limb(posed, points, side, limb_angle, articulation)
            if used:
                used_chains.add(side)
                limb_articulations[side] = articulation
                applied_angles[side] = limb_angle
        frame = _similarity_transform(posed, pivot, angle=angle, scale=scale, dx=dx, dy=dy)
        frame_points = _posed_points(points, pivot, angle, scale, dx, dy, applied_angles, limb_articulations)
        frame = _white_outline(frame, outline_radius)
        frames.append(_add_emotion_details(frame, emotion, frame_points, index))

    active = set(ACTIVE_PARTS[emotion]) & set(points)
    detail_profile = dict(DETAIL_PROFILES[emotion])
    if grounded_forepaws:
        detail_profile.update({
            "limb_articulation": "none-intact-silhouette",
            "opening_bilateral_wrist_wave": False,
            "grounded_forepaws_no_separation": True,
            "joint_overlap": False,
            "limb_mask_max_width_px": 0,
        })
    if intact_bye_forelimb:
        detail_profile.update({
            "limb_articulation": "whole-body-sway-intact-silhouette",
            "erase_proximal_arm": False,
            "joint_overlap": False,
            "limb_mask_max_width_px": 0,
            "decoration_occluded_by_subject": True,
            "raised_forelimb_no_separation": True,
        })
    return frames, {
        "engine": ENGINE_NAME,
        "source_frames": FRAME_COUNT,
        "durations_ms": FRAME_DURATIONS[emotion],
        "active_parts": sorted(active),
        "face_parts": sorted(active & FACE_PARTS),
        "body_parts": sorted(active & BODY_PARTS),
        "geometry_preserving": True,
        "nonuniform_face_or_body_scale": False,
        "support_pivot": [round(pivot[0], 2), round(pivot[1], 2)],
        "rigid_limb_chains": sorted(used_chains),
        "limb_articulations": limb_articulations,
        "rigid_arm_chain": "left" in used_chains,
        "rigid_tail_chain": tail_chain_used,
        "tail_tremor_applied": emotion == "surprised" and tail_chain_used,
        "facial_details": FACIAL_DETAILS[emotion],
        "detail_profile": detail_profile,
        "decorative_accents": DECORATIVE_ACCENTS[emotion],
        "face_guard_applied": bool(used_chains and "head" in points),
        "joint_overlap_applied": bool(used_chains) and all(
            limb_articulations.get(side) in {"distal-wrist-overlap", "full-chain-shoulder-overlap"}
            for side in used_chains
        ),
        "proximal_arm_erased": any(
            limb_articulations.get(side) == "full-chain" for side in used_chains
        ),
        "opening_bilateral_wrist_wave": emotion == "happy" and used_chains == {"left", "right"},
        "intact_subject_silhouette": grounded_forepaws or intact_bye_forelimb,
        "grounded_forepaws_no_separation": grounded_forepaws,
        "raised_forelimb_no_separation": intact_bye_forelimb,
        "motion_policy": motion_policy,
        "detail_level": "fine",
    }


__all__ = ["ENGINE_NAME", "build_pose_preserving_frames", "load_animation_rig", "merged_rig"]
