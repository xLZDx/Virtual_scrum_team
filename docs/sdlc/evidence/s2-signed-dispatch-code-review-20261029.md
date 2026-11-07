# S2 signed dispatch-instruction focused code review — 2026-10-29

## Scope and revision

- Repository: canonical `D:\Repo\Virtual_scrum_team`; no worktree/fork.
- HEAD at review: `0dac9d58a3dd5bf779e1a2908a1ff2929ef5e69f`.
- Reviewed changed tracked files: `tools/vst/store.py`, `tools/vst/supervisor.py`, and
  `tools/vst/supervisor_service.py`.
- Reviewed new untracked files: `tools/vst/dispatch_instruction.py` and
  `tools/vst/dispatch_owner_client.py`.
- Role/model: `code-reviewer`, GPT-6 Luna. Reasoning effort was not explicitly captured in the
  primary session's launch metadata; it is not inferred here.
- The agent made no edits and ran no tests, checks, or builds.

## Findings

No confirmed BLOCKER or MAJOR was found in the signed dispatch-instruction path. The review
verified the exact envelope schema and domain-separated signature binding; principal derivation
from the authenticated peer; verification at the root RPC and again in `Supervisor`; current Store
ownership, lease, attempt, epoch, manifest slot, preflight, budget and generation checks; complete
envelope binding in event/idempotency data; and signature revalidation before delivery and grant
issuance. Unsigned or direct-RPC task-shaped requests cannot obtain a grant.

## Deployment limitations (not code findings)

- Store history validation now requires signed provenance for every `DISPATCH_INTENT_ACCEPTED`
  event. A preexisting unsigned event will make history verification/startup fail closed. The
  source does not rewrite or silently accept it; compatibility with any such Store has not been
  demonstrated.
- The root Supervisor config rejects an empty dispatch-instruction trust registry, so service
  startup remains unavailable until a trusted public key is provisioned through an authorized
  custody path.
- No real instruction issuer/key or owner-service config is evidenced. The source review does not
  close `S2-DISPATCH-M01`, prove runtime, authorize key creation, or approve dispatch.

These limitations preserve fail-closed behavior and require follow-up evidence; they do not imply
data corruption or a test result.
