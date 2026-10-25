"""Check the actual Vercel entrypoint with the frozen model in a clean process."""
from pathlib import Path
import os
import subprocess
import sys


def test_vercel_entrypoint_loads_model_and_uses_temporary_storage(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, TMPDIR=str(tmp_path), LINESIGHT_ROOT="/nonexistent/readonly",
               LINESIGHT_DB="/nonexistent/readonly/events.sqlite3")
    code = '''
import io
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
from PIL import Image
from app import app, ROOT

with TestClient(app) as client:
    assert app.state.root == ROOT
    assert app.state.database.parent == Path(tempfile.gettempdir()) / "linesight"
    assert client.get("/api/health").json()["model_loaded"] is True
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/docs").status_code == 200
    model = client.get("/api/model").json()
    assert model["max_image_bytes"] == 4 * 1024 * 1024
    assert model["history_mode"] == "temporary"
    assert model["owner"]["email"] == "kwa.waibhav@gmail.com"
    image = ROOT / "data/raw/bottle/test/good/000.png"
    if image.is_file():
        raw = image.read_bytes()
    else:
        output = io.BytesIO()
        Image.new("RGB", (64, 64), (100, 110, 120)).save(output, format="PNG")
        raw = output.getvalue()
    response = client.post("/api/inspect", files={"file": ("probe.png", raw, "image/png")})
    assert response.status_code == 200, response.text
    assert response.json()["model_version"] == model["model_version"]
    assert response.json()["heatmap"]
    assert client.get("/api/events").json()["retained_total"] == 1
    too_large = b"x" * (4 * 1024 * 1024 + 1)
    rejected = client.post("/api/inspect", files={"file": ("large.png", too_large, "image/png")})
    assert rejected.status_code == 413
    assert "4 MiB" in rejected.json()["detail"]
    assert client.get("/api/events").json()["retained_total"] == 1
print("Vercel entrypoint: model, dashboard, inference, history and 4 MiB boundary passed.")
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
