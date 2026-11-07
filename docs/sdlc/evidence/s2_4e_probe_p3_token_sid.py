"""P3: _check_token_sid on this process primary token (exercises the primary-token fallback path)."""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from s2_4e_probe_common import REPO, own_user_sid, record, sub, overall

sys.path.insert(0, str(REPO))
from tools.vst import windows_named_pipe as wp  # noqa: E402


def main() -> None:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    a32 = ctypes.WinDLL("advapi32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    a32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    a32.ConvertStringSidToSidW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPVOID)]
    a32.CheckTokenMembership.argtypes = [wintypes.HANDLE, wintypes.LPVOID, ctypes.POINTER(wintypes.BOOL)]
    tok = wintypes.HANDLE()
    assert a32.OpenProcessToken(k32.GetCurrentProcess(), 0x8, ctypes.byref(tok))
    me = own_user_sid()
    subs = []
    # Precondition: CheckTokenMembership must reject a primary token with 1309, else the fallback is not exercised.
    sid = wintypes.LPVOID()
    a32.ConvertStringSidToSidW("S-1-1-0", ctypes.byref(sid))
    member = wintypes.BOOL()
    ctypes.set_last_error(0)
    r = a32.CheckTokenMembership(tok, sid, ctypes.byref(member))
    err = ctypes.get_last_error()
    subs.append(sub("precondition: CheckTokenMembership(primary) fails with 1309",
                    "PASS" if (not r and err == 1309) else "FAIL", f"ret={r} err={err}"))
    cases = [
        ("Users S-1-5-32-545", "S-1-5-32-545", True),
        ("Everyone S-1-1-0", "S-1-1-0", True),
        (f"own user {me}", me, True),
        ("SYSTEM S-1-5-18", "S-1-5-18", False),
        ("Administrators S-1-5-32-544 (deny-only/absent under UAC)", "S-1-5-32-544", False),
        ("unrelated service SID S-1-5-80-1-2-3-4-5", "S-1-5-80-1-2-3-4-5", False),
    ]
    for name, s, expected in cases:
        try:
            got = wp._check_token_sid(tok, s)
            subs.append(sub(name, "PASS" if got is expected else "FAIL", f"got={got} expected={expected}"))
        except Exception as exc:  # noqa: BLE001
            subs.append(sub(name, "FAIL", f"raised {exc!r}"))
    record("P3", "python docs/sdlc/evidence/s2_4e_probe_p3_token_sid.py", overall(subs), subs,
           "; ".join(f"{s['name']}: {s['detail']}" for s in subs))


main()
