"""Diagnostic for the cross-identity probe: is the explicitly set client default DACL really in effect, and does an
explicit DENY for the server user on the client's default DACL change what the server sees? Evidence only."""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_4e_probe_cross_identity_pipe_auth as m  # noqa: E402
from s2_4e_probe_common import own_user_sid, record, sub, overall  # noqa: E402

H, a32, k32, werr, SidAttr, sid_of, logon_sid = m.H, m.a32, m.k32, m.werr, m.SidAttr, m.sid_of, m.logon_sid


def main():
    me = own_user_sid()
    thr = f"S-1-5-21-{secrets.randbelow(10**9)}-{secrets.randbelow(10**9)}-{secrets.randbelow(10**9)}-{1000 + secrets.randbelow(9000)}"
    import ctypes
    tok = H()
    a32.OpenProcessToken(k32.GetCurrentProcess(), 0x2 | 0x1 | 0x8 | 0x4 | 0x80, ctypes.byref(tok))
    arr = (SidAttr * 3)(SidAttr(sid_of("S-1-1-0"), 0), SidAttr(sid_of(thr), 0), SidAttr(sid_of(logon_sid(tok)), 0))
    pipe_sd = f"D:(A;;GA;;;{me})(A;;GA;;;{thr})"

    def wr():
        t = H()
        assert a32.CreateRestrictedToken(tok, 0x8, 0, None, 0, None, 3, arr, ctypes.byref(t)), werr("CRT")
        return t

    plan = [("A2 write-restricted, default DACL = SY + throwaway only", f"D:(A;;GA;;;SY)(A;;GA;;;{thr})"),
            ("E write-restricted, default DACL = explicit DENY GA to server user, then SY + throwaway",
             f"D:(D;;GA;;;{me})(A;;GA;;;SY)(A;;GA;;;{thr})"),
            ("D2 CONTROL write-restricted, natural (unmodified) default DACL", None)]
    subs, results = [], []
    for label, dacl in plan:
        t = wr()
        if dacl:
            m.set_default_dacl(t, dacl)
        r = m.run_variant(label, t, pipe_sd, me)
        results.append(r)
        v1 = r.get("V1_OpenThreadToken_TOKEN_QUERY_OpenAsSelf_TRUE")
        subs.append(sub(label, "INFO", json.dumps({"client_event_dacl": r.get("client_report", {}).get("event_dacl_sddl"),
                                                   "V1": v1, "V2": r.get("V2_OpenThreadToken_TOKEN_QUERY_OpenAsSelf_FALSE"),
                                                   "real_verify": r.get("real_verify_client_sid")})))
        print(json.dumps(subs[-1], indent=1))
    record("cross_identity_pipe_auth_diag", "python docs/sdlc/evidence/s2_4e_probe_cross_identity_diag.py", "INFO", subs,
           json.dumps(results)[-3800:], {"variants": results, "server_user_sid": me, "throwaway_sid": thr})


main()
