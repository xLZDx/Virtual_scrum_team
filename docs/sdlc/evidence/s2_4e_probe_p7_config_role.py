"""P7: WindowsRuntimeConfig.load(role=...) access-denied handling. Real assert_path_acl against a real
NTFS directory whose READ_CONTROL is denied to the current user (icacls, non-elevated). Patched:
resolve_enabled_service_sid (no VST services exist) and assert_path_acl for data_root and for the
non-denied private root (those need SYSTEM/Administrators ownership, impossible non-elevated)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from s2_4e_probe_common import REPO, own_user_sid, record, sub, overall

sys.path.insert(0, str(REPO))
from tools.vst import windows_service_host as sh  # noqa: E402
from tools.vst.contracts import ContractError  # noqa: E402

REAL_ACL = sh.assert_path_acl
SIDS = {name: f"S-1-5-80-1-2-3-4-{i}" for i, name in enumerate(sh._SERVICE_NAMES.values())}
sh.resolve_enabled_service_sid = lambda name: SIDS[name]


def icacls(path, *args):
    return subprocess.run(["icacls", str(path), *args], capture_output=True, text=True)


def run(base: Path, denied: set, role, extra_err=None):
    data, store, signer = base, base / "store", base / "signer"
    roots = {"data_root": str(data), "store_root": str(store), "signer_root": str(signer)}
    denied_paths = {str(store) if "store" in denied else None, str(signer) if "signer" in denied else None}

    def acl(path, **kw):
        if path in denied_paths:
            return REAL_ACL(path, **kw)  # real GetNamedSecurityInfoW -> real access denied
        if extra_err and path == extra_err[0]:
            raise extra_err[1]
        return None
    sh.assert_path_acl = acl
    try:
        sh.WindowsRuntimeConfig.load(roots=roots, role=role)
        return "ok"
    except OSError as e:
        return f"OSError errno={e.errno}"
    except ContractError as e:
        return f"ContractError {e}"


def main() -> None:
    subs = []
    me = own_user_sid()
    base = Path(tempfile.mkdtemp(prefix="s24e-p7-"))
    (base / "store").mkdir()
    (base / "signer").mkdir()
    subs0 = []
    try:
        for d in ("store", "signer"):
            r = icacls(base / d, "/deny", f"*{me}:(RC)")
            subs0.append((d, r.returncode, r.stdout.strip()[-120:], r.stderr.strip()[-120:]))
        # precondition: the real ACL reader must really get errno 5 for the denied roots
        pre = []
        for d in ("store", "signer"):
            try:
                REAL_ACL(str(base / d), allowed_sids={"S-1-5-18"}, writable_sids={"S-1-5-18"}, require_protected=True)
                pre.append((d, "no error"))
            except OSError as e:
                pre.append((d, f"OSError errno={e.errno}"))
            except Exception as e:  # noqa: BLE001
                pre.append((d, repr(e)))
        feasible = all(p[1] == "OSError errno=5" for p in pre)
        subs.append(sub("precondition: deny READ_CONTROL gives real errno 5 from assert_path_acl", "PASS" if feasible else "NOT_RUN",
                        f"icacls={subs0} real_acl={pre}"))
        if feasible:
            cases = [
                ("signer root denied, role=supervisor -> skipped", {"signer"}, "supervisor", "ok"),
                ("store root denied, role=signer -> skipped", {"store"}, "signer", "ok"),
                ("store root denied, role=supervisor (own root) -> re-raises", {"store"}, "supervisor", "OSError errno=5"),
                ("signer root denied, role=signer (own root) -> re-raises", {"signer"}, "signer", "OSError errno=5"),
                ("store root denied, role=None (dispatcher/owner/runner callers pass no role) -> skipped by design", {"store"}, None, "ok"),
                ("signer root denied, role=None -> skipped by design", {"signer"}, None, "ok"),
                ("INFO fail-open: typo role='supervisr', store root denied -> skipped (no role validation)", {"store"}, "supervisr", "ok"),
                ("both denied, role=supervisor -> re-raises (own store)", {"store", "signer"}, "supervisor", "OSError errno=5"),
                ("none denied, role=supervisor -> ok", set(), "supervisor", "ok"),
            ]
            for name, den, role, want in cases:
                got = run(base, den, role)
                subs.append(sub(name, "PASS" if got == want else "FAIL", f"got={got} want={want}"))
            # non-errno-5 failure on another role's root is NOT swallowed
            got = run(base, set(), "supervisor", extra_err=(str(base / "signer"), OSError(2, "not found")))
            subs.append(sub("other role's root fails with errno 2 (not 5) -> re-raises", "PASS" if got == "OSError errno=2" else "FAIL", got))
            got = run(base, set(), "supervisor", extra_err=(str(base / "signer"), ContractError("bad acl")))
            subs.append(sub("other role's root fails with ContractError -> re-raises", "PASS" if got.startswith("ContractError") else "FAIL", got))
    finally:
        for d in ("store", "signer"):
            icacls(base / d, "/remove:d", f"*{me}")
    record("P7_config_role_access_denied", "python docs/sdlc/evidence/s2_4e_probe_p7_config_role.py", overall(subs), subs,
           json.dumps([(s["name"], s["status"], s["detail"]) for s in subs])[-3500:],
           {"patched": "resolve_enabled_service_sid -> fake SIDs; assert_path_acl: no-op for data_root and the non-denied "
                       "private root, REAL for the denied root. Full real load() is impossible non-elevated (no VST "
                       "services in SCM, data_root must be SYSTEM/Administrators-owned)."})


main()
