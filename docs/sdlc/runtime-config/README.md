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
- The runner and one-shot probe units both mask WSL host-integration roots (`/mnt`, `/usr/lib/wsl`,
  `/init`, `/run/WSL`, and `/tmp/.X11-unix`) with root-owned `InaccessiblePaths` drop-ins. This
  follows the actual probe finding that the default WSL unit namespaces exposed host mounts; the
  signed policy must remain absent until the same-path runtime check confirms those paths are
  inaccessible. Explicit inaccessible `/home` and `/root` paths keep host home data hidden, while
  an empty read-only `/run/user` tmpfs keeps host user sockets hidden and lets the required socket
  inventory confirm a complete empty scan.
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
5. Root independently verifies the effective network, mount/socket and systemd facts for the
   exact one-shot probe invocation, then publishes the run/spec/nonce-bound signed network-policy
   attestation. The non-root probe emits canonical measured JSON; the root controller captures
   that exact output into the root-owned mode-0600 preflight file. The probe inventory has no
   signature requirement. Reject failed or incomplete measurements; never turn unknown into PASS.
6. Start Supervisor only after it validates the captured inventory and root network-policy
   attestation. Then start the other configured runtime services for the authorized qualification. The bounded
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
source a600774. Its 45 focused passes and actual kernel-pidfd proof are in change0592. The current
candidate is rebound to source `80c2b81deac364ed6466600fd46af47aafe805e2`; its immutable runtime and
helper are staged but not selected. The official read-only `bootstrap_runtime prepare` generated
the exact transition manifest at `2026-10-30T03:03Z`, binding the staged tree, helper, current
selector and unit fingerprints. The non-secret bundle remains `PREPARED_NOT_INSTALLED`; runtime
selection and configuration installation are separate, unperformed steps.

The source unit templates contain ignored [Service] StartLimitIntervalSec lines. The three
explicit unit-overrides add the intended 60-second interval/Burst3 under [Unit]; retain the
nonfatal base-template diagnostic and verify the effective manager values after installation.
