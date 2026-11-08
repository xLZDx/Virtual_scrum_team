"""Minimal native-pytest plugin that records concrete items and their final outcomes.

Trust model: this plugin runs INSIDE the pytest process, so everything it reports
is candidate-attested evidence. It is not tamper-proof against code executing in
that process (test code, conftest files, or imported modules can alter what is
recorded). The pytest child runs as the operator user with no identity or
privilege separation (operator decision, single-user machine). The checks below
(pytest origin, hook allowlist) and the runner's checks only detect accidental or
naive interference; they are not a security boundary against hostile candidate code.
"""

from __future__ import annotations

import json
import os
import sys
import types
from pathlib import Path
from typing import Any

_PLUGIN: "_QAPlugin | None" = None
_GUARDED_HOOKS = (
    "pytest_runtest_makereport",
    "pytest_runtest_logreport",
    "pytest_collection_modifyitems",
    "pytest_sessionfinish",
)


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup("vst-qa")
    group.addoption("--qa-selection-file", action="store", default=None)
    group.addoption("--qa-events-file", action="store", default=None)
    group.addoption("--qa-repo-root", action="store", default=None)
    group.addoption("--qa-dependency-target", action="store", default=None)


def _under(path: str | None, root: Path) -> bool:
    if not path:
        return False
    try:
        return Path(os.path.realpath(path)).is_relative_to(Path(os.path.realpath(root)))
    except (OSError, ValueError):
        return False


def _origin(plugin: Any) -> tuple[str, str | None]:
    if isinstance(plugin, types.ModuleType):
        name = plugin.__name__
        return name, getattr(plugin, "__file__", None)
    name = getattr(type(plugin), "__module__", "") or ""
    return name, getattr(sys.modules.get(name), "__file__", None)


def _implemented_hooks(plugin: Any) -> list[str]:
    try:
        names = set(dir(plugin))
    except Exception:  # noqa: BLE001 - an undiscoverable plugin cannot be proven hook-free
        return list(_GUARDED_HOOKS)
    return sorted(hook for hook in _GUARDED_HOOKS if hook in names)


class _QAPlugin:
    def __init__(self, config: Any) -> None:
        selection_path = config.getoption("--qa-selection-file")
        events_path = config.getoption("--qa-events-file")
        repo_root = config.getoption("--qa-repo-root")
        dependency_target = config.getoption("--qa-dependency-target")
        if not all(
            isinstance(value, str) and value
            for value in (selection_path, events_path, repo_root, dependency_target)
        ):
            raise RuntimeError("QA plugin options are incomplete")
        self.dependency_target = Path(dependency_target)
        selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
        if not isinstance(selection, dict) or set(selection) != {
            "schema_version", "expected_selectors", "known_selectors"
        }:
            raise RuntimeError("QA selection file schema is invalid")
        if (
            selection["schema_version"] != 2
            or not isinstance(selection["expected_selectors"], dict)
            or not isinstance(selection["known_selectors"], dict)
        ):
            raise RuntimeError("QA selection file contents are invalid")
        self.events_path = Path(events_path)
        self.repo_root = Path(repo_root).resolve(strict=True)
        self.expected_selectors = selection["expected_selectors"]
        self.known_selectors = selection["known_selectors"]
        if (
            not self.expected_selectors
            or not set(self.expected_selectors).issubset(self.known_selectors)
            or any(
                not isinstance(test_id, str)
                or not isinstance(selector, str)
                or self.known_selectors.get(test_id) != selector
                for test_id, selector in self.expected_selectors.items()
            )
            or any(not isinstance(test_id, str) or not isinstance(selector, str)
                   for test_id, selector in self.known_selectors.items())
        ):
            raise RuntimeError("QA selector maps are inconsistent")
        self.expected_selector_values = set(self.expected_selectors.values())
        self.known_selector_values = set(self.known_selectors.values())
        self.collected: dict[str, dict[str, str | None]] = {}
        self.outcomes: dict[str, dict[str, Any]] = {}
        self.duplicates: list[str] = []
        self.collection_errors: list[str] = []
        self.plugin_rows: dict[str, dict[str, Any]] = {}
        self.non_allowlisted: set[str] = set()
        self.origin: dict[str, str | None] = {"pytest_file": None, "_pytest_file": None}

    def _allowed(self, module: str, file: str | None) -> bool:
        if module in {"pytest", "_pytest"} or module.startswith("_pytest."):
            return _under(file, self.dependency_target)
        if module == "tools.qa.pytest_plugin":
            return _under(file, self.repo_root / "tools" / "qa")
        return False

    def audit(self, config: Any) -> None:
        """Record pytest's origin and refuse any non-pinned plugin that implements a guarded hook."""
        import _pytest
        import pytest

        self.origin = {
            "pytest_file": getattr(pytest, "__file__", None),
            "_pytest_file": getattr(_pytest, "__file__", None),
        }
        for name, plugin in config.pluginmanager.list_name_plugin():
            if plugin is None:
                continue
            module, file = _origin(plugin)
            hooks = _implemented_hooks(plugin)
            allowed = not hooks or self._allowed(module, file)
            key = str(name)
            self.plugin_rows[key] = {"name": key, "module": module, "hooks": hooks, "allowed": allowed}
            if not allowed:
                self.non_allowlisted.add(key)

    def audit_record(self) -> dict[str, Any]:
        return {
            **self.origin,
            "plugins": [self.plugin_rows[key] for key in sorted(self.plugin_rows)],
            "non_allowlisted": sorted(self.non_allowlisted),
        }

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
        return selector if selector in self.known_selector_values else None

    def select_items(self, items: list[Any]) -> tuple[list[Any], list[Any]]:
        selected: list[Any] = []
        deselected: list[Any] = []
        for item in items:
            selector = self.selector_for_item(item)
            # Keep unknown selectors from requested source files so the runner can
            # fail closed. Known selectors outside this category (including policy
            # NOT_RUN selectors) are deliberately not executed.
            if selector is None or selector in self.expected_selector_values:
                selected.append(item)
            else:
                deselected.append(item)
        return selected, deselected

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
            "audit": self.audit_record(),
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
        _PLUGIN.audit(session.config)
        _PLUGIN.collect(session)


def pytest_collection_modifyitems(session: Any, config: Any, items: list[Any]) -> None:
    if _PLUGIN is None:
        return
    selected, deselected = _PLUGIN.select_items(items)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected


def pytest_collectreport(report: Any) -> None:
    if _PLUGIN is not None and report.failed:
        _PLUGIN.collection_errors.append(str(report.nodeid))


def pytest_runtest_logreport(report: Any) -> None:
    if _PLUGIN is not None:
        _PLUGIN.log_report(report)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    if _PLUGIN is not None:
        _PLUGIN.audit(session.config)  # catches plugins registered while tests ran
        _PLUGIN.write()
