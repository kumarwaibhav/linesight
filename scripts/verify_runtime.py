#!/usr/bin/env python3
# ruff: noqa: E402
"""Check a security-updated image runtime against original frozen predictions.

Owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
No retraining, threshold changes or hyperparameter selection occurs.
"""
from __future__ import annotations

import csv
import json
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import PIL
from PIL import Image

from linesight.model import Detector, file_sha256


def main() -> None:
    frozen = json.loads((ROOT / "reports/frozen_model.json").read_text())
    artifact = ROOT / "artifacts/linesight.joblib"
    assert file_sha256(artifact) == frozen["artifact_sha256"], "Frozen artifact changed"
    detector = Detector.load(artifact)
    with (ROOT / "reports/test_predictions.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    differences, decisions, timings = [], [], []
    for row in rows:
        with Image.open(ROOT / row["path"]) as image:
            image.load()
            start = time.perf_counter()
            result = detector.inspect(image)
            timings.append((time.perf_counter() - start) * 1000)
        differences.append(abs(result["score"] - float(row["score"])))
        decisions.append(result["is_anomaly"] == (row["is_anomaly"] == "True"))
    max_delta = float(max(differences))
    matches = bool(max_delta <= 1e-12 and all(decisions))
    report = {
        "summary": f"Pillow {PIL.__version__}: all {len(rows)} frozen test decisions match; maximum score difference {max_delta:.3g}.",
        "purpose": "Security patch compatibility, not another selection or model iteration",
        "runtime_python": platform.python_version(), "runtime_pillow": PIL.__version__,
        "original_training_pillow": frozen["versions"]["pillow"],
        "frozen_model_version": detector.model_version, "frozen_artifact_sha256": file_sha256(artifact),
        "model_changed": False, "threshold_changed": False,
        "test_images_compared": len(rows), "max_absolute_score_difference": max_delta,
        "decisions_unchanged": all(decisions), "passed": matches,
        "runtime_model_latency_ms": {"p50": float(np.median(timings)), "p95": float(np.quantile(timings,.95)),
                                     "n": len(timings), "excludes": "image decoding, HTTP, capture, queueing and SQLite"},
        "baseline_predictions_sha256": file_sha256(ROOT / "reports/test_predictions.csv"),
    }
    (ROOT / "reports/runtime_verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if not matches:
        raise SystemExit("Runtime compatibility check failed; do not deploy this runtime.")


if __name__ == "__main__":
    main()
