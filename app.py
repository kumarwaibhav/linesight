"""Vercel entrypoint. Kumar Waibhav Akshat <kwa.waibhav@gmail.com>."""
from pathlib import Path
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
os.environ["LINESIGHT_ROOT"] = str(ROOT)
os.environ["LINESIGHT_DB"] = str(Path(tempfile.gettempdir()) / "linesight" / "events.sqlite3")
os.environ["LINESIGHT_MAX_IMAGE_BYTES"] = str(4 * 1024 * 1024)
os.environ["LINESIGHT_HISTORY_MODE"] = "temporary"
for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
sys.path.insert(0, str(ROOT / "src"))

from linesight.api import create_app  # noqa: E402

app = create_app()
