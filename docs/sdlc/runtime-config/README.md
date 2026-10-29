# S2 existing-runtime configuration bundle

This directory contains non-secret configuration candidates for the existing I01 V1
Supervisor/Store/owner/dispatcher/Runner implementation. Bundle completion requires the final
artifact hashes and mapped verification; creating these files does not install or start services.
The ordered current task is S2-4 in ../backlog.md. Development stays in the canonical Windows
repository. /var/lib/vst-runner/repository is one fixed read-only runtime deployment snapshot,
not a development checkout or a worktree per sprint.

## Binding and technical decisions

- Carry forward the operator's explicit current GO and global technical delegation. Codex owns
  producing the actual configuration, isolated service material and run evidence.
- run-binding.json identifies the concrete run/nonce. deployment-source-manifest.json records
  exact task-source and runtime-source artifacts; these are distinct identities and must never
  be silently relabeled as the current installed revision.
- Service configuration files use the implemented closed schemas. installation-layout.json
  specifies exact destination ownership/modes, isolated private directories and protected keys.
- Public keys and fingerprints are included; private bytes stay in the root-owned mode0700 WSL
  preparation directory. No private material is committed or sent for review.
- model-provenance.json records the actual configured custom-role model. It explicitly does not
  claim provider attestation or provider execution. The root registry binds its actual file hash,
  which is the implemented source contract.
- reviewer-registry.json declares the local technical identity vst-independent-reviewer, not
  GPT-PM. Its UID993 HMAC credential may witness only an actual separate reviewer-agent outcome
  recorded for the exact artifacts. It cannot substitute for the separate correlated PM Bridge
  final acceptance. Root remains the trusted registry issuer; protection against a malicious
  policy-owner root is not claimed. Registration itself is not a review result.
- task-manifest.json uses the designated test role's exact inline pytest adapter. PASS IDs are
  emitted only from actual successful setup/call/teardown reports, never from an echo fixture.
  A leading newline isolates each PASS record from pytest progress; the existing trusted parser
  must recognize the exact executed ID. A substring match or pytest exit zero alone is insufficient.
  Bytecode and pytest caches are disabled. The inner accepted test uses disposable Store state;
  the outer owner-to-Runner service journey must be evidenced by actual runtime events.
- The root network-policy signer acts under delegated operator authority outside Runner/worker
  processes. Any attestation must cover real measured run/spec/nonce evidence and its digest.
  It is machine execution of delegated authority; no personal human signature is asserted.

## Execution order

1. Preserve the exact committed source plan and fresh target inventory; use the existing strict
   stage-only installer to publish the source-specific runtime/helper. Keep actual build/tree
   identities and the unchanged old selector/unit state in evidence. No stale staged runtime may
   be used to claim the new peer-pidfd compatibility code.
2. Complete and verify all bundle file/source/helper/task/policy hashes. Commit and normally push
   the accepted task inputs before the next execution item. Preserve unrelated untracked files.
3. Recheck actual path and identity collisions immediately before installation. Use only matching
   existing identities or create the exact absent candidates; refuse conflicting IDs. Prepare
   private state as specified. Preserve any existing Store; fresh initialization applies only to
   the verified absent fixed target. No existing Store migration is included.
4. Transfer the exact Git bundle/source artifacts and config files to private WSL staging with
   SHA verification and no overwrite. Publish the runtime selector/units using the existing
   fingerprint-bound bootstrap transition contract. Install the exact config/material layout.
   Never expose private key bytes in logs, requests, attachments or repository files.
5. The designated test role obtains actual non-root preflight observations under the fixed
   isolated profile. The independently controlled root signer verifies the effective network,
   mount/socket and systemd facts before signing measured evidence for the exact run. A failed or
   incomplete measurement remains failure/unknown; it is not turned into PASS by signing.
6. Start only the configured runtime services for the authorized qualification. The bounded
   one-shot bootstrap caller submits the immutable request through the existing authenticated
   RPC. Derive issuance-request.json only from its exact successful returned operation identity.
   Preserve the invocation and authenticated response. An ambiguous result stops dependent work;
   there is no automatic task reassignment or signer retry.
7. The separately pinned issuer caller requests the exact instruction. Relay the returned signed
   envelope unchanged through DispatchOwnerSocketClient and actual systemd owner ingress. Record
   Supervisor/Store intent, filtered dispatcher/grant, Runner claim/execution, real test output
   and receipt identities. Use the actual independent review before recording gate acceptance.
8. Record S2-4's exact results and unrun scope, then perform S2-5 final acceptance. Restricted
   process-kill/crash/recovery, mutation campaigns, E8 and policy selectors remain NOT_RUN.

## Current preparation state

The Python3.12 missing SO_PEERPIDFD-name defect was concretely observed and fixed in delivered
source a600774. Its 45 focused passes and actual kernel-pidfd proof are in change0592. The new source was staged successfully. Configuration pins now use the official source-specific
transition manifest, its content-plus-metadata tree digest, and actual compiled helper digest.
The auxiliary E2E content-only tree inventory has a different declared algorithm and is retained
separately; it is not substituted for the transition tree digest. Bundle verification and delivery
remain before installation.

The source unit templates contain ignored [Service] StartLimitIntervalSec lines. The three
explicit unit-overrides add the intended 60-second interval/Burst3 under [Unit]; retain the
nonfatal base-template diagnostic and verify the effective manager values after installation.
