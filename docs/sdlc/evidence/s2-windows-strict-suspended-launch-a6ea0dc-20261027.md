# S2 E4.2 Windows strict suspended-launch probe — safe normal exit

Date: 2026-10-27  
Repository: `D:\Repo\Virtual_scrum_team`  
Branch: `s4-canonical-continuation`  
Source/test HEAD: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`  
Runner blob: `4ee81ab18511f4289811a502838ff2cb1016454c`  
Documentation HEAD before this evidence: `528cd0d0d2eb7dfb953c849b7e7468320a0f0bd4`

## Scope and provenance

- Executor: designated `e2e-runner`, GPT-6 Luna / low effort.
- Environment: Windows; CPython 3.14.3 at `C:\Python314\python.exe`.
- This probe exercised the project's real `_spawn_kwargs(suspended=True)`,
  `_JobObject.attach`, and `_resume_suspended_primary_thread` helpers.
- It used one harmless child that prints and exits immediately. The probe checks strict suspended
  creation, assignment before resume, nested Job Object membership, and normal exit only.
- It does not prove kill-on-close cleanup, descendants, timeout, crash, or prohibited process
  termination behavior.

## Exact invocation

PowerShell:

```powershell
$script = @'
<the complete Python body below>
'@; & 'C:\Python314\python.exe' -c $script
```

Exact in-memory Python body:

```python
import ctypes, hashlib, json, subprocess, sys
from ctypes import wintypes
from tools.vst import runner

api = runner._win_api()
if api is None:
    print(json.dumps({"result":"NOT_RUN","reason":"runner Win32 API bindings unavailable"}))
    raise SystemExit(0)
k32 = api.k32
k32.GetCurrentProcess.restype = wintypes.HANDLE
k32.GetCurrentProcess.argtypes = []
k32.IsProcessInJob.restype = wintypes.BOOL
k32.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
outer = k32.CreateJobObjectW(None, None)
if not outer:
    print(json.dumps({"result":"NOT_RUN","reason":"outer Job Object creation failed","winerror":ctypes.get_last_error()}))
    raise SystemExit(0)
proc = None
inner = None
closed_outer = False
closed_inner = False
try:
    current = k32.GetCurrentProcess()
    ctypes.set_last_error(0)
    if not k32.AssignProcessToJobObject(outer, current):
        print(json.dumps({"result":"NOT_RUN","reason":"probe process cannot enter outer Job Object","winerror":ctypes.get_last_error()}))
        raise SystemExit(0)
    own_member = wintypes.BOOL()
    if not k32.IsProcessInJob(current, outer, ctypes.byref(own_member)) or not own_member.value:
        print(json.dumps({"result":"NOT_RUN","reason":"outer membership could not be confirmed"}))
        raise SystemExit(0)
    child_code = "print('VST_E42_NORMAL_EXIT', flush=True)"
    cmd = [sys.executable, "-I", "-S", "-c", child_code]
    popen_kwargs = runner._spawn_kwargs(suspended=True)
    flags = popen_kwargs.get("creationflags", 0)
    if not flags & runner._CREATE_SUSPENDED:
        print(json.dumps({"result":"NOT_RUN","reason":"project spawn kwargs did not include CREATE_SUSPENDED"}))
        raise SystemExit(0)
    proc = subprocess.Popen(cmd, shell=False, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=r"D:\Repo\Virtual_scrum_team", bufsize=0,
                            **popen_kwargs)
    child_outer = wintypes.BOOL()
    outer_query_ok = bool(k32.IsProcessInJob(int(proc._handle), outer, ctypes.byref(child_outer)))
    inner = runner._JobObject.attach(proc)
    if inner is None:
        # The command is a harmless print-and-exit one-liner. Resume it so it exits
        # naturally; do not invoke any termination API or count this as a pass.
        resume_recovery = runner._resume_suspended_primary_thread(proc.pid)
        stdout, stderr = proc.communicate()
        print(json.dumps({"result":"NOT_RUN","reason":"project inner Job Object assignment unavailable",
                          "outer_member_query_ok":outer_query_ok,"child_in_outer":bool(child_outer.value),
                          "resumed_for_natural_exit":resume_recovery,"exit_code":proc.returncode,
                          "stdout":stdout.decode("utf-8","replace"),"stderr":stderr.decode("utf-8","replace"),
                          "script_sha256":hashlib.sha256(sys.argv[0].encode()).hexdigest() if sys.argv else None}))
        raise SystemExit(0)
    child_inner = wintypes.BOOL()
    inner_query_ok = bool(k32.IsProcessInJob(int(proc._handle), inner._handle, ctypes.byref(child_inner)))
    resumed = runner._resume_suspended_primary_thread(proc.pid)
    if not resumed:
        # Retry the same documented-thread discovery/resume helper once only to
        # let the harmless synthetic child exit naturally; this is not acceptance evidence.
        resumed = runner._resume_suspended_primary_thread(proc.pid)
    if not resumed:
        print(json.dumps({"result":"NOT_RUN","reason":"project resume helper failed; no termination API called",
                          "pid":proc.pid,"outer_member_query_ok":outer_query_ok,
                          "child_in_outer":bool(child_outer.value),"inner_member_query_ok":inner_query_ok,
                          "child_in_inner":bool(child_inner.value)}))
        raise SystemExit(0)
    stdout, stderr = proc.communicate()
    normal_exit = proc.returncode == 0
    if normal_exit:
        closed_inner = bool(k32.CloseHandle(inner._handle))
        if closed_inner:
            inner._handle = None
        closed_outer = bool(k32.CloseHandle(outer))
        outer = None
    print(json.dumps({"result":"PASS" if (outer_query_ok and child_outer.value and inner_query_ok and child_inner.value and resumed and normal_exit and closed_inner and closed_outer) else "INCONCLUSIVE",
                      "outer_member_query_ok":outer_query_ok,"probe_in_outer":bool(own_member.value),
                      "child_in_outer":bool(child_outer.value),"child_inner_query_ok":inner_query_ok,
                      "child_in_inner":bool(child_inner.value),"resumed_by_project_helper":resumed,
                      "exit_code":proc.returncode,"stdout":stdout.decode("utf-8","replace"),
                      "stderr":stderr.decode("utf-8","replace"),"inner_handle_closed_after_exit":closed_inner,
                      "outer_handle_closed_after_exit":closed_outer,
                      "termination_api_invoked":False,"files_or_network_used":False,
                      "source_test_head":"a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3",
                      "runner_blob":"4ee81ab18511f4289811a502838ff2cb1016454c",
                      "child_command":cmd}))
finally:
    # Outer job has no kill-on-close setting. Never close an inner KILL_ON_JOB_CLOSE
    # handle unless the child has naturally exited.
    if proc is not None and proc.poll() is not None and inner is not None and inner._handle:
        if k32.CloseHandle(inner._handle):
            inner._handle = None
    if outer:
        k32.CloseHandle(outer)
```

## Result

PowerShell command exit code and exact elapsed time were **NOT_RECORDED** by the executor wrapper.
The child exit code below is recorded by the script and is not a substitute for the wrapper exit
code or a separately measured duration.

```json
{"result":"PASS","outer_member_query_ok":true,"probe_in_outer":true,"child_in_outer":true,"child_inner_query_ok":true,"child_in_inner":true,"resumed_by_project_helper":true,"exit_code":0,"stdout":"VST_E42_NORMAL_EXIT\r\n","stderr":"","inner_handle_closed_after_exit":true,"outer_handle_closed_after_exit":true,"termination_api_invoked":false,"files_or_network_used":false,"source_test_head":"a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3","runner_blob":"4ee81ab18511f4289811a502838ff2cb1016454c","child_command":["C:\\Python314\\python.exe","-I","-S","-c","print('VST_E42_NORMAL_EXIT', flush=True)"]}
```

The outer Job Object had no configured limits or kill-on-close flag. The child was confirmed in
both outer and project-created inner jobs before resume. It exited normally; both handles were
closed afterward with raw `CloseHandle`. No `TerminateJobObject`, `taskkill`, `proc.kill`, or
`proc.terminate` call was made. No pytest selector, file write, network call, timeout, crash,
descendant, or kill-on-close cleanup was exercised.

## Acceptance effect

This closes only the E4.2 strict suspended-create/assign/resume ordering for one child with a
normal exit on this Windows host. VST-013 remains partial. Job Object cleanup/termination and
Windows ACL/key isolation remain `NOT_VERIFIED`/`NOT_RUN`; S2 Phase 8 remains not approved.

Executor: designated `e2e-runner`, GPT-6 Luna / low effort.
