# Change 0530: keep authenticated principal out of the ACK RPC response

## Why

The dispatch owner acknowledgement request carries five result fields. The authenticated principal
is derived from the Unix peer mapping and persisted in the Store binding; it is not supplied by the
relay. The first executed focused suite showed the in-process Supervisor method returned that
server-derived field in its response, violating the exact five-field RPC response contract.

## What changed

- `Supervisor.ack_dispatch_intent` still asks Store to bind all six values, including authenticated
  principal, but returns only the five request/result fields to the RPC caller.
- Regenerated `governance/DOCUMENT_REGISTRY.md`.

## Verification and acceptance

- `e2e-runner` ran the exact focused command at HEAD
  `bc5862111579f5335fd71e3013607a9ea275852d` from the canonical D: checkout mounted read/write at
  `/mnt/d/Repo/Virtual_scrum_team` in the existing Ubuntu-24.04 distro. Environment: Python 3.12.3,
  pytest 7.4.4. Result: **116 passed, 2 failed**, exit 1, 8.79 seconds. Both failures had the same
  ACK response field mismatch corrected here.
- The earlier Windows collection attempt exited before tests because `socket.AF_UNIX` is absent;
  that path is not acceptance evidence. A separate WSL attempt used absent `python` alias and did
  not reach tests; the successful execution used `python3 -m pytest`.
- This correction has not been rerun. `e2e-runner` owns the next exact-head execution. No runtime
  deployment, systemd activation, privileged write, or real dispatch occurred.
- M03 and S2 remain open pending passing focused evidence, fresh specialist reviews, exact-head
  GPT-PM adjudication, and the other S2 acceptance items.
