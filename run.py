#!/usr/bin/env python3
"""Cross-platform launcher for the Chainlit app.

Works identically on Linux, macOS, and Windows:

    python run.py            # start the chat UI on http://localhost:8000
    PORT=8600 python run.py  # custom port (or set PORT in the environment)

This simply shells out to Chainlit via the current interpreter, so no shell
script is required on any OS.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    port = os.environ.get("PORT", "8000")
    cmd = [
        sys.executable,
        "-m",
        "chainlit",
        "run",
        str(ROOT / "app.py"),
        "--port",
        port,
    ]
    if "--watch" in sys.argv:
        cmd.append("-w")
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
