"""Minimal native-pytest plugin that records concrete items and their final outcomes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_PLUGIN: "_QAPlugin | None" = None


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup("vst-qa")
    group.addoption("--qa-selection-file", action="store", default=None)
    group.addoption("--qa-events-file", action="store", default=None)
    group.addoption("--qa-repo-root", action="store", default=None)


class _QAPlugin:
    def __init__(self, config: Any) -> None:
        selection_path = config.getoption("--qa-selection-file")
        events_path = config.getoption("--qa-events-file")
        repo_root = config.getoption("--qa-repo-root")
        if not all(isinstance(value, str) and value for value in (selection_path, events_path, repo_root)):
            raise RuntimeError("QA plugin options are incomplete")
        selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
        if not isinstance(selection, dict) or set(selection) != {"schema_version", "selectors"}:
            raise RuntimeError("QA selection file schema is invalid")
        if selection["schema_version"] != 1 or not isinstance(selection["selectors"], dict):
            raise RuntimeError("QA selection file contents are invalid")
        self.events_path = Path(events_path)
        self.repo_root = Path(repo_root).resolve(strict=True)
        self.selector_map = selection["selectors"]
        self.collected: dict[str, dict[str, str | None]] = {}
        self.outcomes: dict[str, dict[str, Any]] = {}
        self.duplicates: list[str] = []
        self.collection_errors: list[str] = []
        self.fixture_observations: list[dict[str, str]] = []
        self.current_node_id: str | None = None

    def selector_for_item(self, item: Any) -> str | None:
        try:
            path = Path(str(item.path)).resolve(strict=True)
            relative = path.relative_to(self.repo_root).as_posix()
        except (OSError, ValueError):
            return None
        original = getattr(item, "originalname", None) or item.name
        cls = getattr(item, "cls", None)
        if cls is not None:
            selector = f"{relative}::{cls.__name__}::{original}"
        else:
            selector = f"{relative}::{original}"
        return selector if selector in self.selector_map else None

    def collect(self, session: Any) -> None:
        for item in session.items:
            node_id = item.nodeid
            selector = self.selector_for_item(item)
            if node_id in self.collected:
                self.duplicates.append(node_id)
            self.collected[node_id] = {"selector": selector}
            self.outcomes[node_id] = {
                "node_id": node_id,
                "selector": selector,
                "outcome": "not_run",
                "phases": [],
            }

    def observe(self, fixture_id: str, observed_rejection: str) -> None:
        if self.current_node_id is None:
            raise RuntimeError("fixture observations must be emitted from a test")
        self.fixture_observations.append(
            {
                "fixture_id": fixture_id,
                "test_node_id": self.current_node_id,
                "observed_rejection": observed_rejection,
            }
        )

    def log_report(self, report: Any) -> None:
        node_id = report.nodeid
        if node_id not in self.outcomes:
            return
        event = self.outcomes[node_id]
        event["phases"].append({"phase": report.when, "outcome": report.outcome})
        was_xfail = getattr(report, "wasxfail", None) is not None
        if report.outcome == "failed":
            event["outcome"] = "xpassed" if was_xfail else "failed"
        elif report.outcome == "skipped":
            event["outcome"] = "xfailed" if was_xfail else "skipped"
        elif was_xfail:
            event["outcome"] = "xpassed"
        elif report.outcome == "passed" and report.when == "call" and event["outcome"] == "not_run":
            event["outcome"] = "passed"

    def write(self) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "collected": [
                {
                    "node_id": node_id,
                    "selector": data["selector"],
                    "outcome": self.outcomes[node_id]["outcome"],
                }
                for node_id, data in sorted(self.collected.items())
            ],
            "duplicates": sorted(set(self.duplicates)),
            "collection_errors": sorted(set(self.collection_errors)),
            "fixture_observations": sorted(
                self.fixture_observations,
                key=lambda item: (item["fixture_id"], item["test_node_id"]),
            ),
        }
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        with self.events_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.write("\n")


def pytest_configure(config: Any) -> None:
    global _PLUGIN
    _PLUGIN = _QAPlugin(config)
    config.pluginmanager.register(_PLUGIN, "vst-qa-events")


def pytest_collection_finish(session: Any) -> None:
    if _PLUGIN is not None:
        _PLUGIN.collect(session)


def pytest_collectreport(report: Any) -> None:
    if _PLUGIN is not None and report.failed:
        _PLUGIN.collection_errors.append(str(report.nodeid))


def pytest_runtest_logstart(nodeid: str, location: Any) -> None:
    if _PLUGIN is not None:
        _PLUGIN.current_node_id = nodeid


def pytest_runtest_logfinish(nodeid: str, location: Any) -> None:
    if _PLUGIN is not None and _PLUGIN.current_node_id == nodeid:
        _PLUGIN.current_node_id = None


def pytest_runtest_logreport(report: Any) -> None:
    if _PLUGIN is not None:
        _PLUGIN.log_report(report)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    if _PLUGIN is not None:
        _PLUGIN.write()


def record_fixture_observation(fixture_id: str, observed_rejection: str) -> None:
    if _PLUGIN is None:
        raise RuntimeError("fixture observation API is available only inside the S4 QA run")
    if not isinstance(fixture_id, str) or not fixture_id.startswith("QA-SEED-"):
        raise ValueError("fixture id is invalid")
    if observed_rejection not in {"FAIL", "BLOCKED", "NOT_RUN", "INCONCLUSIVE"}:
        raise ValueError("fixture observation must be non-approving")
    _PLUGIN.observe(fixture_id, observed_rejection)
