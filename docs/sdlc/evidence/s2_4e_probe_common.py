"""Shared helpers for the S2-4E non-elevated Windows probes (evidence only, no product code)."""
from __future__ import annotations

import ctypes
import json
import platform
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent
REPO = EVIDENCE.parents[2]
RESULT = EVIDENCE / "s2-4e-probes-20261107.json"


def revision() -> str:
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", "tools", "tests"],
                           capture_output=True, text=True).stdout.strip()
    return head + (" (tools/tests dirty)" if dirty else " (tools/tests clean)")


def own_user_sid() -> str:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    a32 = ctypes.WinDLL("advapi32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    a32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    a32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
                                        ctypes.POINTER(wintypes.DWORD)]
    a32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    tok = wintypes.HANDLE()
    if not a32.OpenProcessToken(k32.GetCurrentProcess(), 0x8, ctypes.byref(tok)):
        raise ctypes.WinError(ctypes.get_last_error())
    need = wintypes.DWORD()
    a32.GetTokenInformation(tok, 1, None, 0, ctypes.byref(need))
    buf = ctypes.create_string_buffer(need.value)
    if not a32.GetTokenInformation(tok, 1, buf, need.value, ctypes.byref(need)):
        raise ctypes.WinError(ctypes.get_last_error())
    sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p)).contents.value
    text = wintypes.LPWSTR()
    if not a32.ConvertSidToStringSidW(sid_ptr, ctypes.byref(text)):
        raise ctypes.WinError(ctypes.get_last_error())
    value = text.value
    k32.CloseHandle(tok)
    return value


def meta() -> dict:
    return {
        "date": "2026-11-07",
        "task": "S2-4E",
        "revision": revision(),
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "process_is_elevated_admin": bool(ctypes.windll.shell32.IsUserAnAdmin()),
    }


def record(probe: str, command: str, status: str, subs: list, excerpt: str, extra: dict | None = None) -> None:
    data = {}
    if RESULT.exists():
        data = json.loads(RESULT.read_text(encoding="utf-8"))
    data["meta"] = meta()
    data.setdefault("probes", {})[probe] = {
        "command": command,
        "status": status,
        "substeps": subs,
        "output_excerpt": excerpt[-4000:],
        **(extra or {}),
    }
    RESULT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"probe": probe, "status": status,
                      "substeps": [(s["name"], s["status"]) for s in subs]}, indent=1))


def sub(name: str, status: str, detail: str) -> dict:
    return {"name": name, "status": status, "detail": detail}


def overall(subs: list) -> str:
    if any(s["status"] == "FAIL" for s in subs):
        return "FAIL"
    if all(s["status"] == "NOT_RUN" for s in subs):
        return "NOT_RUN"
    return "PASS"
