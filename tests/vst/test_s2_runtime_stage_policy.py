"""S2 stage-only policy for preserving an existing inactive configuration directory."""
from __future__ import annotations

import stat
from types import SimpleNamespace

import pytest

from tools.vst import runtime_bundle as bundle
from tools.vst.contracts import ContractError


CONFIG_DIR = "/etc/vst-runner"


def test_stage_only_allows_absent_configuration_directory(monkeypatch):
    def missing(_path):
        raise FileNotFoundError(CONFIG_DIR)

    monkeypatch.setattr(bundle.os, "lstat", missing)

    bundle.validate_root_config_directory(CONFIG_DIR)


def test_stage_only_allows_existing_root_owned_non_writable_directory(monkeypatch):
    expected = SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=0)
    monkeypatch.setattr(bundle.os, "lstat", lambda _path: expected)

    bundle.validate_root_config_directory(CONFIG_DIR)


@pytest.mark.parametrize(
    "info",
    [
        SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0),
        SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0),
        SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_uid=1000),
        SimpleNamespace(st_mode=stat.S_IFDIR | 0o775, st_uid=0),
        SimpleNamespace(st_mode=stat.S_IFDIR | 0o757, st_uid=0),
    ],
    ids=["symlink", "not-directory", "non-root-owner", "group-writable", "world-writable"],
)
def test_stage_only_rejects_unsafe_existing_configuration_directory(monkeypatch, info):
    monkeypatch.setattr(bundle.os, "lstat", lambda _path: info)

    with pytest.raises(ContractError, match="root-controlled non-writable directory"):
        bundle.validate_root_config_directory(CONFIG_DIR)


def test_stage_only_fails_closed_when_configuration_directory_cannot_be_inspected(monkeypatch):
    def inaccessible(_path):
        raise PermissionError(CONFIG_DIR)

    monkeypatch.setattr(bundle.os, "lstat", inaccessible)

    with pytest.raises(ContractError, match="cannot inspect root configuration directory"):
        bundle.validate_root_config_directory(CONFIG_DIR)
