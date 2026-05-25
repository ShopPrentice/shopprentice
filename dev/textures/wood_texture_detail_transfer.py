#!/usr/bin/env python3
"""Transfer high-frequency wood grain detail from a reference texture.

This preserves the target image's large-scale color and figure while blending
in pore/grain sharpness sampled from a higher-resolution reference image of the
same species. It is intended for improving low-PPI veneer photos, not for
reconstructing exact missing board detail.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def parse_size(value: str) -> tuple[int, int]:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) != 2 or parts[0] <= 0 or parts[1] <= 0:
        raise argparse.ArgumentTypeError("expected positive width,height")
    return parts[0], parts[1]


def parse_rect(value: str) -> tuple[int, int, int, int]:
    parts = [int(p.strip()) for p in value.split(",")]
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        raise argparse.ArgumentTypeError("expected x,y,w,h")
    return parts[0], parts[1], parts[2], parts[3]


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * (x ** (1.0 / 2.4)) - 0.055)


def load_rgb(path: Path) -> Image.Image:
    return Image.open(path).convert("RGB")


def crop_image(img: Image.Image, rect: tuple[int, int, int, int] | None) -> Image.Image:
    if rect is None:
        return img
    x, y, w, h = rect
    return img.crop((x, y, x + w, y + h))


def fit_reference_patch(ref: Image.Image, target_size: tuple[int, int], mode: str) -> Image.Image:
    tw, th = target_size
    if mode == "stretch":
        return ref.resize((tw, th), Image.Resampling.LANCZOS)

    if mode == "tile":
        canvas = Image.new("RGB", (tw, th))
        for y in range(0, th, ref.height):
            for x in range(0, tw, ref.width):
                canvas.paste(ref, (x, y))
        return canvas

    # crop-cover: scale to cover the target, then center crop.
    scale = max(tw / ref.width, th / ref.height)
    rw = int(round(ref.width * scale))
    rh = int(round(ref.height * scale))
    resized = ref.resize((rw, rh), Image.Resampling.LANCZOS)
    left = max(0, (rw - tw) // 2)
    top = max(0, (rh - th) // 2)
    return resized.crop((left, top, left + tw, top + th))


def blur_array(img: Image.Image, radius: float) -> np.ndarray:
    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    return srgb_to_linear(np.asarray(blurred).astype(np.float32) / 255.0)


def luminance(linear: np.ndarray) -> np.ndarray:
    return 0.2126 * linear[:, :, 0] + 0.7152 * linear[:, :, 1] + 0.0722 * linear[:, :, 2]


def add_preview(before: Image.Image, after: Image.Image, output: Path) -> None:
    max_h = 1800
    scale = min(1.0, max_h / before.height)
    bw = int(before.width * scale)
    bh = int(before.height * scale)
    b = before.resize((bw, bh), Image.Resampling.LANCZOS)
    a = after.resize((bw, bh), Image.Resampling.LANCZOS)
    label_h = 54
    gap = 20
    canvas = Image.new("RGB", (bw * 2 + gap, bh + label_h), (245, 242, 236))
    canvas.paste(b, (0, label_h))
    canvas.paste(a, (bw + gap, label_h))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except Exception:
        font = ImageFont.load_default()
    draw.text((18, 12), "Before", fill=(30, 30, 30), font=font)
    draw.text((bw + gap + 18, 12), "After detail transfer", fill=(30, 30, 30), font=font)
    canvas.save(output, quality=95, subsampling=0)


def run(args: argparse.Namespace) -> None:
    target_img = load_rgb(args.target)
    ref_img = crop_image(load_rgb(args.reference), args.reference_rect)

    if args.output_size:
        target_work = target_img.resize(args.output_size, Image.Resampling.LANCZOS)
    else:
        target_work = target_img.copy()

    ref_work = fit_reference_patch(ref_img, target_work.size, args.reference_fit)

    target_lin = srgb_to_linear(np.asarray(target_work).astype(np.float32) / 255.0)
    target_low = blur_array(target_work, args.target_blur)
    ref_lin = srgb_to_linear(np.asarray(ref_work).astype(np.float32) / 255.0)
    ref_low = blur_array(ref_work, args.reference_blur)

    target_luma = np.maximum(luminance(target_lin), 1e-4)
    target_low_luma = np.maximum(luminance(target_low), 1e-4)
    ref_luma = np.maximum(luminance(ref_lin), 1e-4)
    ref_low_luma = np.maximum(luminance(ref_low), 1e-4)

    target_detail = np.clip(target_luma / target_low_luma, 0.55, 1.70)
    ref_detail = np.clip(ref_luma / ref_low_luma, 0.55, 1.70)

    # Blend reference detail with target's own detail so the result gains
    # sharpness without erasing actual target pores/lines.
    blended_detail = (target_detail ** (1.0 - args.reference_weight)) * (
        ref_detail ** args.reference_weight
    )
    multiplier = np.clip(blended_detail / np.maximum(target_detail, 1e-4), 0.70, 1.45)
    multiplier = multiplier ** args.strength

    out_lin = np.clip(target_lin * multiplier[:, :, None], 0.0, 1.0)
    out_srgb = (linear_to_srgb(out_lin) * 255.0 + 0.5).astype(np.uint8)
    out_img = Image.fromarray(out_srgb, "RGB")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(args.output, quality=args.quality, subsampling=0)
    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        add_preview(target_work, out_img, args.preview)
    print(f"wrote {args.output}")
    if args.preview:
        print(f"wrote {args.preview}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transfer high-frequency wood grain detail from a reference texture."
    )
    parser.add_argument("target", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--output-size", type=parse_size, help="Optional output width,height.")
    parser.add_argument("--reference-rect", type=parse_rect, help="Crop reference as x,y,w,h.")
    parser.add_argument(
        "--reference-fit",
        choices=("crop-cover", "stretch", "tile"),
        default="crop-cover",
    )
    parser.add_argument("--target-blur", type=float, default=8.0)
    parser.add_argument("--reference-blur", type=float, default=8.0)
    parser.add_argument("--reference-weight", type=float, default=0.65)
    parser.add_argument("--strength", type=float, default=0.75)
    parser.add_argument("--quality", type=int, default=95)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
