"""Client half of the cross-identity pipe-auth probe (runs under a restricted token; evidence only).

Opens the pipe with SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, sends one request byte, waits for one
reply byte, and prints one JSON line with the exact CreateFile/Write/Read results and its own pid.
"""
import ctypes
import json
import os
import sys
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
H = wintypes.HANDLE
k32.CreateFileW.restype = H
k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                            wintypes.DWORD, wintypes.DWORD, H]
k32.WriteFile.argtypes = [H, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
k32.ReadFile.argtypes = [H, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]

a32 = ctypes.WinDLL("advapi32", use_last_error=True)
k32.CreateEventW.restype = H
k32.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
a32.GetSecurityInfo.argtypes = [H, ctypes.c_int, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
a32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR), ctypes.c_void_p]


def event_sddl():
    """DACL of an unnamed event created with a NULL security descriptor = this process token's default DACL in effect."""
    ev = k32.CreateEventW(None, True, False, None)
    sd = ctypes.c_void_p()
    rc = a32.GetSecurityInfo(ev, 6, 4, None, None, None, None, ctypes.byref(sd))
    if rc:
        return f"GetSecurityInfo rc={rc}"
    txt = wintypes.LPWSTR()
    a32.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd, 1, 4, ctypes.byref(txt), None)
    return txt.value


out = {"pid": os.getpid(), "event_dacl_sddl": event_sddl()}
h = k32.CreateFileW(sys.argv[1], 0xC0000000, 0, None, 3, 0x00100000 | 0x00010000, None)
if h in (None, 0, 0xFFFFFFFFFFFFFFFF, 0xFFFFFFFF):
    out["createfile"] = ctypes.get_last_error()
else:
    out["createfile"] = 0
    n = wintypes.DWORD()
    out["write_ok"] = bool(k32.WriteFile(h, b"R", 1, ctypes.byref(n), None))
    buf = ctypes.create_string_buffer(1)
    out["read_ok"] = bool(k32.ReadFile(h, buf, 1, ctypes.byref(n), None))
    out["read_err"] = 0 if out["read_ok"] else ctypes.get_last_error()
    out["reply"] = buf.raw[:n.value].decode("latin1")
print(json.dumps(out), flush=True)
