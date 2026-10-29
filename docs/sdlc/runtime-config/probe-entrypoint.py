"""Run the existing non-root preflight after root publishes measured policy evidence."""

from __future__ import annotations

import os
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, "/opt/vst-runtime")

from tools.vst.contracts import ContractError, canonical_bytes
from tools.vst.preflight import collect_inventory
from tools.vst.runner_service import _read_root_controlled_json

REQUEST_PATH = "/etc/vst-runner/probe-request.json"
ATTESTATION_PATH = "/run/vst-preflight/network-policy-attestation.json"


def main() -> int:
    if os.geteuid() != 999 or os.getegid() != 989:
        raise ContractError("preflight must run as the configured isolated worker identity")
    request = _read_root_controlled_json(REQUEST_PATH, max_bytes=65536)
    if set(request) != {"run_id", "nonce"}:
        raise ContractError("preflight request fields do not match the configured run binding")
    deadline = time.monotonic() + 60
    while not os.path.lexists(ATTESTATION_PATH):
        if time.monotonic() >= deadline:
            raise ContractError("measured root policy evidence was not published before the deadline")
        time.sleep(0.1)
    attestation = _read_root_controlled_json(ATTESTATION_PATH, max_bytes=65536)
    inventory = collect_inventory(request["run_id"], request["nonce"],
                                  network_policy_attestation=attestation)
    print(canonical_bytes(inventory).decode("ascii"), flush=True)
    return 0 if inventory["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
