"""LINK-2 e2e: router flow against the real AEVE at the pin (35e5de8) with AEVE's own handoff_verify fixtures.

Needs a clean AEVE checkout at the pinned head, given by env AEVE_PIN_CHECKOUT or the default scratch path
D:/tmp/scratch_worktrees/aeve-pin35 (`git -C D:/Repo/AEVE worktree add --detach <path> 35e5de8`). Without it the module is
skipped with that reason. Expected statuses and exit codes come from the fixtures' `*.expected.json` and `cases.json`.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

from tools.vst import router_mode as rm
from tools.vst import router_request as rr

from tests.vst import router_support as S

PIN = "35e5de868edaa37e021955147afb587011ca39c0"
AEVE = pathlib.Path(os.environ.get("AEVE_PIN_CHECKOUT", "D:/tmp/scratch_worktrees/aeve-pin35"))
FIX = AEVE / "tests" / "fixtures" / "handoff_verify"

pytestmark = pytest.mark.skipif(not FIX.is_dir(), reason=f"no AEVE checkout at the pin under {AEVE}")


def request():
    return rr.build_request(role="implementation-engineer", task_id="S20-T08", title="Handoff fixture packet",
                            scope_paths=["src/aeve", "tests"], forbidden_paths=["src/aeve/review.py"],
                            acceptance=["Result stays inside scope."])


def route(tmp_path, result_file):
    mode = S.link_mode_file(tmp_path, "router")
    cfg = rm.RouterConfig(python=None, timeout=120.0, poll_seconds=0.05)
    return rm.route_task(request(), state_root=tmp_path / "state", aeve_root=AEVE, root=FIX / "root",
                         result_source=result_file, pin_head=PIN, mode_path=mode, config=cfg)


def test_checkout_is_at_the_pin_and_clean():
    from tools.uc import aeve_probe
    assert aeve_probe.checkout_head(AEVE) == PIN and aeve_probe.checkout_is_clean(AEVE)


@pytest.mark.parametrize("name,outcome,status", [
    ("verified", "ROUTED_VERIFIED", "VERIFIED"),
    ("rejected", "ROUTED_REJECTED", "REJECTED"),
    ("invalid", "ROUTER_INVALID_INPUT", "INVALID"),
])
def test_fixture_cases_route_to_the_expected_outcome(tmp_path, name, outcome, status):
    expected = json.loads((FIX / f"{name}.expected.json").read_text(encoding="utf-8"))
    row = route(tmp_path, FIX / f"{name}.result.json")
    assert expected["status"] == status
    assert (row.state, row.outcome, row.status) == ("DONE", outcome, status)
    report = json.loads((pathlib.Path(row.work_dir) / "report.json").read_text(encoding="utf-8"))
    assert report == expected
    assert row.aeve_request_sha256 == S.expected_request_sha256(request())


def test_unknown_is_reachable_and_never_a_pass(tmp_path):
    empty = tmp_path / "empty_result.json"
    empty.write_text(json.dumps({"schema_version": "aeve.handoff_result.v1", "task_id": "S20-T08", "changed": []}),
                     encoding="utf-8")
    row = route(tmp_path, empty)
    assert (row.outcome, row.status) == ("ROUTED_UNKNOWN", "UNKNOWN")
    assert rm.route_gate(row.outcome, "CLEAN") == "BLOCKED"


def test_handoff_assisted_roles_of_the_real_matrix_equal_the_router_roles():
    from tools.uc import aeve_probe
    matrix = aeve_probe.load_matrix(AEVE)
    roles = sorted(r["id"] for r in matrix["rows"] if r.get("capability_class") == "HANDOFF_ASSISTED")
    assert roles == sorted(rr.ROUTER_ROLES)  # AC-3
