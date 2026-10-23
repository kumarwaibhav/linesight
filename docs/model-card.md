# Model card: LineSight Isolation Forest

**Owner:** Kumar Waibhav Akshat · kwa.waibhav@gmail.com

**Task:** image-level visual anomaly detection

**Input:** product image

**Output:** anomaly score, frozen threshold, binary review flag, coarse visual evidence

**Runtime:** CPU; NumPy, SciPy, Pillow, scikit-learn

## Intended use

A reproducible bottle inspection research demo and computer vision portfolio project. The normal reference assumes a controlled, fixed product view. A flagged image should be inspected by a person or a separately validated review workflow.

The model is not validated for automatic factory rejection, safety decisions, general object recognition, medical diagnosis, or arbitrary camera scenes. A high score means unusual appearance relative to training normals; it does not identify a specific defect category.

## Feature pipeline

1. Apply EXIF orientation; convert RGB; resize to 192 × 192 with bilinear interpolation.
2. Smooth RGB with a Gaussian filter of sigma 1.0.
3. Learn per-pixel RGB medians and robust MAD-based scales from fit normals. Scale floors are 0.025 for RGB and 0.018 for gradients.
4. Compute RGB appearance residuals and gradient residuals relative to the normal reference.
5. Tile the image into a 12 × 12 grid of non-overlapping 16 × 16 patches.

Each patch has **16 descriptors**: mean, 90th percentile, and maximum of four residual maps; local grayscale mean/standard deviation; and gradient mean/standard deviation. The four residual maps are mean standardized absolute RGB residual, standardized gradient residual, mean raw absolute RGB residual, and maximum standardized RGB residual.

The image representation instead uses **56 descriptors**: global residual quantiles and quadrant summaries. Both representations use a normal reference learned exclusively from the fit partition.

## Estimator and scoring

Isolation Forest is the central estimator. Each tree randomly splits feature values; points isolated with shorter average paths are more unusual. The implementation uses scikit-learn `IsolationForest` with deterministic seed 42, `contamination="auto"`, and `n_jobs=1`.

LineSight explicitly uses **negative `score_samples`** as its anomaly score. It does not use the forest's default `predict` threshold. Its own threshold is calibrated at the image level, independently of fitting and selection.

| Candidate | Forest input | Image score | Trees / sampled descriptors |
| --- | --- | --- | --- |
| `image_if` | 56 image descriptors | Negative image `score_samples` | 192 / up to 125 |
| `patch_if_max` | 16 patch descriptors | Maximum patch anomaly score | 192 / up to 512 |
| `patch_if_top4` | 16 patch descriptors | Mean of four highest patch scores | 192 / up to 512 |
| `patch_if_top9` | 16 patch descriptors | Mean of nine highest patch scores | 192 / up to 512 |

The frozen selected candidate is **`patch_if_max`**: 192 trees, up to 512 sampled patch descriptors per tree, and maximum pooling over 144 patch scores. Its model version is **`ls-a5006862e1ce`** and its decision threshold is **0.73856190923971**. The full artifact hash is recorded in [`reports/frozen_model.json`](../reports/frozen_model.json).

| Candidate | Tune proxy AUROC | Selected |
| --- | ---: | --- |
| `image_if` | 0.8152 | No |
| `patch_if_max` | 0.9211 | Yes |
| `patch_if_top4` | 0.8643 | No |
| `patch_if_top9` | 0.8054 | No |

These are proxy validation values, not test results. The patch candidates share one fitted forest and vary the image pooling policy. See [`reports/`](../reports/) for the final held-out evaluation.

## Model selection

The planned candidates are evaluated on 42 normal tune images and three deterministic synthetic variants per tune image: line, spot, and local inverted/flipped patch corruptions. These are **proxy anomalies**, not additional real defect data. They are never used to claim industrial test performance.

Selection maximizes tune proxy AUROC, then proxy recall at a tune-normal threshold, then follows configured candidate order to break ties. No official test label selects a candidate. A synthetic validation preference can still differ from performance on real defects; this is a deliberate limitation of the normal-only workflow.

## Decision threshold

After selecting the candidate, score **42 independent normal calibration images**. Sort those scores in ascending order and choose rank

\[
k = \left\lceil (n+1)(1-\alpha) \right\rceil,
\quad n=42,\quad \alpha=0.05,\quad k=41.
\]

The threshold is the **41st smallest calibration score** (the second largest). Flag an anomaly only when `score > threshold`.

This split-conformal upper order statistic targets a marginal nominal false-alarm level under exchangeability of calibration and future normal examples. It does not guarantee a 5% false-alarm rate for a particular camera stream, product batch, or shifted operating environment. The small calibration set also makes threshold resolution coarse. For too-small calibration sets where the requested rank exceeds the number of scores, the mathematical threshold is infinite; the serving model must have a finite calibrated threshold.

## Explanation semantics

For a patch candidate, the 12 × 12 heatmap contains patch isolation scores. For an image candidate, it contains normal-reference residual evidence. The latter is not a feature attribution of the image forest.

The heatmap is a coarse inspection aid. Upsampling it does not create pixel-accurate localization, and a bright area is not proof of a defect. Pixel masks are not used to optimize heatmaps or assert segmentation accuracy.

## Evaluation policy

The model, feature state, selected configuration, and threshold are saved before official test evaluation. The evaluator produces image AUROC, average precision, fixed-threshold precision/recall/F1, confusion counts, defect-group recall, bootstrap uncertainty, and timing. Stress tests apply brightness/translation changes to the frozen model (an 8-pixel translation is measured in the resized 192 × 192 model view, not the original 900 × 900 image); their results are diagnostics rather than a second model-selection step.

Report threshold-free ranking metrics alongside actual decision metrics. A model may rank images well while missing defects at its chosen operating point. Results on this small, defect-heavy benchmark are not projected production yield or deployment precision.

## Recorded performance and observed failure boundary

On the untouched official test partition, the frozen model achieved AUROC **0.9468**, average precision **0.9819**, precision **96.36%**, recall **84.13%**, and F1 **89.83%**. Confusion counts were 18 normal passes, 2 false alarms, 10 missed defects, and 53 detected defects. Per-defect detection was 20/20 large breaks, 19/22 small breaks, and 14/21 contamination images. Full uncertainty and per-image predictions are in [`reports/metrics.json`](../reports/metrics.json) and [`reports/test_predictions.csv`](../reports/test_predictions.csv).

The reference-residual baseline achieved AUROC **0.9389** and recall **76.19%** with no false alarms among the 20 test normals. Isolation Forest improved observed recall with a small increase in false alarms. This comparison on one small test set does not establish statistically significant superiority.

**The stress tests exposed substantial imaging sensitivity.** Brightness at 80% and an 8-pixel shift in the resized 192 × 192 view both flagged all 20 normal test images. Brightness at 120% flagged 12/20 normals. A camera/lighting change therefore requires representative data and renewed calibration/validation; this version should not be presented as ready for unrestricted camera scenes.

Measured single-image model timing was **139 ms median / 325 ms p95** on the preparation environment, using one forest thread and two excluded warmups. The timing excludes decoding, uploads, queues, SQLite, HTTP, and camera capture. It is shared-host benchmark evidence rather than a factory latency SLA.

## Reproducibility and artifact trust

Configuration lives in `configs/model.json`. Source-image hashes and roles live in `data/manifest.csv`. Experiment and evaluation outputs record the selected model and artifact identity. Exact dependencies are preserved in the supplied lock record.

The original frozen fit records **Pillow 12.3.0**. The supplied runtime lock uses **Pillow 13.0.0** after a security patch. Compatibility verification compared all 83 official test scores and decisions and found a maximum absolute score difference of zero, without changing the model or threshold. See [`reports/runtime_verification.json`](../reports/runtime_verification.json). Retraining in a patched environment can produce a new artifact identity; the original provenance is intentionally retained rather than rewritten.

The `.joblib` artifact uses pickle semantics. Load only trusted artifacts from this project; loading arbitrary model files can execute Python code. Train from the documented source if artifact provenance is uncertain.

## Failure modes and monitoring

Pose changes, lighting changes, background changes, transparent-surface reflections, tiny defects lost during resizing, and normal variation absent from fit data can cause errors. Monitor normal score distributions, observed review rates, independently labeled outcomes, and camera conditions. Recalibrate only on a separate, representative normal calibration set after any model change; keep a fresh untouched field test set.

Dataset and derived-artifact terms remain separate from the software's MIT license. See the [dataset card](dataset-card.md) and [third-party notices](../THIRD_PARTY_NOTICES.md).
