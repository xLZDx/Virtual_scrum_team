"""pytest bootstrap for the VST control-plane tests: make `tools.vst` importable."""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.vst.s2_dispatch_instruction_fixtures import dispatch_instruction_keypair
