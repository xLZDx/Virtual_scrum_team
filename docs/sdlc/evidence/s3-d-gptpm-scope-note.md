# S3-D GPT-PM code review scope

Task: S3-D Windows-local sandbox-bound proof (one task, no WSL). Base 83cfd64.
Code: tools/vst/windows_sandbox_proof.py (checkers, read-only collectors, probe record builder), scripts/windows_sandbox_provision.ps1 (operator-run provisioning), tests/vst/test_s3d_windows_sandbox_proof.py.

Settled before this review (do not reopen):
- The operator chose a Windows-local sandbox without WSL and chose to run the provisioning script himself; Codex never creates accounts, ACLs or firewall rules.
- The guarantee is weaker than the S2 WSL/VM specification and the record says so; KNOWN_LIMITS lists what is NOT covered (IPC endpoints, service-mediated egress such as DNS, children of protected directories and owner rights, an unauthenticated self-reported probe with no verifier nonce and an unsigned record, a static model of the token instead of AuthzAccessCheck, shared RunRoot siblings).
- A security-reviewer and a python-reviewer ran before this request; their MAJOR/MINOR findings that give a false PASS were fixed in one batch (SDDL exclusion ACEs, firewall rule scope, errno 10013 only, privileged groups, reparse root, whole-class deny, breakaway, CIDR loopback, ACL parser fail-closed, input validation); the remaining ones are recorded as known limits above.

Evidence:
- Functional agent run: 574 passed, 0 failed (tests/vst/test_s3d_windows_sandbox_proof.py, python 3.14, Windows).
- One live run on the provisioned host as the real worker account: worker account PASS, secret isolation PASS (direct list/write test as the worker was denied on both protected paths), egress PASS (external connect refused with errno 10013, loopback canary ok), probe binding PASS, worktree confinement FAIL (the repository folder is writable by the worker through an inherited ACL), job object FAIL (no kill-on-close, process or memory limits yet). The live run found two defects tests missed: an icacls "(N)" deny-all entry and an empty Package value; both fixed and covered by tests.
- NOT_RUN: nested job behavior, symlink creation (needs privilege), a signed record, mutation runs, full npm test (prohibited).

Ask: find the complete BLOCKER/MAJOR set for this task only.
