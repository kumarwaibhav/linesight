# Local deployment and operations

**Owner:** Kumar Waibhav Akshat · kwa.waibhav@gmail.com

LineSight is prepared for local use and container evaluation. This handoff does not publish a Site, deploy a public service, or push to GitHub.

## Python environment

From the repository root, create a virtual environment with Python 3.11–3.13 and install the package:

```bash
python -m pip install -r requirements.lock
python -m pip install -e '.[dev]'
```

Install the lock first to retain the prepared runtime versions.

The runtime lock uses Pillow 13.0.0. Original fitting metadata retains Pillow 12.3.0; all 83 frozen scores and decisions were independently checked under 13.0.0 with zero score difference. This was patch compatibility verification, not another model-selection round. Dataset acquisition needs network access. Trained inference uses local dependencies and the trusted artifact at `artifacts/linesight.joblib`.

```bash
python scripts/download_data.py
python scripts/train.py --root .
python scripts/evaluate.py --root .
python scripts/serve.py
```

Visit http://127.0.0.1:8000. The model must be calibrated before inspection is available. The service reports readiness separately from basic process health when the artifact is missing.

## Configuration

| Setting | Meaning |
| --- | --- |
| `LINESIGHT_ROOT` | Repository/application root used for artifacts, reports, data, and web assets |
| `LINESIGHT_MODEL` | Optional trusted model artifact path |
| `LINESIGHT_DB` | Optional SQLite event database path |
| `python scripts/serve.py --host 127.0.0.1 --port 8000` | Explicit local host and port |

## Container

The repository includes `Dockerfile` and `compose.yaml`. Build and run from the repository root:

```bash
docker compose up --build
```

Use the supplied trained artifact, or train one on the host, before starting the service. Dataset replay additionally requires the local dataset and manifest. Check the Compose volume configuration to keep event metadata persistent across container recreation. Stop with:

```bash
docker compose down
```

The container recipe has not been verified with an actual Docker build in the preparation environment because Docker is unavailable. Native service and test evidence are recorded separately. The image is configured to run as a non-root user. Keep the service bound to localhost for a personal demo. The local SQLite event store and model access policy are designed around a single application worker; scaling to multiple processes requires an explicit storage/concurrency design.

## API workflow

Use the generated OpenAPI interface at `/docs` for precise request and response schemas.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Process and model readiness |
| `GET /api/model` | Model identity, threshold, and metadata |
| `GET /api/metrics` | Recorded evaluation evidence |
| `GET /api/samples` | Available benchmark replay images |
| `GET /api/samples/{id}/image` | Image selected through a known sample identifier |
| `POST /api/inspect` | Inspect a multipart `file` image |
| `GET /api/events` | Recent local inspection metadata |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/inspect \
  -F 'file=@/absolute/path/to/bottle.png' \
  -F 'source_id=upload'
```

The response contains `score`, `threshold`, `is_anomaly`, `heatmap`, `model_version`, timing, heatmap semantics, and event metadata. Optional `source_id` and `frame_id` values are limited to 1–64 letters, digits, underscores, periods, colons, or hyphens.

Inspection accepts PNG, JPEG, and WebP images up to **8 MiB**, **4 million decoded pixels**, a **4096-pixel maximum edge**, and a **32-pixel minimum edge**. The API admits one model inference at a time and returns HTTP `429` when model capacity is occupied. A missing model returns `503` for inspection. Event history retains at most **1000 metadata records** and does not retain uploaded image bytes. Treat a flag as a request for review; the score is not defect confidence.

## Camera and replay

The browser requests camera permission only when camera inspection is started. It samples at approximately 1.2-second intervals and waits for inference completion before another request. Stop the camera when inspection ends. Browser security typically allows camera access on localhost or HTTPS.

The detector expects a bottle view similar to the benchmark. A laptop camera pointed at an arbitrary room is outside its validated domain. The replay mode uses actual dataset images and is explicitly labeled; it is a demonstration of scoring known benchmark samples, not a live factory feed.

## Operational checks

Before a demo, verify model readiness, inspect one known sample, confirm the active source indicator, and check that event metadata appears. Run automated tests after changing the model interface or service.

The API bounds image upload size, decoded pixels, and concurrent work. It avoids arbitrary filesystem-path input and keeps runtime state out of source control. Do not load untrusted `.joblib` artifacts.

A public installation requires a reverse proxy with HTTPS, suitable authentication, request limits, retention controls, operational monitoring, and representative validation. Hardware camera triggers, item tracking, and rejection equipment are separate integrations. Benchmark latency does not establish end-to-end production throughput.

## Reports, notebook, and release files

The executed [walkthrough notebook](../notebooks/01_linesight_walkthrough.ipynb) and [technical report](../output/pdf/LineSight_Technical_Report.pdf) read recorded evidence rather than choosing a new model. Rebuild them with:

```bash
python -m pip install -e '.[notebook,report]'
python scripts/build_notebook.py
python scripts/build_report.py
```

The notebook builder executes through IPython in-process and saves cell outputs. This avoids requiring a network-connected kernel in constrained environments.

Run `python scripts/package_release.py --output ../deliverables` from a locally initialized Git checkout to produce the source archive, complete offline project archive, per-file release manifests, and archive SHA-256 checksums. The source archive excludes raw data, Git metadata, runtime databases, and ignored preview dependencies. The complete archive additionally includes original data and masks under their original noncommercial terms. Packaging performs no external push or publication.

Review [`reports/verification.json`](../reports/verification.json) for the check scope and any unverified surfaces. The recorded run passed 50 tests with zero skips and executed eight notebook code cells. The runtime dependency audit is a point-in-time check, not an ongoing security assessment.

## Updating the detector

Recreate manifests for new appropriately licensed data, preserve product/batch boundaries, and allocate new fit/tune/calibration/test roles. Fit the reference and forest on fit normals, select without using test labels, calibrate independently, then evaluate the frozen candidate. Retain the previous artifact and its report so that a model change can be compared and rolled back deliberately.
