"""Prepare verified sample replay for Vercel without training a model.

Owner: Kumar Waibhav Akshat <kwa.waibhav@gmail.com>.
Only the 83 held-out bottle images are retained in the function bundle.
Training and mask files can always be acquired again with download_data.py.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if not (ROOT / "artifacts" / "linesight.joblib").is_file():
        raise SystemExit("Missing artifacts/linesight.joblib. Commit the trained artifact before deploying.")
    if os.environ.get("LINESIGHT_INCLUDE_SAMPLES", "1") != "0":
        subprocess.run([sys.executable, str(ROOT / "scripts" / "download_data.py")], cwd=ROOT, check=True)
        count = len(list((ROOT / "data" / "raw" / "bottle" / "test").glob("*/*.png")))
        if count != 83:
            raise SystemExit(f"Expected 83 replay images, found {count}.")
        print(f"Keeping {count} verified held-out images for replay.", flush=True)
    else:
        shutil.rmtree(ROOT / "data" / "raw" / "bottle" / "test", ignore_errors=True)
        print("Replay samples disabled; uploaded-image inference remains available.", flush=True)
    for relative in ("data/cache", "data/raw/bottle/train", "data/raw/bottle/ground_truth"):
        shutil.rmtree(ROOT / relative, ignore_errors=True)
    print("Vercel preparation complete. The frozen model was not retrained.", flush=True)


if __name__ == "__main__":
    main()
