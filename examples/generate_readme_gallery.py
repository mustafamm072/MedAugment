"""Render the README gallery from synthetic phantoms and actual library outputs.

Run from the repository root after installing medaugmentx and matplotlib:
    python examples/generate_readme_gallery.py

No patient data, downloads, or image-generation services are used. Transform
strengths are chosen for illustration, not as recommended training policies.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from importlib.metadata import version
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

from medaugmentx import MedVolume
from medaugmentx.transforms import (
    BeamHardening,
    BiasField,
    GridArtifact,
    LimitedAngleBlur,
    MetalStreak,
    ReconStreak,
    RicianNoise,
    ScatterSimulation,
)


def coordinates(size: int = 256) -> tuple[np.ndarray, np.ndarray]:
    return tuple(np.meshgrid(np.linspace(-1, 1, size), np.linspace(-1, 1, size), indexing="ij"))


def ellipse(y, x, cy, cx, ry, rx):
    return ((y - cy) / ry) ** 2 + ((x - cx) / rx) ** 2 < 1


def mri_phantom() -> MedVolume:
    y, x = coordinates()
    head = ellipse(y, x, 0, 0, 0.90, 0.73)
    brain = ellipse(y, x, 0, 0, 0.80, 0.65)
    inner = ellipse(y, x, 0, 0, 0.69, 0.54)
    image = 0.12 * head + 0.43 * brain + 0.18 * inner
    folds = (np.sin(35 * x + 4 * np.cos(13 * y)) * np.sin(28 * y - 3 * x))
    image += 0.08 * folds * brain
    image[ellipse(y, x, -0.02, -0.12, 0.24, 0.07)] = 0.12
    image[ellipse(y, x, -0.02, 0.12, 0.24, 0.07)] = 0.12
    image[(np.abs(x) < 0.012) & brain] *= 0.65
    return MedVolume(gaussian_filter(image, 0.7).astype(np.float32), metadata={"modality": "MR"})


def ct_phantom() -> MedVolume:
    y, x = coordinates()
    body = ellipse(y, x, 0, 0, 0.77, 0.91)
    image = np.full(y.shape, -1000.0)
    image[body] = -100.0
    image[ellipse(y, x, 0, 0, 0.67, 0.80)] = 45.0
    image[ellipse(y, x, -0.14, -0.35, 0.35, 0.29)] = 85.0
    image[ellipse(y, x, -0.07, 0.42, 0.25, 0.19)] = 65.0
    for cx in (-0.29, 0.29):
        image[ellipse(y, x, 0.22, cx, 0.16, 0.11)] = 110.0
    image[ellipse(y, x, 0.40, 0, 0.15, 0.15)] = 800.0
    image[ellipse(y, x, 0.40, 0, 0.09, 0.09)] = 150.0
    image[ellipse(y, x, 0.12, 0.02, 0.07, 0.07)] = 170.0
    return MedVolume(gaussian_filter(image, 0.65).astype(np.float32), metadata={"modality": "CT"})


def xray_phantom() -> MedVolume:
    y, x = coordinates()
    body = ellipse(y, x, 0, 0, 0.94, 0.79)
    image = 0.05 + 0.42 * body.astype(float)
    lungs = ellipse(y, x, -0.08, -0.31, 0.68, 0.25) | ellipse(y, x, -0.08, 0.31, 0.68, 0.25)
    image[lungs] = 0.15
    image += 0.20 * np.exp(-(x / 0.085) ** 2) * body
    image += 0.18 * ellipse(y, x, 0.24, 0.10, 0.32, 0.27)
    for height in np.linspace(-0.67, 0.52, 8):
        arc = height + 0.38 * x**2
        image += 0.14 * np.exp(-((y - arc) / 0.018) ** 2) * body
    image += 0.035 * np.sin(21 * x + 9 * y) * lungs
    return MedVolume(gaussian_filter(image, 0.7).astype(np.float32), metadata={"modality": "DX"})


def dbt_phantom() -> MedVolume:
    # A true 3D phantom. Gallery plane is (z, x) through the middle y index.
    z, y, x = np.meshgrid(np.linspace(-1, 1, 64), np.linspace(-1, 1, 128),
                          np.linspace(-1, 1, 256), indexing="ij")
    tissue = (z / 0.80) ** 2 + (y / 1.15) ** 2 + ((x + 0.33) / 1.15) ** 2 < 1
    image = tissue * (0.16 + 0.035 * np.sin(15 * x + 9 * z) * np.cos(8 * y))
    rng = np.random.default_rng(2026)
    for _ in range(24):
        cz, cx = rng.uniform(-0.6, 0.6), rng.uniform(-0.9, 0.65)
        rz, rx = rng.uniform(0.025, 0.09), rng.uniform(0.025, 0.13)
        blob = np.exp(-((z - cz) / rz) ** 2 - ((x - cx) / rx) ** 2 - (y / 0.35) ** 2)
        image += rng.uniform(0.2, 0.6) * blob * tissue
    return MedVolume(image.astype(np.float32), spacing=(1.0, 0.5, 0.25), metadata={"modality": "DBT"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "docs/assets")
    args = parser.parse_args()
    # Keep font caches outside the checkout, and support headless regeneration.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "medaugmentx-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cases = [
        ("MRI", "Synthetic axial slice", mri_phantom(),
         [BiasField(alpha=0.65, coarse_shape=3, seed=7), RicianNoise(std=0.09, seed=7)], (0, 1)),
        ("CT", "Synthetic axial slice", ct_phantom(),
         [BeamHardening(alpha=0.10, seed=7),
          MetalStreak(intensity=0.16, num_streaks=9, seed=7)], (-250, 350)),
        ("X-RAY", "Synthetic projection", xray_phantom(),
         [ScatterSimulation(fraction=0.5, sigma=22, seed=7),
          GridArtifact(amplitude=0.16, frequency=0.16, seed=7)], (0, 0.85)),
        ("TOMOSYNTHESIS", "Synthetic 3D volume / depth view", dbt_phantom(),
         [LimitedAngleBlur(arc_degrees=15, base_sigma=1.8, seed=7),
          ReconStreak(amplitude=0.3, num_planes=3, displacement=4, seed=7)], (0, 0.8)),
    ]
    fig = plt.figure(figsize=(12, 15.4), facecolor="#f4f6f8")
    fig.text(0.055, 0.972, "See what changes.", fontsize=28, weight="bold", color="#152b3c")
    fig.text(0.055, 0.946, "Four modalities. Real MedAugmentX transforms. Reproducible synthetic inputs.",
             fontsize=12, color="#52616e")
    records = []
    for row, (name, subtitle, volume, transforms, limits) in enumerate(cases):
        top = 0.914 - row * 0.215
        fig.text(0.055, top, name, fontsize=11, weight="bold", color="#087e8b")
        fig.text(0.245, top, subtitle, fontsize=10, color="#52616e")
        outputs = [volume, *(transform(volume) for transform in transforms)]
        titles = ["Original", *(type(transform).__name__ for transform in transforms)]
        for column, (output, title) in enumerate(zip(outputs, titles)):
            assert np.isfinite(output.image).all()
            assert output.shape == volume.shape
            if column:
                assert not np.array_equal(output.image, volume.image)
            plane = output.image if output.ndim == 2 else output.image[:, output.shape[1] // 2, :]
            ax = fig.add_axes((0.055 + column * 0.31, top - 0.189, 0.27, 0.168))
            extent = (0, 64, 64, 0) if output.ndim == 3 else None
            # Same display range for all three panels; no per-image normalization.
            ax.imshow(plane, cmap="gray", vmin=limits[0], vmax=limits[1],
                      interpolation="nearest", extent=extent)
            ax.set_title(title, fontsize=11, color="#152b3c", pad=7)
            ax.set_axis_off()
        records.append({"modality": name, "display_limits": limits,
                        "shape": volume.shape, "spacing": volume.spacing,
                        "view": subtitle, "transforms": [t.to_dict() for t in transforms]})
    fig.text(0.055, 0.028, "Synthetic illustrations, not patient scans. Effects are emphasized for visibility.",
             fontsize=10, color="#52616e")
    fig.text(0.055, 0.013, "Each transform is applied independently to the original. Grayscale limits are fixed within each row.",
             fontsize=9, color="#52616e")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "modality-gallery.png"
    fig.savefig(path, dpi=140, facecolor=fig.get_facecolor(), metadata={"Software": "MedAugmentX gallery"})
    plt.close(fig)
    manifest = {"synthetic": True, "environment": {name: version(name) for name in
                ("medaugmentx", "numpy", "scipy", "matplotlib")}, "examples": records}
    (args.output_dir / "modality-gallery.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
