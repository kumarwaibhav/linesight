"""Leakage-aware candidate development, selection and threshold calibration."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
from pathlib import Path
import time

import numpy as np
from PIL import Image
import PIL
import scipy
import sklearn
from sklearn.metrics import roc_auc_score, recall_score

from .features import synthetic_defect
from .model import Detector, upper_threshold, file_sha256


def read_manifest(root: Path) -> list[dict]:
    with (root / "data/manifest.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("Empty dataset manifest.")
    seen_paths, seen_hashes = set(), set()
    for row in rows:
        if row["split"] not in {"fit", "tune", "calibration", "test"}:
            raise ValueError("Unknown manifest split.")
        if row["path"] in seen_paths or row["sha256"] in seen_hashes:
            raise ValueError("Duplicate path or image bytes in manifest.")
        seen_paths.add(row["path"])
        seen_hashes.add(row["sha256"])
        if row["split"] != "test" and int(row["label"]) != 0:
            raise ValueError("Development splits must contain nominal images only.")
    return rows


def load_images(root: Path, rows: list[dict]) -> list[Image.Image]:
    images = []
    for row in rows:
        path = (root / row["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Dataset path escapes project root.")
        if file_sha256(path) != row["sha256"]:
            raise ValueError(f"Dataset digest mismatch: {row['path']}")
        with Image.open(path) as image:
            images.append(image.convert("RGB").copy())
    return images


def _scores(detector: Detector, cached: list[tuple]) -> np.ndarray:
    if detector.representation == "image":
        return -detector.forest.score_samples(np.stack([item[1] for item in cached]))
    patch_scores = -detector.forest.score_samples(np.concatenate([item[0] for item in cached]))
    values = patch_scores.reshape(len(cached), -1)
    k = {"max": 1, "top4": 4, "top9": 9}[detector.aggregation]
    return np.partition(values, -k, axis=1)[:, -k:].mean(axis=1)


def train(root: str | Path) -> dict:
    root = Path(root).resolve()
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    config = json.loads((root / "configs/model.json").read_text())
    rows = read_manifest(root)
    by_split = {
        split: [row for row in rows if row["split"] == split] for split in ["fit", "tune", "calibration"]
    }
    if any(len(value) < 20 for value in by_split.values()):
        raise ValueError("Each development split must contain at least twenty images.")
    print("Loading only fit, tune and calibration images; test images remain unopened.", flush=True)
    fit = load_images(root, by_split["fit"])
    tune = load_images(root, by_split["tune"])
    calibration = load_images(root, by_split["calibration"])
    proxy = [
        synthetic_defect(im, config["seed"] + 1000 * i + kind, kind)
        for i, im in enumerate(tune)
        for kind in range(3)
    ]
    tune_images = tune + proxy
    labels = np.r_[np.zeros(len(tune)), np.ones(len(proxy))].astype(int)
    detectors, experiments = [], []
    shared_patch = {}
    cached_tune = None
    for index, candidate in enumerate(config["candidates"]):
        print(f"Fitting candidate {index + 1}/{len(config['candidates'])}: {candidate['name']}", flush=True)
        start = time.perf_counter()
        fit_key = tuple(
            (key, candidate.get(key, default))
            for key, default in [("n_estimators", 192), ("max_samples", 512), ("max_features", 1.0)]
        )
        if candidate["representation"] == "patch" and fit_key in shared_patch:
            shared = shared_patch[fit_key]
            detector = Detector(shared.reference, shared.forest, "patch", candidate["aggregation"])
        else:
            detector = Detector.fit(fit, candidate, config["seed"])
            if candidate["representation"] == "patch":
                shared_patch[fit_key] = detector
        if cached_tune is None:
            cached_tune = [detector.reference.transform(im) for im in tune_images]
        scores = _scores(detector, cached_tune)
        tune_threshold, _ = upper_threshold(scores[: len(tune)], config["alpha"])
        exp = {
            "candidate": candidate["name"],
            "config": candidate,
            "proxy_auroc": float(roc_auc_score(labels, scores)),
            "proxy_recall": float(recall_score(labels, scores > tune_threshold)),
            "tune_normal_false_alarm_rate": float(np.mean(scores[: len(tune)] > tune_threshold)),
            "tune_threshold": tune_threshold,
            "development_seconds": round(time.perf_counter() - start, 3),
            "selection_scope": "tune normals and tune-derived synthetic proxy defects only",
            "real_test_used": False,
        }
        experiments.append(exp)
        detectors.append(detector)
        print(json.dumps(exp), flush=True)
    chosen_index = max(
        range(len(experiments)),
        key=lambda i: (experiments[i]["proxy_auroc"], experiments[i]["proxy_recall"], -i),
    )
    selected = experiments[chosen_index]
    detector = detectors[chosen_index]
    # Write selection before calibrating; no test images have been opened.
    (reports / "selection.json").write_text(
        json.dumps(
            {
                "selected": selected,
                "candidates": experiments,
                "tune_normal_count": len(tune),
                "synthetic_proxy_count": len(proxy),
                "proxy_types": ["scratch", "blob", "inverted_patch"],
                "synthetic_seed_rule": "42 + 1000 * tune_index + kind",
                "warning": "Synthetic proxy quality does not establish real-defect performance.",
            },
            indent=2,
        )
        + "\n"
    )
    cal_features = [detector.reference.transform(im) for im in calibration]
    cal_scores = _scores(detector, cal_features)
    detector.threshold, rank = upper_threshold(cal_scores, config["alpha"])
    frozen = {
        "project": "LineSight",
        "owner": "Kumar Waibhav Akshat",
        "email": "kwa.waibhav@gmail.com",
        "seed": config["seed"],
        "selected_candidate": selected["candidate"],
        "config": selected["config"],
        "image_size": 192,
        "patch_size": 16,
        "patch_grid": [12, 12],
        "calibration": {
            "method": "split_conformal_upper_order_statistic",
            "alpha": config["alpha"],
            "n": len(cal_scores),
            "rank_one_indexed": rank,
            "threshold": detector.threshold,
            "strict_decision": "score > threshold",
            "nominal_error_bound_under_exchangeability": float(
                (len(cal_scores) + 1 - rank) / (len(cal_scores) + 1)
            ),
            "assumption": "Calibration and future nominal images must be exchangeable; drift invalidates coverage.",
        },
        "dataset_manifest_sha256": file_sha256(root / "data/manifest.csv"),
        "development_hashes": {split: [row["sha256"] for row in by_split[split]] for split in by_split},
        "selection_real_test_used": False,
        "threshold_real_test_used": False,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pillow": PIL.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    canonical = json.dumps(frozen, sort_keys=True).encode()
    detector.model_version = "ls-" + hashlib.sha256(canonical).hexdigest()[:12]
    frozen["model_version"] = detector.model_version
    detector.metadata = frozen
    artifact = root / "artifacts/linesight.joblib"
    detector.save(artifact)
    frozen["artifact_sha256"] = file_sha256(artifact)
    frozen["artifact_bytes"] = artifact.stat().st_size
    (reports / "frozen_model.json").write_text(json.dumps(frozen, indent=2) + "\n")
    with (reports / "experiment_history.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate",
                "proxy_auroc",
                "proxy_recall",
                "tune_normal_false_alarm_rate",
                "tune_threshold",
                "development_seconds",
                "selected",
            ],
        )
        writer.writeheader()
        for index, exp in enumerate(experiments):
            writer.writerow(
                {
                    **{key: exp[key] for key in writer.fieldnames if key != "selected"},
                    "selected": index == chosen_index,
                }
            )
    with (reports / "calibration_scores.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["path", "score", "threshold", "is_anomaly"])
        writer.writerows(
            (row["path"], float(score), detector.threshold, bool(score > detector.threshold))
            for row, score in zip(by_split["calibration"], cal_scores)
        )
    print(
        f"FROZEN {detector.model_version} — {selected['candidate']}; threshold={detector.threshold:.8f}; artifact={artifact}",
        flush=True,
    )
    return frozen
