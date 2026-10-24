"""S2 probe contract checks; real sandbox inventory remains platform-gated."""
from __future__ import annotations

import hashlib

import pytest

from tools.vst import preflight
from tools.vst.signing import sign

KEY = b"s2-probe-runner-key-0123456789-abcdef"
PROPERTIES = {
    "automount_disabled", "interop_disabled", "no_container_socket", "non_root",
    "external_egress_blocked", "loopback_canary", "empty_external_allowlist",
}


def valid_probe():
    body = {
        "run_id": "run-1", "spec_sha256": hashlib.sha256(preflight.SPEC_PATH.read_bytes()).hexdigest(),
        "nonce": "nonce-1", "checked_properties": {name: True for name in PROPERTIES},
        "result": "PASS", "inventory": {"uid": 1001, "container_socket_paths_present": []},
    }
    return {**body, "signature": sign(body, KEY, preflight.PROBE_LABEL)}


def test_probe_verification_binds_signature_run_spec_nonce_and_every_check():
    probe = valid_probe()
    args = dict(run_id="run-1", spec_sha256=probe["spec_sha256"], nonce="nonce-1", key=KEY)
    assert preflight.verify_fresh_probe(probe, **args)
    for changed in (
        {**probe, "run_id": "other"}, {**probe, "nonce": "other"},
        {**probe, "spec_sha256": "0" * 64}, {**probe, "result": "FAIL"},
    ):
        assert not preflight.verify_fresh_probe(changed, **args)
    for name in sorted(PROPERTIES):
        bad = {**probe, "checked_properties": {**probe["checked_properties"], name: False}}
        assert not preflight.verify_fresh_probe(bad, **args), name
    assert not preflight.verify_fresh_probe(probe, **{**args, "key": b"x" * 32})


def test_sign_inventory_rejects_incomplete_or_extra_contract_fields():
    probe = valid_probe()
    unsigned = {key: value for key, value in probe.items() if key != "signature"}
    assert preflight.sign_inventory(unsigned, KEY)["signature"]
    with pytest.raises(Exception, match="fields do not match"):
        preflight.sign_inventory({**unsigned, "unexpected": True}, KEY)


@pytest.mark.skip(reason="NOT_RUN: actual WSL/VM sandbox inventory and egress probe require operator-provisioned POSIX sandbox; synthetic inventories do not prove platform isolation")
def test_real_sandbox_inventory_has_all_required_properties():
    inventory = preflight.collect_inventory("operator-provisioned-run")
    assert inventory["result"] == "PASS"


@pytest.mark.parametrize("scenario", [
    "worker_crash_mid_edit",
    "STOP_injection_and_cleanup",
    "budget_exhaustion",
    "resume_with_fresh_epoch_and_receipt",
    "unauthorized_write_outside_scope",
    "blocked_egress_attempt",
])
@pytest.mark.skip(reason="NOT_RUN: E8 bake-off requires operator-provisioned sandbox; process-kill and mutation runs are prohibited, and no synthetic result can prove isolation")
def test_e8_sandbox_bakeoff_scenarios_not_run(scenario):
    pytest.skip(scenario)

