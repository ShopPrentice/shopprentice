#!/usr/bin/env python3
"""Color-grade wood texture photos using a known-good reference color region.

The tool estimates a smooth low-frequency color/reflection field in the target
image, then shifts that field toward a reference image or reference rectangle.
High-frequency grain detail is preserved because correction is applied through
a blurred per-channel ratio map.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


def parse_rect(value: str) -> Rect:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("rectangle must be x,y,w,h")
    x, y, w, h = parts
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError("rectangle width/height must be positive")
    return Rect(x, y, w, h)


def parse_pair(value: str) -> tuple[int, int]:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) != 2 or parts[0] <= 0 or parts[1] <= 0:
        raise argparse.ArgumentTypeError("expected positive pair, e.g. 28,64")
    return parts[0], parts[1]


def parse_triplet(value: str) -> np.ndarray:
    parts = [float(p.strip()) for p in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected r,g,b")
    return np.array(parts, dtype=np.float32)[None, None, :]


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * (x ** (1.0 / 2.4)) - 0.055)


def load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float32) / 255.0


def crop_rect(img: np.ndarray, rect: Rect) -> np.ndarray:
    h, w = img.shape[:2]
    x0 = max(0, min(w, rect.x))
    y0 = max(0, min(h, rect.y))
    x1 = max(x0, min(w, rect.x + rect.w))
    y1 = max(y0, min(h, rect.y + rect.h))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("reference rectangle does not overlap the image")
    return img[y0:y1, x0:x1]


def robust_tile_median(tile: np.ndarray) -> np.ndarray:
    luma = 0.2126 * tile[:, :, 0] + 0.7152 * tile[:, :, 1] + 0.0722 * tile[:, :, 2]
    lo, hi = np.percentile(luma, [12, 88])
    mask = (luma >= lo) & (luma <= hi)
    samples = tile[mask]
    if samples.shape[0] < 16:
        samples = tile.reshape(-1, 3)
    return np.median(samples, axis=0)


def median_grid(img: np.ndarray, grid_w: int, grid_h: int) -> np.ndarray:
    h, w = img.shape[:2]
    grid = np.zeros((grid_h, grid_w, 3), dtype=np.float32)
    for gy in range(grid_h):
        y0 = int(gy * h / grid_h)
        y1 = int((gy + 1) * h / grid_h)
        for gx in range(grid_w):
            x0 = int(gx * w / grid_w)
            x1 = int((gx + 1) * w / grid_w)
            grid[gy, gx] = robust_tile_median(img[y0:y1, x0:x1])
    return grid


def smooth_grid(grid: np.ndarray, rounds: int) -> np.ndarray:
    g = grid.copy()
    for _ in range(rounds):
        p = np.pad(g, ((1, 1), (1, 1), (0, 0)), mode="edge")
        g = (
            p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:]
            + 2 * p[1:-1, :-2] + 4 * p[1:-1, 1:-1] + 2 * p[1:-1, 2:]
            + p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]
        ) / 16.0
    return g


def resize_field(field: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    channels = []
    for channel in range(3):
        img = Image.fromarray(field[:, :, channel].astype(np.float32), mode="F")
        img = img.resize(size, Image.Resampling.BICUBIC)
        channels.append(np.asarray(img).astype(np.float32))
    return np.stack(channels, axis=2)


def reflect_pad_core(core: np.ndarray, pad: int) -> np.ndarray:
    if pad <= 0:
        return core
    h, w = core.shape[:2]
    out = np.zeros((h + 2 * pad, w + 2 * pad, 3), dtype=core.dtype)
    out[pad:-pad, pad:-pad] = core
    out[:pad, pad:-pad] = core[pad - 1::-1, :]
    out[-pad:, pad:-pad] = core[:-pad - 1:-1, :]
    out[:, :pad] = out[:, 2 * pad - 1:pad - 1:-1]
    out[:, -pad:] = out[:, -pad - 1:-2 * pad - 1:-1]
    return out


def choose_target_mode(mode: str, ref_shape: tuple[int, int], target_width: int) -> str:
    if mode != "auto":
        return mode
    ref_w = ref_shape[1]
    return "per-x" if ref_w >= target_width * 0.45 else "global"


def target_grid_from_reference(
    ref: np.ndarray,
    target_grid_w: int,
    target_grid_h: int,
    mode: str,
    smooth_rounds: int,
) -> np.ndarray:
    if mode == "global":
        color = robust_tile_median(ref)
        return np.broadcast_to(color, (target_grid_h, target_grid_w, 3)).copy()

    ref_grid_w = max(4, min(target_grid_w, int(ref.shape[1] / 32)))
    ref_grid = median_grid(ref, ref_grid_w, 1)
    ref_line = smooth_grid(ref_grid, smooth_rounds)[0]

    # Resample the reference's horizontal color line across the full target.
    x_src = np.linspace(0.0, 1.0, ref_line.shape[0])
    x_dst = np.linspace(0.0, 1.0, target_grid_w)
    line = np.zeros((target_grid_w, 3), dtype=np.float32)
    for channel in range(3):
        line[:, channel] = np.interp(x_dst, x_src, ref_line[:, channel])
    return np.repeat(line[None, :, :], target_grid_h, axis=0)


def add_preview_labels(before: Image.Image, after: Image.Image, output: Path) -> None:
    max_h = 1800
    scale = min(1.0, max_h / before.height)
    bw = int(before.width * scale)
    bh = int(before.height * scale)
    before_r = before.resize((bw, bh), Image.Resampling.LANCZOS)
    after_r = after.resize((bw, bh), Image.Resampling.LANCZOS)

    label_h = 54
    gap = 20
    canvas = Image.new("RGB", (bw * 2 + gap, bh + label_h), (245, 242, 236))
    canvas.paste(before_r, (0, label_h))
    canvas.paste(after_r, (bw + gap, label_h))

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except Exception:
        font = ImageFont.load_default()
    draw.text((18, 12), "Before", fill=(30, 30, 30), font=font)
    draw.text((bw + gap + 18, 12), "After", fill=(30, 30, 30), font=font)
    canvas.save(output, quality=95, subsampling=0)


def run(args: argparse.Namespace) -> None:
    target_srgb = load_rgb(args.target)
    target_linear = srgb_to_linear(target_srgb)
    h, w = target_linear.shape[:2]

    pad = args.ignore_padding
    if pad > 0:
        work = target_linear[pad:h - pad, pad:w - pad]
    else:
        work = target_linear
    work_h, work_w = work.shape[:2]

    ref_source_path = args.reference_image or args.target
    ref_srgb = load_rgb(ref_source_path)
    ref_linear = srgb_to_linear(ref_srgb)
    if args.reference_rect:
        ref_linear = crop_rect(ref_linear, args.reference_rect)
    elif args.reference_image is None and pad > 0:
        ref_linear = target_linear[pad:h - pad, pad:w - pad]

    grid_w, grid_h = args.grid_size
    observed_grid = smooth_grid(median_grid(work, grid_w, grid_h), args.smooth_rounds)
    target_mode = choose_target_mode(args.target_mode, ref_linear.shape[:2], work_w)
    target_grid = target_grid_from_reference(
        ref_linear, grid_w, grid_h, target_mode, args.smooth_rounds
    )

    observed = resize_field(observed_grid, (work_w, work_h))
    target = resize_field(target_grid, (work_w, work_h))

    ratio = target / np.maximum(observed, 1e-4)
    ratio = np.clip(ratio, args.ratio_min, args.ratio_max)
    ratio = ratio ** (args.strength * args.channel_strength)

    corrected_work = np.clip(work * ratio, 0.0, 1.0)
    if args.regenerate_padding and pad > 0:
        corrected_linear = reflect_pad_core(corrected_work, pad)
    else:
        corrected_linear = target_linear.copy()
        if pad > 0:
            corrected_linear[pad:h - pad, pad:w - pad] = corrected_work
        else:
            corrected_linear = corrected_work

    corrected_srgb = (linear_to_srgb(corrected_linear) * 255.0 + 0.5).astype(np.uint8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(corrected_srgb, "RGB").save(args.output, quality=args.quality, subsampling=0)

    if args.preview:
        before = Image.fromarray((target_srgb * 255.0 + 0.5).astype(np.uint8), "RGB")
        after = Image.fromarray(corrected_srgb, "RGB")
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        add_preview_labels(before, after, args.preview)

    print(f"wrote {args.output}")
    if args.preview:
        print(f"wrote {args.preview}")
    print(f"target_mode={target_mode}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Correct wood texture color/reflection using a reference color region."
    )
    parser.add_argument("target", type=Path, help="Target image to correct.")
    parser.add_argument("output", type=Path, help="Corrected output image.")
    parser.add_argument(
        "--reference-image",
        type=Path,
        help="Image containing the desired color. Defaults to the target image.",
    )
    parser.add_argument(
        "--reference-rect",
        type=parse_rect,
        help="Reference rectangle as x,y,w,h pixels in reference image coordinates.",
    )
    parser.add_argument(
        "--target-mode",
        choices=("auto", "global", "per-x"),
        default="auto",
        help="Use one reference color or preserve horizontal plank variation. Default: auto.",
    )
    parser.add_argument(
        "--grid-size",
        type=parse_pair,
        default=(28, 64),
        help="Low-frequency grid as width,height. Default: 28,64.",
    )
    parser.add_argument(
        "--smooth-rounds",
        type=int,
        default=10,
        help="Smoothing passes for low-frequency fields. Default: 10.",
    )
    parser.add_argument(
        "--strength",
        type=float,
        default=1.0,
        help="Correction strength. 0 disables, 1 is full estimated correction.",
    )
    parser.add_argument(
        "--channel-strength",
        type=parse_triplet,
        default=np.array([1.0, 1.0, 1.0], dtype=np.float32)[None, None, :],
        help="Per-channel exponent strength as r,g,b. Example: 0.95,1,1.12.",
    )
    parser.add_argument("--ratio-min", type=float, default=0.42)
    parser.add_argument("--ratio-max", type=float, default=1.28)
    parser.add_argument(
        "--ignore-padding",
        type=int,
        default=0,
        help="Ignore this many edge pixels while estimating correction.",
    )
    parser.add_argument(
        "--regenerate-padding",
        action="store_true",
        help="Reflect-pad the corrected core back to the original size.",
    )
    parser.add_argument("--preview", type=Path, help="Optional side-by-side preview output.")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality. Default: 95.")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
