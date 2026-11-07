"""Cross-identity pipe-auth probe (H1): does the client token's default DACL block the server's OpenThreadToken?

Non-elevated. Server = this process (current user) with a raw Win32 pipe plus the REAL
tools.vst.windows_named_pipe._verify_client_sid on the same connected handle. Client = child python.exe started with a
primary token built by CreateRestrictedToken/DuplicateTokenEx whose TokenDefaultDacl is set explicitly.
"""
from __future__ import annotations

import ctypes
import json
import os
import secrets
import subprocess
import sys
import threading
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))
from s2_4e_probe_common import own_user_sid, record, sub, overall  # noqa: E402
from s2_4e_probe_p1_restricted_token import (  # noqa: E402
    SidAttr, SecAttr, StartupInfo, ProcInfo, sid_of, logon_sid, werr, k32, a32, H, D, B, P)

PY = r"C:\Python314\python.exe"
CLIENT = str(HERE / "s2_4e_probe_cross_identity_client.py")

k32.CreateNamedPipeW.restype = H
k32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, D, D, D, D, D, D, ctypes.c_void_p]
k32.ConnectNamedPipe.argtypes = [H, ctypes.c_void_p]
k32.CreateFileW.restype = H
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, D, D, ctypes.c_void_p, D, D, H]
k32.GetNamedPipeClientProcessId.argtypes = [H, P(wintypes.ULONG)]
k32.GetNamedPipeClientSessionId.argtypes = [H, P(wintypes.ULONG)]
a32.ImpersonateNamedPipeClient.argtypes = [H]
a32.CheckTokenMembership.argtypes = [H, ctypes.c_void_p, P(B)]
a32.GetTokenInformation.argtypes = [H, ctypes.c_int, ctypes.c_void_p, D, P(D)]
a32.SetTokenInformation.argtypes = [H, ctypes.c_int, ctypes.c_void_p, D]
a32.GetSecurityDescriptorDacl.argtypes = [ctypes.c_void_p, P(B), P(ctypes.c_void_p), P(B)]
H_INVALID = (None, 0, 0xFFFFFFFFFFFFFFFF, 0xFFFFFFFF)


def tok_dword(tok, cls):
    v, n = D(), D()
    if not a32.GetTokenInformation(tok, cls, ctypes.byref(v), 4, ctypes.byref(n)):
        return f"gti-err {ctypes.get_last_error()}"
    return v.value


def set_default_dacl(tok, sddl: str) -> None:
    sd = ctypes.c_void_p()
    if not a32.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(sd), None):
        raise OSError(werr("SDDL"))
    present, defaulted, acl = B(), B(), ctypes.c_void_p()
    a32.GetSecurityDescriptorDacl(sd, ctypes.byref(present), ctypes.byref(acl), ctypes.byref(defaulted))
    holder = ctypes.c_void_p(acl.value)
    if not a32.SetTokenInformation(tok, 6, ctypes.byref(holder), ctypes.sizeof(holder)):
        raise OSError(werr("SetTokenInformation(TokenDefaultDacl)"))


def verr(fn):
    """Run fn; return ('OK', None) or ('ERR', winerror)."""
    try:
        fn()
        return {"result": "OK", "error": 0}
    except OSError as exc:
        return {"result": "ERR", "error": exc.errno, "text": str(exc)[:200]}
    except Exception as exc:  # ContractError etc.
        return {"result": "EXC", "error": None, "text": f"{type(exc).__name__}: {exc}"[:240]}


def server_probe(pipe, me_sid: str, res: dict) -> None:
    """All server-side measurements on one connected pipe instance (after the first read)."""
    # V3 / V4: no token needed
    pid, sess = wintypes.ULONG(), wintypes.ULONG()
    ok = k32.GetNamedPipeClientProcessId(pipe, ctypes.byref(pid))
    res["V3_client_pid"] = {"ok": bool(ok), "pid": pid.value, "error": 0 if ok else ctypes.get_last_error()}
    ok = k32.GetNamedPipeClientSessionId(pipe, ctypes.byref(sess))
    res["V4_client_session"] = {"ok": bool(ok), "session": sess.value, "error": 0 if ok else ctypes.get_last_error()}
    # V1 / V2: impersonate then open the thread token with each OpenAsSelf value
    for key, open_as_self in (("V1_OpenThreadToken_TOKEN_QUERY_OpenAsSelf_TRUE", True),
                              ("V2_OpenThreadToken_TOKEN_QUERY_OpenAsSelf_FALSE", False)):
        if not a32.ImpersonateNamedPipeClient(pipe):
            res[key] = {"impersonate_error": ctypes.get_last_error()}
            continue
        try:
            t = H()
            if a32.OpenThreadToken(k32.GetCurrentThread(), 0x8, open_as_self, ctypes.byref(t)):
                sid = sid_of(me_sid)
                mem = B()
                cm = a32.CheckTokenMembership(t, sid, ctypes.byref(mem))
                res[key] = {"ok": True, "error": 0, "token_type(2=impersonation)": tok_dword(t, 8),
                            "impersonation_level(0=anon,1=ident,2=imp)": tok_dword(t, 9),
                            "CheckTokenMembership_ok": bool(cm),
                            "CheckTokenMembership_error": 0 if cm else ctypes.get_last_error(),
                            "member_of_server_user_sid": bool(mem.value)}
                k32.CloseHandle(t)
            else:
                res[key] = {"ok": False, "error": ctypes.get_last_error()}
        finally:
            a32.RevertToSelf()
    # real product code on the same connected handle
    from tools.vst import windows_named_pipe as wnp
    res["real_verify_client_sid"] = verr(
        lambda: wnp._verify_client_sid(pipe, allowed_services=(), allowed_user_sids=(me_sid,)))


def run_variant(label: str, token, pipe_sd: str, me_sid: str) -> dict:
    name = r"\\.\pipe\s24e-xid-" + secrets.token_hex(6)
    sd = ctypes.c_void_p()
    if not a32.ConvertStringSecurityDescriptorToSecurityDescriptorW(pipe_sd, 1, ctypes.byref(sd), None):
        raise OSError(werr("pipe SDDL"))
    sa = SecAttr(ctypes.sizeof(SecAttr), sd, False)
    pipe = k32.CreateNamedPipeW(name, 3, 0, 1, 4096, 4096, 0, ctypes.byref(sa))
    if pipe in H_INVALID:
        return {"label": label, "setup_error": werr("CreateNamedPipeW")}
    res: dict = {"label": label}

    def worker():
        try:
            if not k32.ConnectNamedPipe(pipe, None) and ctypes.get_last_error() != 535:
                res["connect_error"] = ctypes.get_last_error()
                return
            buf, n = ctypes.create_string_buffer(1), D()
            if not k32.ReadFile(pipe, buf, 1, ctypes.byref(n), None) or n.value != 1:
                res["first_read_error"] = ctypes.get_last_error()
                return
            res["server_read_request_byte"] = buf.raw[:1].decode("latin1")
            server_probe(pipe, me_sid, res)
            k32.WriteFile.argtypes = [H, ctypes.c_void_p, D, P(D), ctypes.c_void_p]
            k32.WriteFile(pipe, b"A", 1, ctypes.byref(n), None)
        except Exception as exc:
            res["worker_exception"] = repr(exc)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    # child with the primary token; stdout captured through an inheritable pipe
    r_out, w_out = H(), H()
    sa2 = SecAttr(ctypes.sizeof(SecAttr), None, True)
    k32.CreatePipe(ctypes.byref(r_out), ctypes.byref(w_out), ctypes.byref(sa2), 0)
    k32.SetHandleInformation(r_out, 1, 0)
    si = StartupInfo()
    si.cb = ctypes.sizeof(si)
    si.dwFlags = 0x100
    si.hStdInput, si.hStdOutput, si.hStdError = None, w_out, w_out
    pi = ProcInfo()
    cmd = ctypes.create_unicode_buffer(f'"{PY}" -I "{CLIENT}" {name}')
    ok = a32.CreateProcessAsUserW(token, None, cmd, None, None, True, 0x8, None, None, ctypes.byref(si), ctypes.byref(pi))
    method = "CreateProcessAsUserW"
    if not ok:
        first = werr("CreateProcessAsUserW")
        ok = a32.CreateProcessWithTokenW(token, 0, None, cmd, 0x8, None, None, ctypes.byref(si), ctypes.byref(pi))
        method = "CreateProcessWithTokenW"
        if not ok:
            res["NOT_RUN"] = f"{first}; {werr('CreateProcessWithTokenW')}"
            return res
    k32.CloseHandle(w_out)
    wait = k32.WaitForSingleObject(pi.hProcess, 25000)
    if wait != 0:
        k32.TerminateProcess(pi.hProcess, 1)
    code = D()
    k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
    data, rb, n = b"", ctypes.create_string_buffer(4096), D()
    while k32.ReadFile(r_out, rb, 4096, ctypes.byref(n), None) and n.value:
        data += rb.raw[:n.value]
    th.join(5)
    if th.is_alive():  # client never connected: release the blocked server thread
        h = k32.CreateFileW(name, 0xC0000000, 0, None, 3, 0, None)
        th.join(5)
        res["server_thread_released_by_dummy_connect"] = True
    res["launch"] = method
    res["child_pid_from_CreateProcess"] = pi.dwProcessId
    res["child_exit"] = f"{code.value:#010x}"
    text = data.decode("utf-8", "replace").strip()
    try:
        res["client_report"] = json.loads(text.splitlines()[-1])
    except Exception:
        res["client_raw_output"] = text[:600]
    k32.CloseHandle(pipe)
    return res


def main() -> None:
    me = own_user_sid()
    throwaway = f"S-1-5-21-{secrets.randbelow(10**9)}-{secrets.randbelow(10**9)}-{secrets.randbelow(10**9)}-{1000 + secrets.randbelow(9000)}"
    tok = H()
    a32.OpenProcessToken(k32.GetCurrentProcess(), 0x2 | 0x1 | 0x8 | 0x4 | 0x80, ctypes.byref(tok))
    lsid = logon_sid(tok)
    arr = (SidAttr * 3)(SidAttr(sid_of("S-1-1-0"), 0), SidAttr(sid_of(throwaway), 0), SidAttr(sid_of(lsid), 0))

    def write_restricted():
        t = H()
        if not a32.CreateRestrictedToken(tok, 0x8, 0, None, 0, None, 3, arr, ctypes.byref(t)):
            raise OSError(werr("CreateRestrictedToken"))
        return t

    def plain_dup():
        t = H()
        if not a32.DuplicateTokenEx(tok, 0x02000000, None, 2, 1, ctypes.byref(t)):
            raise OSError(werr("DuplicateTokenEx(primary)"))
        return t

    # pipe DACL: current user + throwaway SID (stand-in for the client's service SID); restricting pass needs throwaway
    pipe_sd = f"D:(A;;GA;;;{me})(A;;GA;;;{throwaway})"
    dacl_excl = f"D:(A;;GA;;;SY)(A;;GA;;;{throwaway})"          # server's user NOT granted
    dacl_incl = f"D:(A;;GA;;;SY)(A;;GA;;;{me})(A;;GA;;;{throwaway})"  # server's user granted (control)
    plan = [("A write-restricted client, default DACL excludes server user (H1)", write_restricted, dacl_excl, False),
            ("B CONTROL write-restricted client, default DACL grants server user", write_restricted, dacl_incl, True),
            ("C unrestricted client, default DACL excludes server user", plain_dup, dacl_excl, False),
            ("D CONTROL unrestricted client, natural default DACL", plain_dup, None, True)]
    results, subs = [], []
    for label, mk, dacl, expect_v1_ok in plan:
        try:
            t = mk()
            if dacl:
                set_default_dacl(t, dacl)
            r = run_variant(label, t, pipe_sd, me)
        except OSError as exc:
            r = {"label": label, "NOT_RUN": str(exc)}
        r["expect_V1_ok"] = expect_v1_ok
        results.append(r)
        print(json.dumps(r, indent=1))
        if "NOT_RUN" in r or "client_report" not in r:
            subs.append(sub(label, "NOT_RUN", json.dumps(r)[:900]))
            continue
        v1 = r.get("V1_OpenThreadToken_TOKEN_QUERY_OpenAsSelf_TRUE", {})
        v3 = r.get("V3_client_pid", {})
        cf = r["client_report"].get("createfile")
        subs.append(sub(f"{label}: pipe DACL admits client (CreateFile)", "PASS" if cf == 0 else "FAIL", f"createfile_error={cf}"))
        subs.append(sub(f"{label}: V1 OpenThreadToken(TOKEN_QUERY, OpenAsSelf=TRUE)",
                        "PASS" if v1.get("ok") == expect_v1_ok else "FAIL",
                        f"expected {'success' if expect_v1_ok else 'failure'}; got {json.dumps(v1)}"))
        subs.append(sub(f"{label}: V2 OpenThreadToken(OpenAsSelf=FALSE)", "INFO",
                        json.dumps(r.get("V2_OpenThreadToken_TOKEN_QUERY_OpenAsSelf_FALSE"))))
        subs.append(sub(f"{label}: V3 client pid == child pid", "PASS" if v3.get("ok") and v3.get("pid") == r.get("child_pid_from_CreateProcess") else "FAIL",
                        f"pipe_pid={v3.get('pid')} child_pid={r.get('child_pid_from_CreateProcess')} client_self_pid={r['client_report'].get('pid')} err={v3.get('error')}"))
        subs.append(sub(f"{label}: V4 client session id", "PASS" if r.get("V4_client_session", {}).get("ok") else "FAIL",
                        json.dumps(r.get("V4_client_session"))))
        subs.append(sub(f"{label}: real _verify_client_sid outcome", "INFO", json.dumps(r.get("real_verify_client_sid"))))
    record("cross_identity_pipe_auth", "python docs/sdlc/evidence/s2_4e_probe_cross_identity_pipe_auth.py", overall(subs), subs,
           json.dumps(results)[-3800:],
           {"hypothesis": "H1: OpenThreadToken(OpenAsSelf=TRUE) fails with 5 when the client token default DACL excludes the server identity",
            "variants": results, "server_user_sid": me, "throwaway_sid": throwaway,
            "limits": "same-user server vs. restricted client of the same user (DACL separation, not real virtual-account service SIDs); "
                      "non-elevated; no SCM / service SID / session 0; client token made by CreateRestrictedToken, not by SCM."})


if __name__ == "__main__":
    main()
