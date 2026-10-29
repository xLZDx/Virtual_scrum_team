# S2 runtime configuration security review — a600774

## Scope and method

Read-only review of the non-secret candidate configuration under
`docs/sdlc/runtime-config/`, its source/task/policy/run/helper bindings, the new
non-root preflight entrypoint and one-shot callers, and the referenced existing
service contracts. No private key bytes were read. No files in the candidate
bundle were changed by this review. No tests or runtime operations were run by
this reviewer.

The candidate describes configuration and intended execution; it is not
evidence that the configuration has been installed, that a runtime probe
passed, or that any reviewer has approved the task.

## Finding and remediation history

### Initial finding — MAJOR, identity attribution

The initial bundle registered a local HMAC key ID as principal `GPT-PM` while
placing its private credential in the local root-controlled preparation and
reviewer layout. The gate verifies `IndependentReview` receipts with the
registered HMAC bytes and the declared principal string. The bundle did not
establish that the credential belonged to GPT-PM or that a receipt was bound to
a correlated GPT-PM response. A locally usable credential could therefore be
misrepresented as an external GPT-PM review.

### Applied configuration correction — finding resolved

The current candidate registers only `vst-independent-reviewer` with key ID
`s2-local-independent-review-20261030`. `reviewer-use-policy.json` now states
that the credential is local, is not a GPT-PM credential, cannot satisfy final
PM Bridge approval, and may sign only after a separately executed reviewer
outcome is durably recorded against the exact reviewed artifact/source. It
disallows self-approval and explicitly makes no claim of resistance to a
malicious policy-owner root. The reviewer secret remains configured for UID
993, mode `0600`, beneath its UID-993 mode-`0700` private directory; the root
preparation directory remains private. Private bytes were not inspected.

This correction removes the external-identity misrepresentation within the
existing root-signed HMAC trust model. It does not prove that a separate review
has happened. A GPT-PM/PM Bridge result remains a distinct evidence item and is
not replaced by this local reviewer identity.

## Scoped checks and evidence

| Surface | Result | Evidence and limit |
|---|---|---|
| Reviewer identity and use | Clear after correction | `reviewer-registry.json` maps the local key ID to `vst-independent-reviewer`; `reviewer-use-policy.json` prohibits treating it as GPT-PM or PM Bridge approval and requires an actual separate outcome. `reviewer-registry-record.json` canonical unsigned-body digest matches the registry content. The registry HMAC itself was not independently verified because its private root key was intentionally not read. |
| Credential isolation | Configuration is appropriately restricted | `installation-layout.json` maps the reviewer key to UID 993/mode `0600`, with a UID-993/mode-`0700` reviewer directory; private preparation remains root-controlled. This is a candidate layout, not proof of installed ownership/mode. |
| Reviewer gate behavior | Existing HMAC trust behavior understood | `tools/vst/signing.py` uses HMAC-SHA256. `tools/vst/gate.py` verifies IndependentReview using the configured `reviewer_keys` entry and enforces reviewer/author principal distinction. Root is the registry trust issuer in this design; resistance to a malicious root is not claimed. No root-controlled local key may be presented as an external GPT-PM identity. |
| Bundle integrity | Consistent at review time | All 32 entries in `bundle-manifest.json` matched their listed file SHA-256 and size. The manifest describes 18 configuration destinations, 9 unit bindings, and 3 unit-override bindings. This check validates the candidate files only, not their installation. |
| Source, task, policy, and run binding | Consistent at review time | The task manifest equals the nested bootstrap manifest; its canonical SHA-256 matches the single S2-4 TestRun assignment in `assignment-delegation-policy.json`. The task/source identity is `a600774649527ff0b33eb81f4d431f8226119b2c`; bootstrap, probe, and run-binding records agree on the run ID and nonce. The policy allows only the exact S2-4 task and `runtime-tests` slot. |
| Runtime/helper binding | Consistent at review time | The canonical transition-manifest digest matches `deployment-source-manifest.json`; helper source, binary digest, helper HEAD/path, and runtime-tree digest match their runner/deployment bindings. This is configuration consistency, not proof of installed helper bytes. |
| Non-root probe | No actionable issue found in reviewed path | `probe-entrypoint.py` requires UID/GID 999:989, reads root-controlled JSON through the existing no-follow bounded reader, waits with a deadline for the root policy attestation, and calls the existing inventory collector. The attestation and probe must still be validated by the root supervisor for the exact run/spec/nonce. No runtime PASS is claimed here. |
| One-shot bootstrap and issuer callers | No actionable issue found in reviewed path | The units use fixed Python/RPC calls, `Restart=no`, bounded startup timeouts, private network namespaces, and narrow authenticated Supervisor operations. The assignment policy contains one exact task/manifest/TestRun slot and does not authorize unrestricted dispatch. The issuance request is a runtime-derived file, not a caller-selected task or replacement assignment. |
| Service rate-limit overrides | Candidate binding is exact; effective values remain runtime evidence | Three root-owned `[Unit]` drop-ins bind the intended 60-second interval and burst of 3 to Supervisor, Runner, and Signer. The pre-existing base-unit warning is documented and retained. The effective systemd manager values must be verified during authorized runtime qualification; this review did not query the target. |
| Model provenance | Truthfully scoped | `model-provenance.json` records configured role model `gpt-6-luna` while marking provider execution `NOT_VERIFIED` and provider-signed identity `NOT_ATTESTED`. It does not claim provider attestation. |

## Final disposition

No remaining actionable BLOCKER or MAJOR was found in this focused review after
the reviewer identity correction. The prior MAJOR is resolved for the
configuration claim: the local HMAC identity is no longer represented as
GPT-PM. The local reviewer credential may attest only a real, separately
executed reviewer outcome bound to the exact artifact. It cannot satisfy the
separate PM Bridge exact-head gate.

This disposition does not certify installed file ownership/modes, effective
systemd state, an E5 runtime measurement, a TestRun receipt, a local reviewer
outcome, or GPT-PM approval. Those require their own observed evidence. No
runtime tests were executed by this reviewer.

## Follow-up recheck — final task adapter binding

A later task-configuration correction adds a leading newline before the trusted
adapter's `PASS <nodeid>` record. The command is identical in both
`allowed_commands` and `mandatory_commands`; this separates it from pytest's
progress character so the existing parser, which accepts lines beginning with
`PASS `, can recognize the recorded successful test. This was checked from
configuration and parser source only; no test was executed here.

Final candidate binding check:

- Canonical bundle-manifest SHA-256: `84397d39bcf26deacfbbfc90a3b73995d76ef346cc366bc8c7f4933f900be3fd`.
- Canonical task-manifest SHA-256: `2dc6fce44a3096a0f35afd78baa70a952ae4aa2d8ad0b00f8bac166e10d4fe32`.
- Canonical assignment-policy SHA-256: `1859bbf777b12ead6ded46581282a976a746071fc844f4f46a2d5baf6e2072cf`.
- The nested bootstrap task equals the standalone task; the policy digest is
  consistent in the bundle and Supervisor configuration; source HEAD, run ID,
  nonce, runtime-tree and helper source/binary bindings remain consistent.
- All 32 final manifest-listed files match their recorded SHA-256 and size.

No new actionable BLOCKER or MAJOR was found in this narrow delta. This does
not establish that the test ran or that the parser emitted a passing receipt;
the designated test role owns that runtime evidence.
