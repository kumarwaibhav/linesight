#!/usr/bin/env python3
"""Package auditable GitHub source and a complete offline LineSight checkout.

Owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
Never pushes, uploads or creates an external repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def package(output: Path) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                            cwd=ROOT, check=True, capture_output=True)
    source = sorted({ROOT / value.decode() for value in result.stdout.split(b"\0") if value})
    source = [p for p in source if p.is_file() and not p.is_symlink() and not p.is_relative_to(output)]
    if not source or not (ROOT / "artifacts/linesight.joblib").is_file():
        raise RuntimeError("Expected a complete trained checkout")
    raw = sorted((ROOT / "data/raw").rglob("*"))
    raw = [p for p in raw if p.is_file() and not p.is_symlink()]
    if not raw:
        raise RuntimeError("Offline package requires verified raw dataset")
    outputs = []
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    for name, paths, description in [
        ("LineSight_GitHub_Ready.zip", source, "Source, frozen model, tests, documentation and results. Raw dataset excluded by Git ignore policy."),
        ("LineSight_Complete_Project.zip", source + raw, "Complete offline checkout including original MVTec bottle images, masks and license. Noncommercial dataset terms apply."),
    ]:
        manifest = {
            "project": "LineSight", "version": "1.0.0",
            "owner": "Kumar Waibhav Akshat", "email": "kwa.waibhav@gmail.com",
            "description": description, "git_commit": commit.stdout.strip() if commit.returncode == 0 else None,
            "git_metadata_included": False, "remote_created": False, "pushed": False, "published": False,
            "source_license": "MIT", "dataset_and_derived_material_license": "CC-BY-NC-SA-4.0",
            "files": [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)} for p in paths],
        }
        destination = output / name
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in paths:
                kind = zipfile.ZIP_STORED if path.suffix in {".png", ".jpg", ".joblib", ".pdf"} else zipfile.ZIP_DEFLATED
                archive.write(path, arcname="LineSight/" + path.relative_to(ROOT).as_posix(), compress_type=kind)
            archive.writestr("LineSight/RELEASE_MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        with zipfile.ZipFile(destination) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"Archive integrity error: {bad}")
        outputs.append({"path": str(destination), "bytes": destination.stat().st_size,
                        "sha256": digest(destination), "file_count": len(paths) + 1})
    (output / "SHA256SUMS.txt").write_text("".join(f"{item['sha256']}  {Path(item['path']).name}\n" for item in outputs))
    print(json.dumps(outputs, indent=2))
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "deliverables")
    args = parser.parse_args()
    package(args.output.resolve())
