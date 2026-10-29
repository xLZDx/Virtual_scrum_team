# S2 Windows ACL and signer boundary — design disposition

Date: 2026-10-27  
Repository: `D:\Repo\Virtual_scrum_team`  
Branch: `s4-canonical-continuation`  
Source/test baseline: `a6ea0dc15b9e02b37f48a85f1fcc76cbe81df5a3`  
Documentation baseline: `41cfd5e2aad01d77ac5db416dc5aa8c42e66c617`

## Goal

Resolve whether the missing Windows key ACL evidence can be closed with a local helper change,
without weakening the S2 worker/signing trust boundary or implying Windows signed-worker support
that the current code does not provide.

## Current contract and evidence

- S2.3 explicitly requires Windows ACL protection and POSIX owner/mode `0600` checks; the runner
  must refuse to start if the command account can read the signing key (`docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md`, S2.3).
- `tools/vst/runner.py::run_manifest_commands` rejects every non-POSIX host before the signed v2
  execution path. Its worker identity parameters are numeric POSIX UID/GID values.
- `tools/vst/signer.py::_key_is_private` requires POSIX `O_NOFOLLOW`; `AuthenticatedSigner`
  requires POSIX Unix sockets and `SO_PEERCRED`.
- `tools/vst/sandbox.py` therefore fails closed for Windows key and signer IPC checks. These
  helpers are called after the runner's POSIX-only boundary; the Windows signed-worker path is not
  implemented.
- The Windows nested Job Object probe at exact source/test HEAD `a6ea0dc` proved assignment of a
  normal-exit child to nested jobs only. It did not prove key ACL, signed-worker launch, cleanup,
  or descendant termination. Its evidence is
  `s2-windows-nested-job-safe-a6ea0dc-20261027.md`.

Read-only review in this turn:

- `architect` (default GPT-6 Luna, medium) found that a DACL helper alone is disconnected from
  runner launch and signer authentication because no Windows worker SID/token or signer IPC
  contract exists.
- `security-reviewer` (default GPT-6 Luna, medium) independently found that parsing a DACL or
  checking only the runner account cannot establish worker effective access. Group membership,
  inherited ACEs, and reparse/open races must be covered by the actual worker token and key-open
  operation.
- Neither reviewer edited files or ran tests/checks.

PM Bridge status in this turn:

- The exact S2 review request `d9e174a1-fbdf-4ba7-bcd0-ec1902ed38c4` / job
  `11cffada-67dd-442f-9649-6ac6b706086d` remains `uncertain`, `sendPhase=sending`, with
  `userTurnId=null`, `replyId=null`, `correlated=null`, and
  `CHATGPT_RENDERER_STALLED`. The active sending lineage means it must not be blindly resent.
- A separate read-only peek job `59419e68-d9d2-4c22-aa9a-b511721c8d87` surfaced a message whose
  text names that request and says `MODIFY — S2 NOT APPROVED`, but the bridge still reports no
  correlated reply ID or user turn. It is retained only as uncorrelated context, not a gate result
  or architecture adjudication. The PM gate remains `S2-PHASE-8: in-progress`.

## Options and recommendation

1. **Add a standalone Windows ACL helper.** Rejected. It would not be called by the signed v2
   runner, would have no authoritative worker token to evaluate, and would not secure signer IPC.
   Treating it as acceptance would overstate the boundary.
2. **Keep the signed v2 worker POSIX-only and seek explicit platform-scope adjudication.**
   Recommended. Preserve the current fail-closed runner/signer behavior. Keep Windows Job Object
   evidence as a separately bounded host containment result. GPT-PM must decide whether S2.3's
   Windows ACL clause can be scoped to a future Windows worker profile or whether this sprint must
   implement the full Windows boundary. No Windows ACL acceptance is claimed meanwhile.
3. **Implement a complete Windows signed-worker profile.** Required if Windows worker execution is
   in S2: define worker/signer SIDs and the actual worker access token; create the worker under
   that token; check effective file and parent-path access; open the key without following
   reparse points and bind checks to the opened object; define authenticated signer IPC (for
   example, a named pipe bound to the caller token); then add focused negative tests and Windows
   runtime evidence. This is a cross-module trust-boundary change, not a helper-only patch.

## Failure behavior and rollout

Until the platform contract is adjudicated, unsupported Windows signed-worker execution must
continue to fail closed. Do not turn a missing ACL API into a permissive result, reinterpret the
Windows Job Object probe as signer isolation, or alter the signed v2 POSIX contract. If GPT-PM
selects the complete Windows profile, implement the identity/token and signer IPC contract first,
then integrate ACL checks and tests as one reviewed source change. Rollback leaves Windows signed
worker launch unavailable; it must not fall back to an unauthenticated signer channel.

## Verification plan and ownership

- GPT-PM owns the architecture/scope adjudication.
- Codex owns reconciliation of the uncertain PM Bridge lineage, coordination and, if Windows is
  selected, the identity/token/IPC implementation and
  evidence records.
- `functional-test-reviewer` owns focused ACL, token, path-race, and fail-closed tests after source
  coding is complete; `e2e-runner` owns bounded Windows runtime evidence after that.
- The operator owns only any external environment authorization genuinely required; no such
  authorization is requested by this design note.
- No tests/checks/build/CI/migration were run for this design record.

## Disposition

No source change is justified by the current contract evidence. VST-011's Windows ACL and signer
isolation acceptance remains `NOT_VERIFIED`; VST-015's Windows read-only credential behavior also
remains `NOT_VERIFIED`. Existing POSIX evidence remains platform-scoped. The exact-head S2 gate
cannot be marked approved from this design review.

Executor: Codex. Read-only design reviewers: architect and security-reviewer, GPT-6 Luna / medium.
