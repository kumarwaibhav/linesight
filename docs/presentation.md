# LineSight: project presentation outline

**Kumar Waibhav Akshat** · kwa.waibhav@gmail.com

## 1. The operational problem

A visual inspection station sees many normal products and comparatively few examples of every possible defect. A useful first model learns normal appearance and requests review when a product looks unusual.

**Show:** the branded overview and one normal/defective bottle comparison. Explain that the real images are MVTec AD benchmark images, with separate licensing.

## 2. The solution

LineSight combines an Isolation Forest visual anomaly detector with a working inspection console. It supports image upload, sampled browser camera frames, labeled dataset replay, coarse evidence, and local event metadata.

**Show:** the console. Inspect an image and identify score, threshold, model version, and processing time. State that anomaly score is not a defect probability.

## 3. Data and development discipline

Retain the official MVTec train/test boundary. Divide 209 normal training images into fit 125, tune 42, and calibration 42. Keep official test images out of candidate selection and threshold selection.

**Show:** the dataset split table and image-hash manifest. Explain why synthetic tune corruptions are useful proxies but do not replace real defect evaluation.

## 4. How Isolation Forest becomes computer vision

Create a normal appearance reference. Extract local color/edge residual descriptors. Fit the forest on normal descriptors. Pool patch scores or score aggregated image descriptors, then apply an independently calibrated image threshold.

**Show:** `docs/assets/architecture.svg` and one coarse heatmap. Distinguish reference-residual evidence from forest patch scores according to the selected representation.

## 5. Results with an operating point

Read AUROC **0.9468**, average precision **0.9819**, precision **96.36%**, recall **84.13%**, and F1 **89.83%** with their uncertainty from the generated report. Explain the 53 detected defects, 10 misses, and 2 false alarms at the frozen threshold. Disclose that 80% brightness and the 8-pixel resized-view translation flagged every test normal.

**Show:** the ROC/PR plots, score distributions, confusion matrix, and selected sample panels. Avoid equating strong ranking metrics with guaranteed production detection.

## 6. Usability and engineering

The same model serves upload, replay, and camera requests. The API limits input size and concurrent work; the browser avoids building an unbounded camera queue. Artifacts, configuration, experiment history, reports, tests, and container files make the work reviewable.

**Show:** the repository map, a real API response, the 50 passing tests, the executed notebook, and a brief local demo. Open the [technical report](../output/pdf/LineSight_Technical_Report.pdf) for detailed evidence. Keep Docker and physical-camera validation separate from the verified native service checks.

## 7. What a field pilot needs

Use appropriately licensed representative factory data. Validate new cameras, lighting, product batches, defect prevalence, image acquisition timing, and human review/rejection workflows. Establish drift checks and an independently measured operating threshold.

**Closing line:** “LineSight turns normal-only anomaly detection into an inspectable workflow—from source images and experiment decisions to an actionable review signal.”

## A concise project description

> Built LineSight, an end-to-end industrial visual anomaly detection project using Isolation Forest, normal-reference image features, independent threshold calibration, and held-out MVTec AD bottle evaluation. Integrated the trained detector into a FastAPI inspection console with image upload, sampled camera inference, benchmark replay, coarse heatmaps, local event history, reproducible experiments, and container support.

Add measured performance only after checking the generated report, and retain the benchmark category, test size, and operating-point context with any number quoted on a résumé.
