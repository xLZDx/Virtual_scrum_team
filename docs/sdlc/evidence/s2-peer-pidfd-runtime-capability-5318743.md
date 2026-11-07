# S2 peer pidfd runtime capability evidence

## Result

The bounded AF_UNIX peer-pidfd capability probe passed in Ubuntu 24.04 WSL2. It used the current `D:\Repo\Virtual_scrum_team` worktree through a read-only `/mnt/d` mount. The probe created one local socketpair, requested `SO_PEERPIDFD` from the real kernel, matched the returned pidfd's `fdinfo` PID to `SO_PEERCRED`, checked that a zero-timeout poll reported no events, and closed the descriptors it created.

This is evidence for the real socket option and descriptor capability only. It is not full S2 runtime acceptance, production activation, or evidence for process-kill, crash, mutation, E8, policy-selector, service-activation, or key-management scenarios.

## Exact observed output

The successful command exited with code `0` and emitted:

```text
CAPABILITY {"result":"PASS","kernel":"6.6.114.1-microsoft-standard-WSL2","python":"3.12.3","option":77,"peer_pid":404,"pidfd":6,"pidfd_pid":404,"alive_poll_no_events":true}
SOURCE_SHA256 6950bc239fa2c7a706a03412dea3c8bef3519a104332a66c5e5317e311b5688f
```

`SOURCE_SHA256` is SHA-256 of the bytes read from `tools/vst/peer_pidfd.py` in the mounted worktree after the probe closed its descriptors.

## Command and probe source

The successful launcher was a noninteractive PowerShell command that base64-encoded the following complete Python script, then invoked `wsl.exe -d Ubuntu-24.04 -u root -- python3 -c "import base64;exec(compile(base64.b64decode('$b64'),'<capcheck>','exec'))"`. The encoded argument was held in the PowerShell `$b64` variable and was not retained in the command output; the expanded script below is the complete script passed to Python. No claim is made that a literal base64 string was logged.

```python
import os, platform, socket, select, subprocess, sys, hashlib, json
if not os.path.ismount('/mnt/d'):
 os.makedirs('/mnt/d',exist_ok=True); subprocess.run(['mount','-t','drvfs','D:','/mnt/d','-o','ro'],check=True)
repo='/mnt/d/Repo/Virtual_scrum_team'; os.chdir(repo); sys.path.insert(0,repo+'/tools/vst')
from peer_pidfd import peer_pidfd_socket_option
s1=s2=None; pfd=None
try:
 s1,s2=socket.socketpair(socket.AF_UNIX,socket.SOCK_STREAM); opt=peer_pidfd_socket_option(socket)
 if opt is None: raise RuntimeError('option unavailable')
 raw=s1.getsockopt(socket.SOL_SOCKET,opt,4)
 if len(raw)!=4: raise RuntimeError(f'bad getsockopt size={len(raw)}')
 pfd=int.from_bytes(raw,sys.byteorder,signed=True)
 if pfd<0: raise RuntimeError(f'invalid pidfd={pfd}')
 os.set_inheritable(pfd,False)
 cred=s1.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12)
 peer_pid=int.from_bytes(cred[0:4],sys.byteorder,signed=True)
 info=open(f'/proc/self/fdinfo/{pfd}',encoding='ascii').read()
 line=next((x for x in info.splitlines() if x.startswith('Pid:')),None)
 pidfd_pid=int(line.split()[1]) if line else None
 poller=select.poll(); poller.register(pfd,select.POLLIN|select.POLLHUP|select.POLLERR); alive=not bool(poller.poll(0))
 print('CAPABILITY '+json.dumps({'result':'PASS' if pidfd_pid==peer_pid and alive else 'FAIL','kernel':platform.release(),'python':platform.python_version(),'option':opt,'peer_pid':peer_pid,'pidfd':pfd,'pidfd_pid':pidfd_pid,'alive_poll_no_events':alive},separators=(',',':')))
finally:
 if pfd is not None and pfd>=0: os.close(pfd)
 if s1: s1.close()
 if s2: s2.close()
with open('tools/vst/peer_pidfd.py','rb') as f: print('SOURCE_SHA256 '+hashlib.sha256(f.read()).hexdigest())
```

## Repository identity and worktree context

- A scoped Git snapshot observed after the probe reported branch `s2-canonical-continuation` and `HEAD` `531874302f0c559fd83872fcb5d1880f41ca1bea`.
- In that snapshot, `tools/vst/peer_pidfd.py` was untracked (`??`), not present as a blob at that `HEAD`; its worktree SHA-256 was `6950bc239fa2c7a706a03412dea3c8bef3519a104332a66c5e5317e311b5688f`.
- The status snapshot also showed other pre-existing/concurrent modified and untracked paths. They were not changed by this evidence capture.
- The exact repository `HEAD` at probe execution was not recorded. Therefore this report does **not** claim committed-head execution or that the later-observed `HEAD` was the execution-time `HEAD`. The source identity claim is limited to the observed worktree file SHA-256 above.

## Scope limits

No process was killed, crashed, or mutated. No E8 or policy selectors were run. No service was activated and no key operation was performed. The successful observation does not establish the broader S2 runtime or production acceptance criteria.
