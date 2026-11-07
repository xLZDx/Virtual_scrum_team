# S2 WSL provisioning baseline — 2026-10-28

## Scope and method

Read-only inventory of the in-scope `Ubuntu-24.04` WSL2 distribution for the current S2
coordinator/configuration task. The inspected project revision was `e3464a9f5d50156b4b242270c498fb2cffb3b927`.
No test, source install, credential read, service start/enable, network-policy change, or E5 probe
was performed. Secret file contents were not opened or printed.

Commands used from PowerShell (the initial invocation that returned no output and the malformed,
non-executed shell-quoting attempt are excluded):

```text
wsl.exe --list --verbose
wsl.exe -d Ubuntu-24.04 -- bash -lc 'id; uname -r; test -e /etc/vst-runner/runner-service.json && stat -c "%U:%G %a %n" /etc/vst-runner/runner-service.json || echo RUNNER_CONFIG_ABSENT; test -e /etc/vst-runner/supervisor-service.json && stat -c "%U:%G %a %n" /etc/vst-runner/supervisor-service.json || echo SUPERVISOR_CONFIG_ABSENT; test -e /etc/vst-runner/signer-service.json && stat -c "%U:%G %a %n" /etc/vst-runner/signer-service.json || echo SIGNER_CONFIG_ABSENT; systemctl is-enabled vst-supervisor.service vst-signer.service vst-runner.service 2>&1 || true; systemctl is-active vst-supervisor.service vst-signer.service vst-runner.service 2>&1 || true; find /etc/vst-runner /var/lib/vst-runner -maxdepth 2 -type f -printf "%u:%g %m %p\n" 2>/dev/null'
wsl.exe -d Ubuntu-24.04 -- bash -lc 'printf "WSL_CONF_BEGIN\n"; if test -f /etc/wsl.conf; then cat /etc/wsl.conf; else echo WSL_CONF_ABSENT; fi; printf "KEY_METADATA_BEGIN\n"; if test -d /var/lib/vst/keys; then find /var/lib/vst/keys -maxdepth 1 -type f -printf "%u:%g %m %s %f\n"; else echo VST_KEY_DIR_ABSENT; fi; printf "OLD_PRIVATE_E5_METADATA_BEGIN\n"; if test -e /var/lib/vst/private-e5-final-inventory-8024493e38ba44df96ee5f127a24b338.json; then stat -c "%U:%G %a %s %n" /var/lib/vst/private-e5-final-inventory-8024493e38ba44df96ee5f127a24b338.json; else echo OLD_PRIVATE_E5_ABSENT; fi; printf "SYSTEMD_UNIT_FILES_BEGIN\n"; find /etc/systemd/system -maxdepth 2 -type f -name "vst-*.service" -printf "%u:%g %m %p\n" 2>/dev/null; printf "END\n'
wsl.exe -d Ubuntu-24.04 -- bash -lc 'printf "RUNTIME_MANIFEST_BEGIN\n"; if test -f /opt/vst-runtime/.vst-source-manifest.json; then stat -c "%U:%G %a %s %n" /opt/vst-runtime/.vst-source-manifest.json; cat /opt/vst-runtime/.vst-source-manifest.json; else echo RUNTIME_MANIFEST_ABSENT; fi; printf "HELPER_METADATA_BEGIN\n"; find /usr/local/libexec -maxdepth 1 -type f -name "vst-s4-worker-exec-*" -printf "%u:%g %m %s %f\n" 2>/dev/null; printf "UNITS_HASH_BEGIN\n"; sha256sum /etc/systemd/system/vst-runner.service /etc/systemd/system/vst-supervisor.service /etc/systemd/system/vst-signer.service; printf "STORE_DIRS_BEGIN\n"; find /var/lib/vst -maxdepth 2 -type d -printf "%u:%g %m %p\n" 2>/dev/null; printf END'
wsl.exe -d Ubuntu-24.04 -- bash -lc 'find /var/lib/vst/keys -mindepth 2 -maxdepth 4 -type f -printf "%u:%g %m %s %p\n" 2>/dev/null'
Get-FileHash tools/vst/systemd/vst-runner.service,tools/vst/systemd/vst-supervisor.service,tools/vst/systemd/vst-signer.service -Algorithm SHA256
```

The second command inspected only metadata for private key files and one prior private E5 inventory;
it did not read their contents.

## Observed baseline

- `Ubuntu-24.04` exists as WSL2. The running identity inside the distribution was `root`; kernel
  reported `6.6.114.1-microsoft-standard-WSL2`.
- `/etc/wsl.conf` has systemd enabled, automount disabled, interop disabled, and
  `appendWindowsPath=false`.
- The runner, Supervisor and signer configuration files under `/etc/vst-runner` are absent.
  `systemctl is-enabled` returned `disabled` and `systemctl is-active` returned `inactive` for all
  three corresponding services.
- The three installed systemd unit files are byte-identical to the repository templates at the
  inspected revision. SHA-256 values, in runner/Supervisor/signer order: `4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be`, `aa64d16b7801f32146808706acffaa0ca9086653e5e3e9f5f5dac1bc07ab822c`, and `33ed12ee7174c9136493cfba3cd4176a1c48ac9515afb79d5eb0740ff6d3502d`.
- `/opt/vst-runtime/.vst-source-manifest.json` is absent. The only versioned worker helper found is
  `vst-s4-worker-exec-d5001797cb94113efd9a8dc26e4a15f2dc130976`, owned by root and the runner
  group, mode `4750`. It is older than the current S2 source and cannot qualify current runtime
  acceptance.
- Dedicated key directories and six 32-byte HMAC key files exist for operator, worker, event,
  Supervisor, reviewer, and runner-signer roles. File owners and modes match the earlier role
  separation (`root:root 0600` for operator; service-owned `0600` for the other roles). Origin and
  current authorization provenance were not independently verified in this inventory. No key
  bytes were read.
- One private E5 inventory from an earlier run exists with owner/mode `root:root 0600`. Its content
  was not read. The public historical E5 reports bind older code heads (including `f0bbac8` and
  `280e2d0`), so they do not establish fresh E5 for current code.
- No current-head root service configuration, runtime manifest, current signed E5 inventory, or
  fresh operator-authorized network-policy attestation was established.

## Acceptance consequence

This baseline confirms that the dedicated WSL identity restrictions and unit templates are
present, but does not prove effective host network egress policy, current service-key custody,
worker/process containment, systemd runtime fencing, or fresh E5. Runtime remains disabled. Any
unobserved property remains `NOT_VERIFIED`; restricted process/crash/STOP/resume/mutation/policy
scenarios remain `NOT_RUN`.

The operator directed Codex to build the coordinator and prepare root-owned configuration/E5.
GPT-PM's correlated architecture decision allows root-only service configuration and local service
key use only after the exact configuration and key custody are reviewed. It does not authorize
Codex to impersonate the operator attestation authority or to treat its own signature as independent
operator evidence. No service enable/start is authorized by the architecture decision.

## Correlation and next step

The baseline complements coordinator architecture request `dd7175f5-40f3-4714-932d-dc44dca55cc2`
(reply `c064e8f2-eb6d-5945-97e1-f6f6c71d6b92`). The required request-provenance amendment was
sent under request `9fcaec9d-c344-4388-b79a-1392fb6f4cb4`; no completed correlated reply was
available when this record was prepared. Next: close that amendment, implement only the accepted
coordinator boundary, finish code review, then prepare exact-head WSL runtime/configuration and
delegate permitted fresh E5 evidence. Do not enable persistent services or claim full S2 from this
baseline.
