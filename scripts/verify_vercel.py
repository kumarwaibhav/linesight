"""Compare all 83 replay inspections with the frozen evaluation, locally.

Install the project's dev dependencies first. This exercises the Vercel
entrypoint through ASGI; it does not deploy to Vercel or claim cloud validation.
Owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
"""
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import os
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    started = time.perf_counter()
    original_tmp = os.environ.get("TMPDIR")
    original_cache = tempfile.tempdir
    predictions = []
    baseline = list(csv.DictReader((ROOT / "reports" / "test_predictions.csv").open(newline="")))
    assert len(baseline) == 83
    with tempfile.TemporaryDirectory(prefix="linesight-vercel-check-") as temporary:
        os.environ["TMPDIR"] = temporary
        tempfile.tempdir = None
        try:
            sys.path.insert(0, str(ROOT))
            from app import app
            from fastapi.testclient import TestClient

            with TestClient(app) as client:
                assert client.get("/api/health").json()["model_loaded"] is True
                assert client.get("/").status_code == 200
                assert client.get("/assets/app.js").status_code == 200
                samples = client.get("/api/samples").json()
                assert samples["count"] == 83
                index = {(row["defect_type"], row["filename"]): row for row in samples["samples"]}
                for row in baseline:
                    sample = index[(row["defect_type"], Path(row["path"]).name)]
                    image = client.get(sample["image_url"])
                    assert image.status_code == 200
                    response = client.post("/api/inspect",
                        files={"file": (sample["filename"], image.content, "image/png")},
                        data={"source_id": "vercel-verification", "frame_id": sample["id"]})
                    assert response.status_code == 200, response.text
                    result = response.json()
                    delta = abs(result["score"] - float(row["score"]))
                    assert delta <= 1e-12, (row["path"], delta)
                    assert result["threshold"] == float(row["threshold"])
                    assert result["is_anomaly"] == (row["is_anomaly"] == "True")
                    predictions.append({"path": row["path"], "label": int(row["label"]),
                        "score": result["score"], "baseline_score": float(row["score"]),
                        "absolute_delta": delta, "is_anomaly": result["is_anomaly"],
                        "model_version": result["model_version"], "inference_ms": result["inference_ms"]})
                assert client.get("/api/events").json()["retained_total"] == 83
        finally:
            if original_tmp is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = original_tmp
            tempfile.tempdir = original_cache
    artifact_sha = hashlib.sha256((ROOT / "artifacts" / "linesight.joblib").read_bytes()).hexdigest()
    metrics = json.loads((ROOT / "reports" / "metrics.json").read_text())
    assert artifact_sha == metrics["artifact_sha256"]
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_mib = peak / (1024 * 1024 if sys.platform == "darwin" else 1024)
    except ImportError:
        peak_mib = None
    tests = None
    junit = ROOT / "reports" / "vercel-tests.xml"
    if junit.is_file():
        suites = list(ET.parse(junit).getroot().iter("testsuite"))
        tests = {key: sum(int(s.get(key, "0")) for s in suites)
                 for key in ("tests", "failures", "errors", "skipped")}
    tn = sum(p["label"] == 0 and not p["is_anomaly"] for p in predictions)
    fp = sum(p["label"] == 0 and p["is_anomaly"] for p in predictions)
    fn = sum(p["label"] == 1 and not p["is_anomaly"] for p in predictions)
    tp = sum(p["label"] == 1 and p["is_anomaly"] for p in predictions)
    summary = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "owner": {"name": "Kumar Waibhav Akshat", "email": "kwa.waibhav@gmail.com"},
        "scope": "Local ASGI verification of the Vercel entrypoint after deployment preparation",
        "cloud_deployment_verified": False,
        "model_retrained": False,
        "model_version": metrics["model_version"],
        "artifact_sha256": artifact_sha,
        "artifact_unchanged": True,
        "tests": tests,
        "replay_images": len(predictions),
        "scores_match_frozen_evaluation": True,
        "maximum_absolute_score_difference": max(p["absolute_delta"] for p in predictions),
        "confusion_matrix": [[tn, fp], [fn, tp]],
        "upload_limit_bytes": 4 * 1024 * 1024,
        "storage": "temporary per-instance SQLite; no durable shared history",
        "peak_process_memory_mib": peak_mib,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "limitations": ["A real Vercel build and live-domain checks are still required.",
                        "Local process memory is not a measurement of Vercel runtime overhead."]
    }
    with (ROOT / "reports" / "vercel-predictions.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)
    (ROOT / "reports" / "vercel-validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
