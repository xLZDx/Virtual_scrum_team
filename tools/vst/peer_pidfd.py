"""Resolve the peer-pidfd socket option without relaxing descriptor verification."""

from __future__ import annotations

import platform
import socket as _stdlib_socket
import sys
from typing import Any

_ABSENT = object()
# Linux v6.6 include/uapi/asm-generic/socket.h; verified against the target headers.
_LINUX_X86_64_SO_PEERPIDFD = 77


def peer_pidfd_socket_option(socket_api: Any) -> int | None:
    """Return an option number, not a claim that the running kernel supports it.

    Python 3.12 can omit the name while a Linux x86-64 kernel implements the ABI.
    Each caller must still obtain and validate a real descriptor with getsockopt.
    Explicitly unavailable values, test adapters and unverified ABIs stay closed.
    """
    value = getattr(socket_api, "SO_PEERPIDFD", _ABSENT)
    if value is not _ABSENT:
        return value if type(value) is int and value > 0 else None
    if (socket_api is _stdlib_socket and sys.platform == "linux"
            and platform.machine().lower() == "x86_64"):
        return _LINUX_X86_64_SO_PEERPIDFD
    return None
