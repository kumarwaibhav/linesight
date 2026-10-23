"""Frozen-model evaluation, uncertainty, stress tests and report figures."""

from __future__ import annotations

import csv
import json
import platform
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance
from scipy.stats import norm
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)

from .features import image_array
from .model import Detector, file_sha256, upper_threshold
from .training import read_manifest, load_images, _scores


def summary(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    pred = scores > threshold
    tn, fp, fn, tp = confusion_matrix(labels, pred, labels=[0, 1]).ravel().tolist()
    return {
        "auroc": float(roc_auc_score(labels, scores)),
        "average_precision": float(average_precision_score(labels, scores)),
        "precision": float(precision_score(labels, pred, zero_division=0)),
        "recall": float(recall_score(labels, pred)),
        "f1": float(f1_score(labels, pred)),
        "accuracy": float(np.mean(labels == pred)),
        "false_positive_rate": float(fp / (tn + fp)),
        "confusion_matrix": [[tn, fp], [fn, tp]],
        "confusion_labels": ["normal", "defect"],
        "threshold": float(threshold),
    }


def bootstrap_ci(labels: np.ndarray, scores: np.ndarray, threshold: float, n: int = 2000) -> dict:
    """Class-stratified percentile intervals, preserving benchmark prevalence."""
    rng = np.random.default_rng(2026)
    indices = [np.flatnonzero(labels == label) for label in [0, 1]]
    values = {key: [] for key in ["auroc", "average_precision", "precision", "recall", "f1"]}
    for _ in range(n):
        sample = np.concatenate([rng.choice(group, size=len(group), replace=True) for group in indices])
        y, s = labels[sample], scores[sample]
        p = s > threshold
        current = [
            roc_auc_score(y, s),
            average_precision_score(y, s),
            precision_score(y, p, zero_division=0),
            recall_score(y, p),
            f1_score(y, p),
        ]
        for key, value in zip(values, current):
            values[key].append(value)
    return {
        "method": "class-stratified percentile bootstrap",
        "replicates": n,
        "seed": 2026,
        "confidence_level": 0.95,
        "intervals": {key: np.quantile(value, [0.025, 0.975]).tolist() for key, value in values.items()},
        "limitation": "Conditional on this small benchmark's class mix; not factory generalization uncertainty.",
    }


def _wilson(successes: int, n: int) -> list[float]:
    z = float(norm.ppf(0.975))
    p = successes / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [float(max(0, center - half)), float(min(1, center + half))]


def _stress(image: Image.Image, name: str) -> Image.Image:
    if name == "brightness_0.8":
        return ImageEnhance.Brightness(image).enhance(0.8)
    if name == "brightness_1.2":
        return ImageEnhance.Brightness(image).enhance(1.2)
    small = image.resize((192, 192), Image.Resampling.BILINEAR)
    corner = tuple(np.asarray(small)[0, 0, :3].tolist())
    return small.transform(
        (192, 192),
        Image.Transform.AFFINE,
        (1, 0, -8, 0, 1, 0),
        resample=Image.Resampling.BILINEAR,
        fillcolor=corner,
    )


def evaluate(root: str | Path) -> dict:
    root = Path(root).resolve()
    reports = root / "reports"
    frozen = json.loads((reports / "frozen_model.json").read_text())
    if file_sha256(root / "artifacts/linesight.joblib") != frozen["artifact_sha256"]:
        raise ValueError("Artifact differs from frozen selection. Evaluation refused.")
    if file_sha256(root / "data/manifest.csv") != frozen["dataset_manifest_sha256"]:
        raise ValueError("Manifest changed since model freeze. Evaluation refused.")
    detector = Detector.load(root / "artifacts/linesight.joblib")
    rows = read_manifest(root)
    test_rows = [row for row in rows if row["split"] == "test"]
    labels = np.array([int(row["label"]) for row in test_rows])
    print(
        f"Evaluating frozen model {detector.model_version} on {len(test_rows)} official test images.",
        flush=True,
    )
    images = load_images(root, test_rows)
    # Two warmups are excluded; timings include preprocessing/features/forest.
    detector.score(images[0])
    detector.score(images[0])
    outputs = [detector.score(image) for image in images]
    scores = np.array([output[0] for output in outputs])
    results = summary(labels, scores, detector.threshold)
    results.update(
        {
            "model_version": detector.model_version,
            "selected_candidate": frozen["selected_candidate"],
            "artifact_sha256": frozen["artifact_sha256"],
            "dataset": "MVTec AD bottle, official test split",
            "test_count": len(images),
            "test_normal_count": int(np.sum(labels == 0)),
            "test_defect_count": int(np.sum(labels == 1)),
            "positive_class": "defect",
            "score_direction": "higher is more anomalous",
            "score_is_probability": False,
            "model_frozen_before_test": True,
            "selection_and_calibration_use_real_test": False,
        }
    )
    timings = np.array([out[2]["total_ms"] for out in outputs])
    results["latency_ms"] = {
        "p50": float(np.median(timings)),
        "p95": float(np.quantile(timings, 0.95)),
        "mean": float(np.mean(timings)),
        "n": len(timings),
        "batch_size": 1,
        "warmup_count": 2,
        "includes": "RGB resize, reference descriptors and forest score",
        "excludes": "image decoding, upload, queue, SQLite, HTTP and camera capture",
        "forest_threads": 1,
        "platform": platform.platform(),
        "processor": platform.processor() or "not exposed",
        "hard_realtime_validated": False,
    }
    results["latency_ms"]["features_p50"] = float(np.median([o[2]["features_ms"] for o in outputs]))
    results["latency_ms"]["forest_p50"] = float(np.median([o[2]["forest_ms"] for o in outputs]))
    print("Computing 2,000 stratified bootstrap replicates.", flush=True)
    results["uncertainty"] = bootstrap_ci(labels, scores, detector.threshold)
    results["per_defect"] = {}
    for name in sorted({row["defect_type"] for row in test_rows if int(row["label"]) == 1}):
        keep = np.array([row["defect_type"] == name for row in test_rows])
        tp = int(np.sum(scores[keep] > detector.threshold))
        n = int(keep.sum())
        results["per_defect"][name] = {
            "n": n,
            "detected": tp,
            "recall": tp / n,
            "recall_wilson95": _wilson(tp, n),
        }
    tn, fp = results["confusion_matrix"][0]
    results["test_normal_fpr_wilson95"] = _wilson(fp, tn + fp)
    results["stress_tests"] = {}
    for name in ["brightness_0.8", "brightness_1.2", "translation_8px"]:
        print(f"Frozen-model sensitivity probe: {name}", flush=True)
        stress_features = [detector.reference.transform(_stress(im, name)) for im in images]
        stress_scores = _scores(detector, stress_features)
        results["stress_tests"][name] = summary(labels, stress_scores, detector.threshold)
    # A transparent reference-only baseline is evaluated under the same policy.
    cal_rows = [row for row in rows if row["split"] == "calibration"]
    cal_images = load_images(root, cal_rows)
    cal_baseline = np.array([detector.reference.transform(im)[1][4] for im in cal_images])
    base_threshold, _ = upper_threshold(cal_baseline, 0.05)
    base_scores = np.array([detector.reference.transform(im)[1][4] for im in images])
    results["reference_baseline"] = {
        "name": "fit-median standardized residual, pixel 99.5th percentile",
        **summary(labels, base_scores, base_threshold),
        "purpose": "Independent simple baseline; never used to retune the selected Isolation Forest.",
    }
    results["limitations"] = [
        "One fixed-view category; dataset replay is not a live factory validation.",
        "Official test has only 20 normal images; false-alarm uncertainty is large.",
        "Test defect prevalence differs from production and changes precision.",
        "Coarse patch evidence is not validated pixel segmentation.",
        "Brightness/pose drift can violate calibration assumptions and raise false alarms.",
        "Isolation Forest scores are ranking evidence, not defect probabilities.",
        "MVTec AD and benchmark-derived materials are noncommercial (CC BY-NC-SA 4.0).",
    ]
    with (reports / "test_predictions.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["path", "label", "defect_type", "score", "threshold", "is_anomaly", "correct", "model_version"]
        )
        for row, score in zip(test_rows, scores):
            pred = bool(score > detector.threshold)
            writer.writerow(
                [
                    row["path"],
                    row["label"],
                    row["defect_type"],
                    float(score),
                    detector.threshold,
                    pred,
                    pred == bool(int(row["label"])),
                    detector.model_version,
                ]
            )
    (reports / "metrics.json").write_text(json.dumps(results, indent=2) + "\n")
    make_figures(root, detector, test_rows, images, labels, scores, outputs, results)
    write_report(root, results)
    print(
        json.dumps(
            {
                key: results[key]
                for key in [
                    "auroc",
                    "average_precision",
                    "precision",
                    "recall",
                    "f1",
                    "confusion_matrix",
                    "latency_ms",
                ]
            },
            indent=2,
        ),
        flush=True,
    )
    return results


def make_figures(root, detector, rows, images, labels, scores, outputs, results):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = root / "reports/figures"
    out.mkdir(exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.titleweight": "bold",
            "figure.facecolor": "#f7f9fc",
            "axes.facecolor": "#ffffff",
            "axes.labelcolor": "#27364b",
            "text.color": "#142238",
            "xtick.color": "#475569",
            "ytick.color": "#475569",
            "savefig.facecolor": "#f7f9fc",
        }
    )
    normal, anomaly = "#0891b2", "#ea6646"
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), layout="constrained")
    fpr, tpr, _ = roc_curve(labels, scores)
    axes[0].plot(fpr, tpr, color=normal, lw=2.6, label=f"Isolation Forest · AUROC {results['auroc']:.3f}")
    axes[0].plot([0, 1], [0, 1], ls="--", color="#a5afbe", lw=1)
    axes[0].set(
        xlabel="False positive rate",
        ylabel="True positive rate",
        title="Image-level ROC",
        xlim=(-0.02, 1.02),
        ylim=(-0.02, 1.02),
    )
    axes[0].legend(loc="lower right", frameon=False)
    precision, recall, _ = precision_recall_curve(labels, scores)
    axes[1].plot(
        recall,
        precision,
        color=anomaly,
        lw=2.6,
        label=f"Average precision {results['average_precision']:.3f}",
    )
    axes[1].axhline(
        labels.mean(), ls="--", color="#a5afbe", lw=1, label=f"Benchmark prevalence {labels.mean():.2f}"
    )
    axes[1].set(
        xlabel="Recall", ylabel="Precision", title="Precision–recall", xlim=(-0.02, 1.02), ylim=(-0.02, 1.02)
    )
    axes[1].legend(loc="lower left", frameon=False)
    fig.suptitle("LineSight  /  frozen-model benchmark", fontsize=15, fontweight="bold")
    fig.savefig(out / "roc_pr.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), layout="constrained")
    bins = np.linspace(float(scores.min()) - 0.005, float(scores.max()) + 0.005, 19)
    for label, color, name in [(0, normal, "Normal"), (1, anomaly, "Defect")]:
        axes[0].hist(
            scores[labels == label],
            bins=bins,
            alpha=0.7,
            color=color,
            label=f"{name} (n={int((labels == label).sum())})",
        )
    axes[0].axvline(detector.threshold, color="#142238", ls="--", lw=2, label="Normal-only threshold")
    axes[0].set(
        xlabel="Anomaly score · higher means more anomalous",
        ylabel="Images",
        title="Score separation at frozen threshold",
    )
    axes[0].legend(frameon=False, fontsize=8)
    cm = np.asarray(results["confusion_matrix"])
    axes[1].imshow(cm, cmap="Blues", vmin=0, vmax=max(1, cm.max()))
    for r in range(2):
        for c in range(2):
            axes[1].text(
                c,
                r,
                str(cm[r, c]),
                ha="center",
                va="center",
                fontsize=27,
                fontweight="bold",
                color="white" if cm[r, c] > cm.max() * 0.5 else "#142238",
            )
    axes[1].set(
        xticks=[0, 1],
        yticks=[0, 1],
        xticklabels=["Normal", "Defect"],
        yticklabels=["Normal", "Defect"],
        xlabel="Predicted",
        ylabel="Ground truth",
        title="Image-level decisions",
    )
    fig.suptitle(
        f"LineSight  /  precision {results['precision']:.1%} · recall {results['recall']:.1%}",
        fontsize=15,
        fontweight="bold",
    )
    fig.savefig(out / "scores_confusion.png", dpi=180)
    plt.close(fig)
    selection = json.loads((root / "reports/selection.json").read_text())
    candidates = selection["candidates"]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), layout="constrained")
    names = [c["candidate"].replace("_", "\n") for c in candidates]
    colors = [
        normal if c["candidate"] == selection["selected"]["candidate"] else "#b9c7d7" for c in candidates
    ]
    bars = axes[0].bar(names, [c["proxy_auroc"] for c in candidates], color=colors, width=0.62)
    axes[0].set(ylim=(0, 1.08), ylabel="AUROC", title="Tune-only synthetic proxy selection")
    axes[0].bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    stress = {"Original": results, **{k.replace("_", "\n"): v for k, v in results["stress_tests"].items()}}
    x = np.arange(len(stress))
    width = 0.33
    axes[1].bar(
        x - width / 2, [v["recall"] for v in stress.values()], width, color=normal, label="Defect recall"
    )
    axes[1].bar(
        x + width / 2,
        [v["false_positive_rate"] for v in stress.values()],
        width,
        color=anomaly,
        label="Normal false alarms",
    )
    axes[1].set(
        xticks=x,
        xticklabels=list(stress),
        ylim=(0, 1.08),
        ylabel="Rate",
        title="Frozen-threshold sensitivity probes",
    )
    axes[1].legend(frameon=False, fontsize=8)
    fig.suptitle("Development evidence and deployment limits", fontsize=15, fontweight="bold")
    fig.savefig(out / "development_robustness.png", dpi=180)
    plt.close(fig)
    inspection_figure(root, detector, rows, images, scores, [output[1] for output in outputs])
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2), layout="constrained")
    names = list(results["per_defect"])
    vals = [results["per_defect"][n]["recall"] for n in names]
    bars = axes[0].barh([n.replace("_", " ") for n in names], vals, color=normal, height=0.55)
    axes[0].set(
        xlim=(0, 1.15), xlabel="Detected / total defective images", title="Recall by real defect type"
    )
    for bar, n in zip(bars, names):
        v = results["per_defect"][n]
        axes[0].text(
            bar.get_width() + 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{v['detected']}/{v['n']}",
            va="center",
            fontsize=9,
        )
    times = [o[2]["total_ms"] for o in outputs]
    axes[1].hist(times, bins=18, color="#6879aa", alpha=0.9)
    axes[1].axvline(
        results["latency_ms"]["p95"],
        color=anomaly,
        ls="--",
        label=f"p95 {results['latency_ms']['p95']:.1f} ms",
    )
    axes[1].set(
        xlabel="CPU model inference · milliseconds",
        ylabel="Images",
        title="Single-image latency · excludes HTTP/decode",
    )
    axes[1].legend(frameon=False)
    fig.suptitle("Coverage and runtime", fontsize=15, fontweight="bold")
    fig.savefig(out / "defects_latency.png", dpi=180)
    plt.close(fig)


def inspection_figure(root, detector, rows, images, scores, heatmaps):
    """Cover every defect type and show representative errors transparently."""
    import matplotlib.pyplot as plt

    chosen = []
    for name in ["good"] + sorted({r["defect_type"] for r in rows if int(r["label"]) == 1}):
        candidates = [i for i, r in enumerate(rows) if r["defect_type"] == name]
        errors = [
            i for i in candidates if bool(scores[i] > detector.threshold) != bool(int(rows[i]["label"]))
        ]
        if candidates:
            chosen.append((errors or candidates)[0])
    fig, axes = plt.subplots(
        len(chosen), 3, figsize=(9, len(chosen) * 2.65), layout="constrained", squeeze=False
    )
    for row_index, index in enumerate(chosen):
        arr = image_array(images[index])
        heat = heatmaps[index]
        pred = bool(scores[index] > detector.threshold)
        truth = bool(int(rows[index]["label"]))
        outcome = (
            "detected defect"
            if pred and truth
            else "false alarm"
            if pred
            else "missed defect"
            if truth
            else "correct normal"
        )
        axes[row_index, 0].imshow(arr)
        axes[row_index, 0].set_title(
            f"{rows[index]['defect_type']} · {'FLAG' if pred else 'PASS'}\n{outcome} · score {scores[index]:.4f}",
            fontsize=9,
        )
        axes[row_index, 1].imshow(arr)
        extent = (0, 191, 191, 0)
        axes[row_index, 1].imshow(
            heat,
            cmap="inferno",
            vmin=0.3 if detector.representation == "patch" else 0,
            vmax=0.8 if detector.representation == "patch" else 5,
            alpha=0.65,
            interpolation="bilinear",
            extent=extent,
        )
        axes[row_index, 1].set_title("Coarse patch evidence · not segmentation", fontsize=9)
        mask_path = rows[index].get("mask_path", "")
        if mask_path and (root / mask_path).is_file():
            with Image.open(root / mask_path) as source:
                mask = source.convert("L").resize((192, 192), Image.Resampling.NEAREST)
            axes[row_index, 2].imshow(mask, cmap="gray", vmin=0, vmax=255)
        else:
            axes[row_index, 2].imshow(np.zeros((192, 192)), cmap="gray", vmin=0, vmax=255)
        axes[row_index, 2].set_title("Dataset annotation · evaluation only", fontsize=9)
        for ax in axes[row_index]:
            ax.axis("off")
    fig.suptitle("LineSight  /  inspection evidence and failures", fontsize=15, fontweight="bold")
    fig.savefig(root / "reports/figures/inspection_examples.png", dpi=170)
    plt.close(fig)


def write_report(root: Path, results: dict) -> None:
    ci = results["uncertainty"]["intervals"]
    cm = results["confusion_matrix"]
    content = f"""# LineSight — Frozen Model Evaluation

Owner: **Kumar Waibhav Akshat** · [kwa.waibhav@gmail.com](mailto:kwa.waibhav@gmail.com)

Model `{results["model_version"]}` · selected `{results["selected_candidate"]}`.
Official MVTec AD bottle test split: {results["test_count"]} images, {results["test_normal_count"]} normal and {results["test_defect_count"]} defective.
The selected Isolation Forest configuration and threshold were frozen before test-image evaluation.

| Metric | Observed | 95% stratified bootstrap interval |
|---|---:|---:|
| AUROC | {results["auroc"]:.4f} | {ci["auroc"][0]:.4f}–{ci["auroc"][1]:.4f} |
| Average precision | {results["average_precision"]:.4f} | {ci["average_precision"][0]:.4f}–{ci["average_precision"][1]:.4f} |
| Precision | {results["precision"]:.4f} | {ci["precision"][0]:.4f}–{ci["precision"][1]:.4f} |
| Recall | {results["recall"]:.4f} | {ci["recall"][0]:.4f}–{ci["recall"][1]:.4f} |
| F1 | {results["f1"]:.4f} | {ci["f1"][0]:.4f}–{ci["f1"][1]:.4f} |

Confusion matrix: {cm[0][0]} true normal, {cm[0][1]} false alarm, {cm[1][0]} missed defect, {cm[1][1]} detected defect.
Anomaly scores are not probabilities. Precision reflects this defect-heavy benchmark, not a factory defect rate.

## Runtime

Single-image CPU model p50 **{results["latency_ms"]["p50"]:.2f} ms**, p95 **{results["latency_ms"]["p95"]:.2f} ms** across {results["latency_ms"]["n"]} images after two warmups; one forest thread.
This includes normalization, reference features and forest scoring. It excludes image decoding, uploads, HTTP, queueing, SQLite and capture.
No hard real-time or physical-camera deployment has been validated.

## Defect coverage

| Defect | Detected | Recall | Wilson 95% interval |
|---|---:|---:|---:|
"""
    for name, value in results["per_defect"].items():
        interval = value["recall_wilson95"]
        content += f"| {name} | {value['detected']}/{value['n']} | {value['recall']:.3f} | {interval[0]:.3f}–{interval[1]:.3f} |\n"
    content += "\n## Frozen-model stress probes\n\nThese are post-freeze sensitivity checks, not additional model-selection runs.\n\n| Condition | AUROC | Recall | Normal false-alarm rate |\n|---|---:|---:|---:|\n"
    for name, value in results["stress_tests"].items():
        content += f"| {name} | {value['auroc']:.3f} | {value['recall']:.3f} | {value['false_positive_rate']:.3f} |\n"
    b = results["reference_baseline"]
    content += f"\n## Simple reference baseline\n\nA fit-median standardized residual score (pixel 99.5th percentile), calibrated on the same independent normal split, achieved AUROC {b['auroc']:.4f}, recall {b['recall']:.4f}, and F1 {b['f1']:.4f}. This benchmark comparison is reported honestly and was not used to retune the selected Isolation Forest.\n\n## Practical limits\n\n"
    content += "\n".join(f"- {limitation}" for limitation in results["limitations"])
    content += "\n\n## Reproduction and evidence\n\n`python scripts/train.py --root .` freezes a fresh development run. `python scripts/evaluate.py --root .` checks the frozen artifact and manifest digests before evaluating.\n\nMachine-readable results: `metrics.json`, `test_predictions.csv`, `calibration_scores.csv`, `experiment_history.csv`, `selection.json`, and `frozen_model.json`. Bootstrap uses 2,000 class-stratified resamples with seed 2026. Figures are generated from these measured results.\n\n![ROC and precision–recall](figures/roc_pr.png)\n\n![Scores and decisions](figures/scores_confusion.png)\n\n![Inspection evidence](figures/inspection_examples.png)\n\n![Development and stress tests](figures/development_robustness.png)\n\n![Defect coverage and runtime](figures/defects_latency.png)\n"
    (root / "reports/evaluation.md").write_text(content)
