"""Windows-local (no WSL) sandbox-bound proof for one worker run (S3-D).

GUARANTEE (read first): this is Windows-local isolation built from a separate
non-admin local account, NTFS ACLs, a per-account outbound firewall rule and a
Job Object. It is WEAKER than the S2 WSL/VM sandbox spec (no separate kernel, no
mount/namespace isolation, same machine and same registry/OS). It proves only
what the recorded inventories show at the recorded time for the recorded run id
and candidate revision; it is not a security boundary against a kernel exploit.

Layout:
- pure checkers (take inventory dicts, return per-check verdicts);
- read-only collectors (never create accounts, change ACLs or firewall rules);
- a report builder returning a JSON-serializable probe record.

Every public function refuses with ContractError on a non-Windows platform and
on missing, malformed or ambiguous evidence; none returns success on error.
Standard library only; Windows APIs via ctypes / System32 executables.
"""

from __future__ import annotations

import csv
import ctypes
import ipaddress
import json
import math
import ntpath
import os
import re
import socket
import subprocess
import sys
import time
from typing import Any, Callable

from .contracts import ContractError

SCHEMA = "VST_S3_WINDOWS_SANDBOX_PROOF_V1"
GUARANTEE = (
    "Windows-local isolation (separate non-admin account, NTFS ACLs, per-account "
    "outbound firewall rule, Job Object). It is weaker than the S2 WSL/VM sandbox "
    "specification: no separate kernel, no namespace or mount isolation, shared "
    "host OS. It proves only the recorded inventories for the recorded run id and "
    "candidate revision at the recorded time."
)
KNOWN_LIMITS = (
    "Host-path writability is sampled over the supplied host_paths, not exhaustive.",
    "The blocked external probe cannot by itself distinguish a firewall block from a non-routable address; the firewall rule inventory is the primary evidence.",
    "Job Object inventory is read from inside the probed process; parent-job chains are not enumerated.",
    "Egress and Job probes are valid only when executed as the worker account (identity is checked).",
    "IPC endpoints (named pipes, loopback TCP ports, container sockets) are not covered by any check.",
    "Service-mediated egress (for example the DNS Client service) is not blocked by a per-account firewall rule.",
    "Children of protected directories and owner / OWNER RIGHTS are not examined.",
    "The worker probe is a self-report: not authenticated, no verifier nonce, record unsigned.",
    "ACL evaluation is a static model of the token, not AuthzAccessCheck.",
    "RunRoot sibling isolation between runs depends on the provisioning ACL.",
)

BLOCKED_EGRESS_TARGET = ("192.0.2.1", 9)  # TEST-NET-1 documentation range (RFC 5737)
ADMIN_GROUP_SID = "S-1-5-32-544"
# Everyone, Authenticated Users, Users, plus well-known SIDs a local logon token carries:
# Local account, INTERACTIVE, BATCH, NETWORK, LOCAL, CONSOLE LOGON, This Organization.
IMPLICIT_SIDS = frozenset({"S-1-1-0", "S-1-5-11", "S-1-5-32-545", "S-1-5-113", "S-1-5-4", "S-1-5-3",
                           "S-1-5-2", "S-1-2-0", "S-1-2-1", "S-1-5-15"})
# Backup/Server/Account/Print Operators, Replicators, Network Config Operators, Power Users, Hyper-V Admins.
PRIVILEGED_GROUP_SIDS = frozenset({
    "S-1-5-32-551", "S-1-5-32-549", "S-1-5-32-548", "S-1-5-32-550", "S-1-5-32-552",
    "S-1-5-32-556", "S-1-5-32-547", "S-1-5-32-578"})
PRIVILEGED_GROUP_NAMES = frozenset({"docker-users"})
MIN_NESTED_JOB_BUILD = 9200  # Windows 8 / Server 2012: nested Job Objects supported
MAX_WALK_ENTRIES = 500_000
CLOCK_SKEW_SEC = 5.0

_SID_RE = re.compile(r"S-1-\d+(-\d+)+", re.IGNORECASE | re.ASCII)
_HEX40 = re.compile(r"[0-9a-f]{40}", re.ASCII)
_RUN_ID = re.compile(r"[A-Za-z0-9._-]{1,128}", re.ASCII)
_ACCOUNT = re.compile(r"[A-Za-z0-9._-]{1,20}", re.ASCII)

_READ_TOKENS = frozenset({"R", "RX", "GR", "GE", "RD", "REA", "RA", "X", "RC"})
_WRITE_TOKENS = frozenset({"W", "D", "GW", "WD", "AD", "WEA", "WA", "DC", "WDAC", "WO", "DE"})
_BOTH_TOKENS = frozenset({"F", "M", "GA"})
_IGNORED_TOKENS = frozenset({"N", "S"})
_ICACLS_FLAGS = frozenset({"OI", "CI", "IO", "NP", "I"})


# --------------------------------------------------------------------------- basics

def _is_windows() -> bool:
    """True on Windows; tests may replace this to exercise the refusal path."""
    return sys.platform == "win32"


def _require_windows() -> None:
    """Raise ContractError on any non-Windows platform."""
    if not _is_windows():
        raise ContractError("windows sandbox proof requires a Windows host")


def _need(data: Any, key: str, kind: type | tuple[type, ...], where: str) -> Any:
    """Return data[key] if present with the exact type (bool is not an int); else ContractError."""
    if not isinstance(data, dict) or key not in data:
        raise ContractError(f"{where}: missing field {key!r}")
    value = data[key]
    kinds = kind if isinstance(kind, tuple) else (kind,)
    if isinstance(value, bool) and bool not in kinds:
        raise ContractError(f"{where}: field {key!r} must not be bool")
    if not isinstance(value, kinds):
        raise ContractError(f"{where}: field {key!r} has wrong type")
    return value


def _sid(value: Any, where: str) -> str:
    """Validate and upper-case a SID string; ContractError otherwise."""
    if not isinstance(value, str) or not _SID_RE.fullmatch(value):
        raise ContractError(f"{where}: invalid SID")
    return value.upper()


def _sub(sub_id: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"id": sub_id, "ok": bool(ok), "detail": detail}


def _verdict(check: str, subs: list[dict[str, Any]]) -> dict[str, Any]:
    """PASS only when every sub-check passed; sub-checks fail separately."""
    if not subs:
        raise ContractError(f"{check}: no sub-checks evaluated")
    return {"check": check, "result": "PASS" if all(s["ok"] for s in subs) else "FAIL", "subchecks": subs}


def _system32(exe: str) -> str:
    root = os.environ.get("SystemRoot")
    if not root:
        raise ContractError("SystemRoot is not set")
    return os.path.join(root, "System32", exe)


def _powershell_exe() -> str:
    return os.path.join(os.path.dirname(_system32("x")), "WindowsPowerShell", "v1.0", "powershell.exe")


def _run(args: list[str], *, timeout: float = 60.0, encoding: str = "oem") -> str:
    """Run a read-only command; ContractError on spawn failure, timeout or non-zero exit."""
    try:
        proc = subprocess.run(
            args, capture_output=True, timeout=timeout, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ContractError(f"command failed to run: {os.path.basename(args[0])}: {exc}") from exc
    if proc.returncode != 0:
        tail = proc.stderr.decode(encoding, "replace").strip()[-300:]
        raise ContractError(f"{os.path.basename(args[0])} exited {proc.returncode}: {tail}")
    return proc.stdout.decode(encoding, "replace")


def _run_powershell_json(script: str, *, timeout: float = 180.0) -> Any:
    """Run a read-only PowerShell script that prints one JSON document; ContractError otherwise."""
    prefix = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;$ErrorActionPreference='Stop';"
    encoded = (prefix + script).encode("utf-16-le")
    import base64
    cmd = [_powershell_exe(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-EncodedCommand", base64.b64encode(encoded).decode("ascii")]
    text = _run(cmd, timeout=timeout, encoding="utf-8-sig").strip()
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ContractError("PowerShell did not return valid JSON") from exc


def _as_list(value: Any) -> list[Any]:
    """PowerShell collapses one-element arrays; normalize None/dict/list to list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _validate_account_name(name: Any) -> str:
    if not isinstance(name, str) or not _ACCOUNT.fullmatch(name):
        raise ContractError("worker account name must match [A-Za-z0-9._-]{1,20}")
    return name


def _validate_run_binding(run_id: Any, candidate_sha: Any) -> None:
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id) or run_id in (".", ".."):
        raise ContractError("run_id must match [A-Za-z0-9._-]{1,128} and not be '.' or '..'")
    if not isinstance(candidate_sha, str) or not _HEX40.fullmatch(candidate_sha):
        raise ContractError("candidate_sha must be a lowercase 40-hex git object id")


# ------------------------------------------------------------ ACL data and rights

_STATUS_OK = re.compile(r"Successfully processed (\d+) files?(?:; Failed processing (\d+) files?)?", re.IGNORECASE)
_STATUS_FAIL = re.compile(r"Failed processing (\d+) files?", re.IGNORECASE)


def _parse_icacls(text: str, path: str) -> tuple[list[dict[str, Any]], bool]:
    """Parse `icacls <path>` output into (entries, complete); complete needs a clean status line."""
    _require_windows()
    entries: list[dict[str, Any]] = []
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    if not lines or not lines[0].lower().startswith(path.lower()):
        raise ContractError("icacls output does not echo the requested path")
    lines[0] = lines[0][len(path):]
    pattern = re.compile(r"^\s*(?P<name>.+?):(?P<perms>(?:\([^)]*\))+)\s*$")
    status_ok, failed = False, 0
    for line in lines:
        if not line.strip():
            continue  # remainder of the echoed-path line
        match = pattern.match(line)
        if not match:
            ok = _STATUS_OK.fullmatch(line.strip())
            bad = _STATUS_FAIL.fullmatch(line.strip())
            if ok:
                status_ok, failed = True, failed + int(ok.group(2) or 0)
            elif bad:
                status_ok, failed = True, failed + int(bad.group(1))
            else:
                raise ContractError("icacls output has an unrecognized line")
            continue
        groups = re.findall(r"\(([^)]*)\)", match.group("perms"))
        tokens = [t.strip().upper() for g in groups for t in g.split(",") if t.strip()]
        kind = "deny" if "DENY" in tokens else "allow"
        flags = [t for t in tokens if t in _ICACLS_FLAGS]
        rights = [t for t in tokens if t not in _ICACLS_FLAGS and t != "DENY"]
        if kind == "allow" and rights == ["N"]:
            # icacls prints a deny-all ACE as (N) without a DENY marker.
            kind, rights = "deny", ["F"]
        entries.append({"name": match.group("name").strip(), "type": kind, "rights": rights, "flags": flags})
    if not entries:
        raise ContractError("icacls output contained no ACE lines")
    return entries, status_ok and failed == 0


def parse_icacls_output(text: str, path: str) -> list[dict[str, Any]]:
    """Parse `icacls <path>` output into [{name, type, rights, flags}].

    Failure mode: ContractError when the first line does not echo `path`, no ACE
    line parses, or any line is neither an ACE nor a known status line.
    """
    return _parse_icacls(text, path)[0]


def _classes(rights: Any, where: str) -> set[str]:
    """Map right tokens to {'read','write'}; unknown tokens fail closed as both."""
    if not isinstance(rights, list) or not all(isinstance(r, str) for r in rights):
        raise ContractError(f"{where}: rights must be a list of strings")
    out: set[str] = set()
    for raw in rights:
        token = raw.strip().upper()
        if token in _IGNORED_TOKENS:
            continue
        if token in _BOTH_TOKENS:
            out |= {"read", "write"}
        elif token in _READ_TOKENS:
            out.add("read")
        elif token in _WRITE_TOKENS:
            out.add("write")
        else:
            out |= {"read", "write"}
    return out


def _denied_classes(rights: Any, where: str) -> set[str]:
    """Classes a deny removes: only tokens covering the WHOLE class (F, M, GA remove both).

    W/GW alone leave DELETE/WRITE_DAC/WRITE_OWNER and R/GR/RX alone are partial, so they
    remove nothing (conservative: more FAILs).
    """
    if not isinstance(rights, list) or not all(isinstance(r, str) for r in rights):
        raise ContractError(f"{where}: rights must be a list of strings")
    out: set[str] = set()
    for raw in rights:
        if raw.strip().upper() in _BOTH_TOKENS:
            out |= {"read", "write"}
    return out


def _worker_principals(worker: dict[str, Any]) -> set[str]:
    """SIDs through which the worker token can receive access (self, groups, implicit groups)."""
    sids = {_sid(_need(worker, "sid", str, "worker"), "worker.sid")} | set(IMPLICIT_SIDS)
    for grp in _need(worker, "groups", list, "worker"):
        sids.add(_sid(_need(grp, "sid", str, "worker.groups"), "worker.groups.sid"))
    return sids


def _effective_access(entries: Any, principals: set[str], where: str) -> tuple[set[str], int]:
    """Return (allowed minus denied classes for the worker, count of unresolved principals)."""
    if not isinstance(entries, list):
        raise ContractError(f"{where}: entries must be a list")
    allowed: set[str] = set()
    denied: set[str] = set()
    unresolved = 0
    for ent in entries:
        raw_sid = _need(ent, "sid", (str, type(None)), where)
        kind = _need(ent, "type", str, where)
        if kind not in ("allow", "deny"):
            raise ContractError(f"{where}: entry type must be allow or deny")
        if raw_sid is None:
            unresolved += 1
            continue
        if _sid(raw_sid, where) not in principals:
            continue
        rights = _need(ent, "rights", list, where)
        if kind == "allow":
            allowed.update(_classes(rights, where))
            continue
        flags = ent.get("flags")
        if isinstance(flags, list) and any(str(f).upper() == "IO" for f in flags):
            continue  # inherit-only deny does not apply to the object itself
        denied.update(_denied_classes(rights, where))
    return allowed - denied, unresolved


def _check_acl_paths(paths: Any, worker: dict[str, Any], classes: set[str], prefix: str) -> list[dict[str, Any]]:
    """One sub-check per path: worker holds none of `classes` and evidence is complete."""
    if not isinstance(paths, list) or not paths:
        raise ContractError(f"{prefix}: at least one path inventory is required")
    principals = _worker_principals(worker)
    subs = []
    for item in paths:
        path = _need(item, "path", str, prefix)
        complete = _need(item, "complete", bool, prefix)
        if not complete:
            subs.append(_sub(f"{prefix}:{path}", False, "ACL evidence incomplete"))
            continue
        effective, unresolved = _effective_access(_need(item, "entries", list, prefix), principals, prefix)
        hit = sorted(effective & classes)
        if unresolved:
            subs.append(_sub(f"{prefix}:{path}", False, f"{unresolved} ACL principal(s) unresolved"))
        elif hit:
            subs.append(_sub(f"{prefix}:{path}", False, "worker has " + "/".join(hit) + " access"))
        else:
            subs.append(_sub(f"{prefix}:{path}", True, "no worker access"))
    return subs


# ------------------------------------------------------------------ pure checkers

def check_worker_account(inv: dict[str, Any]) -> dict[str, Any]:
    """(a) Worker is a distinct, enabled, local, non-admin account and not the runner.

    inv = {"worker": {name,sid,enabled,is_local,groups:[{sid,name}],groups_complete},
           "runner": {name,sid}}. Failure: ContractError on malformed input; FAIL per sub-check.
    """
    _require_windows()
    worker = _need(inv, "worker", dict, "account")
    runner = _need(inv, "runner", dict, "account")
    wsid = _sid(_need(worker, "sid", str, "worker"), "worker.sid")
    rsid = _sid(_need(runner, "sid", str, "runner"), "runner.sid")
    wname = _need(worker, "name", str, "worker").lower()
    rname = _need(runner, "name", str, "runner").lower()
    groups = {_sid(_need(g, "sid", str, "worker.groups"), "worker.groups.sid") for g in _need(worker, "groups", list, "worker")}
    complete = _need(worker, "groups_complete", bool, "worker")
    is_admin = ADMIN_GROUP_SID in groups or wsid.endswith("-500")
    privileged = sorted(groups & PRIVILEGED_GROUP_SIDS)
    for g in _need(worker, "groups", list, "worker"):
        gname = g.get("name") if isinstance(g, dict) else None
        if isinstance(gname, str) and gname.lower().split("\\")[-1] in PRIVILEGED_GROUP_NAMES:
            privileged.append(gname)
    return _verdict("worker_account", [
        _sub("is_local", _need(worker, "is_local", bool, "worker"), "local account required"),
        _sub("enabled", _need(worker, "enabled", bool, "worker"), "account must be enabled"),
        _sub("group_evidence_complete", complete, "group membership must be fully enumerated"),
        _sub("not_admin", complete and not is_admin, "not in Administrators and not RID 500"),
        _sub("no_privileged_groups", complete and not privileged,
             "privileged: " + ", ".join(privileged) if privileged else "no operator/privileged group membership"),
        _sub("distinct_from_runner", wsid != rsid and wname.split("\\")[-1] != rname.split("\\")[-1],
             "worker SID and name differ from runner"),
    ])


def check_secret_isolation(acl: dict[str, Any], worker: dict[str, Any]) -> dict[str, Any]:
    """(b) Signing key / signer endpoint / store paths: worker has neither read nor write.

    acl = {"paths": [{path, complete, entries:[{sid, type?, rights}]}]}; entries need
    explicit "type" (allow|deny). Failure: incomplete or unresolved ACL evidence fails.
    """
    _require_windows()
    subs = _check_acl_paths(_need(acl, "paths", list, "acl"), worker, {"read", "write"}, "no_worker_access")
    return _verdict("secret_isolation", subs)


def _inside(child: str, parent: str) -> bool:
    """Case-insensitive Windows containment test on normalized absolute paths."""
    c, p = ntpath.normcase(ntpath.normpath(child)), ntpath.normcase(ntpath.normpath(parent))
    if not (ntpath.isabs(c) and ntpath.isabs(p)):
        raise ContractError("paths must be absolute")
    try:
        return ntpath.commonpath([c, p]) == p
    except ValueError:  # different drives
        return False


def _require_deep_dir(path: str, what: str) -> None:
    """Refuse a drive/share root or a path with fewer than 2 components below the drive."""
    drive, rest = ntpath.splitdrive(ntpath.normpath(path))
    if not drive or len([p for p in rest.split("\\") if p]) < 2:
        raise ContractError(f"{what} must be at least two levels below the drive root")


def check_worktree_confinement(inv: dict[str, Any], worker: dict[str, Any]) -> dict[str, Any]:
    """(c) Worktree inside run dir, no escaping reparse point, no sampled host path writable.

    inv = {run_dir, run_dir_real, worktree, worktree_real, walk_complete,
           reparse_points:[{path,target}], host_paths:[acl path items]}.
    Failure: unresolved reparse target counts as escaping; empty host_paths is ContractError.
    """
    _require_windows()
    run_real = _need(inv, "run_dir_real", str, "worktree")
    wt_real = _need(inv, "worktree_real", str, "worktree")
    _require_deep_dir(run_real, "run_dir_real")
    subs = [
        _sub("worktree_inside_run_dir", _inside(wt_real, run_real), "real worktree path under real run dir"),
        _sub("run_dir_not_aliased",
             ntpath.normcase(ntpath.normpath(_need(inv, "run_dir", str, "worktree"))) == ntpath.normcase(ntpath.normpath(run_real)),
             "run dir has no reparse alias"),
        _sub("walk_complete", _need(inv, "walk_complete", bool, "worktree"), "full tree walk required"),
    ]
    escaping = []
    for rp in _need(inv, "reparse_points", list, "worktree"):
        target = _need(rp, "target", (str, type(None)), "reparse_points")
        rp_path = _need(rp, "path", str, "reparse_points")
        if target is None or not _inside(target, wt_real):
            escaping.append(rp_path)
    subs.append(_sub("no_escaping_reparse", not escaping, "escaping: " + ", ".join(escaping) if escaping else "none"))
    host = _need(inv, "host_paths", list, "worktree")
    subs.extend(_check_acl_paths(host, worker, {"write"}, "host_path_not_writable"))
    return _verdict("worktree_confinement", subs)


def _is_loopback(addr: str) -> bool:
    """True only when every endpoint (and its whole CIDR prefix) is loopback; anything unparsable is False."""
    for raw in addr.split("-"):
        tok = raw.strip().lower()
        if tok == "localhost":
            continue
        try:
            if "/" in tok:
                net = ipaddress.ip_network(tok, strict=False)
                ok = net[0].is_loopback and net[-1].is_loopback
            else:
                ok = ipaddress.ip_address(tok).is_loopback
        except ValueError:
            return False
        if not ok:
            return False
    return True


def _intervals(addresses: list[str]) -> tuple[list[tuple[int, int]], list[tuple[int, int]], bool]:
    """Parse firewall RemoteAddress tokens to merged v4/v6 integer intervals; third value = 'Any'."""
    v4: list[tuple[int, int]] = []
    v6: list[tuple[int, int]] = []
    for token in addresses:
        tok = str(token).strip()
        if tok.lower() == "any":
            return [], [], True
        try:
            if "-" in tok:
                lo_s, hi_s = tok.split("-", 1)
                lo, hi = ipaddress.ip_address(lo_s.strip()), ipaddress.ip_address(hi_s.strip())
            elif "/" in tok:
                net = ipaddress.ip_network(tok, strict=False)
                lo, hi = net[0], net[-1]
            else:
                lo = hi = ipaddress.ip_address(tok)
        except ValueError:
            continue  # keyword such as LocalSubnet: contributes no coverage (fail closed)
        if lo.version != hi.version:
            continue
        (v4 if lo.version == 4 else v6).append((int(lo), int(hi)))
    return v4, v6, False


def _covers(ivs: list[tuple[int, int]], lo: int, hi: int) -> bool:
    need = lo
    for a, b in sorted(ivs):
        if a > need:
            break
        need = max(need, b + 1)
        if need > hi:
            return True
    return need > hi


def _covers_non_loopback(addresses: list[str]) -> bool:
    """True when the address set covers every IPv4/IPv6 address except loopback."""
    v4, v6, any_addr = _intervals(addresses)
    if any_addr:
        return True
    return (_covers(v4, 0, 0x7EFFFFFF) and _covers(v4, 0x80000000, 0xFFFFFFFF)
            and _covers(v6, 2, (1 << 128) - 1))


_RULE_UNRESTRICTED_FIELDS = ("protocol", "local_port", "remote_port", "program", "service",
                             "interface_type", "local_address")


def _unrestricted(value: Any) -> bool:
    """True for the Any / empty form of a firewall filter field (a list must hold only such tokens)."""
    items = value if isinstance(value, list) else [value]
    return all(x is None or str(x).strip().lower() in ("", "any", "*") for x in items)


def _profile_covers(value: Any, profiles: list[Any]) -> bool:
    """Rule Profile covers Any, All, or every enabled firewall profile."""
    items = value if isinstance(value, list) else [value]
    tokens = {t.strip().lower() for x in items for t in str(x).split(",") if t.strip()}
    if tokens & {"any", "all"}:
        return True
    active = {str(p.get("name", "")).strip().lower() for p in profiles if isinstance(p, dict) and p.get("enabled") is True}
    return bool(active) and active <= tokens


def _rule_is_unrestricted(rule: dict[str, Any], profiles: list[Any]) -> bool:
    """Block rule counts as covering only when every filter field is in its unrestricted form (missing = restricted)."""
    if any(f not in rule or not _unrestricted(rule[f]) for f in _RULE_UNRESTRICTED_FIELDS):
        return False
    if "package" in rule and not _unrestricted(rule["package"]):
        return False  # Package is read when the platform exposes it
    return "profile" in rule and _profile_covers(rule["profile"], profiles)


def _sddl_binding(sddl: Any, wsid: str) -> tuple[bool, bool, bool]:
    """Parse a LocalUser SDDL into (unrestricted, bound, ambiguous).

    bound only through an A ACE whose trustee is exactly the worker SID. Any D ACE, any
    other ACE type, or unparsable text is ambiguous (fail closed: block rules do not apply).
    """
    if sddl is None or str(sddl).strip().lower() == "any":
        return True, False, False
    text = str(sddl)
    idx = text.upper().find("D:")
    aces = re.findall(r"\(([^()]*)\)", text[idx + 2:]) if idx >= 0 else []
    if idx < 0 or not aces:
        return False, False, True
    bound = ambiguous = False
    for ace in aces:
        fields = ace.split(";")
        if len(fields) < 6 or fields[0].upper() not in ("A", "D"):
            ambiguous = True
        elif fields[0].upper() == "D":
            ambiguous = True
        elif fields[5].strip().upper() == wsid:
            bound = True
    return False, bound and not ambiguous, ambiguous


def check_egress(fw: dict[str, Any], probe: dict[str, Any], worker: dict[str, Any]) -> dict[str, Any]:
    """(d) Per-account default-deny outbound plus blocked-external and loopback-canary probe results.

    fw = {"profiles":[{name,enabled}], "rules":[{name,enabled,direction,action,profile,protocol,
          local_port,remote_port,program,service,interface_type,local_address,
          local_user_sddl|None,remote_addresses:[..]}]}
    probe = {identity_sid, loopback_canary_ok, external_connected, external_errno}.
    Windows Firewall has no account-wide default outbound action, so default-deny is
    proven as an enabled, otherwise-unrestricted Block rule applicable to the worker covering
    all non-loopback addresses, no worker-bound Allow rule to a non-loopback address, and the
    probes. Only errno 10013 (WSAEACCES) counts as blocked; a timeout or other error is inconclusive.
    """
    _require_windows()
    wsid = _sid(_need(worker, "sid", str, "worker"), "worker.sid")
    profiles = _need(fw, "profiles", list, "firewall")
    if not profiles:
        raise ContractError("firewall: no profiles enumerated")
    block_ok, allow_bad = False, []
    for rule in _need(fw, "rules", list, "firewall"):
        if not (_need(rule, "enabled", bool, "rule") and str(_need(rule, "direction", str, "rule")).lower() == "outbound"):
            continue
        sddl = _need(rule, "local_user_sddl", (str, type(None)), "rule")
        unrestricted, bound, ambiguous = _sddl_binding(sddl, wsid)
        applies = (unrestricted or bound) and not ambiguous
        action = str(_need(rule, "action", str, "rule")).lower()
        remote = [str(a) for a in _need(rule, "remote_addresses", list, "rule")]
        if action == "block" and applies and _rule_is_unrestricted(rule, profiles) and _covers_non_loopback(remote):
            block_ok = True
        if action == "allow" and (bound or ambiguous) and (not remote or not all(_is_loopback(a) for a in remote)):
            allow_bad.append(_need(rule, "name", str, "rule"))
    ext_errno = probe.get("external_errno") if isinstance(probe, dict) else None
    connected = _need(probe, "external_connected", bool, "probe")
    errno_ok = isinstance(ext_errno, int) and not isinstance(ext_errno, bool) and ext_errno == 10013
    return _verdict("egress", [
        _sub("firewall_profiles_enabled", all(_need(p, "enabled", bool, "profile") for p in profiles), "all profiles on"),
        _sub("worker_block_rule_covers_non_loopback", block_ok, "enabled unrestricted outbound Block rule for worker"),
        _sub("no_worker_allow_rule_non_loopback", not allow_bad, "allow rules: " + ", ".join(allow_bad) if allow_bad else "none"),
        _sub("probe_ran_as_worker", _sid(_need(probe, "identity_sid", str, "probe"), "probe.identity_sid") == wsid,
             "probe identity equals worker SID"),
        _sub("external_blocked", connected is False and errno_ok,
             f"connect refused by policy (errno {ext_errno})" if connected is False and errno_ok
             else f"INCONCLUSIVE: connected={connected}, errno {ext_errno} (only 10013 proves a block)"),
        _sub("loopback_canary_ok", _need(probe, "loopback_canary_ok", bool, "probe") is True, "loopback canary succeeded"),
    ])


def check_probe_binding(meta: dict[str, Any], *, run_id: str, candidate_sha: str,
                        now: float, max_age_sec: float) -> dict[str, Any]:
    """(e) Probe bound to run id, candidate SHA and freshness window; stale or missing -> FAIL/refuse.

    meta = {run_id, candidate_sha, observed_at_epoch}. Failure: ContractError for
    malformed expectations or meta; future-dated (> 5 s skew) probes are not fresh.
    """
    _require_windows()
    _validate_run_binding(run_id, candidate_sha)
    if isinstance(max_age_sec, bool) or not isinstance(max_age_sec, (int, float)):
        raise ContractError("max_age_sec must be a number")
    observed = _need(meta, "observed_at_epoch", (int, float), "probe_meta")
    if isinstance(now, bool) or not isinstance(now, (int, float)):
        raise ContractError("now must be a number")
    try:
        finite = math.isfinite(max_age_sec) and math.isfinite(observed) and math.isfinite(now)
    except OverflowError:
        finite = False
    if not finite or not 0 < max_age_sec <= 86400:
        raise ContractError("max_age_sec must be finite and in (0, 86400]; now/observed must be finite")
    if abs(observed) >= 1e12:
        raise ContractError("observed_at_epoch is out of range")
    age = now - observed
    return _verdict("probe_binding", [
        _sub("run_id_matches", _need(meta, "run_id", str, "probe_meta") == run_id, "run id bound"),
        _sub("candidate_sha_matches", _need(meta, "candidate_sha", str, "probe_meta") == candidate_sha, "candidate revision bound"),
        _sub("fresh", -CLOCK_SKEW_SEC <= age <= max_age_sec, f"age {age:.1f}s, window {max_age_sec}s"),
    ])


def check_job_object(inv: dict[str, Any]) -> dict[str, Any]:
    """(f) Process is in a Job Object with kill-on-close, process-count and memory limits; nesting supported.

    inv = {in_job, windows_build, nesting_supported, limits:{kill_on_job_close,
    active_process_limit, process_memory_limit, job_memory_limit, process_time_limit_100ns,
    job_time_limit_100ns}}. Failure: unsupported nesting or any missing limit -> FAIL.
    """
    _require_windows()
    lim = _need(inv, "limits", dict, "job")
    in_job = _need(inv, "in_job", bool, "job")
    mem = max(_need(lim, "process_memory_limit", int, "limits"), _need(lim, "job_memory_limit", int, "limits"))
    breakaway = _need(lim, "breakaway_ok", bool, "limits")
    silent = _need(lim, "silent_breakaway_ok", bool, "limits")
    return _verdict("job_object", [
        _sub("in_job", in_job, "process must be assigned to a Job Object"),
        _sub("nesting_supported", _need(inv, "nesting_supported", bool, "job")
             and _need(inv, "windows_build", int, "job") >= MIN_NESTED_JOB_BUILD, "nested jobs need Windows 8+"),
        _sub("kill_on_job_close", _need(lim, "kill_on_job_close", bool, "limits"), "children die with the job"),
        _sub("active_process_limit", _need(lim, "active_process_limit", int, "limits") > 0, "process count capped"),
        _sub("memory_limit", mem > 0, "process or job memory capped"),
        _sub("no_breakaway", not breakaway and not silent,
             f"breakaway_ok={breakaway}, silent_breakaway_ok={silent}"),
    ])


# ------------------------------------------------------------------ collectors

def _identity() -> tuple[str, str]:
    """(name, SID) of the calling process token via `whoami /user`; ContractError if unparsable."""
    out = _run([_system32("whoami.exe"), "/user", "/fo", "csv", "/nh"], timeout=15)
    rows = list(csv.reader(out.strip().splitlines()))
    if len(rows) != 1 or len(rows[0]) != 2:
        raise ContractError("unexpected whoami output")
    return rows[0][0], _sid(rows[0][1], "whoami sid")


def collect_account_inventory(worker_name: str) -> dict[str, Any]:
    """Read-only: worker local-account facts and runner identity. ContractError if the account is missing."""
    _require_windows()
    name = _validate_account_name(worker_name)
    script = (
        f"$u=Get-LocalUser -Name '{name}';$gs=@();$complete=$true;"
        "foreach($g in Get-LocalGroup){try{$m=@(Get-LocalGroupMember -Group $g.Name|"
        "Where-Object{$_.SID.Value -eq $u.SID.Value});"
        "if($m.Count -gt 0){$gs+=[pscustomobject]@{name=$g.Name;sid=$g.SID.Value}}}"
        "catch{if($g.SID.Value -eq 'S-1-5-32-544'){throw};$complete=$false}};"
        "[pscustomobject]@{name=$u.Name;sid=$u.SID.Value;enabled=[bool]$u.Enabled;groups=@($gs);"
        "groups_complete=$complete}|ConvertTo-Json -Depth 4 -Compress"
    )
    data = _run_powershell_json(script)
    if not isinstance(data, dict) or not all(k in data for k in ("name", "sid", "enabled", "groups_complete")):
        raise ContractError("account inventory has an unexpected shape")
    runner_name, runner_sid = _identity()
    return {
        "worker": {"name": data["name"], "sid": data["sid"], "enabled": data["enabled"], "is_local": True,
                   "groups": _as_list(data.get("groups")), "groups_complete": data["groups_complete"]},
        "runner": {"name": runner_name, "sid": runner_sid},
    }


_SID_CACHE: dict[str, str | None] = {}


def _lookup_sid(account: str) -> str | None:
    """Resolve an account name to a SID string; None when unresolvable (reported, never guessed)."""
    if _SID_RE.fullmatch(account):
        return account.upper()
    if account in _SID_CACHE:
        return _SID_CACHE[account]
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kern = ctypes.WinDLL("kernel32", use_last_error=True)
    sid_len, dom_len, use = ctypes.c_uint32(0), ctypes.c_uint32(0), ctypes.c_uint32(0)
    adv.LookupAccountNameW(None, account, None, ctypes.byref(sid_len), None, ctypes.byref(dom_len), ctypes.byref(use))
    result: str | None = None
    if sid_len.value:
        sid_buf = ctypes.create_string_buffer(sid_len.value)
        dom_buf = ctypes.create_unicode_buffer(max(dom_len.value, 1))
        if adv.LookupAccountNameW(None, account, sid_buf, ctypes.byref(sid_len), dom_buf,
                                  ctypes.byref(dom_len), ctypes.byref(use)):
            out = ctypes.c_wchar_p()
            if adv.ConvertSidToStringSidW(sid_buf, ctypes.byref(out)):
                result = out.value
                kern.LocalFree(ctypes.cast(out, ctypes.c_void_p))
    _SID_CACHE[account] = result
    return result


def collect_acl_inventory(paths: list[str]) -> dict[str, Any]:
    """Read-only `icacls` of each existing path, principals resolved to SIDs. ContractError on any failure."""
    _require_windows()
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and ntpath.isabs(p) for p in paths):
        raise ContractError("paths must be a non-empty list of absolute paths")
    items = []
    for path in paths:
        if not os.path.exists(path):
            raise ContractError(f"path does not exist: {path}")
        parsed, complete = _parse_icacls(_run([_system32("icacls.exe"), path]), path)
        entries = [{"sid": _lookup_sid(e["name"]), "name": e["name"], "type": e["type"],
                    "rights": e["rights"], "flags": e["flags"]} for e in parsed]
        items.append({"path": path, "complete": complete, "entries": entries})
    return {"paths": items}


_FW_LIST_FIELDS = ("profile", "protocol", "local_port", "remote_port", "program", "service",
                   "package", "interface_type", "local_address", "remote_addresses")


def collect_firewall_inventory(worker_sid: str) -> dict[str, Any]:
    """Read-only ActiveStore firewall data: profiles, all enabled outbound Block rules and worker-bound Allow rules.

    Uses PowerShell NetSecurity cmdlets (netsh cannot show the per-account LocalUser filter).
    Each rule carries Profile, Protocol, ports, Program, Service, Package (when exposed),
    InterfaceType and LocalAddress; an unreadable value is reported as '<unavailable>' (restricted).
    """
    _require_windows()
    sid = _sid(worker_sid, "worker_sid")
    script = (
        f"$w='{sid}';$p=@(Get-NetFirewallProfile -PolicyStore ActiveStore|"
        "ForEach-Object{[pscustomobject]@{name=[string]$_.Name;enabled=($_.Enabled -eq 'True')}});"
        "$s={param($v) if($null -eq $v){,@('<unavailable>')}else{,@($v|ForEach-Object{[string]$_})}};"
        "$r=@();foreach($x in Get-NetFirewallRule -PolicyStore ActiveStore -Direction Outbound -Enabled True){"
        "$sf=$x|Get-NetFirewallSecurityFilter;$u=[string]$sf.LocalUser;"
        "if(([string]$x.Action -eq 'Block') -or $u.Contains($w)){"
        "$af=$x|Get-NetFirewallAddressFilter;$pf=$x|Get-NetFirewallPortFilter;"
        "$ap=$x|Get-NetFirewallApplicationFilter;$sv=$x|Get-NetFirewallServiceFilter;"
        "$if=$x|Get-NetFirewallInterfaceTypeFilter;"
        "$o=[ordered]@{name=[string]$x.Name;enabled=$true;direction='Outbound';"
        "action=[string]$x.Action;local_user_sddl=$(if($u -eq 'Any' -or $u -eq ''){$null}else{$u});"
        "profile=(&$s $x.Profile);protocol=(&$s $pf.Protocol);local_port=(&$s $pf.LocalPort);"
        "remote_port=(&$s $pf.RemotePort);program=(&$s $ap.Program);service=(&$s $sv.Service);"
        "interface_type=(&$s $if.InterfaceType);local_address=(&$s $af.LocalAddress);"
        "remote_addresses=(&$s $af.RemoteAddress)};"
        "if($ap.PSObject.Properties['Package']){$o.package=$(if([string]::IsNullOrEmpty([string]$ap.Package)){,@('Any')}else{&$s $ap.Package})};"
        "$r+=[pscustomobject]$o}};"
        "[pscustomobject]@{profiles=$p;rules=$r}|ConvertTo-Json -Depth 5 -Compress"
    )
    data = _run_powershell_json(script, timeout=300)
    if not isinstance(data, dict):
        raise ContractError("firewall inventory has an unexpected shape")
    rules = []
    for r in _as_list(data.get("rules")):
        if not isinstance(r, dict):
            raise ContractError("firewall rule has an unexpected shape")
        rules.append({k: (_as_list(v) if k in _FW_LIST_FIELDS else v) for k, v in r.items()})
    return {"profiles": _as_list(data.get("profiles")), "rules": rules}


def _reparse_walk(root: str) -> tuple[list[dict[str, Any]], bool, int]:
    """Iterative walk without following reparse points; returns (reparse_points, complete, entries_seen)."""
    found: list[dict[str, Any]] = []
    stack, seen, complete = [root], 0, True
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    seen += 1
                    if seen > MAX_WALK_ENTRIES:
                        return found, False, seen
                    attrs = entry.stat(follow_symlinks=False).st_file_attributes
                    if attrs & 0x400:  # FILE_ATTRIBUTE_REPARSE_POINT
                        try:
                            target: str | None = os.path.realpath(entry.path)
                        except OSError:
                            target = None
                        found.append({"path": entry.path, "target": target})
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
        except OSError:
            complete = False
    return found, complete, seen


def collect_worktree_inventory(run_dir: str, worktree: str, host_paths: list[str]) -> dict[str, Any]:
    """Read-only: real paths, reparse-point walk of the worktree, and ACLs of sampled host paths."""
    _require_windows()
    for p in (run_dir, worktree):
        if not isinstance(p, str) or not ntpath.isabs(p) or not os.path.isdir(p):
            raise ContractError("run_dir and worktree must be existing absolute directories")
    _require_deep_dir(run_dir, "run_dir")
    _require_deep_dir(os.path.realpath(run_dir), "run_dir_real")
    points, complete, seen = _reparse_walk(os.path.realpath(worktree))
    return {
        "run_dir": run_dir, "run_dir_real": os.path.realpath(run_dir),
        "worktree": worktree, "worktree_real": os.path.realpath(worktree),
        "walk_complete": complete, "entries_checked": seen, "reparse_points": points,
        "host_paths": collect_acl_inventory(host_paths)["paths"],
    }


def _loopback_canary() -> bool:
    """TCP connect/accept over 127.0.0.1 on an ephemeral port; False on any OSError."""
    server = client = None
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.settimeout(2.0)
        client.settimeout(2.0)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        client.connect(server.getsockname())
        server.accept()[0].close()
        return True
    except OSError:
        return False
    finally:
        if client is not None:
            client.close()
        if server is not None:
            server.close()


def _blocked_connect() -> tuple[bool, int | None]:
    """Attempt a short connect to a documentation-range address; (connected, errno/winerror)."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        sock.connect(BLOCKED_EGRESS_TARGET)
        return True, None
    except socket.timeout:
        return False, 10060
    except OSError as exc:
        return False, getattr(exc, "winerror", None) or exc.errno
    finally:
        if sock is not None:
            sock.close()


class _BasicLimit(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32)]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BasicLimit), ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def collect_job_inventory() -> dict[str, Any]:
    """Read-only: Job Object of the CALLING process and its recorded limits.

    ContractError when the Win32 queries fail. A process outside any job reports in_job False.
    """
    _require_windows()
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    k32.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                              ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    flag = ctypes.c_int(0)
    if not k32.IsProcessInJob(k32.GetCurrentProcess(), None, ctypes.byref(flag)):
        raise ContractError("IsProcessInJob failed")
    build = sys.getwindowsversion().build
    info, ret = _ExtendedLimit(), ctypes.c_uint32(0)
    in_job = bool(flag.value)
    if in_job and not k32.QueryInformationJobObject(None, 9, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(ret)):
        raise ContractError("QueryInformationJobObject failed")
    basic = info.BasicLimitInformation
    return {
        "in_job": in_job, "windows_build": build, "nesting_supported": build >= MIN_NESTED_JOB_BUILD,
        "limits": {
            "kill_on_job_close": bool(basic.LimitFlags & 0x2000),
            "breakaway_ok": bool(basic.LimitFlags & 0x800),  # JOB_OBJECT_LIMIT_BREAKAWAY_OK
            "silent_breakaway_ok": bool(basic.LimitFlags & 0x1000),  # JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK
            "active_process_limit": int(basic.ActiveProcessLimit) if basic.LimitFlags & 0x8 else 0,
            "process_memory_limit": int(info.ProcessMemoryLimit) if basic.LimitFlags & 0x100 else 0,
            "job_memory_limit": int(info.JobMemoryLimit) if basic.LimitFlags & 0x200 else 0,
            "process_time_limit_100ns": int(basic.PerProcessUserTimeLimit) if basic.LimitFlags & 0x2 else 0,
            "job_time_limit_100ns": int(basic.PerJobUserTimeLimit) if basic.LimitFlags & 0x4 else 0,
        },
    }


def collect_worker_probe(run_id: str, candidate_sha: str, *, now: float | None = None) -> dict[str, Any]:
    """Run INSIDE the worker process: identity, egress probes and Job Object, bound to run id and SHA."""
    _require_windows()
    _validate_run_binding(run_id, candidate_sha)
    _, identity_sid = _identity()
    connected, err = _blocked_connect()
    return {
        "meta": {"run_id": run_id, "candidate_sha": candidate_sha,
                 "observed_at_epoch": time.time() if now is None else now},
        "egress": {"identity_sid": identity_sid, "loopback_canary_ok": _loopback_canary(),
                   "external_target": f"{BLOCKED_EGRESS_TARGET[0]}:{BLOCKED_EGRESS_TARGET[1]}",
                   "external_connected": connected, "external_errno": err},
        "job": collect_job_inventory(),
    }


# ------------------------------------------------------------------ report builder

def evaluate_proof(inventories: dict[str, Any], *, run_id: str, candidate_sha: str,
                   now: float, max_age_sec: float) -> dict[str, Any]:
    """Run all checkers over inventories; a missing inventory or ambiguous evidence gives INCONCLUSIVE.

    inventories keys: account, acl, worktree, firewall, worker_probe (None = collector unavailable).
    Overall: INCONCLUSIVE if anything is unavailable/ambiguous, else FAIL if any check failed, else PASS.
    """
    _require_windows()
    _validate_run_binding(run_id, candidate_sha)
    if not isinstance(inventories, dict):
        raise ContractError("inventories: must be an object")
    account = inventories.get("account")
    probe = inventories.get("worker_probe")
    worker = account.get("worker") if isinstance(account, dict) else None

    def need(*parts: Any) -> bool:
        return all(p is not None for p in parts)

    plan: list[tuple[str, tuple[Any, ...], Callable[[], dict[str, Any]]]] = [
        ("worker_account", (account,), lambda: check_worker_account(account)),
        ("secret_isolation", (inventories.get("acl"), worker), lambda: check_secret_isolation(inventories["acl"], worker)),
        ("worktree_confinement", (inventories.get("worktree"), worker),
         lambda: check_worktree_confinement(inventories["worktree"], worker)),
        ("egress", (inventories.get("firewall"), probe, worker),
         lambda: check_egress(inventories["firewall"], probe["egress"], worker)),
        ("probe_binding", (probe,), lambda: check_probe_binding(
            probe["meta"], run_id=run_id, candidate_sha=candidate_sha, now=now, max_age_sec=max_age_sec)),
        ("job_object", (probe,), lambda: check_job_object(probe["job"])),
    ]
    checks: dict[str, dict[str, Any]] = {}
    for name, deps, run in plan:
        if not need(*deps):
            checks[name] = {"check": name, "result": "INCONCLUSIVE", "subchecks": [], "reason": "evidence unavailable"}
            continue
        try:
            checks[name] = run()
        except (ContractError, KeyError, TypeError, AttributeError, ArithmeticError, ValueError) as exc:
            checks[name] = {"check": name, "result": "INCONCLUSIVE", "subchecks": [], "reason": f"ambiguous evidence: {exc}"}
    results = {c["result"] for c in checks.values()}
    overall = "INCONCLUSIVE" if "INCONCLUSIVE" in results else ("FAIL" if "FAIL" in results else "PASS")
    return {"checks": checks, "result": overall}


def _default_collectors() -> dict[str, Callable[..., Any]]:
    return {"account": collect_account_inventory, "acl": collect_acl_inventory,
            "firewall": collect_firewall_inventory, "worktree": collect_worktree_inventory,
            "worker_probe": collect_worker_probe}


def build_probe_record(*, run_id: str, candidate_sha: str, worker_name: str, run_dir: str, worktree: str,
                       protected_paths: list[str], host_paths: list[str], max_age_sec: float = 300,
                       worker_probe: dict[str, Any] | None = None, now: float | None = None,
                       collectors: dict[str, Callable[..., Any]] | None = None) -> dict[str, Any]:
    """Collect (read-only) and evaluate, returning a JSON-serializable probe record.

    worker_probe: JSON produced by collect_worker_probe inside the worker; if None the probe is
    taken in this process, which passes only if this process IS the worker (identity check).
    A collector that raises leaves its inventory None -> INCONCLUSIVE with the error recorded.
    """
    _require_windows()
    _validate_run_binding(run_id, candidate_sha)
    started = time.time() if now is None else now
    col = collectors or _default_collectors()
    errors: dict[str, str] = {}

    def attempt(name: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except (ContractError, OSError, KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
            return None

    account = attempt("account", lambda: col["account"](worker_name))
    wsid = attempt("account_sid", lambda: account["worker"]["sid"]) if isinstance(account, dict) and "worker" in account else None
    if wsid is not None and not isinstance(wsid, str):
        errors["account_sid"] = "worker sid is not a string"
        wsid = None
    inventories = {
        "account": account,
        "acl": attempt("acl", lambda: col["acl"](protected_paths)),
        "worktree": attempt("worktree", lambda: col["worktree"](run_dir, worktree, host_paths)),
        "firewall": attempt("firewall", lambda: col["firewall"](wsid)) if wsid else None,
        "worker_probe": worker_probe if worker_probe is not None
        else attempt("worker_probe", lambda: col["worker_probe"](run_id, candidate_sha)),
    }
    if wsid is None:
        errors.setdefault("firewall", "worker SID unavailable")
    verdict = evaluate_proof(inventories, run_id=run_id, candidate_sha=candidate_sha,
                             now=time.time() if now is None else now, max_age_sec=max_age_sec)
    record = {
        "schema": SCHEMA, "run_id": run_id, "candidate_sha": candidate_sha, "worker_account": worker_name,
        "started_at_epoch": started, "finished_at_epoch": time.time() if now is None else now,
        "max_age_sec": max_age_sec, "inventories": inventories, "collector_errors": errors,
        "checks": verdict["checks"], "result": verdict["result"],
        "guarantee": GUARANTEE, "known_limits": list(KNOWN_LIMITS),
    }
    try:
        return json.loads(json.dumps(record, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ContractError("probe record is not JSON-serializable") from exc


def main(argv: list[str] | None = None) -> int:
    """CLI: `probe --run-id ID --sha SHA` prints collect_worker_probe JSON (run it as the worker)."""
    import argparse
    parser = argparse.ArgumentParser(description="Windows sandbox worker probe (run as the worker account)")
    parser.add_argument("command", choices=["probe"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(collect_worker_probe(args.run_id, args.sha), allow_nan=False))
    except (ContractError, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
