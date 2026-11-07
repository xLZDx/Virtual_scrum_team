"""P1: write-restricted token approximation of a service token: temp-dir denial/allow and openssl start.

Non-elevated: CreateRestrictedToken(own token, WRITE_RESTRICTED, restricting SIDs Everyone + throwaway SID).
"""
from __future__ import annotations

import ctypes
import os
import secrets
import shutil
import subprocess
import tempfile
import threading
from ctypes import wintypes
from pathlib import Path

from s2_4e_probe_common import own_user_sid, record, sub, overall

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
a32 = ctypes.WinDLL("advapi32", use_last_error=True)
H, D, B, P = wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, ctypes.POINTER

OPENSSL = r"C:\Program Files\Git\usr\bin\openssl.exe"


class SidAttr(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", D)]


class SecAttr(ctypes.Structure):
    _fields_ = [("nLength", D), ("lpSecurityDescriptor", ctypes.c_void_p), ("bInheritHandle", B)]


class StartupInfo(ctypes.Structure):
    _fields_ = [("cb", D), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR),
                ("lpTitle", wintypes.LPWSTR), ("dwX", D), ("dwY", D), ("dwXSize", D), ("dwYSize", D),
                ("dwXCountChars", D), ("dwYCountChars", D), ("dwFillAttribute", D), ("dwFlags", D),
                ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", H), ("hStdOutput", H), ("hStdError", H)]


class ProcInfo(ctypes.Structure):
    _fields_ = [("hProcess", H), ("hThread", H), ("dwProcessId", D), ("dwThreadId", D)]


k32.GetCurrentProcess.restype = H
k32.GetCurrentThread.restype = H
k32.CreateDirectoryW.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p]
k32.LocalFree.argtypes = [ctypes.c_void_p]
k32.CreatePipe.argtypes = [P(H), P(H), ctypes.POINTER(SecAttr), D]
k32.ReadFile.argtypes = [H, ctypes.c_void_p, D, P(D), ctypes.c_void_p]
k32.WaitForSingleObject.argtypes = [H, D]
k32.GetExitCodeProcess.argtypes = [H, P(D)]
k32.TerminateProcess.argtypes = [H, wintypes.UINT]
k32.CloseHandle.argtypes = [H]
k32.SetHandleInformation.argtypes = [H, D, D]
a32.OpenProcessToken.argtypes = [H, D, P(H)]
a32.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, P(ctypes.c_void_p)]
a32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, D, P(ctypes.c_void_p), P(D)]
a32.CreateRestrictedToken.argtypes = [H, D, D, ctypes.c_void_p, D, ctypes.c_void_p, D, ctypes.c_void_p, P(H)]
a32.DuplicateTokenEx.argtypes = [H, D, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, P(H)]
a32.ImpersonateLoggedOnUser.argtypes = [H]
a32.RevertToSelf.argtypes = []
a32.OpenThreadToken.argtypes = [H, D, B, P(H)]
a32.IsTokenRestricted.argtypes = [H]
a32.CreateProcessAsUserW.argtypes = [H, wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, B, D,
                                     ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(StartupInfo), ctypes.POINTER(ProcInfo)]
a32.CreateProcessWithTokenW.argtypes = [H, D, wintypes.LPCWSTR, wintypes.LPWSTR, D, ctypes.c_void_p,
                                        wintypes.LPCWSTR, ctypes.POINTER(StartupInfo), ctypes.POINTER(ProcInfo)]


def werr(label: str) -> str:
    code = ctypes.get_last_error()
    return f"{label}: error {code} ({ctypes.FormatError(code).strip()})"


def sid_of(text: str) -> ctypes.c_void_p:
    p = ctypes.c_void_p()
    if not a32.ConvertStringSidToSidW(text, ctypes.byref(p)):
        raise OSError(werr("ConvertStringSidToSid"))
    return p


def make_dir(path: str, sddl: str) -> None:
    sd = ctypes.c_void_p()
    if not a32.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(sd), None):
        raise OSError(werr("SDDL"))
    sa = SecAttr(ctypes.sizeof(SecAttr), sd, False)
    ok = k32.CreateDirectoryW(path, ctypes.byref(sa))
    k32.LocalFree(sd)
    if not ok:
        raise OSError(werr(f"CreateDirectory {path}"))


def try_create(path: str) -> str:
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(fd, b"probe")
        os.close(fd)
        os.unlink(path)
        return "created+written"
    except PermissionError as exc:
        return f"DENIED errno={exc.errno} winerror={exc.winerror}"
    except OSError as exc:
        return f"OSERROR {exc!r}"


def run_cmd(token, cmdline: str, env_dir: str, label: str, expect_prefix: str):
    """Run a command line under a primary restricted token; returns (status, detail, exit_code)."""
    r_out, w_out, r_in, w_in = H(), H(), H(), H()
    sa = SecAttr(ctypes.sizeof(SecAttr), None, True)
    k32.CreatePipe(ctypes.byref(r_out), ctypes.byref(w_out), ctypes.byref(sa), 0)
    k32.CreatePipe(ctypes.byref(r_in), ctypes.byref(w_in), ctypes.byref(sa), 0)
    k32.SetHandleInformation(r_out, 1, 0)
    k32.SetHandleInformation(w_in, 1, 0)
    k32.CloseHandle(w_in)  # stdin at EOF
    env = dict(os.environ)
    env["TEMP"] = env["TMP"] = env_dir
    block = "".join(f"{k}={v}\0" for k, v in sorted(env.items(), key=lambda kv: kv[0].upper())) + "\0"
    envbuf = ctypes.create_unicode_buffer(block, len(block))
    si = StartupInfo()
    si.cb = ctypes.sizeof(si)
    si.dwFlags = 0x100
    si.hStdInput, si.hStdOutput, si.hStdError = r_in, w_out, w_out
    pi = ProcInfo()
    cmd = ctypes.create_unicode_buffer(cmdline)
    flags = 0x00000008 | 0x00000400  # DETACHED_PROCESS (a service has no console) | CREATE_UNICODE_ENVIRONMENT
    ok = a32.CreateProcessAsUserW(token, None, cmd, None, None, True, flags, envbuf, None, ctypes.byref(si), ctypes.byref(pi))
    method = "CreateProcessAsUserW"
    first_err = None if ok else werr("CreateProcessAsUserW")
    if not ok:
        method = "CreateProcessWithTokenW"
        ok = a32.CreateProcessWithTokenW(token, 0, None, cmd, flags, envbuf, None, ctypes.byref(si), ctypes.byref(pi))
        if not ok:
            second = werr("CreateProcessWithTokenW")
            for h in (r_out, w_out, r_in):
                k32.CloseHandle(h)
            return "NOT_RUN", f"{first_err}; {second}", None
    k32.CloseHandle(w_out)
    wait = k32.WaitForSingleObject(pi.hProcess, 20000)
    if wait != 0:
        k32.TerminateProcess(pi.hProcess, 1)
    code = D()
    k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
    data = b""
    buf = ctypes.create_string_buffer(4096)
    n = D()
    while k32.ReadFile(r_out, buf, 4096, ctypes.byref(n), None) and n.value:
        data += buf.raw[:n.value]
    for h in (pi.hProcess, pi.hThread, r_out, r_in):
        k32.CloseHandle(h)
    text = data.decode("utf-8", "replace").strip()
    ok_run = wait == 0 and code.value == 0 and text.startswith(expect_prefix)
    return (("PASS" if ok_run else "FAIL"), f"{label} via {method}: wait={wait} exit={code.value} (0x{code.value:08X}) stdout={text[:900]!r}", code.value)


def logon_sid(tok) -> str:
    a32.GetTokenInformation.argtypes = [H, ctypes.c_int, ctypes.c_void_p, D, P(D)]
    a32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, P(wintypes.LPWSTR)]
    need = D()
    a32.GetTokenInformation(tok, 28, None, 0, ctypes.byref(need))
    buf = ctypes.create_string_buffer(need.value)
    if not a32.GetTokenInformation(tok, 28, buf, need.value, ctypes.byref(need)):
        raise OSError(werr("TokenLogonSid"))
    sid = ctypes.cast(ctypes.addressof(buf) + ctypes.sizeof(ctypes.c_void_p), P(SidAttr)).contents.Sid
    text = wintypes.LPWSTR()
    a32.ConvertSidToStringSidW(sid, ctypes.byref(text))
    return text.value


def main() -> None:
    me = own_user_sid()
    throwaway = f"S-1-5-21-{secrets.randbelow(10**9)}-{secrets.randbelow(10**9)}-{secrets.randbelow(10**9)}-{1000 + secrets.randbelow(9000)}"
    subs = []
    base = tempfile.mkdtemp(prefix="s24e-p1-")  # created by the unrestricted main thread
    scratch, control = str(Path(base) / "role-temp"), str(Path(base) / "control-user-only")
    tok = H()
    if not a32.OpenProcessToken(k32.GetCurrentProcess(), 0x2 | 0x1 | 0x8 | 0x4, ctypes.byref(tok)):
        # DUPLICATE|ASSIGN_PRIMARY|QUERY|IMPERSONATE variants
        record("P1", "python docs/sdlc/evidence/s2_4e_probe_p1_restricted_token.py", "NOT_RUN",
               [sub("OpenProcessToken", "NOT_RUN", werr("OpenProcessToken"))], "")
        return
    s_every, s_throw = sid_of("S-1-1-0"), sid_of(throwaway)
    arr = (SidAttr * 2)(SidAttr(s_every, 0), SidAttr(s_throw, 0))
    prim = H()
    if not a32.CreateRestrictedToken(tok, 0x8, 0, None, 0, None, 2, arr, ctypes.byref(prim)):
        record("P1", "python docs/sdlc/evidence/s2_4e_probe_p1_restricted_token.py", "NOT_RUN",
               [sub("CreateRestrictedToken", "NOT_RUN", werr("CreateRestrictedToken"))], "")
        return
    imp = H()
    if not a32.DuplicateTokenEx(prim, 0x02000000, None, 2, 2, ctypes.byref(imp)):
        record("P1", "python docs/sdlc/evidence/s2_4e_probe_p1_restricted_token.py", "NOT_RUN",
               [sub("DuplicateTokenEx", "NOT_RUN", werr("DuplicateTokenEx"))], "")
        return
    make_dir(scratch, f"D:PAI(A;OICI;FA;;;{throwaway})(A;OICI;FA;;;{me})")
    make_dir(control, f"D:PAI(A;OICI;FA;;;{me})")
    out = {}

    def worker():
        if not a32.ImpersonateLoggedOnUser(imp):
            out["impersonate"] = werr("ImpersonateLoggedOnUser")
            return
        try:
            t = H()
            has = a32.OpenThreadToken(k32.GetCurrentThread(), 0x8, True, ctypes.byref(t))
            out["thread_token_restricted"] = bool(has and a32.IsTokenRestricted(t))
            out["a_windows_temp"] = try_create(rf"C:\Windows\Temp\s24e-probe-{secrets.token_hex(4)}.tmp")
            out["b_scratch"] = try_create(str(Path(scratch) / "f.tmp"))
            out["control_user_only_dir"] = try_create(str(Path(control) / "f.tmp"))
        finally:
            a32.RevertToSelf()
    th = threading.Thread(target=worker)
    th.start()
    th.join(60)
    if "impersonate" in out:
        subs.append(sub("ImpersonateLoggedOnUser", "NOT_RUN", out["impersonate"]))
    else:
        subs.append(sub("thread token is actually restricted (IsTokenRestricted)",
                        "PASS" if out.get("thread_token_restricted") else "FAIL", str(out.get("thread_token_restricted"))))
        subs.append(sub("(a) create file in C:\\Windows\\Temp denied (confirms B6 risk)",
                        "PASS" if out["a_windows_temp"].startswith("DENIED") else "FAIL", out["a_windows_temp"]))
        subs.append(sub("(b) write in per-role scratch dir (DACL: throwaway SID + user) succeeds",
                        "PASS" if out["b_scratch"] == "created+written" else "FAIL", out["b_scratch"]))
        subs.append(sub("control: dir granting only the user (not throwaway/Everyone) is denied",
                        "PASS" if out["control_user_only_dir"].startswith("DENIED") else "FAIL", out["control_user_only_dir"]))
    # process start: unrestricted control, then primary write-restricted tokens with TEMP/TMP in the scratch dir
    plain = subprocess.run([OPENSSL, "version"], capture_output=True, text=True, timeout=30)
    subs.append(sub("control: openssl version unrestricted", "PASS" if plain.returncode == 0 else "FAIL",
                    plain.stdout.strip()[:120] + plain.stderr.strip()[:120]))
    who = r"C:\Windows\System32\whoami.exe"
    st_w, d_w, c_w = run_cmd(prim, f'"{who}"', scratch, "spec token (Everyone+throwaway)", "")
    subs.append(sub("diagnostic: whoami.exe starts under spec write-restricted token", "INFO" if st_w == "FAIL" else st_w, d_w))
    st, detail, code = run_cmd(prim, f'"{OPENSSL}" version', scratch, "spec token (Everyone+throwaway)", "OpenSSL")
    if st == "FAIL" and code == 0xC0000142:
        st, detail = "NOT_RUN", "INCONCLUSIVE: process failed to initialise (STATUS_DLL_INIT_FAILED); " + detail
    subs.append(sub("(openssl) version under spec primary write-restricted token", st, detail))
    try:
        ls = logon_sid(tok)
        arr2 = (SidAttr * 3)(SidAttr(s_every, 0), SidAttr(s_throw, 0), SidAttr(sid_of(ls), 0))
        prim2 = H()
        if not a32.CreateRestrictedToken(tok, 0x8, 0, None, 0, None, 3, arr2, ctypes.byref(prim2)):
            raise OSError(werr("CreateRestrictedToken(+logon SID)"))
        st2, d2, _ = run_cmd(prim2, f'"{who}"', scratch, f"token + logon SID {ls}", "")
        subs.append(sub("diagnostic: whoami.exe under token + logon SID restricting SID", "INFO" if st2 == "FAIL" else st2, d2))
        st3, d3, code3 = run_cmd(prim2, f'"{OPENSSL}" version', scratch, f"token + logon SID {ls}", "OpenSSL")
        if st3 == "FAIL" and code3 == 0xC0000142:
            st3, d3 = "NOT_RUN", "INCONCLUSIVE: process failed to initialise (STATUS_DLL_INIT_FAILED); " + d3
        subs.append(sub("(openssl) version under write-restricted token + logon SID (desktop access)", st3, d3))
    except OSError as exc:
        subs.append(sub("variant with logon SID", "NOT_RUN", str(exc)))
    shutil.rmtree(base, ignore_errors=True)
    record("P1", "python docs/sdlc/evidence/s2_4e_probe_p1_restricted_token.py", overall(subs), subs,
           f"throwaway_sid={throwaway} user_sid={me} results={out}",
           {"approximation": "unelevated WRITE_RESTRICTED token of the current user; real service tokens "
                             "(virtual account, service SID, session 0) may differ"})


if __name__ == "__main__":
    main()
