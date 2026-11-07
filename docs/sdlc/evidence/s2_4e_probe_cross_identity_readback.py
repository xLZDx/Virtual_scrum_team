"""Readback: confirm SetTokenInformation(TokenDefaultDacl) really stores the intended ACEs on the token (instrument check)."""
import ctypes, json, secrets, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_4e_probe_cross_identity_pipe_auth as m
from s2_4e_probe_common import own_user_sid
from ctypes import wintypes
me = own_user_sid()
thr = "S-1-5-21-1-2-3-1234"
tok = m.H(); m.a32.OpenProcessToken(m.k32.GetCurrentProcess(), 0xFF, ctypes.byref(tok))
class AclSize(ctypes.Structure):
    _fields_ = [("AceCount", wintypes.DWORD), ("AclBytesInUse", wintypes.DWORD), ("AclBytesFree", wintypes.DWORD)]
m.a32.GetAclInformation.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_int]
def count(t):
    n = wintypes.DWORD(); m.a32.GetTokenInformation(t, 6, None, 0, ctypes.byref(n))
    b = ctypes.create_string_buffer(n.value)
    assert m.a32.GetTokenInformation(t, 6, b, n.value, ctypes.byref(n))
    acl = ctypes.c_void_p.from_buffer(b).value
    s = AclSize(); m.a32.GetAclInformation(acl, ctypes.byref(s), ctypes.sizeof(s), 2)
    return s.AceCount
out = {"original_process_token_default_dacl_aces": count(tok)}
for name, sddl in (("deny_me+SY+thr", f"D:(D;;GA;;;{me})(A;;GA;;;SY)(A;;GA;;;{thr})"), ("SY+thr", f"D:(A;;GA;;;SY)(A;;GA;;;{thr})")):
    t = m.H(); assert m.a32.DuplicateTokenEx(tok, 0x02000000, None, 2, 1, ctypes.byref(t))
    m.set_default_dacl(t, sddl); out[name] = count(t)
print(json.dumps(out))
