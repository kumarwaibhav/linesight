#!/usr/bin/env python3
"""Acquire a pinned MVTec AD bottle mirror and write an audited split manifest.

Owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
Raw images retain the MVTec CC BY-NC-SA 4.0 license.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import tarfile
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REVISION = "dc1c313de9de1be8e41fe6818dc43caac8601efa"
URL = f"https://huggingface.co/datasets/XavierZXY/MvT-tar/resolve/{REVISION}/bottle.tar.xz"
ARCHIVE_SHA256 = "726512129cb3b1f47d4f6cd7c7fc9170db7fc209132249c788fec06029cb5dc3"
EXPECTED = {"train/good": 209, "test/good": 20, "test/broken_large": 20,
            "test/broken_small": 22, "test/contamination": 21}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_checked(archive: Path, destination: Path) -> None:
    """Reject links, path traversal, unexpected layout, and extraction bombs."""
    destination = destination.resolve()
    with tarfile.open(archive, "r:xz") as handle:
        members = handle.getmembers()
        if len(members) > 500 or sum(m.size for m in members) > 250_000_000:
            raise ValueError("Archive exceeds expected bottle dataset bounds")
        for member in members:
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination) or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsafe archive member: {member.name}")
        handle.extractall(destination, members=members, filter="data")


def build_manifest(root: Path, source_description: str) -> dict:
    bottle = root / "data/raw/bottle"
    actual = {folder: len(list((bottle / folder).glob("*.png"))) for folder in EXPECTED}
    if actual != EXPECTED:
        raise ValueError(f"Unexpected dataset structure: {actual}; expected {EXPECTED}")
    normals = sorted((bottle / "train/good").glob("*.png"))
    random.Random(42).shuffle(normals)
    role = {p: "fit" if i < 125 else "tune" if i < 167 else "calibration"
            for i, p in enumerate(normals)}
    rows = []
    hashes: set[str] = set()
    for path in sorted(list((bottle / "train").glob("*/*.png")) +
                       list((bottle / "test").glob("*/*.png"))):
        with Image.open(path) as image:
            if image.size != (900, 900):
                raise ValueError(f"Unexpected image dimensions: {path} {image.size}")
            image.verify()
        digest = sha256(path)
        if digest in hashes:
            raise ValueError(f"Duplicate image bytes detected: {path}")
        hashes.add(digest)
        defect = path.parent.name
        mask = bottle / "ground_truth" / defect / f"{path.stem}_mask.png"
        if defect != "good":
            if not mask.is_file():
                raise ValueError(f"Missing defect mask: {mask}")
            with Image.open(mask) as image:
                image.verify()
        rows.append({"path": path.relative_to(root).as_posix(),
                     "split": role.get(path, "test"), "label": int(defect != "good"),
                     "defect_type": defect, "sha256": digest,
                     "mask_path": mask.relative_to(root).as_posix() if defect != "good" else ""})
    manifest = root / "data/manifest.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    mask_rows = [{"path": p.relative_to(root).as_posix(), "sha256": sha256(p)}
                 for p in sorted((bottle / "ground_truth").glob("*/*.png"))]
    (root / "data/mask_checksums.json").write_text(json.dumps(mask_rows, indent=2) + "\n")
    summary = {
        "dataset": "MVTec AD", "category": "bottle", "seed": 42,
        "owner": "MVTec Software GmbH and original authors",
        "project_owner": "Kumar Waibhav Akshat <kwa.waibhav@gmail.com>",
        "official_source": "https://www.mvtec.com/research-teaching/datasets/mvtec-ad",
        "license": "CC-BY-NC-SA-4.0",
        "license_url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "acquisition": source_description, "mirror_url": URL,
        "mirror_revision": REVISION, "archive_sha256": ARCHIVE_SHA256,
        "verification_scope": "Pinned mirror hash and structural counts verified; not independently compared byte-for-byte with an official download.",
        "image_count": len(rows), "mask_count": len(mask_rows),
        "split_counts": dict(Counter(row["split"] for row in rows)),
        "official_counts": actual, "manifest_sha256": sha256(manifest),
        "duplicate_image_hashes": 0,
        "split_policy": "Official train normals -> fit125/tune42/calibration42. Official test83 untouched for selection. Tune synthetic variants never leave tune role.",
    }
    (root / "data/provenance.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Existing bottle directory with train/test/ground_truth")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing raw data and regenerate manifest")
    args = parser.parse_args()
    bottle = ROOT / "data/raw/bottle"
    description = "Pinned public Hugging Face archive mirror of MVTec AD bottle"
    if args.source:
        source = args.source.expanduser().resolve()
        if source != bottle.resolve():
            if bottle.exists():
                raise SystemExit("Raw destination already exists; use --verify-only or a clean checkout")
            shutil.copytree(source, bottle)
        description = "User-supplied local bottle directory; per-file SHA256 manifest recorded"
    elif not args.verify_only and not (bottle / "train/good").is_dir():
        cache = ROOT / "data/cache"
        cache.mkdir(parents=True, exist_ok=True)
        archive = cache / "bottle.tar.xz"
        if not archive.exists() or sha256(archive) != ARCHIVE_SHA256:
            partial = cache / "bottle.tar.xz.part"
            request = urllib.request.Request(URL, headers={"User-Agent": "LineSight/1.0 educational-research"})
            print("Downloading pinned bottle archive (~156 MB)...", flush=True)
            with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
                transferred = 0
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    transferred += len(chunk)
                    if transferred % (25 * 1024 * 1024) == 0:
                        print(f"Downloaded {transferred // (1024 * 1024)} MiB", flush=True)
            if sha256(partial) != ARCHIVE_SHA256:
                partial.unlink(missing_ok=True)
                raise SystemExit("Archive checksum mismatch; no data were extracted")
            partial.replace(archive)
        with tempfile.TemporaryDirectory(prefix="linesight-data-") as temporary:
            unpacked = Path(temporary)
            extract_checked(archive, unpacked)
            candidates = [p.parent.parent for p in unpacked.rglob("train/good")]
            if len(candidates) != 1:
                raise SystemExit("Archive does not contain exactly one bottle dataset")
            bottle.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(candidates[0], bottle, dirs_exist_ok=True)
    build_manifest(ROOT, description)


if __name__ == "__main__":
    main()
