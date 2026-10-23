"""Service contracts, image boundaries and retained decision records."""
from __future__ import annotations

import asyncio
import csv
import io
from pathlib import Path
import time

from fastapi.testclient import TestClient
import httpx
from PIL import Image
import pytest

from linesight.api import MAX_REQUEST_BYTES, _save_event, create_app

ROOT = Path(__file__).resolve().parents[1]


class StubDetector:
    threshold = 0.55
    model_version = "test-frozen"
    metadata = {}

    def inspect(self, image):
        return {"score": 0.62, "threshold": self.threshold, "is_anomaly": True,
                "heatmap": [[0.4, 0.6], [0.5, 0.7]], "model_version": self.model_version}


def image_bytes(size=(64, 64), format="PNG"):
    data = io.BytesIO()
    Image.new("RGB", size, (100, 110, 120)).save(data, format=format)
    return data.getvalue()


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(root=tmp_path, detector=StubDetector()))


def test_missing_model_is_explicit_unready_and_inspection503(tmp_path):
    client = TestClient(create_app(root=tmp_path))
    assert client.get("/api/health").json()["model_loaded"] is False
    assert client.get("/api/model").json()["threshold"] is None
    response = client.post("/api/inspect", files={"file": ("sample.png", image_bytes(), "image/png")})
    assert response.status_code == 503
    assert client.get("/api/samples").json()["samples"] == []


def test_corrupt_trusted_artifact_reports_unready_instead_of_crashing(tmp_path):
    artifact = tmp_path / "artifacts" / "linesight.joblib"
    artifact.parent.mkdir()
    artifact.write_bytes(b"\x80\x04invalid_pickle_stream")
    client = TestClient(create_app(root=tmp_path))
    health = client.get("/api/health").json()
    assert health["status"] == "unready"
    assert health["model_error"]


def test_inspection_is_logged_with_inference_and_model_contract(client):
    response = client.post("/api/inspect", files={"file": ("sample.png", image_bytes(), "image/png")},
                           data={"source_id": "unit-test", "frame_id": "frame-001"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["score"] > result["threshold"]
    assert result["is_anomaly"] is True
    assert result["model_version"] == "test-frozen"
    assert result["width"] == 64
    assert result["height"] == 64
    assert result["inference_ms"] >= 0
    events = client.get("/api/events").json()
    assert events["retained_total"] == 1
    assert events["retained_alerts"] == 1
    assert events["events"][0]["id"] == result["id"]
    assert events["events"][0]["frame_id"] == "frame-001"
    assert events["events"][0]["is_anomaly"] is True
    assert "heatmap" not in events["events"][0]


@pytest.mark.parametrize("content,filename,status", [
    (b"", "empty.png", 400),
    (b"not an image", "fake.png", 415),
    (b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "image.svg", 415),
    (image_bytes(format="GIF"), "image.gif", 415),
    (image_bytes(size=(12, 50)), "tiny.png", 422),
    (image_bytes(size=(2100, 2100)), "large.png", 413),
    (image_bytes(size=(4100, 32)), "long.png", 413),
])
def test_actual_decoder_and_image_dimensions_are_checked(client, content, filename, status):
    response = client.post("/api/inspect", files={"file": (filename, content, "image/png")})
    assert response.status_code == status
    assert client.get("/api/events").json()["retained_total"] == 0


@pytest.mark.parametrize("format,filename", [("PNG", "p.png"), ("JPEG", "p.jpg"), ("WEBP", "p.webp")])
def test_supported_decoders_accept_images_regardless_of_spoofed_mime(client, format, filename):
    response = client.post("/api/inspect", files={"file": (filename, image_bytes(format=format), "application/octet-stream")})
    assert response.status_code == 200


def test_upload_body_rejected_before_multipart_decode(client):
    response = client.post("/api/inspect", content=b"x" * (MAX_REQUEST_BYTES + 1), headers={"Content-Type": "application/octet-stream"})
    assert response.status_code == 413
    assert client.get("/api/events").json()["retained_total"] == 0


def test_chunked_request_cannot_bypass_body_limit(tmp_path):
    app = create_app(root=tmp_path, detector=StubDetector())
    async def send_request():
        async def chunks():
            yield b"x" * (MAX_REQUEST_BYTES // 2)
            yield b"x" * (MAX_REQUEST_BYTES // 2 + 2)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.post("/api/inspect", content=chunks(), headers={"Content-Type": "application/octet-stream"})
    assert asyncio.run(send_request()).status_code == 413


def test_bad_identifiers_and_unbounded_event_queries_are_rejected(client):
    response = client.post("/api/inspect", files={"file": ("ok.png", image_bytes(), "image/png")}, data={"source_id": "<script>alert(1)</script>"})
    assert response.status_code == 422
    assert client.get("/api/events?limit=101").status_code == 422
    assert client.get("/api/events?limit=0").status_code == 422


def test_unknown_and_traversal_sample_ids_do_not_expose_files(client):
    assert client.get("/api/samples/unknown/image").status_code == 404
    assert client.get("/api/samples/%2e%2e%2f%2e%2e%2fetc%2fpasswd/image").status_code == 404


def test_manifest_sample_is_only_served_by_resolved_identifier(tmp_path):
    image = tmp_path / "data" / "bottle" / "test" / "good" / "001.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(image_bytes())
    manifest = tmp_path / "data" / "manifest.csv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "split", "label", "defect_type", "sha256", "mask_path"])
        writer.writeheader()
        writer.writerow({"path": str(image.relative_to(tmp_path)), "split": "test", "label": 0, "defect_type": "good"})
        writer.writerow({"path": "/etc/passwd", "split": "test", "label": 1, "defect_type": "unsafe"})
    client = TestClient(create_app(root=tmp_path, detector=StubDetector()))
    listing = client.get("/api/samples").json()
    assert listing["count"] == 1
    sample = listing["samples"][0]
    assert "path" not in sample
    assert client.get(sample["image_url"]).content == image_bytes()


def test_event_retention_is_bounded_and_most_recent_first(tmp_path):
    app = create_app(root=tmp_path, detector=StubDetector())
    event = {"id": "", "timestamp": "2026-10-22T00:00:00+00:00", "source_id": "test", "frame_id": None,
             "filename": "image.png", "score": 0.6, "threshold": 0.55, "is_anomaly": True,
             "model_version": "test", "inference_ms": 1.2, "width": 64, "height": 64}
    for index in range(1002):
        _save_event(app.state.database, {**event, "id": str(index)})
    response = TestClient(app).get("/api/events?limit=2").json()
    assert response["retained_total"] == 1000
    assert [row["id"] for row in response["events"]] == ["1001", "1000"]


def test_concurrent_inference_is_bounded_with_retry_response(tmp_path):
    class SlowDetector(StubDetector):
        def inspect(self, image):
            time.sleep(0.2)
            return super().inspect(image)
    app = create_app(root=tmp_path, detector=SlowDetector())
    async def send_requests():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await asyncio.gather(*[
                client.post("/api/inspect", files={"file": ("frame.png", image_bytes(), "image/png")}) for _ in range(2)
            ])
    responses = asyncio.run(send_requests())
    assert sorted(response.status_code for response in responses) == [200, 429]


def test_self_hosted_dashboard_and_api_reference_obey_csp(tmp_path):
    app = create_app(root=ROOT, detector=StubDetector(), database_path=tmp_path / "events.sqlite3")
    client = TestClient(app)
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "script-src 'self'" in dashboard.headers["content-security-policy"]
    assert dashboard.headers["x-content-type-options"] == "nosniff"
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "cdn.jsdelivr.net" not in docs.text
    assert '<script src="/assets/api-docs.js"' in docs.text
    assert client.get("/assets/api-docs.js").status_code == 200
    assert "/api/inspect" in client.get("/openapi.json").json()["paths"]


def test_real_model_can_inspect_one_held_out_image(tmp_path):
    artifact = ROOT / "artifacts" / "linesight.joblib"
    manifest = ROOT / "data" / "manifest.csv"
    if not artifact.exists() or not manifest.exists():
        pytest.skip("Run training pipeline to generate real model and data")
    client = TestClient(create_app(root=ROOT, database_path=tmp_path / "events.sqlite3"))
    assert client.get("/api/health").json()["model_loaded"] is True
    sample = client.get("/api/samples").json()["samples"][0]
    raw = client.get(sample["image_url"]).content
    result = client.post("/api/inspect", files={"file": (sample["filename"], raw, "image/png")})
    assert result.status_code == 200
    body = result.json()
    assert body["score_is_probability"] is False
    assert len(body["heatmap"]) == 12
    assert body["is_anomaly"] == (body["score"] > body["threshold"])
