"""Emit one bounded in-memory runtime observation from the isolated worker."""

from __future__ import annotations

import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, "/opt/vst-runtime")

from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst.preflight import collect_inventory


def main() -> int:
    if os.geteuid() != 999 or os.getegid() != 989:
        raise ContractError("preflight must run as the configured isolated worker identity")
    inventory = collect_inventory()
    print(canonical_bytes(inventory).decode("ascii"), flush=True)
    return 0 if inventory["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
