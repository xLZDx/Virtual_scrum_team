"""Retired detached probe-capture entrypoint.

S2 runtime observations are now executed once inside the Supervisor service and
consumed in memory through the Store replay binding. This module intentionally
accepts no request, attestation, key, or output-file arguments.
"""
from __future__ import annotations

import sys


def run_probe(*_args, **_kwargs):
    raise RuntimeError(
        "detached probe capture is retired; use the Supervisor-owned in-memory runtime observation"
    )


def main(argv: list[str] | None = None) -> int:
    del argv
    print("detached probe capture is retired", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
