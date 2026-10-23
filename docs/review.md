# Independent implementation and evidence review

Reviewed on 22 October 2026 for **Kumar Waibhav Akshat**
([kwa.waibhav@gmail.com](mailto:kwa.waibhav@gmail.com)).

This review checks data lineage, numerical calibration, model persistence,
reported benchmark evidence, and application boundaries. It does not certify a
factory installation or establish performance on a new product or camera.

## Data and model checks

The reviewer test modules are `tests/test_data.py` and `tests/test_model.py`.
They make no network requests and cover the following independently checked
properties:

- All 292 source images have unique paths and byte digests. Fit, tune, and
  calibration contain only official training normals; all 83 official test
  images remain in the test role.
- The local raw dataset, when present, matches every recorded image digest and
  all 63 mask digests. Raw-data tests explicitly skip in a source-only checkout
  until the documented downloader has been run.
- Archive extraction rejects traversal, absolute paths, symbolic links, and
  hard links. Training rejects changed image bytes and paths outside the
  project root.
- The calibration threshold is the 41st ordered score among 42 normals, with
  a strict `score > threshold` decision. An exhaustive 43-way exchangeable-rank
  example independently verifies the finite-sample exceedance rate of 2/43.
  Ties are conservative and too-small calibration sets require an infinite
  mathematical threshold that the serving detector refuses to use.
- Inference leaves learned reference statistics unchanged. Synthetic tune
  corruptions are deterministic and do not mutate their source images.
- Patch evidence and image scores agree with the negative Isolation Forest
  score direction and the declared aggregation. The image forest retains its
  separate reference-residual explanation semantics.
- Saving and loading preserve the score, threshold, decision, heatmap, and
  model identity. Artifact and manifest digests agree with the frozen run;
  calibration rows reproduce its threshold exactly.
- Every final prediction reconciles with the reported confusion matrix,
  precision, recall, F1, and false-positive rate. AUROC is independently
  checked using its pairwise ranking definition, rather than calling the
  evaluation implementation again.

These modules contain **28 passing test cases** in the reviewed run. The API
test module adds decoder, size-limit, concurrency, event-retention, readiness,
self-hosted API reference, corrupt-artifact, and actual-model integration
checks. The independent final regression run under **Pillow 13.0.0** completed
with **50 passed, zero failed, and zero skipped in 33.03 seconds**, using
`python -m pytest -q --tb=short`. One upstream Starlette warning marks its
`httpx` test-client integration as deprecated; the tests still pass. The final
machine-readable complete-suite record is maintained in the project reports.

## Findings corrected during review

| Finding | Correction |
| --- | --- |
| Patch-candidate forest reuse could ignore changed estimator parameters in future configuration edits. | The fitted-forest cache is keyed by fitting parameters; alternate score pooling can share a forest only when those parameters agree. |
| The default FastAPI documentation assets conflicted with the dashboard's self-only Content Security Policy. | The API reference and its scripts/styles are self-hosted; no CDN or relaxed script policy is required. |
| A corrupt serialized artifact could bypass the intended unready-service fallback. | The specific unpickling error is handled and covered by a regression test. |
| A camera result could be overlaid on a later live-video frame or carried to another source mode. | Results are displayed on their submitted still frame, and source switches clear prior heatmap evidence. |

Application tests also exposed an event-insert column-count mismatch, which was
corrected before delivery. SQLite connections are explicitly closed after
transaction use. Final runtime dependency and compatibility checks are recorded
separately so original training provenance is retained.

## Runtime dependency resolution

The runtime dependency audit initially identified Pillow advisories. Pillow was
upgraded to **13.0.0**. The original trained artifact was retained rather than
changing the model after viewing test performance. The compatibility check
rescored **all 83 held-out images** with the unchanged artifact and threshold:
every decision matched, and the maximum absolute score difference was **0.0**.
The record identifies both the original training Pillow version and the patched
serving version.

The final audit reports **zero known vulnerabilities among 30 pinned runtime
packages**. This is a result from the recorded dependency audit, not a guarantee
against undisclosed defects. See the machine-readable records below.

## What the measured results support

The frozen detector's official bottle test results are **AUROC 0.946825**,
**precision 0.963636**, **recall 0.841270**, and **F1 0.898305**. The underlying
counts are **53 detected defects, 10 missed defects, 18 correctly passed normal
images, and 2 false alarms**. These are benchmark observations at the frozen
normal-calibrated threshold, not a guarantee for a factory stream.

The reference-only baseline has AUROC 0.938889 and detects 48/63 defects with no
false alarms among the 20 test normals. The selected forest detects five more
defects while producing two additional false alarms. This tradeoff is visible
in the evidence rather than hidden behind one ranking metric.

The sensitivity probes expose a material operating limitation: reducing
brightness to 0.8 or translating by eight pixels in the resized 192-pixel view
flags **all 20 test normals** at the frozen threshold. A stable view and
representative calibration are essential. Reusing these test results to tune
the current model would weaken the held-out evaluation; the project therefore
reports the failure and leaves the model unchanged.

The heatmap is coarse evidence, not validated segmentation. Scores are not
probabilities, and model-only timing excludes decoding, HTTP, capture,
queueing, and event storage. Physical-camera behavior and container execution
require their own validation; neither follows from unit tests alone.

## Review evidence

- [`data/manifest.csv`](../data/manifest.csv) and
  [`data/provenance.json`](../data/provenance.json)
- [`reports/frozen_model.json`](../reports/frozen_model.json) and
  [`reports/calibration_scores.csv`](../reports/calibration_scores.csv)
- [`reports/test_predictions.csv`](../reports/test_predictions.csv) and
  [`reports/metrics.json`](../reports/metrics.json)
- [`reports/evaluation.md`](../reports/evaluation.md)
- [`reports/runtime_verification.json`](../reports/runtime_verification.json)
  and [`reports/dependency-audit.json`](../reports/dependency-audit.json)
- [`tests/test_data.py`](../tests/test_data.py),
  [`tests/test_model.py`](../tests/test_model.py), and
  [`tests/test_api.py`](../tests/test_api.py)

## Final browser integration

The root reviewer checked the desktop dashboard against the frozen model: a broken-large bottle scored 0.7420 and was flagged; recorded normal samples produced both the documented false alarm (0.7633) and nominal decisions (for example, 0.6304). Sequential replay stopped cleanly, history retained the decisions, and the self-hosted API reference returned HTTP 200 with model readiness. Physical camera capture and a separate mobile viewport were not verified.
