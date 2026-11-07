# Change 0596 — S2 exact runtime installation and qualification

Date: 2026-10-30
Owner: Codex
Current task: S2-4 actual run-bound evidence (ordered backlog item3)

## Accepted baseline and concrete delta

The exact non-secret input bundle was committed in473e559 and normally pushed; actual output
was9021b98..473e559 on s2-canonical-continuation. Existing source/runtime identity remains
a600774. Source acceptance,45 pidfd cases,9 configuration cases, exact UID999 parser-aware
command viability, security review and32 Git-blob bindings are retained; none are reopened.

The missing acceptance is the actual target installation/effective service boundary and the
permitted run-bound preflight plus owner-to-Runner journey. The actual e2e-runner role owns
required runtime execution, with Codex owning technical preparation, tracking and Git delivery.
No successful installation, measurement, signature or receipt is inferred from prior source tests.

## Execution checkpoint

Runtime role dispatched after473e559 push. Evidence destination:
docs/sdlc/evidence/s2-runtime-qualification-a600774.md. Initial designated e2e-runner inventory is recorded below; installation and measurements
remain pending actual observation.
Private material stays inside the root-controlled WSL target. Preserve existing Store/state,
fail closed on identity/path conflicts and ambiguous operations. No automatic re-signing or
restricted scenario execution. No unrestricted dispatch or personal human signature claim.

## Remaining acceptance

Actual byte/ownership verification; effective systemd isolation/rate limits; current run/spec/nonce
observations and truthful root-machine signature; authenticated fresh bootstrap and issuance;
unchanged owner envelope, Store/dispatcher grant, Runner execution and actual receipt. Record each
result or precise failure and direct correction. S2-5 remains after this task; S3 is unstarted.

## Operator contract delta — preflight inventory is not Runner-signed

On 2026-10-30 the operator explicitly directed: remove the requirement for a Runner signature on
the preflight inventory and do not require it again. This supersedes the earlier S2 E5 wording and
the inherited signed probe artifact as an acceptance prerequisite; the historical signed artifact
remains factual evidence for its original run only.

The probe still must be executed in its configured non-root isolated systemd unit. The source
contract requires Supervisor to read a root-owned mode-0600 record, but this checkout does not yet
implement or prove the step that captures the unit's stdout into that file. Do not treat file
ownership, a synthetic fixture, or a probe report alone as proof of root capture. Supervisor
continues to require exact run/spec/nonce binding, all seven positive checks, complete socket
enumeration, and the separately root-signed network-policy attestation. The policy attestation is
accepted only after measured facts are independently verified; it does not authenticate the probe
inventory. Dispatch-instruction signatures, Runner TestRun signatures and other product checks are
unchanged.

The previous code required a symmetric probe key in Supervisor and exposed probe signing helpers in
`preflight.py`/`signer.py`. The working-tree correction removes those requirements and validates a
strict unsigned inventory at the root-owned input boundary. Store still hashes and persistently
consumes the exact run/spec/nonce-bound record. The designated functional-test reviewer reports 65
passed, 8 skipped, and the security reviewer found no source regression assuming root capture; both
are source-level evidence only. Runtime root capture, installation, service activation, Store/API,
and owner-to-Runner journey remain `NOT_RUN`. See change record
`0597-s2-4-remove-runner-probe-signature.md`.

## Current architecture/runtime finding

The designated `e2e-runner` reports that no bootstrap/service request was sent: the prior probe
invocation had ended, and current target checks found the probe, Supervisor, signer, assignment,
issuer, dispatcher and Runner units inactive, with both preflight record and Store absent. Its
read-only source audit identified the earlier signer→Supervisor dependency cycle; removal of the
probe-signature dependency is the operator-directed code remedy. This report is role evidence, not
a newly reproduced current-target run. Continue only the exact configured run after the updated
source/tests/review are complete. Restricted process-kill, crash/recovery, mutation, E8 and policy
selectors remain `NOT_RUN`.

## First observed target checkpoint

The actual e2e-runner reported fresh Ubuntu-24.04 target inventory at
2026-10-30T00:01:52.913942Z against Windows control HEAD473e559. PID1 is systemd;
planned new numeric identities and names are absent, configured existing identities match.
Target Store/config directories and candidate units/drop-ins are absent; source units are
inactive/dead or not-found. No drvfs/Windows mount or WSL_INTEROP was observed in that
inventory. Runtime/helper a600 are already staged, selector is still d500. The existing
/run/vst-signer uid995:gid988 mode0710 directory is preserved. Root private preparation
metadata is mode0700/0600 as intended; no private content was exported. This is a role's
actual target observation, not evidence that installation or the probe has succeeded.
