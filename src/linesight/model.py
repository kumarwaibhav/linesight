"""Persisted Isolation Forest detector and calibrated decision policy.

Owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import hashlib
import time

import joblib
import numpy as np
from PIL import Image
from sklearn.ensemble import IsolationForest

from .features import ReferenceFeatures


def upper_threshold(scores: np.ndarray, alpha: float = 0.05) -> tuple[float, int]:
    """Finite-sample split-conformal upper order statistic, strict > decision.

    The guarantee requires exchangeable future nominal examples. It does not
    apply under camera drift. An infinite threshold is required for too-small n.
    """
    scores = np.asarray(scores, dtype=float)
    if scores.ndim != 1 or len(scores) == 0 or not np.isfinite(scores).all():
        raise ValueError("Calibration scores must be a nonempty finite vector.")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    rank = int(np.ceil((len(scores) + 1) * (1 - alpha)))
    return (float(np.sort(scores)[rank - 1]) if rank <= len(scores) else float("inf"), rank)


@dataclass
class Detector:
    reference: ReferenceFeatures
    forest: IsolationForest
    representation: str = "patch"
    aggregation: str = "top4"
    threshold: float = float("inf")
    model_version: str = "unfrozen"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def fit(cls, images: list[Image.Image], config: dict[str, Any], seed: int = 42) -> "Detector":
        reference = ReferenceFeatures.fit(images)
        features = [reference.transform(im) for im in images]
        representation = config.get("representation", "patch")
        X = (
            np.concatenate([v[0] for v in features])
            if representation == "patch"
            else np.stack([v[1] for v in features])
        )
        forest = IsolationForest(
            n_estimators=config.get("n_estimators", 192),
            max_samples=min(config.get("max_samples", 512), len(X)),
            max_features=config.get("max_features", 1.0),
            contamination="auto",
            random_state=seed,
            n_jobs=1,
        )
        forest.fit(X)
        return cls(reference, forest, representation, config.get("aggregation", "top4"))

    def score(self, image: Image.Image) -> tuple[float, np.ndarray, dict[str, float]]:
        start = time.perf_counter()
        patches, global_features, residual = self.reference.transform(image)
        features_done = time.perf_counter()
        if self.representation == "patch":
            values = -self.forest.score_samples(patches)
            k = {"max": 1, "top4": 4, "top9": 9}[self.aggregation]
            score = float(np.partition(values, -k)[-k:].mean())
            heatmap = values.reshape(residual.shape)
        else:
            score = float(-self.forest.score_samples(global_features.reshape(1, -1))[0])
            # This is reference residual evidence, not an attribution of IF.
            heatmap = residual
        end = time.perf_counter()
        return (
            score,
            heatmap,
            {
                "features_ms": (features_done - start) * 1000,
                "forest_ms": (end - features_done) * 1000,
                "total_ms": (end - start) * 1000,
            },
        )

    def inspect(self, image: Image.Image) -> dict[str, Any]:
        score, heatmap, timing = self.score(image)
        if not np.isfinite(score) or not np.isfinite(heatmap).all() or not np.isfinite(self.threshold):
            raise ValueError("Detector has nonfinite score or has not been calibrated.")
        return {
            "score": score,
            "threshold": float(self.threshold),
            "is_anomaly": bool(score > self.threshold),
            "heatmap": heatmap.tolist(),
            "model_version": self.model_version,
            "timing_ms": timing,
            "heatmap_kind": "patch_isolation_score"
            if self.representation == "patch"
            else "reference_residual",
            "score_is_probability": False,
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path, compress=3)

    @classmethod
    def load(cls, path: str | Path) -> "Detector":
        """Load trusted artifacts only: joblib uses Python pickle semantics."""
        detector = joblib.load(path)
        if not isinstance(detector, cls):
            raise ValueError("Artifact does not contain a LineSight Detector.")
        return detector


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
