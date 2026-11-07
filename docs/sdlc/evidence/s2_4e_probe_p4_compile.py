"""P4: py_compile of changed files + Windows PowerShell 5.1 parser on the provisioning script."""
from __future__ import annotations

import py_compile
import subprocess
import tempfile
from pathlib import Path

from s2_4e_probe_common import REPO, record, sub, overall

FILES = ["tools/vst/windows_named_pipe.py", "tools/vst/windows_service_host.py",
         "tools/vst/dispatcher_service.py", "tools/vst/execution_grant.py",
         "tests/vst/s2_4e_windows_provision.py"]
PS = "tests/vst/provision_s2_4e_windows.ps1"
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
SCRIPT = ("$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('{p}',[ref]$t,[ref]$e);"
          "'PSVersion=' + $PSVersionTable.PSVersion;'PSEdition=' + $PSVersionTable.PSEdition;"
          "'ERRORS=' + @($e).Count;@($e) | ForEach-Object {{ $_.ToString() }}")


def ps_parse(path: str):
    r = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", SCRIPT.format(p=path)],
                       capture_output=True, text=True, timeout=60)
    out = (r.stdout + r.stderr).strip()
    n = None
    for line in out.splitlines():
        if line.startswith("ERRORS="):
            n = int(line.split("=", 1)[1])
    return out, n, f"rc={r.returncode}"


def main() -> None:
    subs, excerpt = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for rel in FILES:
            try:
                py_compile.compile(str(REPO / rel), cfile=str(Path(tmp) / (Path(rel).name + "c")), doraise=True)
                subs.append(sub(f"py_compile {rel}", "PASS", "compiled"))
            except Exception as exc:  # noqa: BLE001
                subs.append(sub(f"py_compile {rel}", "FAIL", repr(exc)))
        bad = Path(tmp) / "bad.py"
        bad.write_text("def x(:\n", encoding="utf-8")
        try:
            py_compile.compile(str(bad), cfile=str(Path(tmp) / "bad.pyc"), doraise=True)
            subs.append(sub("control: broken .py is rejected", "FAIL", "broken file compiled"))
        except py_compile.PyCompileError:
            subs.append(sub("control: broken .py is rejected", "PASS", "PyCompileError raised"))
        badps = Path(tmp) / "bad.ps1"
        badps.write_text("if ($x { Write-Host 'a' \n", encoding="utf-8")
        out, n, rc = ps_parse(str(badps))
        subs.append(sub("control: broken .ps1 is rejected by PS parser", "PASS" if n else "FAIL", f"{rc} {out[:300]}"))
    out, n, rc = ps_parse(str(REPO / PS))
    excerpt.append(out)
    ok = n == 0 and "PSVersion=5.1" in out
    subs.append(sub(f"PowerShell 5.1 ParseFile {PS}", "PASS" if ok else "FAIL", f"{rc} errors={n}"))
    record("P4", "python docs/sdlc/evidence/s2_4e_probe_p4_compile.py", overall(subs), subs, "\n".join(excerpt))


main()
