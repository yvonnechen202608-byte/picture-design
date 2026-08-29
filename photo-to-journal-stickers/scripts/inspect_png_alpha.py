#!/usr/bin/env python3
"""Validate that PNG files contain real transparent pixels.

Uses only the Python standard library. For 8-bit, non-interlaced grayscale+alpha
or RGBA PNGs it also reports transparent area, partial-alpha area, and whether
visible pixels touch a canvas edge.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def unfilter(raw: bytes, width: int, height: int, bytes_per_pixel: int) -> list[bytes]:
    stride = width * bytes_per_pixel
    rows: list[bytes] = []
    offset = 0
    previous = bytearray(stride)

    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        scanline = bytearray(raw[offset : offset + stride])
        offset += stride

        for i in range(stride):
            left = scanline[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
            up = previous[i]
            upper_left = previous[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
            if filter_type == 1:
                scanline[i] = (scanline[i] + left) & 0xFF
            elif filter_type == 2:
                scanline[i] = (scanline[i] + up) & 0xFF
            elif filter_type == 3:
                scanline[i] = (scanline[i] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                scanline[i] = (scanline[i] + paeth(left, up, upper_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter type: {filter_type}")

        rows.append(bytes(scanline))
        previous = scanline

    return rows


def inspect_png(path: Path) -> dict[str, object]:
    result: dict[str, object] = {"path": str(path), "valid": False}
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        result["error"] = "not a PNG file"
        return result

    offset = len(PNG_SIGNATURE)
    ihdr = None
    idat_parts: list[bytes] = []
    has_trns = False

    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload_start = offset + 8
        payload_end = payload_start + length
        payload = data[payload_start:payload_end]
        offset = payload_end + 4
        if chunk_type == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", payload)
        elif chunk_type == b"IDAT":
            idat_parts.append(payload)
        elif chunk_type == b"tRNS":
            has_trns = True
        elif chunk_type == b"IEND":
            break

    if ihdr is None:
        result["error"] = "missing IHDR chunk"
        return result

    width, height, bit_depth, color_type, compression, filtering, interlace = ihdr
    alpha_channel = color_type in (4, 6)
    result.update(
        {
            "width": width,
            "height": height,
            "bit_depth": bit_depth,
            "color_type": color_type,
            "alpha_channel": alpha_channel,
            "transparency_chunk": has_trns,
        }
    )

    if not alpha_channel and not has_trns:
        result["error"] = "PNG has no alpha channel or tRNS transparency"
        return result

    if has_trns and not alpha_channel:
        result.update(
            {
                "valid": True,
                "analysis": "tRNS transparency present; pixel coverage not decoded",
            }
        )
        return result

    if bit_depth != 8 or interlace != 0 or compression != 0 or filtering != 0:
        result["error"] = "alpha exists, but this checker only decodes 8-bit non-interlaced PNG pixels"
        return result

    bytes_per_pixel = 4 if color_type == 6 else 2
    alpha_offset = 3 if color_type == 6 else 1
    try:
        rows = unfilter(zlib.decompress(b"".join(idat_parts)), width, height, bytes_per_pixel)
    except (ValueError, zlib.error, IndexError) as exc:
        result["error"] = f"could not decode alpha pixels: {exc}"
        return result

    total = width * height
    clear = 0
    partial = 0
    visible = 0
    min_x, min_y = width, height
    max_x = max_y = -1

    for y, row in enumerate(rows):
        for x in range(width):
            alpha = row[x * bytes_per_pixel + alpha_offset]
            if alpha == 0:
                clear += 1
            elif alpha < 255:
                partial += 1
                visible += 1
            else:
                visible += 1
            if alpha > 0:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    transparent = clear + partial
    if transparent == 0:
        result["error"] = "alpha channel is fully opaque; no transparent pixels found"
        return result
    if visible == 0:
        result["error"] = "image is fully transparent; no visible subject found"
        return result

    touches_edge = min_x == 0 or min_y == 0 or max_x == width - 1 or max_y == height - 1
    result.update(
        {
            "valid": True,
            "transparent_fraction": round(transparent / total, 6),
            "clear_fraction": round(clear / total, 6),
            "partial_alpha_fraction": round(partial / total, 6),
            "visible_bbox": [min_x, min_y, max_x, max_y],
            "touches_edge": touches_edge,
        }
    )
    if touches_edge:
        result["warning"] = "visible pixels touch a canvas edge; inspect for cropping"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png", nargs="+", type=Path, help="PNG file(s) to inspect")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of readable lines")
    args = parser.parse_args()

    results = []
    for path in args.png:
        try:
            results.append(inspect_png(path))
        except (OSError, struct.error) as exc:
            results.append({"path": str(path), "valid": False, "error": str(exc)})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for item in results:
            status = "PASS" if item["valid"] else "FAIL"
            details = []
            if "transparent_fraction" in item:
                details.append(f"transparent={item['transparent_fraction']:.1%}")
            if "visible_bbox" in item:
                details.append(f"bbox={item['visible_bbox']}")
            if "warning" in item:
                details.append(f"warning={item['warning']}")
            if "error" in item:
                details.append(f"error={item['error']}")
            suffix = " | " + "; ".join(details) if details else ""
            print(f"{status} {item['path']}{suffix}")

    return 0 if all(item["valid"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
