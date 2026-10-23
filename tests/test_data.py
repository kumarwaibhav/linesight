"""Dataset lineage and archive-boundary tests. No network requests are made."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import tarfile
from collections import Counter
from pathlib import Path

import pytest
from PIL import Image

from linesight.training import load_images, read_manifest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("download_data", ROOT / "scripts/download_data.py")
DOWNLOAD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DOWNLOAD)


def _archive(path: Path, name: str, kind: bytes = tarfile.REGTYPE) -> None:
    with tarfile.open(path, "w:xz") as archive:
        member = tarfile.TarInfo(name)
        member.type = kind
        if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            member.linkname = "/tmp/linesight-untrusted-link-target"
            archive.addfile(member)
        else:
            member.size = 4
            archive.addfile(member, io.BytesIO(b"safe"))


@pytest.mark.parametrize("name,kind", [
    ("../escaped.txt", tarfile.REGTYPE),
    ("/tmp/linesight-escaped.txt", tarfile.REGTYPE),
    ("bottle/link", tarfile.SYMTYPE),
    ("bottle/hardlink", tarfile.LNKTYPE),
])
def test_untrusted_archive_members_cannot_escape_or_link(tmp_path, name, kind):
    archive = tmp_path / "untrusted.tar.xz"
    _archive(archive, name, kind)
    with pytest.raises(ValueError, match="Unsafe archive member"):
        DOWNLOAD.extract_checked(archive, tmp_path / "destination")
    assert not (tmp_path / "escaped.txt").exists()


def test_safe_archive_extracts_exact_bytes(tmp_path):
    archive = tmp_path / "safe.tar.xz"
    _archive(archive, "bottle/train/good/example.png")
    destination = tmp_path / "destination"
    DOWNLOAD.extract_checked(archive, destination)
    assert (destination / "bottle/train/good/example.png").read_bytes() == b"safe"


def test_committed_manifest_preserves_official_test_and_normal_development():
    rows = read_manifest(ROOT)
    assert Counter(row["split"] for row in rows) == {
        "fit": 125, "tune": 42, "calibration": 42, "test": 83,
    }
    assert len({row["sha256"] for row in rows}) == 292
    assert len({row["path"] for row in rows}) == 292
    for row in rows:
        relative = Path(row["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        if row["split"] == "test":
            assert "/test/" in row["path"]
        else:
            assert "/train/good/" in row["path"] and row["label"] == "0"
    assert Counter(row["defect_type"] for row in rows if row["split"] == "test") == {
        "good": 20, "broken_large": 20, "broken_small": 22, "contamination": 21,
    }
    provenance = json.loads((ROOT / "data/provenance.json").read_text())
    assert provenance["manifest_sha256"] == hashlib.sha256((ROOT / "data/manifest.csv").read_bytes()).hexdigest()


def test_available_raw_data_match_every_manifest_digest():
    rows = read_manifest(ROOT)
    if not (ROOT / rows[0]["path"]).exists():
        pytest.skip("Raw dataset is intentionally absent from Git source; run download_data.py for full audit")
    for row in rows:
        path = ROOT / row["path"]
        assert path.is_file()
        assert DOWNLOAD.sha256(path) == row["sha256"], row["path"]
        if row["label"] == "1":
            assert (ROOT / row["mask_path"]).is_file()
    masks = json.loads((ROOT / "data/mask_checksums.json").read_text())
    assert len(masks) == 63
    assert all(DOWNLOAD.sha256(ROOT / row["path"]) == row["sha256"] for row in masks)


def _write_manifest(root: Path, rows: list[dict]) -> None:
    (root / "data").mkdir()
    with (root / "data/manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "split", "label", "sha256"])
        writer.writeheader()
        writer.writerows(rows)


def test_manifest_refuses_anomalies_in_development_and_duplicate_bytes(tmp_path):
    row = {"path": "data/normal.png", "split": "tune", "label": "1", "sha256": "a" * 64}
    _write_manifest(tmp_path, [row])
    with pytest.raises(ValueError, match="nominal"):
        read_manifest(tmp_path)
    row["label"] = "0"
    with (tmp_path / "data/manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerows([row, {**row, "path": "data/copy.png", "split": "test"}])
    with pytest.raises(ValueError, match="Duplicate"):
        read_manifest(tmp_path)


def test_training_rejects_mutated_data_and_manifest_path_traversal(tmp_path):
    image_path = tmp_path / "nominal.png"
    Image.new("RGB", (32, 32), "white").save(image_path)
    expected = hashlib.sha256(image_path.read_bytes()).hexdigest()
    Image.new("RGB", (32, 32), "black").save(image_path)
    with pytest.raises(ValueError, match="digest mismatch"):
        load_images(tmp_path, [{"path": "nominal.png", "sha256": expected}])
    with pytest.raises(ValueError, match="escapes"):
        load_images(tmp_path, [{"path": "../outside.png", "sha256": expected}])
