"""Windows SCM identity and service-dispatch primitives for the local runtime.

This module is deliberately inert when imported on other platforms.  SCM
service SIDs are resolved from Windows, never copied from configuration; the
role names and pipe names below are part of the local runtime contract.
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import stat
import sys
import threading
from dataclasses import dataclass
from ctypes import wintypes
from importlib import import_module
from typing import Any, Callable, Mapping

if __package__ in {None, ""}:
    # SCM launches this file by absolute path, so make package-relative imports
    # deterministic even when the service working directory is System32.
    _repository_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, _repository_root)
    __package__ = "tools.vst"

from .contracts import ContractError

_SID_RE = re.compile(r"S-1-\d+(?:-\d+){1,15}\Z", re.ASCII)
_SERVICE_NAMES = {
    "owner": "VSTOwner",
    "supervisor": "VSTSupervisor",
    "dispatcher": "VSTDispatcher",
    "runner": "VSTRunner",
    "signer": "VSTSigner",
    "worker": "VSTWorker",
}
_PIPE_NAMES = {
    "owner": "owner-instructions",
    "supervisor_dispatcher": "supervisor-dispatcher",
    "supervisor_owner": "supervisor-owner",
    "supervisor_runner": "supervisor-runner",
    "supervisor_signer": "supervisor-signer",
    "supervisor_operator": "supervisor-operator",
    "supervisor_worker": "supervisor-worker",
    "runner_dispatch": "runner-dispatch",
    "runner_signer": "runner-signer",
    "runner_worker": "runner-worker",
}
_ROLE_PIPE_NAMES = {
    "owner": "owner-instructions",
    "supervisor": None,
    "dispatcher": "supervisor-dispatcher",
    "runner": "runner-dispatch",
    "signer": "runner-signer",
    "worker": "runner-worker",
}
_ROLE_SERVICE_TYPE = 0x10  # SERVICE_WIN32_OWN_PROCESS
_SERVICE_CONFIG_SERVICE_SID_INFO = 5
_SERVICE_SID_TYPE_UNRESTRICTED = 1
_SERVICE_SID_TYPE_RESTRICTED = 3
_SE_FILE_OBJECT = 1
_OWNER_SECURITY_INFORMATION = 0x00000001
_DACL_SECURITY_INFORMATION = 0x00000004
_SE_DACL_PROTECTED = 0x1000
_ACL_SIZE_INFORMATION = 2
_ACCESS_ALLOWED_ACE_TYPE = 0
_WRITE_ACCESS_MASK = 0x00000002 | 0x00000004 | 0x00000010 | 0x00000100 | 0x00010000 | 0x00040000 | 0x00080000 | 0x40000000 | 0x10000000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_SC_MANAGER_CONNECT = 0x0001
_SERVICE_QUERY_CONFIG = 0x0001
_ERROR_INSUFFICIENT_BUFFER = 122
_SERVICE_TABLE_END = (None, None)


@dataclass(frozen=True)
class WindowsRoleIdentity:
    role: str
    service_name: str
    service_sid: str
    pipe_name: str | None


@dataclass(frozen=True)
class WindowsRuntimeConfig:
    """Non-secret runtime paths plus SCM-resolved role identities.

    ``roots`` is an explicit injection seam for isolated functional tests. It
    is not an alternate production config source and values still undergo the
    same absolute-path validation.
    """

    data_root: str
    store_root: str
    signer_root: str
    role_identities: Mapping[str, WindowsRoleIdentity]

    @classmethod
    def load(cls, path: str | None = None, *, roots: Mapping[str, str] | None = None,
             role: str | None = None) -> "WindowsRuntimeConfig":
        if os.name != "nt":
            raise ContractError("Windows SCM runtime is available only on Windows")
        config_path = path or os.path.join(
            os.environ.get("ProgramData", r"C:\ProgramData"), "VST", "runtime.json",
        )
        if not isinstance(config_path, str) or not os.path.isabs(config_path):
            raise ContractError("Windows runtime config path must be absolute")
        if roots is None:
            try:
                with open(config_path, "rb") as stream:
                    raw = stream.read(65537)
                if len(raw) > 65536:
                    raise ContractError("Windows runtime config exceeds its size limit")
                values = json.loads(raw)
            except (OSError, ValueError, UnicodeDecodeError) as exc:
                raise ContractError("Windows runtime config is unavailable or malformed") from exc
            if not isinstance(values, dict) or set(values) != {"data_root", "store_root", "signer_root"}:
                raise ContractError("Windows runtime config fields do not match the non-secret schema")
            supplied = dict(values)
        else:
            if not isinstance(roots, Mapping) or set(roots) != {"data_root", "store_root", "signer_root"}:
                raise ContractError("injected Windows runtime roots do not match the schema")
            supplied = dict(roots)
        for name in ("data_root", "store_root", "signer_root"):
            value = supplied[name]
            if not isinstance(value, str) or not os.path.isabs(value):
                raise ContractError(f"Windows runtime {name} must be an absolute path")
        if os.path.commonpath((supplied["data_root"], supplied["store_root"])) != supplied["data_root"]:
            raise ContractError("Supervisor Store root must be under the runtime data root")
        if os.path.commonpath((supplied["data_root"], supplied["signer_root"])) != supplied["data_root"]:
            raise ContractError("Signer root must be under the runtime data root")
        identities = {
            role: WindowsRoleIdentity(
                role=role,
                service_name=service_name,
                service_sid=resolve_enabled_service_sid(service_name),
                pipe_name=_ROLE_PIPE_NAMES[role],
            )
            for role, service_name in _SERVICE_NAMES.items()
        }
        if role is not None and role not in _SERVICE_NAMES:
            raise ContractError("unknown Windows VST service role")
        system_sid, administrators_sid = "S-1-5-18", "S-1-5-32-544"
        all_service_sids = {item.service_sid for item in identities.values()}
        if roots is None:
            assert_path_acl(
                config_path,
                allowed_sids={system_sid, administrators_sid, *all_service_sids},
                writable_sids={system_sid, administrators_sid},
            )
        assert_path_acl(
            supplied["data_root"],
            allowed_sids={system_sid, administrators_sid, *all_service_sids},
            writable_sids={system_sid, administrators_sid}, require_protected=True,
        )
        for root_name, owner_role in (("store_root", "supervisor"), ("signer_root", "signer")):
            owner_sids = {system_sid, administrators_sid, identities[owner_role].service_sid}
            try:
                assert_path_acl(
                    supplied[root_name], allowed_sids=owner_sids, writable_sids=owner_sids,
                    require_protected=True,
                )
            except OSError as exc:
                # A private role root is deliberately unreadable (even its ACL) to the
                # other roles. Access denied is therefore the expected boundary for
                # them; the owning role re-verifies this root in full before it reads
                # any key from it (read_role_private_file / read_signer_private_key).
                # The owning role itself must never skip its own root check.
                if exc.errno != 5 or role == owner_role:
                    raise
        return cls(
            data_root=supplied["data_root"], store_root=supplied["store_root"],
            signer_root=supplied["signer_root"], role_identities=identities,
        )

    def identity(self, role: str) -> WindowsRoleIdentity:
        try:
            return self.role_identities[role]
        except (KeyError, TypeError) as exc:
            raise ContractError("unknown Windows VST service role") from exc

    def pipe_name(self, endpoint: str) -> str:
        try:
            return _PIPE_NAMES[endpoint]
        except (KeyError, TypeError) as exc:
            raise ContractError("unknown Windows VST pipe endpoint") from exc


def read_runtime_json(runtime: WindowsRuntimeConfig, filename: str, *, max_bytes: int = 65536) -> dict[str, Any]:
    """Read one protected non-secret role config from the shared data root."""
    if (not isinstance(runtime, WindowsRuntimeConfig)
            or not isinstance(filename, str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}\.json", filename, re.ASCII)
            or type(max_bytes) is not int or not 1 <= max_bytes <= 1024 * 1024):
        raise ContractError("Windows role config request is invalid")
    path = os.path.join(runtime.data_root, filename)
    try:
        if os.path.commonpath((runtime.data_root, path)) != runtime.data_root:
            raise ContractError("Windows role config path escaped the data root")
    except ValueError as exc:
        raise ContractError("Windows role config is on another volume") from exc
    system_admin = {"S-1-5-18", "S-1-5-32-544"}
    allowed = system_admin | {item.service_sid for item in runtime.role_identities.values()}
    assert_path_acl(path, allowed_sids=allowed, writable_sids=system_admin)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ContractError("Windows role config contains duplicate keys")
            result[key] = value
        return result

    try:
        with open(path, "rb") as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ContractError("Windows role config exceeds its size limit")
        value = json.loads(raw, object_pairs_hook=unique_object)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ContractError("Windows role config is unavailable or malformed") from exc
    if not isinstance(value, dict):
        raise ContractError("Windows role config must be an object")
    return value


class _ServiceSidInfo(ctypes.Structure):
    _fields_ = [("dwServiceSidType", wintypes.DWORD)]


class _QueryServiceConfig(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwStartType", wintypes.DWORD),
        ("dwErrorControl", wintypes.DWORD),
        ("lpBinaryPathName", wintypes.LPWSTR),
        ("lpLoadOrderGroup", wintypes.LPWSTR),
        ("dwTagId", wintypes.DWORD),
        ("lpDependencies", wintypes.LPWSTR),
        ("lpServiceStartName", wintypes.LPWSTR),
        ("lpDisplayName", wintypes.LPWSTR),
    ]


class _AclSizeInformation(ctypes.Structure):
    _fields_ = [("AceCount", wintypes.DWORD), ("AclBytesInUse", wintypes.DWORD),
                ("AclBytesFree", wintypes.DWORD)]


def _win_api():
    if os.name != "nt":
        raise ContractError("Windows SCM identity lookup is available only on Windows")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi.OpenSCManagerW.restype = wintypes.HANDLE
    advapi.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    advapi.OpenServiceW.restype = wintypes.HANDLE
    advapi.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    advapi.QueryServiceConfig2W.restype = wintypes.BOOL
    advapi.QueryServiceConfig2W.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi.QueryServiceConfigW.restype = wintypes.BOOL
    advapi.QueryServiceConfigW.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
                                             wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.CloseServiceHandle.restype = wintypes.BOOL
    advapi.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    advapi.LookupAccountNameW.restype = wintypes.BOOL
    advapi.LookupAccountNameW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
    ]
    advapi.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi.ConvertSidToStringSidW.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.GetNamedSecurityInfoW.restype = wintypes.DWORD
    advapi.GetNamedSecurityInfoW.argtypes = [
        wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.LPVOID),
    ]
    advapi.GetSecurityDescriptorDacl.restype = wintypes.BOOL
    advapi.GetSecurityDescriptorDacl.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.BOOL),
    ]
    advapi.GetSecurityDescriptorControl.restype = wintypes.BOOL
    advapi.GetSecurityDescriptorControl.argtypes = [
        wintypes.LPVOID, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD),
    ]
    advapi.GetAclInformation.restype = wintypes.BOOL
    advapi.GetAclInformation.argtypes = [wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD]
    advapi.GetAce.restype = wintypes.BOOL
    advapi.GetAce.argtypes = [wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID)]
    kernel.LocalFree.restype = wintypes.HLOCAL
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    return advapi, kernel


def _service_configuration(service: wintypes.HANDLE, advapi: Any) -> tuple[int, str]:
    needed = wintypes.DWORD()
    advapi.QueryServiceConfigW(service, None, 0, ctypes.byref(needed))
    if needed.value <= 0 or needed.value > 65536:
        raise ContractError("SCM service configuration is unavailable")
    buffer = ctypes.create_string_buffer(needed.value)
    if not advapi.QueryServiceConfigW(service, buffer, needed.value, ctypes.byref(needed)):
        raise OSError(ctypes.get_last_error(), "cannot read SCM service type")
    config = ctypes.cast(buffer, ctypes.POINTER(_QueryServiceConfig)).contents
    start_name = config.lpServiceStartName
    if not isinstance(start_name, str) or not start_name:
        raise ContractError("SCM service start account is unavailable")
    return int(config.dwServiceType), start_name


def resolve_enabled_service_sid(service_name: str) -> str:
    """Resolve the service SID only when SCM reports its SID type enabled."""
    if not isinstance(service_name, str) or service_name not in _SERVICE_NAMES.values():
        raise ContractError("Windows VST service name is not in the fixed role registry")
    advapi, kernel = _win_api()
    scm = advapi.OpenSCManagerW(None, None, _SC_MANAGER_CONNECT)
    if not scm:
        raise OSError(ctypes.get_last_error(), "cannot connect to Service Control Manager")
    service = None
    try:
        service = advapi.OpenServiceW(scm, service_name, _SERVICE_QUERY_CONFIG)
        if not service:
            raise OSError(ctypes.get_last_error(), "configured VST service is not installed")
        service_type, start_name = _service_configuration(service, advapi)
        if service_type != _ROLE_SERVICE_TYPE:
            raise ContractError("each VST role must run in its own SCM service process")
        expected_start_name = f"NT SERVICE\\{service_name}"
        if start_name.casefold() != expected_start_name.casefold():
            raise ContractError("each VST role must run under its own non-admin virtual service account")
        needed = wintypes.DWORD()
        advapi.QueryServiceConfig2W(service, _SERVICE_CONFIG_SERVICE_SID_INFO, None, 0,
                                    ctypes.byref(needed))
        if needed.value != ctypes.sizeof(_ServiceSidInfo):
            raise ContractError("SCM service SID configuration is unavailable")
        info = _ServiceSidInfo()
        if not advapi.QueryServiceConfig2W(service, _SERVICE_CONFIG_SERVICE_SID_INFO,
                                           ctypes.byref(info), needed.value,
                                           ctypes.byref(needed)):
            raise OSError(ctypes.get_last_error(), "cannot read SCM service SID policy")
        if info.dwServiceSidType not in {
            _SERVICE_SID_TYPE_UNRESTRICTED, _SERVICE_SID_TYPE_RESTRICTED,
        }:
            raise ContractError("SCM service SID is disabled")
    finally:
        if service:
            advapi.CloseServiceHandle(service)
        advapi.CloseServiceHandle(scm)
    sid_size = wintypes.DWORD()
    domain_size = wintypes.DWORD()
    use = wintypes.DWORD()
    advapi.LookupAccountNameW(None, f"NT SERVICE\\{service_name}", None,
                              ctypes.byref(sid_size), None, ctypes.byref(domain_size), ctypes.byref(use))
    if sid_size.value <= 0 or sid_size.value > 1024 or domain_size.value > 1024:
        raise ContractError("SCM service SID could not be resolved")
    sid = ctypes.create_string_buffer(sid_size.value)
    domain = ctypes.create_unicode_buffer(domain_size.value or 1)
    if not advapi.LookupAccountNameW(None, f"NT SERVICE\\{service_name}", sid,
                                     ctypes.byref(sid_size), domain, ctypes.byref(domain_size),
                                     ctypes.byref(use)):
        raise OSError(ctypes.get_last_error(), "cannot resolve configured SCM service SID")
    sid_text = wintypes.LPWSTR()
    if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
        raise OSError(ctypes.get_last_error(), "cannot format SCM service SID")
    try:
        result = sid_text.value
    finally:
        kernel.LocalFree(sid_text)
    if not isinstance(result, str) or not _SID_RE.fullmatch(result):
        raise ContractError("SCM returned an invalid service SID")
    return result


def assert_current_service_identity(identity: WindowsRoleIdentity) -> None:
    """Require this process to be the live SCM instance for the role SID."""
    if os.name != "nt" or not isinstance(identity, WindowsRoleIdentity):
        raise ContractError("current Windows service identity is unavailable")
    # Reuse the same token membership and SCM PID primitives used by the pipe
    # transport so a service-name string alone can never establish identity.
    from .windows_named_pipe import _service_process_id, _check_token_sid

    if identity.service_name != service_name_for_role(identity.role):
        raise ContractError("current Windows role identity does not match the fixed registry")
    if identity.service_sid != resolve_enabled_service_sid(identity.service_name):
        raise ContractError("current Windows service SID differs from current SCM configuration")
    advapi, kernel = _win_api()
    token = wintypes.HANDLE()
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.argtypes = []
    kernel.OpenProcessToken.restype = wintypes.BOOL
    kernel.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    if not kernel.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise OSError(ctypes.get_last_error(), "cannot inspect current VST service token")
    try:
        if not _check_token_sid(token, identity.service_sid):
            raise ContractError("current process token lacks the configured SCM service SID")
        if any(_check_token_sid(token, sid) for sid in ("S-1-5-18", "S-1-5-32-544")):
            raise ContractError("VST service token must not be LocalSystem or a local administrator")
    finally:
        kernel.CloseHandle(token)
    if os.getpid() != _service_process_id(identity.service_name):
        raise ContractError("current process is not the active SCM PID for this VST role")


def assert_path_acl(path: str, *, allowed_sids: set[str], writable_sids: set[str],
                    require_protected: bool = False) -> None:
    """Reject reparse traversal and ACL entries outside the explicit service policy.

    This is a verifier only: it never repairs or broadens an existing ACL.
    Callers provision paths separately and fail closed when the ACL differs.
    """
    if os.name != "nt" or not isinstance(path, str) or not os.path.isabs(path):
        raise ContractError("Windows ACL path must be absolute")
    advapi, kernel = _win_api()
    kernel.GetFileAttributesW.restype = wintypes.DWORD
    kernel.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    absolute = os.path.abspath(path)
    drive, tail = os.path.splitdrive(absolute)
    current = drive + os.sep
    for component in [part for part in tail.split(os.sep) if part]:
        current = os.path.join(current, component)
        attrs = kernel.GetFileAttributesW(current)
        if attrs == 0xFFFFFFFF or attrs & _FILE_ATTRIBUTE_REPARSE_POINT:
            raise ContractError("Windows protected path is unavailable or traverses a reparse point")
    owner = ctypes.c_void_p()
    group = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    result = advapi.GetNamedSecurityInfoW(
        # The owner is verified below, so it must be requested together with the DACL;
        # requesting only the DACL leaves the owner pointer NULL on every path.
        absolute, _SE_FILE_OBJECT, _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
        ctypes.byref(owner), ctypes.byref(group), ctypes.byref(dacl), None,
        ctypes.byref(descriptor),
    )
    if result != 0 or not descriptor:
        raise OSError(result or ctypes.get_last_error(), "cannot read Windows protected-path ACL")
    try:
        present = wintypes.BOOL()
        defaulted = wintypes.BOOL()
        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not advapi.GetSecurityDescriptorControl(
            descriptor, ctypes.byref(control), ctypes.byref(revision),
        ):
            raise ContractError("Windows protected-path security descriptor is malformed")
        if require_protected and not control.value & _SE_DACL_PROTECTED:
            raise ContractError("Windows protected service directory must block inherited ACL entries")
        if not advapi.GetSecurityDescriptorDacl(
            descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted),
        ) or not present.value or not dacl:
            raise ContractError("Windows protected path must have an explicit DACL")
        if not owner:
            raise ContractError("Windows protected path owner is unavailable")
        owner_text = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(owner, ctypes.byref(owner_text)):
            raise ContractError("Windows protected path owner SID is invalid")
        try:
            if owner_text.value.casefold() not in {sid.casefold() for sid in writable_sids}:
                raise ContractError("Windows protected path owner can alter its ACL")
        finally:
            kernel.LocalFree(owner_text)
        summary = _AclSizeInformation()
        if not advapi.GetAclInformation(
            dacl, ctypes.byref(summary), ctypes.sizeof(summary), _ACL_SIZE_INFORMATION,
        ) or summary.AceCount > 64:
            raise ContractError("Windows protected-path DACL is invalid or oversized")
        observed: set[str] = set()
        for index in range(summary.AceCount):
            ace = ctypes.c_void_p()
            if not advapi.GetAce(dacl, index, ctypes.byref(ace)) or not ace:
                raise ContractError("Windows protected-path ACE cannot be read")
            ace_type = ctypes.cast(ace, ctypes.POINTER(ctypes.c_ubyte)).contents.value
            if ace_type != _ACCESS_ALLOWED_ACE_TYPE:
                raise ContractError("Windows protected path contains a non-allow or unsupported ACE")
            mask = ctypes.cast(ctypes.c_void_p(ace.value + 4), ctypes.POINTER(wintypes.DWORD)).contents.value
            sid = ctypes.c_void_p(ace.value + 8)
            sid_text = wintypes.LPWSTR()
            if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
                raise OSError(ctypes.get_last_error(), "cannot read Windows protected-path trustee")
            try:
                trustee = sid_text.value
            finally:
                kernel.LocalFree(sid_text)
            if trustee not in allowed_sids:
                raise ContractError("Windows protected path grants access to an unauthorized trustee")
            if mask & _WRITE_ACCESS_MASK and trustee not in writable_sids:
                raise ContractError("Windows protected path is writable by a read-only service identity")
            observed.add(trustee)
        if not allowed_sids.issuperset(observed) or not writable_sids.issubset(observed):
            raise ContractError("Windows protected-path ACL does not include the required service trustees")
    finally:
        kernel.LocalFree(descriptor)


def read_signer_private_key(path: str, *, signer_sid: str, signer_root: str) -> bytes:
    """Read the HMAC key only after checking its Signer-only NTFS boundary."""
    if not isinstance(path, str) or not isinstance(signer_root, str):
        raise ContractError("Windows Signer key path configuration is invalid")
    absolute, root = os.path.abspath(path), os.path.abspath(signer_root)
    try:
        if os.path.commonpath((root, absolute)) != root or absolute == root:
            raise ContractError("Windows Signer key is outside its private root")
    except ValueError as exc:
        raise ContractError("Windows Signer key and root are on different volumes") from exc
    system_admin = {"S-1-5-18", "S-1-5-32-544"}
    assert_path_acl(root, allowed_sids=system_admin | {signer_sid},
                    writable_sids=system_admin | {signer_sid}, require_protected=True)
    assert_path_acl(absolute, allowed_sids=system_admin | {signer_sid},
                    writable_sids=system_admin)
    try:
        info = os.stat(absolute, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_size < 32 or info.st_size > 4096:
            raise ContractError("Windows Signer key must be a bounded regular file")
        with open(absolute, "rb") as stream:
            key = stream.read(4097)
    except OSError as exc:
        raise ContractError("Windows Signer private key is unavailable") from exc
    if len(key) < 32 or len(key) > 4096:
        raise ContractError("Windows Signer key has an invalid length")
    return key


def read_role_private_file(path: str, *, service_sid: str, service_root: str,
                           max_bytes: int = 65536) -> bytes:
    """Read a bounded secret under one role's protected NTFS directory."""
    if (not isinstance(path, str) or not isinstance(service_root, str)
            or type(max_bytes) is not int or not 32 <= max_bytes <= 1024 * 1024):
        raise ContractError("Windows role secret configuration is invalid")
    absolute, root = os.path.abspath(path), os.path.abspath(service_root)
    try:
        if os.path.commonpath((root, absolute)) != root or absolute == root:
            raise ContractError("Windows role secret is outside its private root")
    except ValueError as exc:
        raise ContractError("Windows role secret and root are on different volumes") from exc
    system_admin = {"S-1-5-18", "S-1-5-32-544"}
    assert_path_acl(root, allowed_sids=system_admin | {service_sid},
                    writable_sids=system_admin | {service_sid}, require_protected=True)
    assert_path_acl(absolute, allowed_sids=system_admin | {service_sid},
                    writable_sids=system_admin)
    try:
        info = os.stat(absolute, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_size < 32 or info.st_size > max_bytes:
            raise ContractError("Windows role secret must be a bounded regular file")
        with open(absolute, "rb") as stream:
            content = stream.read(max_bytes + 1)
    except OSError as exc:
        raise ContractError("Windows role secret is unavailable") from exc
    if len(content) < 32 or len(content) > max_bytes:
        raise ContractError("Windows role secret has an invalid length")
    return content


def _report_service_failure(advapi: Any, service_name: str, exc: BaseException) -> None:
    """Record a start/run failure in the Windows Application event log (best effort).

    The Application log is readable by local users, so only exception type names,
    code locations, ContractError messages (fixed, value-free strings in this
    codebase) and OSError errno/winerror codes are recorded. Other messages, and
    OSError text (it carries file paths), are omitted. Each entry is formatted
    independently so one unprintable exception cannot drop the whole event. A
    logging failure must not mask the stop status.
    """
    try:
        import traceback

        lines: list[str] = []
        current: BaseException | None = exc
        seen = 0
        while current is not None and seen < 5:
            seen += 1
            try:
                if isinstance(current, ContractError):
                    lines.append("%s: %s" % (type(current).__name__, current))
                elif isinstance(current, OSError):
                    lines.append("%s: errno=%s winerror=%s" % (
                        type(current).__name__, current.errno,
                        getattr(current, "winerror", None),
                    ))
                else:
                    lines.append("%s (message omitted)" % type(current).__name__)
                for frame in traceback.extract_tb(current.__traceback__)[-8:]:
                    lines.append("  at %s:%s in %s" % (
                        os.path.basename(frame.filename), frame.lineno, frame.name,
                    ))
            except Exception:
                lines.append("<unprintable %s>" % type(current).__name__)
            current = current.__cause__ or current.__context__
            if current is not None:
                lines.append("caused by:")
        text = ("VST service %s stopped: %s" % (service_name, "\n".join(lines)))[:4000]
        advapi.RegisterEventSourceW.restype = wintypes.HANDLE
        advapi.RegisterEventSourceW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        advapi.ReportEventW.restype = wintypes.BOOL
        advapi.ReportEventW.argtypes = [
            wintypes.HANDLE, wintypes.WORD, wintypes.WORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.WORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPCWSTR), wintypes.LPVOID,
        ]
        advapi.DeregisterEventSource.restype = wintypes.BOOL
        advapi.DeregisterEventSource.argtypes = [wintypes.HANDLE]
        source = advapi.RegisterEventSourceW(None, service_name)
        if not source:
            return
        try:
            strings = (wintypes.LPCWSTR * 1)(text)
            advapi.ReportEventW(source, 0x0001, 0, 1, None, 1, 0, strings, None)
        finally:
            advapi.DeregisterEventSource(source)
    except Exception:
        return


def run_scm_service(service_name: str, target_factory: Callable[[], Any]) -> None:
    """Run one real own-process service through StartServiceCtrlDispatcherW."""
    if os.name != "nt":
        raise ContractError("Windows SCM dispatcher is available only on Windows")
    if service_name not in _SERVICE_NAMES.values() or not callable(target_factory):
        raise ContractError("SCM entrypoint service is not a configured VST role")
    advapi, kernel = _win_api()
    SERVICE_WIN32_OWN_PROCESS = 0x10
    SERVICE_STOPPED, SERVICE_START_PENDING, SERVICE_RUNNING, SERVICE_STOP_PENDING = 1, 2, 4, 3
    SERVICE_ACCEPT_STOP = 0x1
    SERVICE_CONTROL_STOP = 0x1
    SERVICE_STATUS = type("SERVICE_STATUS", (ctypes.Structure,), {"_fields_": [
        ("dwServiceType", wintypes.DWORD), ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD), ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD), ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
    ]})
    SERVICE_STATUS_HANDLE = wintypes.HANDLE
    HANDLER = ctypes.WINFUNCTYPE(wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.LPVOID, wintypes.LPVOID)
    SERVICE_MAIN = ctypes.WINFUNCTYPE(None, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR))
    stop = threading.Event()
    target: Any = None
    status_handle = SERVICE_STATUS_HANDLE()

    def publish(state: int, accepted: int = 0, winerror: int = 0) -> None:
        status = SERVICE_STATUS(SERVICE_WIN32_OWN_PROCESS, state, accepted, winerror, 0, 0, 30000)
        if not advapi.SetServiceStatus(status_handle, ctypes.byref(status)):
            raise OSError(ctypes.get_last_error(), "cannot publish VST service status")

    advapi.RegisterServiceCtrlHandlerExW.restype = SERVICE_STATUS_HANDLE
    advapi.RegisterServiceCtrlHandlerExW.argtypes = [wintypes.LPCWSTR, HANDLER, wintypes.LPVOID]
    advapi.SetServiceStatus.restype = wintypes.BOOL
    advapi.SetServiceStatus.argtypes = [SERVICE_STATUS_HANDLE, ctypes.POINTER(SERVICE_STATUS)]

    @HANDLER
    def control(code: int, _event_type: int, _event_data: Any, _context: Any) -> int:
        if code == SERVICE_CONTROL_STOP:
            stop.set()
            if target is not None:
                target.shutdown()
            try:
                publish(SERVICE_STOP_PENDING)
            except Exception:
                return 1
        return 0

    @SERVICE_MAIN
    def service_main(_argc: int, _argv: Any) -> None:
        nonlocal status_handle, target
        status_handle = advapi.RegisterServiceCtrlHandlerExW(service_name, control, None)
        if not status_handle:
            return
        try:
            publish(SERVICE_START_PENDING)
            role = next((name for name, configured in _SERVICE_NAMES.items()
                         if configured == service_name), None)
            if role is None:
                raise ContractError("SCM service role is not in the fixed registry")
            assert_current_service_identity(WindowsRoleIdentity(
                role, service_name, resolve_enabled_service_sid(service_name),
                _ROLE_PIPE_NAMES[role],
            ))
            target = target_factory()
            publish(SERVICE_RUNNING, SERVICE_ACCEPT_STOP)
            target.serve_forever()
            publish(SERVICE_STOPPED)
        except Exception as exc:
            # Never fail silently: SCM itself only reports "Incorrect function".
            _report_service_failure(advapi, service_name, exc)
            try:
                publish(SERVICE_STOPPED, winerror=1)
            except Exception:
                pass

    class _ServiceTable(ctypes.Structure):
        _fields_ = [("lpServiceName", wintypes.LPWSTR), ("lpServiceProc", SERVICE_MAIN)]

    table = (_ServiceTable * 2)(
        _ServiceTable(service_name, service_main), _ServiceTable(None, SERVICE_MAIN()),
    )
    advapi.StartServiceCtrlDispatcherW.restype = wintypes.BOOL
    advapi.StartServiceCtrlDispatcherW.argtypes = [ctypes.POINTER(_ServiceTable)]
    if not advapi.StartServiceCtrlDispatcherW(table):
        raise OSError(ctypes.get_last_error(), "SCM dispatcher refused the VST service")


def service_name_for_role(role: str) -> str:
    try:
        return _SERVICE_NAMES[role]
    except (KeyError, TypeError) as exc:
        raise ContractError("unknown Windows VST service role") from exc


def role_names() -> Mapping[str, str]:
    """Return an immutable copy of the fixed SCM role-name contract."""
    from types import MappingProxyType

    return MappingProxyType(dict(_SERVICE_NAMES))


def main() -> None:
    """SCM image entrypoint: route one fixed service role to its real factory."""
    if os.name != "nt":
        raise ContractError("Windows SCM service host is available only on Windows")
    if len(sys.argv) != 3 or sys.argv[1] != "--role":
        raise ContractError("SCM host requires exactly --role <configured-service-role>")
    role = sys.argv[2]
    modules = {
        "owner": (".dispatch_owner_service", []),
        "supervisor": (".supervisor_service", []),
        "dispatcher": (".dispatcher_service", []),
        "runner": (".runner_service", ["runner"]),
        "signer": (".signer", []),
        "worker": (".runner_service", ["worker"]),
    }
    try:
        module_name, role_arguments = modules[role]
        service = import_module(module_name, package=__package__)
    except (KeyError, ImportError) as exc:
        raise ContractError("SCM role is not available in the local runtime") from exc
    sys.argv = [sys.argv[0], "--windows-scm", *role_arguments]
    try:
        service.main()
    except Exception as exc:
        # Failures before run_scm_service (config load, ACL checks, key reads) would
        # otherwise reach SCM only as "service did not respond"; record them first.
        try:
            advapi, _kernel = _win_api()
            _report_service_failure(advapi, service_name_for_role(role), exc)
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
