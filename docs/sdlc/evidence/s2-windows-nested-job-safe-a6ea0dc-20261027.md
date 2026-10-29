# S2 Windows nested Job Object assignment — safe bounded evidence

Date: 2026-10-27. Repository: `D:\Repo\Virtual_scrum_team`.

## Scope and provenance

- Source/test HEAD: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`.
- Documentation HEAD before this record: `ebaf69993d0700d57928b5a25fcc1174a80eb07f`.
- Executor: designated `e2e-runner`, GPT-6 Luna / medium.
- Environment: Windows; Python 3.14.3 at `C:\Python314\python.exe`.
- This checked only E4.2 nested Job Object assignment. It did not test process termination, kill-on-close cleanup, strict suspended launch sequencing, descendants, timeout, crash, or ACL/key boundaries.

## Exact invocation

PowerShell, working directory `D:\Repo\Virtual_scrum_team`, `login=false`:

```powershell
$script = @'
<in-memory Python body below>
'@; & 'C:\Python314\python.exe' -c $script; Write-Output "EXIT:$LASTEXITCODE"
```

The body creates an outer Job Object without setting limits or `KILL_ON_JOB_CLOSE`, assigns the current probe process to it, then launches one stdin-blocked child. It instruments the actual project `runner._JobObject.attach(proc)`, checks child membership in both jobs, releases the child to exit normally, and only then closes both job handles. The exact body was executed as follows:

```python
import ctypes, json, subprocess, sys, time
from ctypes import wintypes
from tools.vst import runner
started = time.monotonic()
api = runner._win_api()
if api is None:
    print(json.dumps({"result":"UNAVAILABLE","reason":"runner._win_api returned None","os_name":__import__('os').name}))
    raise SystemExit(2)
k32 = api.k32
k32.GetCurrentProcess.restype = wintypes.HANDLE
k32.GetCurrentProcess.argtypes = []
k32.IsProcessInJob.restype = wintypes.BOOL
k32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
outer = k32.CreateJobObjectW(None, None)
if not outer:
    err = ctypes.get_last_error()
    print(json.dumps({"result":"OUTER_CREATE_FAILED","winerror":err}))
    raise SystemExit(2)
current = k32.GetCurrentProcess()
ctypes.set_last_error(0)
outer_assigned = bool(k32.AssignProcessToJobObject(outer, current))
outer_error = 0 if outer_assigned else ctypes.get_last_error()
if not outer_assigned:
    close_ok = bool(k32.CloseHandle(outer))
    print(json.dumps({"result":"OUTER_ASSIGN_FAILED","winerror":outer_error,"outer_close_ok":close_ok,"elapsed_sec":round(time.monotonic()-started,3)}))
    raise SystemExit(2)
member = wintypes.BOOL()
if not k32.IsProcessInJob(current, outer, ctypes.byref(member)) or not member.value:
    close_ok = bool(k32.CloseHandle(outer))
    print(json.dumps({"result":"OUTER_MEMBERSHIP_UNCONFIRMED","outer_close_ok":close_ok,"elapsed_sec":round(time.monotonic()-started,3)}))
    raise SystemExit(2)
child_code = "import sys; print('READY',flush=True); data=sys.stdin.buffer.read(1); print('RELEASED',flush=True); sys.exit(0 if data == b'x' else 1)"
proc = subprocess.Popen([sys.executable, "-c", child_code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
child_in_outer = wintypes.BOOL()
child_query_ok = bool(k32.IsProcessInJob(int(proc._handle), outer, ctypes.byref(child_in_outer)))
original_assign = k32.AssignProcessToJobObject
inner_assign_calls = []
def observed_assign(job_handle, process_handle):
    ctypes.set_last_error(0)
    result = bool(original_assign(job_handle, process_handle))
    inner_assign_calls.append({"result":result,"winerror":0 if result else ctypes.get_last_error()})
    return result
k32.AssignProcessToJobObject = observed_assign
try:
    inner = runner._JobObject.attach(proc)
finally:
    k32.AssignProcessToJobObject = original_assign
inner_member = None
if inner is not None:
    check = wintypes.BOOL()
    inner_member = bool(k32.IsProcessInJob(int(proc._handle), inner._handle, ctypes.byref(check))) and bool(check.value)
stdout, stderr = proc.communicate(input=b"x", timeout=5)
if proc.returncode != 0:
    print(json.dumps({"result":"CHILD_NONZERO","returncode":proc.returncode,"stdout":stdout.decode(errors="replace"),"stderr":stderr.decode(errors="replace"),"elapsed_sec":round(time.monotonic()-started,3)}))
    raise SystemExit(3)
inner_close_ok = None
if inner is not None:
    inner_close_ok = bool(k32.CloseHandle(inner._handle))
    if inner_close_ok:
        inner._handle = None
outer_close_ok = bool(k32.CloseHandle(outer))
print(json.dumps({"result":"PASS" if inner is not None and child_query_ok and child_in_outer.value and inner_member and inner_close_ok and outer_close_ok else "PARTIAL_OR_UNAVAILABLE","python":sys.version.split()[0],"source_head":"a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3","runner_was_inside_created_outer_job":True,"child_in_outer_job":bool(child_query_ok and child_in_outer.value),"inner_job_created_and_attached":inner is not None,"inner_assign_calls":inner_assign_calls,"child_in_inner_job":inner_member,"child_exit":proc.returncode,"child_stdout":stdout.decode(errors="replace"),"child_stderr":stderr.decode(errors="replace"),"inner_close_after_normal_exit":inner_close_ok,"outer_close_after_normal_exit":outer_close_ok,"outer_has_no_limits_or_kill_on_close":True,"elapsed_sec":round(time.monotonic()-started,3),"scope_limit":"nested assignment only; no strict suspended launch, cleanup kill, descendant, timeout, crash, or kill-on-close acceptance"},sort_keys=True))
```

## Result

PowerShell exit code: `0`. Runtime: `1.626s`. Exact JSON output:

```json
{"child_exit": 0, "child_in_inner_job": true, "child_in_outer_job": true, "child_stderr": "", "child_stdout": "READY\r\nRELEASED\r\n", "elapsed_sec": 1.626, "inner_assign_calls": [{"result": true, "winerror": 0}], "inner_close_after_normal_exit": true, "inner_job_created_and_attached": true, "outer_close_after_normal_exit": true, "outer_has_no_limits_or_kill_on_close": true, "python": "3.14.3", "result": "PASS", "runner_was_inside_created_outer_job": true, "scope_limit": "nested assignment only; no strict suspended launch, cleanup kill, descendant, timeout, crash, or kill-on-close acceptance", "source_head": "a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3"}
```

`IsProcessInJob` confirmed the probe process was inside the created outer job and the child was inside both outer and inner jobs. The project's `AssignProcessToJobObject` call returned true with WinError 0. The child consumed one stdin byte, printed `READY`/`RELEASED`, and exited normally with code 0. `CloseHandle` returned true for inner and outer handles after that normal exit.

The script made no filesystem writes; the child only read stdin and wrote captured stdout. No `TerminateJobObject`, `taskkill`, other kill API, pytest selector, network call, descendant process, crash, or persistent system change occurred. No repository files were modified by the execution.

## Acceptance limits

This records nested assignment only. It does not prove strict suspended creation/assignment/resume ordering, termination or kill-on-close semantics, descendant containment, timeout cleanup, or Windows ACL/key isolation. VST-013 remains partial and S2 remains `NOT APPROVED`.
