"""Authenticated, bounded Windows named-pipe transport primitives for VST services.

The pipe DACL admits only the configured service SIDs plus LocalSystem. Both
ends verify the remote process token's service SID and that the peer PID is the
currently registered PID of the configured SCM service before exchanging data.
This module provides bounded byte-stream operations, not a drop-in socket API:
Windows named pipes do not support a socket-style write-half shutdown. Protocol
framing, authorization, signing, and Store decisions remain with callers.
"""

from __future__ import annotations

import ctypes
import os
import re
import threading
import time
from ctypes import wintypes
from typing import Iterable

from .contracts import ContractError


_PIPE_PREFIX = r"\\.\pipe\vst-"
_SID_RE = re.compile(r"S-1-\d+(?:-\d+){1,15}\Z", re.ASCII)
_PIPE_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z", re.ASCII)

_ERROR_FILE_NOT_FOUND = 2
_ERROR_ACCESS_DENIED = 5
_ERROR_BROKEN_PIPE = 109
_ERROR_NO_DATA = 232
_ERROR_PIPE_CONNECTED = 535
_ERROR_PIPE_LISTENING = 536
_ERROR_SEM_TIMEOUT = 121
_ERROR_NO_IMPERSONATION_TOKEN = 1309
_TOKEN_USER_CLASS = 1
_TOKEN_GROUPS_CLASS = 2
_SE_GROUP_ENABLED = 0x00000004
_SE_GROUP_USE_FOR_DENY_ONLY = 0x00000010

_PIPE_ACCESS_DUPLEX = 0x00000003
_PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
_FILE_FLAG_FIRST_PIPE_INSTANCE = 0x00080000
_PIPE_TYPE_BYTE = 0x00000000
_PIPE_READMODE_BYTE = 0x00000000
_PIPE_WAIT = 0x00000000
_PIPE_NOWAIT = 0x00000001
_PIPE_UNLIMITED_INSTANCES = 255
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_GENERIC_READ_SDDL = "GR"
_GENERIC_WRITE_SDDL = "GW"
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_TOKEN_QUERY = 0x0008
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SC_MANAGER_CONNECT = 0x0001
_SERVICE_QUERY_STATUS = 0x0004
_SC_STATUS_PROCESS_INFO = 0
_SDDL_REVISION_1 = 1
_SERVICE_NAME_RE = re.compile(r"[A-Za-z0-9_.-]{1,256}\Z", re.ASCII)


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _ServiceStatusProcess(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
        ("dwProcessId", wintypes.DWORD),
        ("dwServiceFlags", wintypes.DWORD),
    ]


def _api() -> tuple[ctypes.WinDLL, ctypes.WinDLL]:
    if os.name != "nt":
        raise ContractError("Windows named-pipe transport is available only on Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentThread.restype = wintypes.HANDLE
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    advapi32.ConvertStringSidToSidW.restype = wintypes.BOOL
    kernel32.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
        wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    ]
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
    kernel32.SetNamedPipeHandleState.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
    kernel32.PeekNamedPipe.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    kernel32.GetNamedPipeServerProcessId.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG),
    ]
    kernel32.GetNamedPipeClientProcessId.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG),
    ]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcessToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertStringSidToSidW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.CheckTokenMembership.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, ctypes.POINTER(wintypes.BOOL),
    ]
    advapi32.ImpersonateNamedPipeClient.argtypes = [wintypes.HANDLE]
    advapi32.OpenThreadToken.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.RevertToSelf.argtypes = []
    kernel32.GetCurrentThread.argtypes = []
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    advapi32.OpenSCManagerW.restype = wintypes.HANDLE
    advapi32.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    advapi32.OpenServiceW.restype = wintypes.HANDLE
    advapi32.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    advapi32.QueryServiceStatusEx.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    return kernel32, advapi32


def _last_error(message: str) -> OSError:
    code = ctypes.get_last_error()
    return OSError(code, f"{message}: {ctypes.FormatError(code).strip()}")


def _pipe_path(name: str) -> str:
    if not isinstance(name, str) or not _PIPE_NAME_RE.fullmatch(name):
        raise ContractError("Windows named-pipe name is invalid")
    return _PIPE_PREFIX + name


def _service_name(value: object) -> str:
    if not isinstance(value, str) or not _SERVICE_NAME_RE.fullmatch(value):
        raise ContractError("Windows named-pipe service name is invalid")
    return value


def _validated_sids(values: Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ContractError("Windows named-pipe SID policy must be a sequence")
    result = tuple(values)
    if not result or len(result) > 8 or len(set(result)) != len(result):
        raise ContractError("Windows named-pipe SID policy is empty, duplicated, or oversized")
    if any(not isinstance(sid, str) or not _SID_RE.fullmatch(sid) for sid in result):
        raise ContractError("Windows named-pipe SID policy contains an invalid SID")
    return result


_MAX_CONNECT_WAIT_SEC = 30.0
_MAX_CLIENT_IO_TIMEOUT_SEC = 3600.0


def _validated_timeout(value: object, *, label: str) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not 0.1 <= value <= 30.0):
        raise ContractError(f"Windows named-pipe {label} is outside its allowed range")
    return float(value)


def _security_descriptor(allowed_sids: tuple[str, ...]) -> tuple[ctypes.c_void_p, ctypes.WinDLL]:
    _kernel32, advapi32 = _api()
    # LocalSystem retains the minimum rights needed to connect to and service
    # the endpoint. Configured peers receive only the byte-stream rights they
    # need; do not grant generic-all/owner/DACL-management rights.
    trustees = tuple(dict.fromkeys(("S-1-5-18", *allowed_sids)))
    dacl = "D:P" + "".join(f"(A;;{_GENERIC_READ_SDDL}{_GENERIC_WRITE_SDDL};;;{sid})" for sid in trustees)
    descriptor = ctypes.c_void_p()
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        dacl, _SDDL_REVISION_1, ctypes.byref(descriptor), None,
    ):
        raise _last_error("cannot build named-pipe security descriptor")
    return descriptor, advapi32


def _primary_token_has_enabled_sid(token: wintypes.HANDLE, sid: ctypes.c_void_p) -> bool:
    _kernel32, advapi32 = _api()
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.EqualSid.restype = wintypes.BOOL
    advapi32.EqualSid.argtypes = [wintypes.LPVOID, wintypes.LPVOID]
    # The token user (e.g. S-1-5-18 for LocalSystem) is not listed among the groups
    # but counts as membership, exactly as in CheckTokenMembership.
    needed = wintypes.DWORD()
    advapi32.GetTokenInformation(token, _TOKEN_USER_CLASS, None, 0, ctypes.byref(needed))
    if needed.value <= 0 or needed.value > 4096:
        raise ContractError("Windows token user is unavailable")
    user_buffer = ctypes.create_string_buffer(needed.value)
    if not advapi32.GetTokenInformation(
        token, _TOKEN_USER_CLASS, user_buffer, needed.value, ctypes.byref(needed),
    ):
        raise _last_error("cannot read Windows token user")
    user_sid = ctypes.cast(user_buffer, ctypes.POINTER(wintypes.LPVOID)).contents.value
    if advapi32.EqualSid(user_sid, sid):
        return True
    needed = wintypes.DWORD()
    advapi32.GetTokenInformation(token, _TOKEN_GROUPS_CLASS, None, 0, ctypes.byref(needed))
    if needed.value <= 0 or needed.value > 1024 * 1024:
        raise ContractError("Windows token groups are unavailable")
    buffer = ctypes.create_string_buffer(needed.value)
    if not advapi32.GetTokenInformation(
        token, _TOKEN_GROUPS_CLASS, buffer, needed.value, ctypes.byref(needed),
    ):
        raise _last_error("cannot read Windows token groups")

    class _SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]

    count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
    offset = ctypes.sizeof(ctypes.c_void_p)  # GroupCount DWORD padded to pointer alignment
    entries = ctypes.cast(
        ctypes.addressof(buffer) + offset, ctypes.POINTER(_SidAndAttributes * count),
    ).contents
    for entry in entries:
        if not advapi32.EqualSid(entry.Sid, sid):
            continue
        attributes = entry.Attributes
        return bool(attributes & _SE_GROUP_ENABLED) and not attributes & _SE_GROUP_USE_FOR_DENY_ONLY
    return False


def _check_token_sid(token: wintypes.HANDLE, expected_sid: str) -> bool:
    _kernel32, advapi32 = _api()
    sid = ctypes.c_void_p()
    if not advapi32.ConvertStringSidToSidW(expected_sid, ctypes.byref(sid)):
        raise ContractError("configured Windows service SID is invalid")
    try:
        member = wintypes.BOOL()
        if advapi32.CheckTokenMembership(token, sid, ctypes.byref(member)):
            return bool(member.value)
        if ctypes.get_last_error() != _ERROR_NO_IMPERSONATION_TOKEN:
            raise _last_error("cannot verify Windows named-pipe peer SID")
        # CheckTokenMembership accepts only impersonation tokens. For a primary
        # process token, read its groups (TOKEN_QUERY suffices) and require the
        # SID to be enabled and not deny-only.
        return _primary_token_has_enabled_sid(token, sid)
    finally:
        _kernel32, _advapi32 = _api()
        _kernel32.LocalFree(sid)


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TokenUser(ctypes.Structure):
    _fields_ = [("User", _SidAndAttributes)]


def _check_token_user_sid(token: wintypes.HANDLE, expected_sid: str) -> bool:
    """Match the token's actual user SID; group membership is not sufficient."""
    kernel32, advapi32 = _api()
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    needed = wintypes.DWORD()
    advapi32.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
    if needed.value <= 0 or needed.value > 4096:
        raise ContractError("Windows named-pipe client user token is unavailable")
    buffer = ctypes.create_string_buffer(needed.value)
    if not advapi32.GetTokenInformation(
        token, 1, buffer, needed.value, ctypes.byref(needed),
    ):
        raise _last_error("cannot read Windows named-pipe client user SID")
    token_user = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents
    if not token_user.User.Sid:
        raise ContractError("Windows named-pipe client user SID is missing")
    sid_text = wintypes.LPWSTR()
    if not advapi32.ConvertSidToStringSidW(token_user.User.Sid, ctypes.byref(sid_text)):
        raise _last_error("cannot format Windows named-pipe client user SID")
    try:
        return sid_text.value.casefold() == expected_sid.casefold()
    finally:
        kernel32.LocalFree(sid_text)


def _verify_server_sid(pipe: wintypes.HANDLE, expected_sid: str) -> None:
    kernel32, advapi32 = _api()
    pid = wintypes.ULONG()
    if not kernel32.GetNamedPipeServerProcessId(pipe, ctypes.byref(pid)) or pid.value <= 0:
        raise _last_error("cannot identify named-pipe server process")
    process = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not process:
        raise _last_error("cannot open named-pipe server process")
    token = wintypes.HANDLE()
    try:
        if not advapi32.OpenProcessToken(process, _TOKEN_QUERY, ctypes.byref(token)):
            raise _last_error("cannot inspect named-pipe server identity")
        if not _check_token_sid(token, expected_sid):
            raise ContractError("Windows named-pipe server service SID is unauthorized")
    finally:
        if token:
            kernel32.CloseHandle(token)
        kernel32.CloseHandle(process)


def _service_process_id(service_name: str) -> int:
    """Return the active PID registered for one Windows service name."""
    kernel32, advapi32 = _api()
    scm = advapi32.OpenSCManagerW(None, None, _SC_MANAGER_CONNECT)
    if not scm:
        raise _last_error("cannot connect to Windows Service Control Manager")
    service = None
    try:
        service = advapi32.OpenServiceW(scm, service_name, _SERVICE_QUERY_STATUS)
        if not service:
            raise _last_error("cannot identify configured Windows service")
        status = _ServiceStatusProcess()
        needed = wintypes.DWORD()
        if not advapi32.QueryServiceStatusEx(
            service, _SC_STATUS_PROCESS_INFO, ctypes.byref(status),
            ctypes.sizeof(status), ctypes.byref(needed),
        ):
            raise _last_error("cannot read configured Windows service process")
        if status.dwProcessId <= 0:
            raise ContractError("configured Windows service is not running")
        return int(status.dwProcessId)
    finally:
        if service:
            advapi32.CloseServiceHandle(service)
        advapi32.CloseServiceHandle(scm)


def _verify_service_process(pipe: wintypes.HANDLE, *, service_name: str, server: bool) -> None:
    kernel32, _advapi32 = _api()
    pid = wintypes.ULONG()
    get_pid = kernel32.GetNamedPipeServerProcessId if server else kernel32.GetNamedPipeClientProcessId
    if not get_pid(pipe, ctypes.byref(pid)) or pid.value <= 0:
        raise _last_error("cannot identify named-pipe service process")
    if int(pid.value) != _service_process_id(service_name):
        role = "server" if server else "client"
        raise ContractError(f"Windows named-pipe {role} is not the configured service instance")


def _verify_client_sid(
    pipe: wintypes.HANDLE, allowed_services: tuple[tuple[str, str], ...],
    allowed_user_sids: tuple[str, ...] = (),
) -> None:
    kernel32, advapi32 = _api()
    if not advapi32.ImpersonateNamedPipeClient(pipe):
        raise _last_error("cannot authenticate named-pipe client")
    token = wintypes.HANDLE()
    try:
        if not advapi32.OpenThreadToken(
            kernel32.GetCurrentThread(), _TOKEN_QUERY, True, ctypes.byref(token),
        ):
            raise _last_error("cannot inspect named-pipe client identity")
        allowed = next((
            (sid, service_name) for sid, service_name in allowed_services
            if _check_token_sid(token, sid)
        ), None)
        if allowed is not None:
            _sid, service_name = allowed
            _verify_service_process(pipe, service_name=service_name, server=False)
            return
        if any(_check_token_user_sid(token, sid) for sid in allowed_user_sids):
            return
        raise ContractError("Windows named-pipe client SID is unauthorized")
    finally:
        if token:
            kernel32.CloseHandle(token)
        if not advapi32.RevertToSelf():
            raise _last_error("cannot revert named-pipe client impersonation")


class WindowsNamedPipeConnection:
    """Bounded byte stream over one authenticated pipe instance (no half-close)."""

    def __init__(
        self, handle: wintypes.HANDLE, *, timeout_sec: float = 10.0,
        prefetched: bytes = b"",
    ) -> None:
        if not isinstance(timeout_sec, (int, float)) or isinstance(timeout_sec, bool) or timeout_sec <= 0:
            raise ContractError("Windows named-pipe timeout is invalid")
        self._handle = handle
        self._timeout_sec = float(timeout_sec)
        self._closed = False
        if not isinstance(prefetched, bytes):
            raise ContractError("Windows named-pipe prefetched bytes are invalid")
        self._prefetched = bytearray(prefetched)

    def settimeout(self, timeout_sec: float) -> None:
        if not isinstance(timeout_sec, (int, float)) or isinstance(timeout_sec, bool) or timeout_sec <= 0:
            raise ContractError("Windows named-pipe timeout is invalid")
        self._timeout_sec = float(timeout_sec)

    def recv(self, size: int) -> bytes:
        if type(size) is not int or size <= 0:
            raise ContractError("Windows named-pipe read size is invalid")
        if self._closed:
            return b""
        if self._prefetched:
            count = min(size, len(self._prefetched))
            data = bytes(self._prefetched[:count])
            del self._prefetched[:count]
            return data
        kernel32, _advapi32 = _api()
        deadline = time.monotonic() + self._timeout_sec
        while True:
            available = wintypes.DWORD()
            if not kernel32.PeekNamedPipe(self._handle, None, 0, None, ctypes.byref(available), None):
                code = ctypes.get_last_error()
                if code in (_ERROR_BROKEN_PIPE, _ERROR_NO_DATA):
                    return b""
                raise _last_error("cannot inspect Windows named-pipe data")
            if available.value:
                buffer = ctypes.create_string_buffer(min(size, available.value))
                read = wintypes.DWORD()
                if not kernel32.ReadFile(self._handle, buffer, len(buffer), ctypes.byref(read), None):
                    code = ctypes.get_last_error()
                    if code in (_ERROR_BROKEN_PIPE, _ERROR_NO_DATA):
                        return b""
                    raise _last_error("cannot read Windows named-pipe data")
                return buffer.raw[:read.value]
            if time.monotonic() >= deadline:
                raise TimeoutError("Windows named-pipe read timed out")
            time.sleep(0.005)

    def sendall(self, data: bytes) -> None:
        if not isinstance(data, bytes):
            raise ContractError("Windows named-pipe payload must be bytes")
        if self._closed:
            raise OSError("Windows named-pipe connection is closed")
        kernel32, _advapi32 = _api()
        offset = 0
        deadline = time.monotonic() + self._timeout_sec
        while offset < len(data):
            chunk = data[offset:offset + 64 * 1024]
            buffer = ctypes.create_string_buffer(chunk, len(chunk))
            written = wintypes.DWORD()
            if not kernel32.WriteFile(self._handle, buffer, len(chunk), ctypes.byref(written), None):
                code = ctypes.get_last_error()
                if code == _ERROR_NO_DATA and time.monotonic() < deadline:
                    time.sleep(0.005)
                    continue
                raise _last_error("cannot write Windows named-pipe data")
            if written.value <= 0:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Windows named-pipe write timed out")
                time.sleep(0.005)
                continue
            offset += written.value

    def close(self) -> None:
        if not self._closed:
            kernel32, _advapi32 = _api()
            self._closed = True
            kernel32.CloseHandle(self._handle)

    def __enter__(self) -> "WindowsNamedPipeConnection":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _read_initial_client_byte(
    handle: wintypes.HANDLE, *, deadline: float, close_event: threading.Event,
) -> bytes | None:
    """Read one bounded client byte before impersonation, as Win32 requires."""
    kernel32, _advapi32 = _api()
    while not close_event.is_set() and time.monotonic() < deadline:
        available = wintypes.DWORD()
        if not kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
            code = ctypes.get_last_error()
            if code == _ERROR_NO_DATA:
                time.sleep(0.005)
                continue
            if code == _ERROR_BROKEN_PIPE:
                return None
            raise _last_error("cannot wait for the first Windows named-pipe client byte")
        if available.value:
            buffer = ctypes.create_string_buffer(1)
            read = wintypes.DWORD()
            if not kernel32.ReadFile(handle, buffer, 1, ctypes.byref(read), None):
                code = ctypes.get_last_error()
                if code == _ERROR_NO_DATA:
                    time.sleep(0.005)
                    continue
                if code == _ERROR_BROKEN_PIPE:
                    return None
                raise _last_error("cannot read the first Windows named-pipe client byte")
            if read.value == 1:
                return buffer.raw[:1]
        time.sleep(0.005)
    if close_event.is_set():
        raise OSError("Windows named-pipe listener is closed")
    return None


class WindowsNamedPipeClient:
    def __init__(
        self, name: str, *, expected_server_sid: str,
        expected_server_service: str, timeout_sec: float = 10.0,
    ) -> None:
        self.path = _pipe_path(name)
        _validated_sids((expected_server_sid,))
        self.expected_server_sid = expected_server_sid
        self.expected_server_service = _service_name(expected_server_service)
        # The I/O timeout covers a whole request/response, which for dispatch can last
        # as long as the task itself; only the endpoint wait is bounded to 30 seconds.
        if (isinstance(timeout_sec, bool) or not isinstance(timeout_sec, (int, float))
                or not 0.1 <= timeout_sec <= _MAX_CLIENT_IO_TIMEOUT_SEC):
            raise ContractError("Windows named-pipe client timeout is outside its allowed range")
        self.timeout_sec = float(timeout_sec)

    def connect(self) -> WindowsNamedPipeConnection:
        kernel32, _advapi32 = _api()
        timeout_ms = int(min(self.timeout_sec, _MAX_CONNECT_WAIT_SEC) * 1000)
        if not kernel32.WaitNamedPipeW(self.path, timeout_ms):
            code = ctypes.get_last_error()
            if code == _ERROR_SEM_TIMEOUT:
                raise TimeoutError("Windows named-pipe endpoint did not become available")
            raise _last_error("Windows named-pipe endpoint is unavailable")
        handle = kernel32.CreateFileW(
            self.path, _GENERIC_READ | _GENERIC_WRITE, 0, None, _OPEN_EXISTING,
            _FILE_ATTRIBUTE_NORMAL, None,
        )
        if handle == wintypes.HANDLE(-1).value:
            raise _last_error("cannot open Windows named-pipe endpoint")
        try:
            mode = wintypes.DWORD(_PIPE_READMODE_BYTE | _PIPE_NOWAIT)
            if not kernel32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None):
                raise _last_error("cannot configure Windows named-pipe client")
            _verify_server_sid(handle, self.expected_server_sid)
            _verify_service_process(
                handle, service_name=self.expected_server_service, server=True,
            )
            return WindowsNamedPipeConnection(handle, timeout_sec=self.timeout_sec)
        except Exception:
            kernel32.CloseHandle(handle)
            raise


class WindowsNamedPipeListener:
    def __init__(
        self,
        name: str,
        *,
        server_sid: str,
        server_service: str,
        allowed_client_services: dict[str, str],
        allowed_client_user_sids: tuple[str, ...] = (),
        timeout_sec: float = 10.0,
    ) -> None:
        self.path = _pipe_path(name)
        self.server_sid = _validated_sids((server_sid,))[0]
        self.server_service = _service_name(server_service)
        if not isinstance(allowed_client_services, dict):
            raise ContractError("Windows named-pipe client policy must map service SIDs to names")
        if not isinstance(allowed_client_user_sids, tuple):
            raise ContractError("Windows named-pipe user policy must be a tuple of exact user SIDs")
        allowed_sids = _validated_sids(allowed_client_services.keys()) if allowed_client_services else ()
        user_sids = _validated_sids(allowed_client_user_sids) if allowed_client_user_sids else ()
        service_names = tuple(_service_name(value) for value in allowed_client_services.values())
        if (not allowed_sids and not user_sids
                or self.server_sid in allowed_sids or self.server_sid in user_sids
                or set(allowed_sids) & set(user_sids)
                or len(set(service_names)) != len(service_names)):
            raise ContractError("Windows named-pipe server and client SIDs must be distinct")
        self.allowed_client_services = tuple(zip(allowed_sids, service_names, strict=True))
        self.allowed_client_user_sids = user_sids
        if not isinstance(timeout_sec, (int, float)) or isinstance(timeout_sec, bool) or timeout_sec <= 0:
            raise ContractError("Windows named-pipe timeout is invalid")
        self.timeout_sec = float(timeout_sec)
        self._closed = False
        self._close_event = threading.Event()
        self._state_lock = threading.Lock()
        self._active_handle: wintypes.HANDLE | None = None
        self._accept_lock = threading.Lock()

    def accept(self, timeout_sec: float | None = None) -> WindowsNamedPipeConnection | None:
        if self._closed:
            raise OSError("Windows named-pipe listener is closed")
        kernel32, _advapi32 = _api()
        timeout = self.timeout_sec if timeout_sec is None else timeout_sec
        timeout = _validated_timeout(timeout, label="accept timeout")
        if not self._accept_lock.acquire(blocking=False):
            raise ContractError("Windows named-pipe listener already has an active accept")
        handle = wintypes.HANDLE(-1).value
        transferred = False
        try:
            client_sids = (
                tuple(sid for sid, _service in self.allowed_client_services)
                + self.allowed_client_user_sids
            )
            descriptor, advapi32 = _security_descriptor((self.server_sid, *client_sids))
            try:
                attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), descriptor, False)
                deadline = time.monotonic() + timeout
                handle = kernel32.CreateNamedPipeW(
                    self.path,
                    _PIPE_ACCESS_DUPLEX | _FILE_FLAG_FIRST_PIPE_INSTANCE | _PIPE_REJECT_REMOTE_CLIENTS,
                    _PIPE_TYPE_BYTE | _PIPE_READMODE_BYTE | _PIPE_NOWAIT,
                    _PIPE_UNLIMITED_INSTANCES, 64 * 1024, 64 * 1024, 0,
                    ctypes.byref(attributes),
                )
            finally:
                advapi32.LocalFree(descriptor)
            if handle == wintypes.HANDLE(-1).value:
                raise _last_error("cannot create authenticated Windows named-pipe endpoint")
            with self._state_lock:
                if self._closed:
                    kernel32.CloseHandle(handle)
                    handle = wintypes.HANDLE(-1).value
                    raise OSError("Windows named-pipe listener is closed")
                self._active_handle = handle
            _verify_service_process(
                handle, service_name=self.server_service, server=True,
            )
            while time.monotonic() < deadline and not self._close_event.is_set():
                if kernel32.ConnectNamedPipe(handle, None):
                    break
                code = ctypes.get_last_error()
                if code == _ERROR_PIPE_CONNECTED:
                    break
                if code != _ERROR_PIPE_LISTENING:
                    raise _last_error("cannot accept Windows named-pipe client")
                time.sleep(0.005)
            else:
                if self._close_event.is_set():
                    raise OSError("Windows named-pipe listener is closed")
                return None
            mode = wintypes.DWORD(_PIPE_READMODE_BYTE | _PIPE_NOWAIT)
            if not kernel32.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None):
                raise _last_error("cannot configure Windows named-pipe server")
            first_byte = _read_initial_client_byte(
                handle, deadline=time.monotonic() + self.timeout_sec,
                close_event=self._close_event,
            )
            if first_byte is None:
                return None
            _verify_client_sid(
                handle, self.allowed_client_services, self.allowed_client_user_sids,
            )
            connection = WindowsNamedPipeConnection(
                handle, timeout_sec=self.timeout_sec, prefetched=first_byte,
            )
            with self._state_lock:
                if self._closed:
                    raise OSError("Windows named-pipe listener closed during accept")
                self._active_handle = None
                transferred = True
            return connection
        except Exception:
            if handle != wintypes.HANDLE(-1).value:
                with self._state_lock:
                    closed_by_close = self._closed and self._active_handle is None
                if not closed_by_close:
                    kernel32.DisconnectNamedPipe(handle)
            raise
        finally:
            with self._state_lock:
                if self._active_handle == handle:
                    self._active_handle = None
                closed_by_close = self._closed
            if handle != wintypes.HANDLE(-1).value and not closed_by_close and not transferred:
                kernel32.CloseHandle(handle)
            self._accept_lock.release()

    def close(self) -> None:
        kernel32, _advapi32 = _api()
        with self._state_lock:
            if self._closed:
                return
            self._closed = True
            self._close_event.set()
            handle = self._active_handle
            self._active_handle = None
        if handle is not None:
            kernel32.DisconnectNamedPipe(handle)
            kernel32.CloseHandle(handle)
