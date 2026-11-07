# S2 Store-backed Pub/Sub GPT-PM source review — 2026-10-28

## Decision

GPT-PM request `b2d8f20e-4eb0-4a4c-98ec-13c1c9437279` returned:

- `APPROVE — ATTACHED SOURCE SCOPE`
- 0 confirmed BLOCKER / MAJOR findings in the supplied source
- Full S2 remains `NOT APPROVED`; `S2-DISPATCH-M01` remains `MAJOR / OPEN`
- Real kernel peer enforcement is `NOT_VERIFIED`; production dispatch is `NOT_RUN`
- Migration application, root-key/config provisioning, systemd activation, real dispatch, restricted scenarios, push/PR/merge/deploy are not authorized by this decision

The review covered Store intent authority, typed event integrity, durable subscription and signed
cursor, Supervisor filtering and grant revalidation, RPC role separation, dispatcher forwarding,
runtime packaging, and focused functional test evidence. It found no new confirmed MINOR; the
existing fail-stop/manual-recovery observation remains documented as a non-blocking operational
follow-up. GPT-PM qualified that it could not independently inspect the Windows Git checkout and
therefore did not independently establish exact Git-head attribution from its side.

## Local exact-file provenance

After the response, Codex checked the current repository at
`673479dccc0f37de7d723ede275c46a8f4b4595c`. The tracked worktree was clean; the only status entry
was the pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`, which was not
modified. For every attached implementation and test file, the SHA-256 of the checked-out bytes
was computed and `git hash-object <path>` was compared with `git rev-parse HEAD:<path>`; all values
matched. The focused test file SHA-256 was
`78EC9DB801D31E98B4918D70CD3735C714DAFEA3A6B8FCFE5FD3B50016ECC867`, matching the recorded passing
run. The implementation source did not change after the tested source head; later commits added
the test/evidence and documentation. This local check establishes repository provenance for the
attached files; it does not imply that GPT-PM independently mounted or inspected `.git`.

## Focused test boundary

`python -m pytest -q tests/vst/test_s2_store_backed_pubsub.py` recorded 20 passed, 0 failed,
0 skipped, exit 0, with one pytest-asyncio deprecation warning. This is local Store/Supervisor and
mocked receipt-binding evidence. It does not prove Linux peer credentials, cgroup enforcement,
root configuration, current signed E5/sandbox provenance, active services, or real dispatch.
The assigned production E2E review remains `NOT_RUN` because these prerequisites are absent or
unprovisioned.

## Closure boundary

The Pub/Sub source scope is approved and its attached bytes have local exact-HEAD provenance.
This does not close `S2-DISPATCH-M01` or S2. Remaining S2 gates include authenticated production
owner submission, separately reviewed and authorized schema-v6 application, root-owned runtime
configuration/credentials, current signed E5 and independent sandbox provenance, active service
integration, real POSIX identity/cgroup evidence, remaining Windows/POSIX containment, and
restricted scenarios that must remain `NOT_RUN` absent the relevant authorization. S3 remains
unstarted.
