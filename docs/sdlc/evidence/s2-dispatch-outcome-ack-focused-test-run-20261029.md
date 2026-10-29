# S2 dispatch outcome acknowledgement focused test run — 2026-10-29

## Exact passing run

- Exact repository HEAD: `a34c574d232448b21f8169b9fa058ca7c6be8d61`.
- Executor: `e2e-runner` role; no source, test, evidence, or configuration files were changed by the
  executor.
- Environment: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4. The existing canonical Windows
  checkout was mounted into the same WSL invocation at `/mnt/d/Repo/Virtual_scrum_team`; no copy,
  worktree, fork, or project temp directory was created.
- Exact command:

  ```sh
  python3 -m pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py
  ```

- Result: **119 passed, 0 failed**, exit code 0, 12.66 seconds.
- Test file SHA-256 at the tested revision:
  - `tests/vst/test_s2_signed_dispatch_instruction.py` — `2aa3be64de28bcb3ae5646c68cda19adf07f18b5d470068d77a8671fc224acde`
  - `tests/vst/test_s2_store_backed_pubsub.py` — `22d16982a0e2c9e28a5e95ca3907a9b30ade5836d6518b434da9c030b0fbbac2`
  - `tests/vst/test_s2_dispatch_owner_service.py` — `ab07bab43d78b10ed0cc324430c1c19ea5d71e06f270c3235e21bb2459621ce4`
  - `tests/vst/test_s2_dispatch_owner_latch.py` — `fd8c7e9710b6904f41fd503990b651021f58567b59c21719511056ae23671356`

## Earlier attempts and corrections

1. At HEAD `1f02b39048bf8c3f0c90a1c8d443abca02824a7c`, the native Windows command exited 1 during
   collection because Windows Python has no `socket.AF_UNIX`; no test executed.
2. A WSL invocation after a separate mount attempt could not `chdir` to `/mnt/d/Repo/Virtual_scrum_team`
   because the distro stopped and removed that session mount; no test executed. Mount and execution
   were then combined into one WSL invocation against the existing checkout.
3. At HEAD `bc5862111579f5335fd71e3013607a9ea275852d`, WSL executed the four selectors and reported
   110 passed, 8 failed. All eight exposed the incorrect assumption that control NOTE `task_id`
   equals `event_id`; Store writes `task_id="__control__"`. Change 0529 corrected this.
4. At HEAD `80b01c55c700d029e357297f1af920e3b3033683`, WSL reported 118 passed, 0 failed. Fresh
   review then found a missing global order check across different request IDs; change 0531 and the
   new regression test address that finding.
5. At HEAD `a34c574d232448b21f8169b9fa058ca7c6be8d61`, the exact suite above passed 119/119.

## Acceptance limits

The new tests cover transactional pending-marker atomicity, exact replay, different-ID refusal,
acknowledgement binding and authorization, duplicate/conflicting ACK behavior, local send and ACK
RPC failures, Store reopen, legacy history, malformed and cross-request out-of-order histories,
and `synchronous=FULL` read-back. The tests are synthetic Store/socket fixtures. They do not prove
installed systemd behavior, physical power-loss durability, production peer provisioning, E5,
Windows/POSIX containment, or a production coordinator.

The current generation contract binds active Runner generation to `INVOCATION_ID`. A pending
outcome cannot be ordinarily replayed after that generation changes, and no dispatch-outcome
reconciliation endpoint is implemented. This remains MAJOR/OPEN pending an adjudicated recovery
contract. S2 remains NOT APPROVED.
