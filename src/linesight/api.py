"""LineSight's bounded, CPU-only inspection service.

Owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
The service records decisions; it never actuates production equipment.
"""
from __future__ import annotations

import asyncio
import csv
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
import math
import os
from pathlib import Path
import pickle
import re
import sqlite3
import threading
import time
from typing import Any, Iterator
import uuid
import warnings

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

LOGGER = logging.getLogger("linesight.api")
OWNER = {"name": "Kumar Waibhav Akshat", "email": "kwa.waibhav@gmail.com"}
MAX_IMAGE_BYTES = int(os.environ.get("LINESIGHT_MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
if not 0 < MAX_IMAGE_BYTES <= 8 * 1024 * 1024:
    raise ValueError("LINESIGHT_MAX_IMAGE_BYTES must be between 1 and 8388608.")
IMAGE_LIMIT_LABEL = f"{MAX_IMAGE_BYTES / (1024 * 1024):g} MiB"
MAX_REQUEST_BYTES = MAX_IMAGE_BYTES + 64 * 1024
MAX_IMAGE_PIXELS = 4_000_000
MAX_IMAGE_EDGE = 4096
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


class InspectionBodyLimit:
    """Bound request bytes before Starlette parses/spools multipart file content."""

    def __init__(self, app: Any, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.slots = asyncio.Semaphore(4)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("path") != "/api/inspect":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        raw_length = headers.get(b"content-length", b"")
        if raw_length:
            try:
                if int(raw_length) < 0:
                    raise ValueError
                if int(raw_length) > self.max_bytes:
                    await JSONResponse({"detail": f"Upload exceeds the {IMAGE_LIMIT_LABEL} image limit."}, 413)(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse({"detail": "Invalid Content-Length."}, 400)(scope, receive, send)
                return
        try:
            await asyncio.wait_for(self.slots.acquire(), timeout=0.05)
        except TimeoutError:
            await JSONResponse({"detail": "Inspection capacity is busy. Retry shortly."}, 429)(scope, receive, send)
            return
        try:
            chunks: list[bytes] = []
            total = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    continue
                body = message.get("body", b"")
                total += len(body)
                if total > self.max_bytes:
                    await JSONResponse({"detail": f"Upload exceeds the {IMAGE_LIMIT_LABEL} image limit."}, 413)(scope, receive, send)
                    return
                chunks.append(body)
                if not message.get("more_body", False):
                    break
            sent = False

            async def replay() -> dict:
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
                return await receive()

            await self.app(scope, replay, send)
        finally:
            self.slots.release()


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(path, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    try:
        with con:
            yield con
    finally:
        con.close()


def _prepare_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("""CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, source_id TEXT NOT NULL,
            frame_id TEXT, filename TEXT, score REAL NOT NULL, threshold REAL NOT NULL,
            is_anomaly INTEGER NOT NULL, model_version TEXT NOT NULL,
            inference_ms REAL NOT NULL, width INTEGER NOT NULL, height INTEGER NOT NULL
        )""")


def _save_event(path: Path, event: dict) -> None:
    with _connect(path) as con:
        con.execute(
            "INSERT INTO events (id,timestamp,source_id,frame_id,filename,score,threshold,is_anomaly,model_version,inference_ms,width,height) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(event[key] for key in (
                "id", "timestamp", "source_id", "frame_id", "filename", "score", "threshold",
                "is_anomaly", "model_version", "inference_ms", "width", "height"
            )),
        )
        con.execute("DELETE FROM events WHERE rowid NOT IN (SELECT rowid FROM events ORDER BY rowid DESC LIMIT 1000)")


def _read_json(paths: list[Path]) -> dict:
    for path in paths:
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    return value
            except (OSError, ValueError):
                LOGGER.warning("Could not read report %s", path.name)
    return {}


def _sample_index(root: Path, ready: bool) -> dict[str, dict]:
    manifest = root / "data" / "manifest.csv"
    if not ready or not manifest.is_file():
        return {}
    samples = {}
    with manifest.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("split") != "test":
                continue
            image_path = (root / row["path"]).resolve()
            if not image_path.is_relative_to(root.resolve()) or not image_path.is_file():
                continue
            sample_id = hashlib.sha256(row["path"].encode()).hexdigest()[:16]
            samples[sample_id] = {
                "id": sample_id, "filename": image_path.name,
                "defect_type": row.get("defect_type", "unknown"),
                "label": int(row.get("label", "0")), "path": image_path,
                "image_url": f"/api/samples/{sample_id}/image",
            }
    return samples


def decode_image(raw: bytes) -> Image.Image:
    """Validate actual decoder format and dimensions before full pixel allocation."""
    if not raw:
        raise HTTPException(400, "The image is empty.")
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"Image exceeds {IMAGE_LIMIT_LABEL}.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ALLOWED_FORMATS:
                    raise HTTPException(415, "Use a PNG, JPEG, or WebP image.")
                width, height = image.size
                if min(width, height) < 32:
                    raise HTTPException(422, "Image must be at least 32 × 32 pixels.")
                if width * height > MAX_IMAGE_PIXELS or max(width, height) > MAX_IMAGE_EDGE:
                    raise HTTPException(413, "Image exceeds 4 megapixels or a 4096-pixel edge.")
                image.load()
                return ImageOps.exif_transpose(image).convert("RGB")
    except HTTPException:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise HTTPException(413, "Image dimensions exceed the supported limit.") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise HTTPException(415, "The upload is not a readable PNG, JPEG, or WebP image.") from None


def create_app(
    root: str | Path | None = None,
    detector: Any | None = None,
    database_path: str | Path | None = None,
) -> FastAPI:
    project_root = Path(root or os.environ.get("LINESIGHT_ROOT") or Path(__file__).resolve().parents[2]).resolve()
    database = Path(database_path or os.environ.get("LINESIGHT_DB") or project_root / "runtime" / "events.sqlite3")
    model_path = Path(os.environ.get("LINESIGHT_MODEL", str(project_root / "artifacts" / "linesight.joblib")))
    loaded_detector = detector
    load_error = None
    if loaded_detector is None and model_path.is_file():
        try:
            from .model import Detector
            loaded_detector = Detector.load(model_path)
        except (OSError, ValueError, ImportError, EOFError, RuntimeError, TypeError, AttributeError, pickle.UnpicklingError) as error:
            LOGGER.exception("Model load failed")
            load_error = type(error).__name__
    _prepare_database(database)
    inference_lock = threading.Lock()
    app = FastAPI(
        title="LineSight Inspection API", version="1.0.0", docs_url=None, redoc_url=None,
        description="CPU visual anomaly detection using Isolation Forest. Score is not a probability.",
        contact=OWNER,
    )
    app.add_middleware(InspectionBodyLimit)
    app.state.detector = loaded_detector
    app.state.database = database
    app.state.root = project_root

    @app.middleware("http")
    async def security_headers(request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
            "connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ready" if loaded_detector is not None else "unready",
                "model_loaded": loaded_detector is not None, "model_error": load_error,
                "service": "LineSight", "version": "1.0.0"}

    @app.get("/api/model")
    def model_info() -> dict:
        metadata = getattr(loaded_detector, "metadata", {}) or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "name": "LineSight", "owner": OWNER, "ready": loaded_detector is not None,
            "max_image_bytes": MAX_IMAGE_BYTES,
            "history_mode": os.environ.get("LINESIGHT_HISTORY_MODE", "local"),
            "algorithm": "Isolation Forest", "category": "MVTec AD · bottle",
            "model_version": getattr(loaded_detector, "model_version", metadata.get("model_version")),
            "threshold": getattr(loaded_detector, "threshold", metadata.get("threshold")),
            "score_semantics": "Higher means more anomalous. This is not a probability.",
            "heatmap_semantics": "Coarse patch evidence, not a validated segmentation mask.",
            "deployment_scope": "Research demonstration; camera sampling is not a validated factory line integration.",
        }

    @app.get("/api/metrics")
    def metrics() -> dict:
        report = _read_json([
            project_root / "reports" / "metrics.json", project_root / "reports" / "evaluation.json",
            project_root / "reports" / "evaluation" / "metrics.json",
        ])
        return {"available": bool(report), "report": report}

    @app.get("/api/samples")
    def samples() -> dict:
        index = _sample_index(project_root, loaded_detector is not None)
        return {"mode": "held-out dataset replay", "count": len(index),
                "samples": [{key: value for key, value in row.items() if key != "path"} for row in index.values()]}

    @app.get("/api/samples/{sample_id}/image")
    def sample_image(sample_id: str) -> Any:
        sample = _sample_index(project_root, loaded_detector is not None).get(sample_id)
        if sample is None:
            raise HTTPException(404, "Unknown sample.")
        return FileResponse(sample["path"], media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

    @app.get("/api/events")
    def events(limit: int = Query(30, ge=1, le=100)) -> dict:
        with _connect(database) as con:
            rows = [dict(row) for row in con.execute("SELECT * FROM events ORDER BY rowid DESC LIMIT ?", (limit,))]
            total, alerts = con.execute("SELECT COUNT(*), COALESCE(SUM(is_anomaly),0) FROM events").fetchone()
        for row in rows:
            row["is_anomaly"] = bool(row["is_anomaly"])
        return {"events": rows, "retained_total": total, "retained_alerts": alerts, "retention_limit": 1000}

    def inspect_locked(image: Image.Image) -> tuple[dict, float]:
        if not inference_lock.acquire(timeout=0.05):
            raise HTTPException(429, "Detector is busy. Send one frame at a time.")
        try:
            started = time.perf_counter()
            result = loaded_detector.inspect(image)
            elapsed = (time.perf_counter() - started) * 1000
            for key in ("score", "threshold"):
                if not math.isfinite(float(result[key])):
                    raise ValueError("Non-finite model output")
            return result, elapsed
        finally:
            inference_lock.release()

    @app.post("/api/inspect")
    async def inspect(
        file: UploadFile = File(...), source_id: str = Form("upload"), frame_id: str | None = Form(None),
    ) -> dict:
        if loaded_detector is None:
            raise HTTPException(503, "Model unavailable. Train the model, then restart the service.")
        if not IDENTIFIER.fullmatch(source_id) or (frame_id is not None and not IDENTIFIER.fullmatch(frame_id)):
            raise HTTPException(422, "source_id and frame_id must use 1–64 letters, digits, dots, colons, underscores, or hyphens.")
        raw = await file.read(MAX_IMAGE_BYTES + 1)
        await file.close()
        image = decode_image(raw)
        try:
            result, elapsed = await run_in_threadpool(inspect_locked, image)
        except HTTPException:
            raise
        except (ValueError, RuntimeError, TypeError, KeyError) as error:
            LOGGER.exception("Model inspection failed: %s", type(error).__name__)
            raise HTTPException(500, "Inspection failed. Check server logs.") from None
        event = {
            "id": uuid.uuid4().hex, "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_id": source_id, "frame_id": frame_id, "filename": Path(file.filename or "image").name[:128],
            "score": float(result["score"]), "threshold": float(result["threshold"]),
            "is_anomaly": bool(result["is_anomaly"]), "model_version": str(result["model_version"]),
            "inference_ms": round(elapsed, 3), "width": image.width, "height": image.height,
        }
        await run_in_threadpool(_save_event, database, event)
        return {**result, **event, "heatmap_note": "Coarse patch evidence, not a validated segmentation mask."}

    web_root = project_root / "web"
    if web_root.is_dir():
        app.mount("/assets", StaticFiles(directory=web_root), name="assets")

        @app.get("/docs", include_in_schema=False)
        def api_reference() -> FileResponse:
            return FileResponse(web_root / "api.html")

        @app.get("/", include_in_schema=False)
        def dashboard() -> FileResponse:
            return FileResponse(web_root / "index.html")
    return app
