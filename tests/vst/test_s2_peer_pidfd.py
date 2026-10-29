"""Focused tests for fail-closed SO_PEERPIDFD option resolution."""

from __future__ import annotations

import socket as stdlib_socket
from types import SimpleNamespace

import pytest

from tools.vst import peer_pidfd


def _platform(monkeypatch, *, sys_platform: str, machine: str) -> None:
    monkeypatch.setattr(peer_pidfd, "sys", SimpleNamespace(platform=sys_platform))
    monkeypatch.setattr(peer_pidfd, "platform", SimpleNamespace(machine=lambda: machine))


def test_native_socket_constant_is_used_without_numeric_fallback(monkeypatch):
    monkeypatch.setattr(stdlib_socket, "SO_PEERPIDFD", 123, raising=False)
    _platform(monkeypatch, sys_platform="win32", machine="arm64")

    assert peer_pidfd.peer_pidfd_socket_option(stdlib_socket) == 123


@pytest.mark.parametrize(
    "value",
    [None, False, 0, -1, "77", 77.0],
    ids=["none", "boolean", "zero", "negative", "string", "float"],
)
def test_explicit_invalid_socket_constant_is_refused_without_fallback(monkeypatch, value):
    monkeypatch.setattr(stdlib_socket, "SO_PEERPIDFD", value, raising=False)
    _platform(monkeypatch, sys_platform="linux", machine="x86_64")

    assert peer_pidfd.peer_pidfd_socket_option(stdlib_socket) is None


def test_numeric_abi_resolution_is_limited_to_real_linux_x86_64_socket_module(monkeypatch):
    monkeypatch.delattr(stdlib_socket, "SO_PEERPIDFD", raising=False)
    _platform(monkeypatch, sys_platform="linux", machine="x86_64")

    assert peer_pidfd.peer_pidfd_socket_option(stdlib_socket) == 77
    assert peer_pidfd.peer_pidfd_socket_option(SimpleNamespace()) is None


@pytest.mark.parametrize(
    ("sys_platform", "machine"),
    [
        ("win32", "x86_64"),
        ("linux", "aarch64"),
        ("darwin", "x86_64"),
    ],
    ids=["windows", "linux-arm64", "darwin"],
)
def test_numeric_abi_resolution_fails_closed_on_unsupported_platforms(
    monkeypatch, sys_platform, machine,
):
    monkeypatch.delattr(stdlib_socket, "SO_PEERPIDFD", raising=False)
    _platform(monkeypatch, sys_platform=sys_platform, machine=machine)

    assert peer_pidfd.peer_pidfd_socket_option(stdlib_socket) is None
