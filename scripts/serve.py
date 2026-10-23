"""Serve LineSight locally: python scripts/serve.py --port 8000."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def main() -> None:
    import uvicorn
    parser = argparse.ArgumentParser(description="LineSight local inspection dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Use 0.0.0.0 only behind a trusted network boundary")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    uvicorn.run("linesight.api:create_app", factory=True, host=arguments.host, port=arguments.port, workers=1)


if __name__ == "__main__":
    main()
