#!/usr/bin/env python3
"""Upscale wood textures with a conservative Real-ESRGAN/generic 2x blend.

Pipeline:
1. Lanczos resize to 2x plus mild unsharp mask.
2. Native Real-ESRGAN x2 via realesrgan-ncnn-vulkan.
3. Blend 60% Real-ESRGAN + 40% generic 2x to keep wood roughness.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


DEFAULT_BINARY = (
    Path(".context")
    / "upscale"
    / "bin"
    / "realesrgan-ncnn-vulkan-v0.2.0-macos"
    / "realesrgan-ncnn-vulkan"
)
DEFAULT_MODEL_DIR = (
    Path(".context")
    / "upscale"
    / "venv-py311"
    / "lib"
    / "python3.11"
    / "site-packages"
    / "realesrgan_ncnn_py"
    / "models"
)


def build_generic_2x(source: Path, output: Path, sharpen_percent: int) -> None:
    img = Image.open(source).convert("RGB")
    up = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
    up = up.filter(ImageFilter.UnsharpMask(radius=0.8, percent=sharpen_percent, threshold=3))
    up.save(output, quality=95, subsampling=0)


def run_realesrgan(source: Path, output: Path, binary: Path, model_dir: Path) -> None:
    cmd = [
        str(binary),
        "-i",
        str(source),
        "-o",
        str(output),
        "-m",
        str(model_dir),
        "-n",
        "realesr-animevideov3",
        "-s",
        "2",
        "-f",
        output.suffix.lstrip(".") or "png",
    ]
    subprocess.run(cmd, check=True)


def blend_images(generic: Path, realesrgan: Path, output: Path, generic_weight: float) -> None:
    gen = Image.open(generic).convert("RGB")
    real = Image.open(realesrgan).convert("RGB")
    if gen.size != real.size:
        gen = gen.resize(real.size, Image.Resampling.LANCZOS)
    g = np.asarray(gen).astype(np.float32)
    r = np.asarray(real).astype(np.float32)
    out = r * (1.0 - generic_weight) + g * generic_weight
    Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB").save(
        output, quality=95, subsampling=0
    )


def update_sidecar(source: Path, output: Path, generic_weight: float) -> None:
    source_json = source.with_suffix(".json")
    if not source_json.exists():
        return

    data = json.loads(source_json.read_text())
    out_img = Image.open(output)
    scale = 2
    data["output_image"] = str(output)
    data["image_size_px"] = {"width": out_img.width, "height": out_img.height}

    if "rectified_size_px" in data:
        data["rectified_size_px"] = {
            "width": int(data["rectified_size_px"]["width"]) * scale,
            "height": int(data["rectified_size_px"]["height"]) * scale,
        }
    if "crop_px" in data:
        data["crop_px"] = {
            key: int(value) * scale for key, value in data["crop_px"].items()
        }
    if "px_per_mm" in data:
        data["px_per_mm"] = float(data["px_per_mm"]) * scale
        data["dpi"] = round(data["px_per_mm"] * 25.4, 4)

    if "core_image_px" in data and "edge_padding_px" in data:
        pad = int(data.get("edge_padding_px", 0)) * scale
        data["core_image_px"] = {
            "width": out_img.width - 2 * pad,
            "height": out_img.height - 2 * pad,
        }
        data["edge_padding_px"] = pad
    data["upscale"] = {
        "method": "2x Lanczos/unsharp + native Real-ESRGAN x2 blend",
        "realesrgan_model": "realesr-animevideov3",
        "scale": 2,
        "realesrgan_weight": round(1.0 - generic_weight, 4),
        "generic_lanczos_weight": round(generic_weight, 4),
    }
    output.with_suffix(".json").write_text(json.dumps(data, indent=2) + "\n")


def process_one(args: argparse.Namespace, source: Path) -> Path:
    suffix = args.suffix
    output = source.with_name(f"{source.stem}{suffix}{source.suffix}")
    if args.output_dir:
        output = args.output_dir / output.name
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="wood-upscale-") as tmp_dir:
        tmp = Path(tmp_dir)
        generic = tmp / f"{source.stem}_generic_2x.jpg"
        real = tmp / f"{source.stem}_realesrgan_x2.png"
        build_generic_2x(source, generic, args.sharpen_percent)
        run_realesrgan(source, real, args.realesrgan_binary, args.model_dir)
        blend_images(generic, real, output, args.generic_weight)

    update_sidecar(source, output, args.generic_weight)
    print(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".context/wood_texture_pipeline/candidates"),
        help=(
            "Directory for generated candidates. Defaults outside the repo's "
            "tracked texture directory so only selected final assets are copied in."
        ),
    )
    parser.add_argument("--suffix", default="_2x_blend40")
    parser.add_argument("--generic-weight", type=float, default=0.40)
    parser.add_argument("--sharpen-percent", type=int, default=65)
    parser.add_argument("--realesrgan-binary", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    args = parser.parse_args()

    if not 0.0 <= args.generic_weight <= 1.0:
        raise ValueError("--generic-weight must be between 0 and 1")
    if not args.realesrgan_binary.exists():
        raise FileNotFoundError(args.realesrgan_binary)
    if not args.model_dir.exists():
        raise FileNotFoundError(args.model_dir)

    for source in args.sources:
        process_one(args, source)


if __name__ == "__main__":
    main()
