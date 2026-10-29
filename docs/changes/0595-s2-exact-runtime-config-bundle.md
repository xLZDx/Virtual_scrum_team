# Change 0595 — Exact non-secret configuration bundle for the existing S2 runtime

Date: 2026-10-30
Owner: Codex
Task: S2-4 runtime inputs, one ordered task

## Concrete acceptance delta

The observed dedicated WSL target had no /etc/vst-runner configs or owner/dispatcher identities.
Prepare exact inputs for the existing accepted I01 implementation, not a replacement coordinator.
Existing operator delegation is carried forward; actual artifacts and observations must still be
produced. The concrete Python pidfd-name correction was delivered in a600774 (change0592).
The strict existing StageOnly handoff then staged that exact source/helper without selecting it,
changing units/config/Store, or starting services. Actual stage evidence is linked below.

## Bundle content and binding

docs/sdlc/runtime-config/bundle-manifest.json identifies every bound non-secret artifact, exact
configuration destination/mode/owner, nine unit bindings and three rate-limit drop-ins.
The source/runtime/task identities are explicit. The read-only runtime deployment snapshot is
a single fixed /var/lib/vst-runner/repository; all development remains in the canonical checkout.
A real source Git bundle is retained under .git for deployment, with SHA and size in the binding.

The six service/fence configs use implemented closed schemas. The exact bootstrap request and
assignment policy allow only one qualification task/slot and source/manifest digest. Root issuer
and grant keys are distinct; only public PEM bytes and fingerprints are in this repository.
Private material is prepared under root-owned mode0700 WSL staging and is never attached/exported.
The isolated signer and local reviewer credential destinations have separate identities/modes.

Configured model provenance is an actual role-model binding, not a provider signature or proof
of provider execution. Independent local review uses vst-independent-reviewer, never a local
key falsely named as GPT-PM. Its usage policy requires a real separately executed reviewer result;
it cannot substitute for actual final correlated GPT-PM acceptance through PM Bridge.

The non-root probe entrypoint invokes the existing measured preflight after independently
controlled root policy evidence is published. It neither holds a signing key nor manufactures
PASS. The actor is a delegated root machine policy signer, with no personal human signature claim.
All source cryptographic checks, role separation and restricted-selector limits remain enforced.

## Actual review and verification records

- docs/sdlc/evidence/s2-4-pidfd-stage-a600774.md: actual immutable stage/build output, helper SHA
  40cca741389d4b711dfca45da2698846a6acc801be006456cc7af207e2dd6353.
- runtime-transition-manifest.json: official metadata-inclusive runtime tree digest
  6ec90c3ef82478b09f07390c0d3f38f36317efb58976cef4c060dc1968649b12; canonical transition digest
  6a9db55005044ba306f4135c93fa411a4ce7e0572482b32ed7ecfecbea35e50a.
  E2E content-only tree digest 42faf635 is separately labeled and is not interchangeable.
- docs/sdlc/evidence/s2-runtime-config-functional-a600774.md: actual mapped functional runs,
  initial adapter failure and final targeted rerun results.
- docs/sdlc/evidence/s2-runtime-config-unit-verification-a600774.md: actual systemd-analyze
  verification. The ignored old [Service] rate-limit diagnostic is retained; explicit [Unit]
  drop-ins provide the intended settings. Effective live-manager values are verified later.
- docs/sdlc/evidence/s2-runtime-config-security-a600774.md: initial false reviewer-identity MAJOR
  and its narrow correction; final source/config review has no actionable BLOCKER/MAJOR.
- The exact UID999 command and trusted-parser viability result are recorded in the functional
  evidence above; they are not a full owner-to-Runner runtime result.

The inner existing test is a disposable Store fixture mapped to REQ-003. Its real observed pytest
PASS IDs are not relabeled as production evidence. The outer real service journey remains a
separate S2-4 AC-1/REQ-005 qualification after bundle delivery. Initial pluggy hook-parameter
failure was corrected to report. A subsequent integration inspection found that pytest progress
produced `.PASS`, which the existing trusted parser correctly ignored. The adapter now emits a
leading newline; mapped tests must assert the actual parser returns the exact executed ID, rather
than accepting a substring. Caches are disabled and no fake PASS command is used.

Final candidate identities after this direct regression correction:
- TaskManifest canonical SHA-256: 2dc6fce44a3096a0f35afd78baa70a952ae4aa2d8ad0b00f8bac166e10d4fe32.
- Assignment policy canonical SHA-256: 1859bbf777b12ead6ded46581282a976a746071fc844f4f46a2d5baf6e2072cf.
- Bundle manifest canonical SHA-256: 84397d39bcf26deacfbbfc90a3b73995d76ef346cc366bc8c7f4933f900be3fd.

## Final mapped verification

The designated functional-test-reviewer reports the explicit Ubuntu-24.04 focused suite:
9 passed in 2.92s, exit0. The exact TaskManifest argv separately executed as UID999/GID989;
pytest reported one passed and the existing trusted parser recognized the exact required ID.
The current functional evidence preserves the earlier hook-signature and progress-prefix
failures and distinguishes this command viability from service-runner acceptance.
The security reviewer rechecked only the corrected bindings and found no new actionable
BLOCKER/MAJOR; all32 listed payload sizes/hashes match. Unit parsing remains exit0 with the
previously recorded nonfatal base-template warning; effective properties are not yet proven.

The designated test role also verified the actual local reviewer registry HMAC in root process
memory: signature valid, tampered registry rejected, exit0; no secret bytes were exported.
This verifies registry integrity only, not a review outcome or final GPT-PM approval.

## Files and delivery boundary

Changed: .gitignore allows only the two explicitly named public PEM anchors (private PEM remains
ignored); .gitattributes pins runtime-config LF bytes across checkouts; docs/sdlc/runtime-config/ (exact artifact list in its manifest); linked evidence above;
docs/sdlc/backlog.md, requirements.md, test-plan.md, verify-evidence.md;
docs/S2_SANDBOX_WORKER_PLAN_2026-10-24.md; core/STATE.md and
core/DECISION_LOG.md; this record. Existing unrelated protected untracked artifacts are preserved.

This task prepares and verifies exact deployable inputs; it does not claim service activation,
current preflight success, real dispatch, independent review outcome or full S2 acceptance.
Normally commit/push this task after its mapped verification, then execute the next ordered
configuration/runtime qualification work. Existing Store migration and restricted scenarios
remain outside this exact task.

Security reviewer delivery inspection: staged Git blobs match all32 payload sizes/SHA-256
values; no private PEM marker exists in those payloads. Only the two explicit public
anchors are exempted from *.pem ignore. Staged whitespace inspection was clean.
