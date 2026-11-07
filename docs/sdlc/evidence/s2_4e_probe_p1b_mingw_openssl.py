"""S2-4E D2/D1 follow-up: native mingw64 openssl under the write-restricted token, PE imports, and
server-side CloseHandle-only close semantics (local copy of the logic, no product code touched)."""
from __future__ import annotations

import ctypes
import secrets
import struct
import shutil
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

import s2_4e_probe_p1_restricted_token as p1
from s2_4e_probe_common import own_user_sid, record, sub, overall

MINGW = Path(r"C:\Program Files\Git\mingw64\bin")
EXE = MINGW / "openssl.exe"
SYS32 = Path(r"C:\Windows\System32")
k32, a32, H, D = p1.k32, p1.a32, p1.H, p1.D


def pe_imports(path: Path) -> list:
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dd = opt + (112 if magic == 0x20B else 96)
    rva, _size = struct.unpack_from("<II", data, dd + 8)  # import directory
    secs = []
    so = opt + optsz
    for i in range(nsec):
        vs, va, rs, ro = struct.unpack_from("<IIII", data, so + 40 * i + 8)
        secs.append((va, max(vs, rs), ro))

    def off(r):
        for va, sz, ro in secs:
            if va <= r < va + sz:
                return r - va + ro
        raise ValueError(hex(r))
    names, pos = [], off(rva) if rva else None
    while pos is not None:
        name_rva = struct.unpack_from("<I", data, pos + 12)[0]
        if not name_rva:
            break
        o = off(name_rva)
        names.append(data[o:data.index(b"\0", o)].decode())
        pos += 20
    return names


def classify(dll: str) -> str:
    low = dll.lower()
    if (MINGW / dll).exists():
        return "mingw64\\bin"
    if low.startswith("api-ms-") or (SYS32 / dll).exists():
        return "system"
    return "NOT FOUND"


def closure() -> dict:
    seen, todo = {}, [EXE]
    while todo:
        f = todo.pop()
        for d in pe_imports(f):
            if d.lower() in seen:
                continue
            seen[d.lower()] = classify(d)
            if seen[d.lower()] == "mingw64\\bin":
                todo.append(MINGW / d)
    return seen


# ---- D1: server CloseHandle only -------------------------------------------------------------
for fn, res, args in [("CreateNamedPipeW", H, [wintypes.LPCWSTR, D, D, D, D, D, D, ctypes.c_void_p]),
                      ("CreateFileW", H, [wintypes.LPCWSTR, D, D, ctypes.c_void_p, D, D, H]),
                      ("ConnectNamedPipe", wintypes.BOOL, [H, ctypes.c_void_p]),
                      ("DisconnectNamedPipe", wintypes.BOOL, [H]),
                      ("WriteFile", wintypes.BOOL, [H, ctypes.c_void_p, D, ctypes.POINTER(D), ctypes.c_void_p]),
                      ("PeekNamedPipe", wintypes.BOOL, [H, ctypes.c_void_p, D, ctypes.POINTER(D), ctypes.POINTER(D), ctypes.POINTER(D)]),
                      ("SetNamedPipeHandleState", wintypes.BOOL, [H, ctypes.POINTER(D), ctypes.c_void_p, ctypes.c_void_p])]:
    f = getattr(k32, fn)
    f.restype, f.argtypes = res, args


def close_semantics(payload: bytes, mode: str) -> dict:
    name = r"\\.\pipe\s24e-d1-" + secrets.token_hex(4)
    srv = k32.CreateNamedPipeW(name, 3, 0, 255, 65536, 65536, 0, None)  # duplex, byte, blocking
    cli = k32.CreateFileW(name, 0xC0000000, 0, None, 3, 0x80, None)
    assert cli != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    nowait = D(1)
    k32.SetNamedPipeHandleState(cli, ctypes.byref(nowait), None, None)  # same client mode as the product
    k32.ConnectNamedPipe(srv, None)
    buf = ctypes.create_string_buffer(payload, len(payload))
    w = D()
    ok = k32.WriteFile(srv, buf, len(payload), ctypes.byref(w), None)
    if mode == "disconnect_then_close":
        k32.DisconnectNamedPipe(srv)
    k32.CloseHandle(srv)  # server side: CloseHandle (optionally preceded by Disconnect), never FlushFileBuffers
    got, final_err, deadline = b"", None, time.monotonic() + 5
    while time.monotonic() < deadline:
        avail = D()
        if not k32.PeekNamedPipe(cli, None, 0, None, ctypes.byref(avail), None):
            final_err = ctypes.get_last_error()
            break
        if avail.value:
            rb = ctypes.create_string_buffer(avail.value)
            n = D()
            if not k32.ReadFile(cli, rb, avail.value, ctypes.byref(n), None):
                final_err = ctypes.get_last_error()
                break
            got += rb.raw[:n.value]
        else:
            time.sleep(0.005)
    k32.CloseHandle(cli)
    return {"mode": mode, "payload": len(payload), "server_written": w.value, "write_ok": bool(ok),
            "client_received": len(got), "intact": got == payload, "terminal_error_after_drain": final_err}


def main() -> None:
    me = own_user_sid()
    subs = []
    throwaway = f"S-1-5-21-{secrets.randbelow(10**9)}-{secrets.randbelow(10**9)}-{secrets.randbelow(10**9)}-{1000 + secrets.randbelow(9000)}"
    base = tempfile.mkdtemp(prefix="s24e-p1b-")
    scratch = str(Path(base) / "role-temp")
    tok = H()
    p1.a32.OpenProcessToken(k32.GetCurrentProcess(), 0x2 | 0x1 | 0x8 | 0x4, ctypes.byref(tok))
    ls = p1.logon_sid(tok)  # needed for process init (desktop access); plain Everyone+throwaway gives 0xC0000142
    arr = (p1.SidAttr * 3)(p1.SidAttr(p1.sid_of("S-1-1-0"), 0), p1.SidAttr(p1.sid_of(throwaway), 0),
                           p1.SidAttr(p1.sid_of(ls), 0))
    prim = H()
    if not a32.CreateRestrictedToken(tok, 0x8, 0, None, 0, None, 3, arr, ctypes.byref(prim)):
        subs.append(sub("CreateRestrictedToken", "NOT_RUN", p1.werr("CreateRestrictedToken")))
    else:
        p1.make_dir(scratch, f"D:PAI(A;OICI;FA;;;{throwaway})(A;OICI;FA;;;{me})")
        msg = Path(scratch) / "msg.txt"
        msg.write_bytes(b"s2-4e ed25519 probe message\n")
        exe = f'"{EXE}"'
        key, sig = str(Path(scratch) / "k.pem"), str(Path(scratch) / "sig.bin")
        st, d, _ = p1.run_cmd(prim, f"{exe} version", scratch, "mingw64 openssl, write-restricted", "OpenSSL")
        subs.append(sub("1. mingw64 openssl version under write-restricted token (Everyone+throwaway+logon SID)", st, d))
        st, d, _ = p1.run_cmd(prim, f"{exe} genpkey -algorithm ED25519 -out \"{key}\"", scratch, "genpkey", "")
        key_ok = Path(key).exists() and Path(key).stat().st_size > 0
        subs.append(sub("2a. genpkey -algorithm ED25519 writes key in scratch", "PASS" if st == "PASS" and key_ok else "FAIL", f"{d} key_exists={key_ok}"))
        st, d, _ = p1.run_cmd(prim, f"{exe} pkeyutl -sign -rawin -inkey \"{key}\" -in \"{msg}\" -out \"{sig}\"", scratch, "sign", "")
        sig_ok = Path(sig).exists() and Path(sig).stat().st_size == 64
        subs.append(sub("2b. pkeyutl -sign -rawin yields a 64-byte signature", "PASS" if st == "PASS" and sig_ok else "FAIL",
                        f"{d} sig_size={Path(sig).stat().st_size if Path(sig).exists() else None}"))
        st, d, _ = p1.run_cmd(prim, f"{exe} pkeyutl -verify -rawin -inkey \"{key}\" -in \"{msg}\" -sigfile \"{sig}\"", scratch, "verify", "Signature Verified Successfully")
        subs.append(sub("2c. pkeyutl -verify -rawin reports success", st, d))
        # negative: tampered message must NOT verify (proves the verify step can fail)
        bad = Path(scratch) / "tampered.txt"
        bad.write_bytes(b"s2-4e ed25519 probe message TAMPERED\n")
        st, d, _ = p1.run_cmd(prim, f"{exe} pkeyutl -verify -rawin -inkey \"{key}\" -in \"{bad}\" -sigfile \"{sig}\"", scratch, "verify tampered", "Signature Verified Successfully")
        subs.append(sub("2d. control: tampered message does not verify (process ran, exit 1, no success text)",
                        "PASS" if (" exit=1 " in d and "Signature Verified" not in d.split("stdout=")[1]) else ("NOT_RUN" if "0xC0000142" in d else "FAIL"), d))
    # 3. imports
    try:
        direct = pe_imports(EXE)
        full = closure()
        subs.append(sub("3. PE import table of mingw64 openssl.exe (own parser; no dumpbin, no pefile)", "PASS",
                        "direct=" + ", ".join(f"{d} [{classify(d)}]" for d in direct)
                        + " || transitive mingw64 DLLs to copy: " + ", ".join(sorted(k for k, v in full.items() if v == "mingw64\\bin"))
                        + " || NOT FOUND: " + ", ".join(k for k, v in full.items() if v == "NOT FOUND")))
    except Exception as exc:  # noqa: BLE001
        subs.append(sub("3. PE imports", "FAIL", repr(exc)))
    # 4. D1 close semantics
    results = [close_semantics(b"hello-response\n", "close_only"),
               close_semantics(bytes(range(256)) * 200, "close_only"),
               close_semantics(b"hello-response\n", "disconnect_then_close")]
    ok = all(r["intact"] for r in results[:2]) and all(r["terminal_error_after_drain"] in (109, 233) for r in results[:2])
    subs.append(sub("4. server CloseHandle only: client reads full buffered response then EOF", "PASS" if ok else "FAIL",
                    str(results[:2])))
    subs.append(sub("4b. INFO contrast: Disconnect+Close without Flush", "INFO", str(results[2])))
    shutil.rmtree(base, ignore_errors=True)
    # keep the two new keys separate in the evidence file
    openssl_subs = [s for s in subs if s["name"][0] in "123"]
    d1_subs = [s for s in subs if s["name"][0] == "4"]
    cmd = "python docs/sdlc/evidence/s2_4e_probe_p1b_mingw_openssl.py"
    record("P1b_mingw64_openssl_D2", cmd, overall(openssl_subs), openssl_subs, "\n".join(s["detail"] for s in openssl_subs))
    record("P2b_D1_server_closehandle_only", cmd, overall(d1_subs), d1_subs, "\n".join(s["detail"] for s in d1_subs))


main()
