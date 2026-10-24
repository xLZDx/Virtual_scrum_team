"""Emit the trusted pass-line protocol and bounded collection events for VST."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path


MAX_EVENT_BYTES = 256 * 1024
_CONFIG = None


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


def pytest_collectreport(report):
    if report.failed:
        errors = getattr(_CONFIG, "_vst_qa_collection_errors", None)
        if errors is not None and len(errors) < 256:
            errors.append(str(report.nodeid)[:1024])


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
        "schema_version": 1,
        "collected_ids": session.config._vst_qa_collected,
        "passed_ids": sorted(key for key, value in outcomes.items() if value == "passed"),
        "skipped_ids": sorted(key for key, value in outcomes.items() if value == "skipped"),
        "xfail_ids": sorted(key for key, value in outcomes.items() if value == "xfail"),
        "failed_ids": sorted(key for key, value in outcomes.items() if value == "failed"),
        "collection_errors": session.config._vst_qa_collection_errors,
        "exit_status": int(exitstatus),
    }
    payload = _canonical_bytes(events)
    if len(payload) > MAX_EVENT_BYTES:
        return
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        return
