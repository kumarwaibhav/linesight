"""Fixed-view visual descriptors learned only from nominal training images.

Copyright (c) 2026 Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter, sobel


IMAGE_SIZE = 192
PATCH_SIZE = 16


def image_array(image: Image.Image, size: int = IMAGE_SIZE) -> np.ndarray:
    """Normalize image orientation, color and geometry deterministically."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    return np.asarray(image.resize((size, size), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0


def _gray(rgb: np.ndarray) -> np.ndarray:
    return rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def _tiles(array: np.ndarray, patch_size: int = PATCH_SIZE) -> np.ndarray:
    h, w = array.shape
    return (
        array.reshape(h // patch_size, patch_size, w // patch_size, patch_size)
        .transpose(0, 2, 1, 3)
        .reshape(-1, patch_size**2)
    )


@dataclass
class ReferenceFeatures:
    """Median reference and robust per-pixel dispersion for a fixed camera view.

    Descriptors represent deviation from nominal appearance. They are not
    pretrained deep embeddings and are sensitive to camera/illumination shift.
    """

    median: np.ndarray
    scale: np.ndarray
    gradient_median: np.ndarray
    gradient_scale: np.ndarray
    image_size: int = IMAGE_SIZE
    patch_size: int = PATCH_SIZE

    @classmethod
    def fit(cls, images: Sequence[Image.Image]) -> "ReferenceFeatures":
        if len(images) < 5:
            raise ValueError("At least five nominal fit images are required.")
        arrays = np.stack([image_array(im) for im in images])
        smooth = gaussian_filter(arrays, sigma=(0, 1.0, 1.0, 0))
        median = np.median(smooth, axis=0).astype(np.float32)
        scale = np.maximum(1.4826 * np.median(np.abs(smooth - median), axis=0), 0.025).astype(np.float32)
        grays = np.stack([_gray(a) for a in smooth])
        gradients = np.hypot(sobel(grays, axis=1), sobel(grays, axis=2)) / 8.0
        gm = np.median(gradients, axis=0).astype(np.float32)
        gs = np.maximum(1.4826 * np.median(np.abs(gradients - gm), axis=0), 0.018).astype(np.float32)
        return cls(median, scale, gm, gs)

    def transform(self, image: Image.Image) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return patch features, image features and a coarse residual grid.

        144 non-overlapping 16-pixel patches cover the 192-pixel view. All
        normalizing statistics come from the fit partition, never from input
        batches or test labels.
        """
        arr = image_array(image, self.image_size)
        smooth = gaussian_filter(arr, sigma=(1.0, 1.0, 0))
        gray = _gray(smooth)
        grad = np.hypot(sobel(gray, axis=0), sobel(gray, axis=1)) / 8.0
        z = np.mean(np.abs(smooth - self.median) / self.scale, axis=2)
        gz = np.abs(grad - self.gradient_median) / self.gradient_scale
        raw = np.mean(np.abs(smooth - self.median), axis=2)
        color = np.max(np.abs(smooth - self.median) / self.scale, axis=2)
        maps = [z, gz, raw, color]
        blocks = [_tiles(m, self.patch_size) for m in maps]
        # Mean, 90th percentile and maximum summarize both broad and tiny faults.
        descriptors = []
        for block in blocks:
            descriptors.extend([block.mean(axis=1), np.quantile(block, 0.9, axis=1), block.max(axis=1)])
        # Local brightness and edge variation retain contextual appearance.
        gb = _tiles(gray, self.patch_size)
        eb = _tiles(grad, self.patch_size)
        descriptors.extend([gb.mean(axis=1), gb.std(axis=1), eb.mean(axis=1), eb.std(axis=1)])
        patch_features = np.stack(descriptors, axis=1).astype(np.float32)
        # Global quantiles + spatial quadrant summaries form an image IF baseline.
        image_features = []
        for m in maps:
            image_features.extend(np.quantile(m, [0.5, 0.9, 0.95, 0.98, 0.995, 1.0]).tolist())
            for region in [m[:96, :96], m[:96, 96:], m[96:, :96], m[96:, 96:]]:
                image_features.extend([float(region.mean()), float(np.quantile(region, 0.99))])
        residual_grid = blocks[0].mean(axis=1).reshape(self.image_size // self.patch_size, -1)
        return patch_features, np.asarray(image_features, dtype=np.float32), residual_grid


def synthetic_defect(image: Image.Image, seed: int, kind: int) -> Image.Image:
    """Tune-only proxy corruption; never presented as a real industrial defect."""
    from PIL import ImageDraw

    rng = np.random.default_rng(seed)
    out = image.convert("RGB").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.BILINEAR).copy()
    draw = ImageDraw.Draw(out)
    x, y = rng.integers(48, 145, size=2).tolist()
    shade = int(rng.choice([5, 235]))
    if kind % 3 == 0:
        draw.line(
            (x, y, x + int(rng.integers(-20, 20)), y + int(rng.integers(12, 35))),
            fill=(shade,) * 3,
            width=int(rng.integers(2, 5)),
        )
    elif kind % 3 == 1:
        radius = int(rng.integers(4, 12))
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(shade,) * 3)
    else:
        patch = out.crop((x, y, x + 16, y + 16)).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        patch = ImageOps.invert(patch)
        out.paste(patch, (x, y))
    return out
