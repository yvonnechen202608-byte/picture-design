#!/usr/bin/env python3
"""Create small, anatomy-aware sticker animations with smooth local warps.

The rig uses normalized coordinates inside the visible subject bounding box.  Each
frame starts from the same source image; local Gaussian warps move facial and body
landmarks without cutting the illustration into visibly separate cardboard parts.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


FRAME_COUNT = 10

DEFAULT_POINTS: dict[str, dict[str, float]] = {
    "head": {"x": 0.50, "y": 0.30, "r": 0.30},
    "left_eye": {"x": 0.41, "y": 0.32, "r": 0.065},
    "right_eye": {"x": 0.59, "y": 0.32, "r": 0.065},
    "mouth": {"x": 0.50, "y": 0.45, "r": 0.085},
    "left_ear": {"x": 0.28, "y": 0.10, "r": 0.14},
    "right_ear": {"x": 0.72, "y": 0.10, "r": 0.14},
    "left_paw": {"x": 0.34, "y": 0.62, "r": 0.14},
    "right_paw": {"x": 0.66, "y": 0.62, "r": 0.14},
    "left_wrist": {"x": 0.36, "y": 0.56, "r": 0.12},
    "right_wrist": {"x": 0.64, "y": 0.56, "r": 0.12},
    "left_shoulder": {"x": 0.39, "y": 0.52, "r": 0.14},
    "right_shoulder": {"x": 0.61, "y": 0.52, "r": 0.14},
    "body": {"x": 0.50, "y": 0.70, "r": 0.30},
    "left_foot": {"x": 0.38, "y": 0.90, "r": 0.13},
    "right_foot": {"x": 0.62, "y": 0.90, "r": 0.13},
    "tail": {"x": 0.87, "y": 0.72, "r": 0.15},
    "left_tear": {"x": 0.39, "y": 0.41, "r": 0.045},
    "right_tear": {"x": 0.61, "y": 0.41, "r": 0.045},
}

FACE_PARTS = {"head", "left_eye", "right_eye", "mouth", "left_ear", "right_ear", "left_tear", "right_tear"}
BODY_PARTS = {
    "left_paw", "right_paw", "left_wrist", "right_wrist", "left_shoulder", "right_shoulder",
    "body", "left_foot", "right_foot", "tail_base", "tail_mid", "tail",
}

CYCLE = (0.0, 0.48, 0.86, 1.0, 0.58, 0.0, -0.58, -1.0, -0.48, 0.0)
PULSE = (0.0, 0.25, 0.65, 1.0, 0.72, 0.30, 0.05, 0.18, 0.08, 0.0)
BOW = (0.0, 0.12, 0.42, 0.82, 1.0, 0.82, 0.48, 0.18, 0.05, 0.0)
# A single still illustration cannot synthesize a fully closed eyelid reliably.
# Keep the blink as a readable squint; stronger inverse scaling creates folds in
# fur or hair around large cartoon eyes.
BLINK = (1.0, 1.0, 1.0, 1.0, 1.0, 0.88, 0.72, 0.90, 1.0, 1.0)

FRAME_DURATIONS = {
    "happy": [130, 80, 80, 80, 90, 80, 70, 80, 100, 130],
    "angry": [100, 70, 70, 80, 70, 90, 70, 80, 100, 120],
    "sad": [150, 120, 110, 110, 120, 120, 110, 110, 130, 160],
    "laugh": [100, 70, 70, 70, 80, 70, 70, 80, 100, 120],
    "surprised": [150, 60, 70, 90, 90, 90, 90, 90, 110, 150],
    "shy": [140, 100, 90, 90, 100, 90, 90, 100, 120, 150],
    "thanks": [150, 100, 90, 100, 120, 110, 100, 100, 130, 160],
    "bye": [130, 80, 70, 80, 80, 80, 70, 80, 110, 140],
}


def load_animation_rig(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("coordinate_space") not in {None, "subject-bbox-normalized"}:
        raise ValueError("animation rig 的 coordinate_space 必须为 subject-bbox-normalized")
    expressions = data.get("expressions")
    if not isinstance(expressions, dict):
        raise ValueError("animation rig 缺少 expressions 对象")
    return expressions


def merged_rig(entry: dict[str, Any] | None) -> dict[str, dict[str, float]]:
    points = {name: dict(value) for name, value in DEFAULT_POINTS.items()}
    if entry:
        disabled = set(entry.get("disabled", []))
        for name in disabled:
            points.pop(name, None)
        supplied = entry.get("points", entry)
        for name, value in supplied.items():
            if name in {"disabled", "notes"}:
                continue
            if not isinstance(value, dict):
                continue
            required = {"x", "y"}
            if not required.issubset(value):
                raise ValueError(f"animation rig 点 {name} 缺少 x/y")
            point = dict(points.get(name, {"r": 0.10}))
            point.update({key: float(value[key]) for key in value if key in {"x", "y", "r"}})
            if not (0 <= point["x"] <= 1 and 0 <= point["y"] <= 1 and 0.01 <= point.get("r", 0.1) <= 0.5):
                raise ValueError(f"animation rig 点 {name} 超出允许范围")
            points[name] = point
    return points


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    box = image.getchannel("A").point(lambda value: 255 if value >= 8 else 0).getbbox()
    if box is None:
        raise ValueError("图片没有可见主体")
    return box


def rig_to_pixels(image: Image.Image, entry: dict[str, Any] | None) -> dict[str, dict[str, float]]:
    left, top, right, bottom = alpha_bbox(image)
    width, height = right - left, bottom - top
    extent = max(width, height)
    result: dict[str, dict[str, float]] = {}
    for name, point in merged_rig(entry).items():
        result[name] = {
            "x": left + point["x"] * width,
            "y": top + point["y"] * height,
            "r": max(2.0, point.get("r", 0.10) * extent),
        }
    return result


def _op(points: dict[str, dict[str, float]], part: str, kind: str, **values: float) -> dict[str, float] | None:
    point = points.get(part)
    if point is None:
        return None
    return {"part": part, "kind": kind, "cx": point["x"], "cy": point["y"], "radius": point["r"], **values}


def _choreography(emotion: str, points: dict[str, dict[str, float]], index: int) -> tuple[list[dict[str, float]], set[str]]:
    wave = CYCLE[index]
    pulse = PULSE[index]
    blink = BLINK[index]
    bow = BOW[index]
    ops: list[dict[str, float]] = []
    active: set[str] = set()

    def add(part: str, kind: str, **values: float) -> None:
        operation = _op(points, part, kind, **values)
        if operation is not None:
            ops.append(operation)
            active.add(part)

    def blink_eyes(amount: float = 1.0) -> None:
        scale = 1.0 - (1.0 - blink) * amount
        add("left_eye", "scale", sx=1.0, sy=scale)
        add("right_eye", "scale", sx=1.0, sy=scale)

    if emotion == "happy":
        lift = -2.2 * pulse
        add("head", "translate", dx=0.0, dy=lift)
        add("left_ear", "translate", dx=-1.2 * pulse, dy=-1.5 * pulse)
        add("right_ear", "translate", dx=1.2 * pulse, dy=-1.5 * pulse)
        add("left_paw", "translate", dx=-1.7 * pulse, dy=-3.8 * pulse)
        add("right_paw", "translate", dx=1.7 * pulse, dy=-3.8 * pulse)
        add("mouth", "scale", sx=1.0 + 0.03 * pulse, sy=1.0 + 0.12 * pulse)
        add("body", "scale", sx=1.0 + 0.018 * pulse, sy=1.0 - 0.025 * pulse)
        blink_eyes()
    elif emotion == "angry":
        stomp = (0.0, -1.0, 3.8, -1.5, 4.5, -0.8, 2.5, -1.0, 1.0, 0.0)[index]
        jitter = (0.0, -1.5, 1.5, -1.2, 1.4, -1.0, 1.0, -0.6, 0.4, 0.0)[index]
        add("head", "translate", dx=jitter, dy=1.1 * pulse)
        add("left_eye", "scale", sx=1.0, sy=0.92 - 0.08 * pulse)
        add("right_eye", "scale", sx=1.0, sy=0.92 - 0.08 * pulse)
        add("mouth", "translate", dx=0.5 * jitter, dy=0.4 * pulse)
        add("left_ear", "rotate", angle=-2.3 * pulse)
        add("right_ear", "rotate", angle=2.3 * pulse)
        add("left_paw", "translate", dx=-0.5 * pulse, dy=stomp)
        add("right_paw", "translate", dx=0.35 * jitter, dy=-0.4 * pulse)
        add("body", "translate", dx=0.35 * jitter, dy=0.5 * pulse)
    elif emotion == "sad":
        droop = bow
        add("head", "translate", dx=-0.7 * droop, dy=3.2 * droop)
        add("head", "rotate", angle=-1.3 * droop)
        add("left_ear", "translate", dx=1.0 * droop, dy=2.7 * droop)
        add("right_ear", "translate", dx=-1.0 * droop, dy=2.7 * droop)
        add("mouth", "scale", sx=0.96, sy=1.0 - 0.10 * droop)
        add("left_tear", "translate", dx=-0.25 * droop, dy=2.8 * droop)
        add("right_tear", "translate", dx=0.25 * droop, dy=3.2 * droop)
        add("left_paw", "translate", dx=0.45 * droop, dy=1.3 * droop)
        add("right_paw", "translate", dx=-0.45 * droop, dy=1.3 * droop)
        add("body", "scale", sx=1.0 - 0.015 * droop, sy=1.0 - 0.025 * droop)
        blink_eyes(0.55)
    elif emotion == "laugh":
        laugh = abs(wave)
        add("head", "rotate", angle=1.6 * wave)
        add("head", "translate", dx=0.8 * wave, dy=-1.6 * laugh)
        add("mouth", "scale", sx=1.0 + 0.045 * laugh, sy=1.0 + 0.16 * laugh)
        add("left_paw", "translate", dx=-1.3 * laugh, dy=-1.4 * laugh)
        add("right_paw", "translate", dx=1.3 * laugh, dy=-1.4 * laugh)
        add("body", "scale", sx=1.0 + 0.022 * laugh, sy=1.0 - 0.032 * laugh)
        add("left_foot", "rotate", angle=-1.7 * wave)
        add("right_foot", "rotate", angle=1.7 * wave)
        add("tail", "translate", dx=4.3 * wave, dy=-1.0 * abs(wave))
    elif emotion == "surprised":
        pop = pulse
        add("head", "translate", dx=0.0, dy=-2.8 * pop)
        add("left_eye", "scale", sx=1.0 + 0.07 * pop, sy=1.0 + 0.10 * pop)
        add("right_eye", "scale", sx=1.0 + 0.07 * pop, sy=1.0 + 0.10 * pop)
        add("mouth", "scale", sx=1.0 + 0.07 * pop, sy=1.0 + 0.18 * pop)
        add("left_ear", "translate", dx=-1.8 * pop, dy=-2.5 * pop)
        add("right_ear", "translate", dx=1.8 * pop, dy=-2.5 * pop)
        add("left_paw", "translate", dx=-3.2 * pop, dy=-2.0 * pop)
        add("right_paw", "translate", dx=3.2 * pop, dy=-2.0 * pop)
        add("left_foot", "translate", dx=-0.8 * pop, dy=1.4 * pop)
        add("right_foot", "translate", dx=0.8 * pop, dy=1.4 * pop)
        add("body", "scale", sx=1.0 - 0.018 * pop, sy=1.0 + 0.028 * pop)
    elif emotion == "shy":
        sway = 0.75 * wave
        add("head", "rotate", angle=1.3 * sway)
        add("head", "translate", dx=1.0 * sway, dy=0.5 * abs(sway))
        add("left_eye", "translate", dx=1.1 * sway, dy=0.0)
        add("right_eye", "translate", dx=1.1 * sway, dy=0.0)
        blink_eyes()
        add("mouth", "scale", sx=1.0 - 0.04 * abs(sway), sy=1.0)
        add("left_ear", "translate", dx=0.7 * abs(sway), dy=1.3 * abs(sway))
        add("right_ear", "translate", dx=-0.7 * abs(sway), dy=1.3 * abs(sway))
        add("left_paw", "translate", dx=1.6 * abs(sway), dy=0.6 * abs(sway))
        add("right_paw", "translate", dx=-1.6 * abs(sway), dy=0.6 * abs(sway))
        add("body", "translate", dx=0.55 * sway, dy=0.0)
    elif emotion == "thanks":
        add("head", "translate", dx=0.2 * bow, dy=4.8 * bow)
        add("head", "rotate", angle=-1.8 * bow)
        add("left_ear", "translate", dx=0.5 * bow, dy=2.2 * bow)
        add("right_ear", "translate", dx=-0.5 * bow, dy=2.2 * bow)
        add("mouth", "scale", sx=1.0 + 0.025 * bow, sy=1.0 - 0.05 * bow)
        add("left_paw", "translate", dx=1.2 * bow, dy=1.3 * bow)
        add("right_paw", "translate", dx=-1.2 * bow, dy=1.3 * bow)
        add("body", "scale", sx=1.0 - 0.018 * bow, sy=1.0 - 0.025 * bow)
        add("tail", "translate", dx=3.3 * wave, dy=-0.7 * abs(wave))
    elif emotion == "bye":
        # Propagate the wave from a stable shoulder through wrist to paw tip.
        # This avoids the rubber-hose look caused by moving only the paw region.
        add("left_shoulder", "translate", dx=0.7 * wave, dy=0.0)
        add("left_wrist", "translate", dx=3.0 * wave, dy=-0.8 * abs(wave))
        add("left_paw", "translate", dx=5.8 * wave, dy=-1.8 * abs(wave))
        add("head", "rotate", angle=0.45 * wave)
        add("head", "translate", dx=0.3 * wave, dy=-0.2 * abs(wave))
        add("tail", "translate", dx=-3.4 * wave, dy=-0.7 * abs(wave))
        add("body", "translate", dx=0.2 * wave, dy=0.0)
        add("left_ear", "rotate", angle=-0.55 * wave)
        add("right_ear", "rotate", angle=0.55 * wave)
        add("mouth", "scale", sx=1.0, sy=1.0 + 0.07 * abs(wave))
        blink_eyes()
    else:
        raise ValueError(f"未知动画语义：{emotion}")
    return ops, active


def _sample_bilinear(array: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    height, width, _ = array.shape
    x0 = np.floor(map_x).astype(np.int32)
    y0 = np.floor(map_y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)
    x0 = np.clip(x0, 0, width - 1)
    y0 = np.clip(y0, 0, height - 1)
    wx = (map_x - x0)[..., None]
    wy = (map_y - y0)[..., None]
    top = array[y0, x0] * (1.0 - wx) + array[y0, x1] * wx
    bottom = array[y1, x0] * (1.0 - wx) + array[y1, x1] * wx
    return top * (1.0 - wy) + bottom * wy


def warp_frame(image: Image.Image, operations: list[dict[str, float]], pixel_style: bool = False) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
    alpha = rgba[..., 3:4]
    premultiplied = np.concatenate((rgba[..., :3] * alpha, alpha), axis=2)
    height, width = rgba.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    map_x, map_y = xx.copy(), yy.copy()

    for operation in operations:
        cx, cy, radius = operation["cx"], operation["cy"], max(1.0, operation["radius"])
        dx0, dy0 = xx - cx, yy - cy
        weight = np.exp(-(dx0 * dx0 + dy0 * dy0) / (2.0 * radius * radius))
        kind = operation["kind"]
        if kind == "translate":
            map_x -= operation.get("dx", 0.0) * weight
            map_y -= operation.get("dy", 0.0) * weight
        elif kind == "scale":
            sx = max(0.12, operation.get("sx", 1.0))
            sy = max(0.12, operation.get("sy", 1.0))
            map_x += ((cx + dx0 / sx) - xx) * weight
            map_y += ((cy + dy0 / sy) - yy) * weight
        elif kind == "rotate":
            angle = math.radians(-operation.get("angle", 0.0))
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            rotated_x = cx + cos_a * dx0 - sin_a * dy0
            rotated_y = cy + sin_a * dx0 + cos_a * dy0
            map_x += (rotated_x - xx) * weight
            map_y += (rotated_y - yy) * weight
        else:
            raise ValueError(f"未知局部变形类型：{kind}")

    map_x = np.clip(map_x, 0, width - 1)
    map_y = np.clip(map_y, 0, height - 1)
    if pixel_style:
        sampled = premultiplied[np.rint(map_y).astype(np.int32), np.rint(map_x).astype(np.int32)]
    else:
        sampled = _sample_bilinear(premultiplied, map_x, map_y)

    out_alpha = sampled[..., 3:4]
    out_rgb = np.divide(sampled[..., :3], out_alpha, out=np.zeros_like(sampled[..., :3]), where=out_alpha > 1e-5)
    output = np.concatenate((out_rgb, out_alpha), axis=2)
    output = np.clip(np.rint(output * 255.0), 0, 255).astype(np.uint8)
    return Image.fromarray(output, "RGBA")


def build_part_aware_frames(
    image: Image.Image,
    emotion: str,
    rig_entry: dict[str, Any] | None,
    style: str,
) -> tuple[list[Image.Image], dict[str, Any]]:
    points = rig_to_pixels(image, rig_entry)
    frames: list[Image.Image] = []
    active: set[str] = set()
    for index in range(FRAME_COUNT):
        operations, frame_active = _choreography(emotion, points, index)
        frames.append(warp_frame(image, operations, pixel_style=style == "pixel"))
        active.update(frame_active)
    return frames, {
        "engine": "part-aware-rbf-v2",
        "source_frames": FRAME_COUNT,
        "durations_ms": FRAME_DURATIONS[emotion],
        "active_parts": sorted(active),
        "face_parts": sorted(active & FACE_PARTS),
        "body_parts": sorted(active & BODY_PARTS),
    }
