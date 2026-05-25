#!/usr/bin/env python3
"""Rectify a photographed wood board/veneer into a calibrated texture image.

Given four source corner points and the real physical size, this tool removes
perspective distortion, optionally crops bad edges/labels, optionally adds
reflected clamp padding, and writes a JSON sidecar with Fusion-friendly scale
metadata.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


MM_PER_UNIT = {
    "mm": 1.0,
    "cm": 10.0,
    "in": 25.4,
}


@dataclass(frozen=True)
class Crop:
    left: int
    top: int
    right: int
    bottom: int


def parse_corners(value: str) -> np.ndarray:
    """Parse `x,y x,y x,y x,y` in TL, TR, BR, BL order."""
    pairs = value.replace(";", " ").split()
    if len(pairs) != 4:
        raise argparse.ArgumentTypeError("corners must be four x,y pairs: TL TR BR BL")
    pts = []
    for pair in pairs:
        xy = [float(p.strip()) for p in pair.split(",")]
        if len(xy) != 2:
            raise argparse.ArgumentTypeError("corner points must be x,y")
        pts.append(xy)
    return np.array(pts, dtype=np.float64)


def parse_pair(value: str) -> tuple[float, float]:
    parts = [float(p.strip()) for p in value.split(",")]
    if len(parts) != 2 or parts[0] <= 0 or parts[1] <= 0:
        raise argparse.ArgumentTypeError("expected positive width,height")
    return parts[0], parts[1]


def parse_crop(value: str) -> Crop:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) != 4 or any(p < 0 for p in parts):
        raise argparse.ArgumentTypeError("expected non-negative left,top,right,bottom")
    return Crop(*parts)


def solve_homography(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Return H mapping src points to dst points."""
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        a.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, _, vh = np.linalg.svd(np.array(a, dtype=np.float64))
    h = vh[-1].reshape(3, 3)
    return h / h[2, 2]


def bilinear_sample(img: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    x = np.clip(x, 0, w - 1)
    y = np.clip(y, 0, h - 1)

    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)

    wx = (x - x0)[..., None]
    wy = (y - y0)[..., None]

    top = img[y0, x0] * (1 - wx) + img[y0, x1] * wx
    bot = img[y1, x0] * (1 - wx) + img[y1, x1] * wx
    return top * (1 - wy) + bot * wy


def warp_perspective(src_img: Image.Image, corners: np.ndarray, width_px: int, height_px: int) -> Image.Image:
    src = np.asarray(src_img.convert("RGB")).astype(np.float32)
    dst = np.array(
        [
            [0, 0],
            [width_px - 1, 0],
            [width_px - 1, height_px - 1],
            [0, height_px - 1],
        ],
        dtype=np.float64,
    )
    h_src_to_dst = solve_homography(corners, dst)
    h_dst_to_src = np.linalg.inv(h_src_to_dst)

    yy, xx = np.indices((height_px, width_px), dtype=np.float64)
    ones = np.ones_like(xx)
    coords = np.stack([xx, yy, ones], axis=0).reshape(3, -1)
    mapped = h_dst_to_src @ coords
    mapped /= mapped[2:3, :]
    sx = mapped[0].reshape(height_px, width_px)
    sy = mapped[1].reshape(height_px, width_px)

    warped = bilinear_sample(src, sx, sy)
    return Image.fromarray(np.clip(warped + 0.5, 0, 255).astype(np.uint8), "RGB")


def apply_crop(img: Image.Image, crop: Crop) -> Image.Image:
    w, h = img.size
    if crop.left + crop.right >= w or crop.top + crop.bottom >= h:
        raise ValueError("crop removes the entire image")
    return img.crop((crop.left, crop.top, w - crop.right, h - crop.bottom))


def reflect_pad(img: Image.Image, pad: int) -> Image.Image:
    if pad <= 0:
        return img
    arr = np.asarray(img.convert("RGB"))
    h, w = arr.shape[:2]
    out = np.zeros((h + 2 * pad, w + 2 * pad, 3), dtype=arr.dtype)
    out[pad:-pad, pad:-pad] = arr
    out[:pad, pad:-pad] = arr[pad - 1::-1, :]
    out[-pad:, pad:-pad] = arr[:-pad - 1:-1, :]
    out[:, :pad] = out[:, 2 * pad - 1:pad - 1:-1]
    out[:, -pad:] = out[:, -pad - 1:-2 * pad - 1:-1]
    return Image.fromarray(out, "RGB")


def write_metadata(
    output: Path,
    source: Path,
    corners: np.ndarray,
    unit: str,
    physical_size: tuple[float, float],
    px_per_mm: float,
    rectified_size_px: tuple[int, int],
    crop_px: Crop,
    pad_px: int,
    final_img: Image.Image,
) -> None:
    width_mm = physical_size[0] * MM_PER_UNIT[unit]
    height_mm = physical_size[1] * MM_PER_UNIT[unit]
    cropped_width_mm = width_mm - (crop_px.left + crop_px.right) / px_per_mm
    cropped_height_mm = height_mm - (crop_px.top + crop_px.bottom) / px_per_mm
    if cropped_width_mm <= 0 or cropped_height_mm <= 0:
        raise ValueError("crop produces non-positive physical size")

    data = {
        "description": "Rectified wood veneer texture",
        "source_image": str(source),
        "output_image": str(output),
        "source_corners_px_tl_tr_br_bl": corners.round(3).tolist(),
        "input_physical_size": {
            "width": physical_size[0],
            "height": physical_size[1],
            "unit": unit,
        },
        "rectified_size_px": {
            "width": rectified_size_px[0],
            "height": rectified_size_px[1],
        },
        "crop_px": {
            "left": crop_px.left,
            "top": crop_px.top,
            "right": crop_px.right,
            "bottom": crop_px.bottom,
        },
        "edge_padding_px": pad_px,
        "core_image_px": {
            "width": final_img.size[0] - 2 * pad_px,
            "height": final_img.size[1] - 2 * pad_px,
        },
        "image_size_px": {
            "width": final_img.size[0],
            "height": final_img.size[1],
        },
        "physical_size_mm_after_crop": {
            "width": round(cropped_width_mm, 4),
            "height": round(cropped_height_mm, 4),
        },
        "px_per_mm": px_per_mm,
        "dpi": round(px_per_mm * 25.4, 4),
        "fusion_scale_in": {
            "x": round(cropped_width_mm / 25.4, 4),
            "y": round(cropped_height_mm / 25.4, 4),
        },
        "fusion_offset_in_centered": {
            "x": round(-(cropped_width_mm / 25.4) / 2.0, 4),
            "y": round(-(cropped_height_mm / 25.4) / 2.0, 4),
        },
    }
    if pad_px:
        data["note"] = (
            "Fusion scale values describe the cropped wood core. Edge padding is "
            "reflected clamp padding and should not be counted as real board size."
        )

    metadata_path = output.with_suffix(".json")
    metadata_path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Perspective-rectify and crop a photographed wood veneer texture."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--corners",
        required=True,
        type=parse_corners,
        help="Four source corners in TL,TR,BR,BL order: 'x,y x,y x,y x,y'.",
    )
    parser.add_argument(
        "--physical-size",
        required=True,
        type=parse_pair,
        help="Real source rectangle width,height in --unit.",
    )
    parser.add_argument("--unit", choices=sorted(MM_PER_UNIT), default="mm")
    parser.add_argument(
        "--px-per-mm",
        type=float,
        default=3.0,
        help="Output resolution before padding. Default: 3.",
    )
    parser.add_argument(
        "--crop-px",
        type=parse_crop,
        default=Crop(0, 0, 0, 0),
        help="Crop after rectification: left,top,right,bottom pixels.",
    )
    parser.add_argument(
        "--reflect-pad-px",
        type=int,
        default=0,
        help="Add reflected edge padding after crop for clamp safety.",
    )
    parser.add_argument("--quality", type=int, default=95)
    args = parser.parse_args()

    width_mm = args.physical_size[0] * MM_PER_UNIT[args.unit]
    height_mm = args.physical_size[1] * MM_PER_UNIT[args.unit]
    width_px = int(round(width_mm * args.px_per_mm))
    height_px = int(round(height_mm * args.px_per_mm))
    if width_px <= 1 or height_px <= 1:
        raise ValueError("rectified output size is too small")

    src_img = Image.open(args.source).convert("RGB")
    rectified = warp_perspective(src_img, args.corners, width_px, height_px)
    cropped = apply_crop(rectified, args.crop_px)
    final = reflect_pad(cropped, args.reflect_pad_px)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    final.save(args.output, quality=args.quality, subsampling=0)
    write_metadata(
        output=args.output,
        source=args.source,
        corners=args.corners,
        unit=args.unit,
        physical_size=args.physical_size,
        px_per_mm=args.px_per_mm,
        rectified_size_px=(width_px, height_px),
        crop_px=args.crop_px,
        pad_px=args.reflect_pad_px,
        final_img=final,
    )
    print(f"wrote {args.output}")
    print(f"wrote {args.output.with_suffix('.json')}")


if __name__ == "__main__":
    main()
