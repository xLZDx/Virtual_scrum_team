#!/usr/bin/env python3.12
"""Repository entry point for the immutable S2 bootstrap selector."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.dont_write_bytecode = True
from tools.vst.bootstrap_runtime import main


if __name__ == "__main__":
    raise SystemExit(main())
