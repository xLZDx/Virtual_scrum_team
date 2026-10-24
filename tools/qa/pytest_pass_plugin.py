"""Emit the trusted pass-line protocol and bounded collection events for VST."""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path


MAX_EVENT_BYTES = 256 * 1024
_CONFIG = None
_FIXTURE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_REJECTION_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")


def _safe_event_path(config) -> Path | None:
    raw = os.environ.get("VST_QA_EVENTS_PATH")
    if not raw or os.path.isabs(raw) or ".." in Path(raw).parts:
        return None
    root = Path.cwd().resolve()
    target = root / raw
    try:
        parent = target.parent.resolve(strict=True)
        if parent != root and root not in parent.parents:
            return None
        if target.exists() or target.is_symlink():
            return None
    except OSError:
        return None
    return target


def pytest_configure(config):
    global _CONFIG
    _CONFIG = config
    config._vst_qa_collected = []
    config._vst_qa_outcomes = {}
    config._vst_qa_collection_errors = []
    config._vst_qa_seeded_failure_observations = []
    config._vst_qa_current_test_id = None


def record_seeded_failure_observation(
    *, fixture_id: str, input_sha256: str, expected_rejection: str,
    observed_rejection: str, test_id: str,
) -> None:
    """Attach a bounded, explicit fixture verdict to its pytest node ID.

    Seeded-failure test bodies call this only after invoking unchanged product
    code. The runner compares the record with the committed fixture catalog
    before it can emit an accepting report.
    """
    if _CONFIG is None:
        raise RuntimeError("QA pytest plugin is not configured")
    if not isinstance(fixture_id, str) or not _FIXTURE_ID.fullmatch(fixture_id):
        raise ValueError("fixture_id is invalid")
    if not isinstance(input_sha256, str) or not _SHA256.fullmatch(input_sha256):
        raise ValueError("input_sha256 must be a lowercase SHA-256 digest")
    if (not isinstance(expected_rejection, str) or
            not _REJECTION_CODE.fullmatch(expected_rejection) or
            not isinstance(observed_rejection, str) or
            not _REJECTION_CODE.fullmatch(observed_rejection)):
        raise ValueError("expected and observed rejection codes must be stable uppercase identifiers")
    if not isinstance(test_id, str) or not test_id or len(test_id) > 1024 or "::" not in test_id:
        raise ValueError("test_id must be a bounded pytest node ID")
    if test_id != getattr(_CONFIG, "_vst_qa_current_test_id", None):
        raise ValueError("test_id must identify the currently executing pytest node")
    observations = _CONFIG._vst_qa_seeded_failure_observations
    if len(observations) >= 256:
        raise ValueError("seeded-failure observation count exceeds 256")
    if any(item["fixture_id"] == fixture_id for item in observations):
        raise ValueError("seeded-failure fixture was observed more than once")
    observations.append({
        "fixture_id": fixture_id,
        "input_sha256": input_sha256,
        "expected_rejection": expected_rejection,
        "observed_rejection": observed_rejection,
        "test_id": test_id,
    })


def pytest_collectreport(report):
    if report.failed:
        errors = getattr(_CONFIG, "_vst_qa_collection_errors", None)
        if errors is not None and len(errors) < 256:
            errors.append(str(report.nodeid)[:1024])


def pytest_runtest_setup(item):
    _CONFIG._vst_qa_current_test_id = str(item.nodeid)[:1024]


def pytest_runtest_teardown(item, nextitem):
    _CONFIG._vst_qa_current_test_id = None


def pytest_collection_finish(session):
    session.config._vst_qa_collected = sorted(
        {str(item.nodeid)[:1024] for item in session.items}
    )


def pytest_runtest_logreport(report):
    if report.when not in ("setup", "call", "teardown"):
        return
    nodeid = str(report.nodeid)[:1024]
    outcomes = getattr(_CONFIG, "_vst_qa_outcomes", None)
    if outcomes is None:
        return
    if report.failed:
        outcomes[nodeid] = "failed"
    elif report.skipped:
        outcomes[nodeid] = "xfail" if hasattr(report, "wasxfail") else "skipped"
    elif report.when == "call" and report.passed and not hasattr(report, "wasxfail"):
        outcomes.setdefault(nodeid, "passed")
        terminal = _CONFIG.pluginmanager.get_plugin("terminalreporter")
        if terminal is not None:
            terminal.write_line(f"PASS {nodeid}")
    elif report.when == "call" and report.passed and hasattr(report, "wasxfail"):
        # XPASS violates the expected-failure contract and must not count as PASS.
        outcomes[nodeid] = "failed"


def pytest_sessionfinish(session, exitstatus):
    target = _safe_event_path(session.config)
    if target is None:
        return
    outcomes = session.config._vst_qa_outcomes
    events = {
        "schema_version": 2,
        "collected_ids": session.config._vst_qa_collected,
        "passed_ids": sorted(key for key, value in outcomes.items() if value == "passed"),
        "skipped_ids": sorted(key for key, value in outcomes.items() if value == "skipped"),
        "xfail_ids": sorted(key for key, value in outcomes.items() if value == "xfail"),
        "failed_ids": sorted(key for key, value in outcomes.items() if value == "failed"),
        "collection_errors": session.config._vst_qa_collection_errors,
        "seeded_failure_observations": session.config._vst_qa_seeded_failure_observations,
        "exit_status": int(exitstatus),
    }
    payload = _canonical_bytes(events)
    if len(payload) > MAX_EVENT_BYTES:
        return
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        # The runner owns the parent directory and reads the completed event
        # file after the worker exits. The parent is mode 0730 (only runner
        # owner and worker group can traverse it), so a world-readable file is
        # safe here and avoids relying on runner membership in the worker GID.
        descriptor = os.open(target, flags, 0o644)
        with os.fdopen(descriptor, "wb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return
            os.fchmod(handle.fileno(), 0o644)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        return
