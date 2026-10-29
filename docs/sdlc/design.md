# S2 exact runtime bundle and revision transition

Sprint: `39b7cc253f5d` (active S2)
Design scope: source/config preparation and a reversible, bootstrap-only artifact transition from the observed runtime `d5001797cb94113efd9a8dc26e4a15f2dc130976` to source revision `9c1be0fbe42b48f7a9cd547be36af23413fcfc8e`. This transition is supported only while the host remains unconfigured; upgrades of configured hosts are refused and deferred to a separately reviewed design.

## Goal and non-goals

Prepare the smallest reproducible, non-secret deployment description and a safe way to select the exact initial runtime revision on the observed unconfigured host, while retaining the previous revision. Keep all S2 services inactive until their separately gated configuration and activation prerequisites pass verification.

This design does not create or impersonate an instruction issuer, sign E5, execute provisioning, migrate or initialize a Store, activate a service, dispatch work, or close S2. It does not add a scheduler, coordinator, or assignment authority: GPT-PM accepted the existing bounded `DispatchOwnerService` → authenticated Supervisor/Store → filtered Pub/Sub → `StoreBackedDispatcher` path; production M01 remains open pending real authorized runtime evidence (`docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`). The machine issuer/attestor source design is accepted in principle only; production signing and attestation remain gated by the separate trust-contract review recorded by GPT-PM.

## Current behavior and evidence

The point-in-time WSL inventory records `/opt/vst-runtime` resolving to the immutable `d5001797…` directory, and Supervisor, Runner, and Signer units loaded but inactive. It found no Store database by immediate-entry metadata inspection, so Store disposition remains **UNKNOWN**, not “fresh” (`docs/sdlc/evidence/s2-runtime-bundle-inventory-20261029.md`). The observed identity and UID/GID availability is not a reservation; repeat collision checks immediately before any authorized identity creation.

`tools/qa/install_wsl_runtime.ps1` packages the committed HEAD and writes a root-only source manifest containing schema, full HEAD, and archive SHA-256. `tools/qa/install_wsl_runner_runtime.sh` installs a versioned `/opt/vst-runtime-<HEAD>` tree with a matching manifest and checks systemd unit bytes. Both installers deliberately fail closed if `/opt/vst-runtime` already selects a different revision or an installed unit differs. They install immutable artifacts; they do not implement revision switching, rollback, or service activation. The old runtime and versioned worker helper are retained and must not be overwritten or deleted. `docs/sdlc/S2_VERSIONED_WORKER_HELPER_DESIGN.md` records the same no-overwrite rule for the helper. The inventory shows `/etc/vst-runner`, `/run/vst-supervisor`, and `/run/vst-runner` absent, and the observed relevant loaded units inactive. This supports only a first-deployment transition while those preconditions still hold; it is not evidence for a configured-host upgrade.

Service loaders are strict contracts, not config generators: Supervisor requires its exact field set (`tools/vst/supervisor_service.py`), Runner binds the full helper commit, source digest, binary digest, and exact versioned helper path (`tools/vst/runner_service.py`), Signer has a separate key/ledger contract (`tools/vst/signer.py`), Dispatcher has fixed Supervisor/Runner socket paths (`tools/vst/dispatcher_service.py`), and Dispatch Owner accepts only the fixed principal/OpenSSL contract plus a root-controlled trust registry (`tools/vst/dispatch_owner_service.py`). `tools/vst/systemd/README.md` documents the root-owned config paths, service identities, startup preflight, inactive-by-default operator peer, schema-v6 migration gate, and unit ordering.

## Design

Keep the deployment description separate from secrets and executable authority. Add one canonical, non-secret bundle manifest during source/config preparation. It binds:

- repository identity, full source HEAD, exact archive SHA-256, `docs/SANDBOX_SPEC.md` digest, source-manifest schema, and hashes of all six shipped systemd unit files;
- the exact runtime and worker-helper paths, full helper HEAD, helper source and binary digests, and the expected root/group/mode metadata;
- each service config's schema/field set and intended absolute path, owner, group, and mode; fixed service UID/GID and socket/cgroup relationships; and the required unit start order;
- Store disposition as `UNKNOWN`, `FRESH`, or `EXISTING`, with evidence reference. `UNKNOWN` blocks Store initialization, migration, and service activation. It does not block selecting inactive code artifacts because the bootstrap transition neither opens nor changes Store data. An existing Store is read-only inspected and any migration remains behind its separate gate;
- key purpose, custody owner, and expected key-file path only. Never include private key bytes, passwords, tokens, or signing material. Public trust entries may name a verified public-key path and key ID, but must not be fabricated to make validation pass;
- the prior selected runtime, prior unit digests, and rollback target so the transition is reviewable and recoverable.

Config examples produced at this stage are explicitly non-installable templates: values for runtime keys, issuer identity, signed probe, operator attestation, and unresolved Store disposition remain absent. Do not write placeholder JSON into privileged config paths. A schema validator should reject missing values and any unknown field before installation; the existing loaders remain the final runtime contract.

### Ordered operational stages

1. **Source and config preparation (non-privileged).** Finish source changes and their required test/review gates first. Rebuild the archive from the canonical checkout at the exact reviewed HEAD; record archive, sandbox-spec, helper, and unit digests. Prepare the manifest and non-installable schema templates. Reconcile it with the accepted conditional PM scope in `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`. No WSL state changes.
2. **Artifact staging (conditional GO only).** Recheck host identity and exact old runtime, helper, and unit fingerprints. Require `/etc/vst-runner`, `/run/vst-supervisor`, and `/run/vst-runner` absent; require all six S2 service/socket units inactive, no systemd jobs for them, and no nonempty S2 service cgroups. Verify that the exact new versioned runtime and helper destinations are absent, then install them with no-replace semantics and verify owner, group, mode, manifests, and every digest. Do not create identities, configs, sockets, or Store data in this stage. Store remains UNKNOWN and unopened. Keep every old immutable artifact. Any failed precondition or destination collision aborts before selector or unit changes.
3. **Bootstrap artifact selection (new code required).** Add a separate explicit root transition operation limited to that unconfigured state. It rechecks every staging precondition immediately before mutation and verifies exact old selector/link and fixed-name unit bytes plus exact staged runtime/helper fingerprints against the reviewed manifest. It must refuse if any service config/runtime/socket directory exists, any relevant unit is active/has a job, an S2 cgroup is nonempty, any baseline fingerprint differs, or a destination is unexpected. Preserve old selector and unit bytes as a verified rollback snapshot. Replace the selector and each unit file through same-filesystem temporary files and atomic rename; each individual rename is atomic, while the multi-path set is not one atomic transaction. Record completed replacements in a root-owned transition journal before proceeding to the next path. Re-read and verify all selected paths and fingerprints. Never start, enable, or reload a service as part of selection. This design explicitly refuses configured-host upgrades; support for them needs a later independent cutover/rollback design.
4. **Configuration and Store classification (separately gated).** Only after artifact selection, recheck identities and inspect Store using the authorized procedure. Install exact root-owned configuration only when all values and trust references are known. Store UNKNOWN continues to block initialization, migration, and activation; an EXISTING Store remains read-only until its separate migration gate. Do not generate issuer authority or attestation keys as a side effect of artifact selection.
5. **Service activation (blocked).** Keep units disabled/inactive and production dispatch fail-closed until an authorized issuer policy/key and the applicable accepted machine or human E5 trust contract exist, plus authentic fresh run-bound host/probe evidence passes against the exact sandbox-spec and policy digests. A machine attestation must be explicitly machine-labelled, sourced from independent trusted measurements, and accepted under its own versioned trust domain; it must never masquerade as a human signature. Then, only within the accepted mapped scope and separate activation gate, execute the precise unit activation and runtime E2E sequence. Restricted process/crash/mutation/policy selectors remain `NOT_RUN`.

## State ownership and failure behavior

### Staging and journal implementation contract

Use two different manifests. The reviewed pre-stage source plan binds source HEAD, archive,
sandbox spec, helper source/build recipe, shipped unit bytes and fixed target paths. It does not
claim installed-runtime or compiler-result provenance. After stage-only finishes, a read-only
target-host `prepare` emits a second canonical manifest with the actual complete new tree and
helper binary digests plus the exact old selector/unit/runtime baseline. GPT-PM must review that
second manifest's digest before selector mutation; a locally calculated digest is not approval.

Add an explicit `--stage-only` argument to the distro runtime installer and a corresponding
`-StageOnly` argument to the Windows handoff. Launch the selector with Python `-B -I -S` and
load it from the fixed full-versioned runtime path so importing it cannot create `__pycache__`
inside the immutable measured tree. The repository wrapper must disable bytecode before import.
Default install behavior stays fail-closed and
unchanged. Stage-only validates the same source archive, host restrictions and immutable tree.
Before publication it rescans the complete staged runtime tree against the reviewed member map;
missing, extra, changed, linked, or special files fail closed on fresh and existing destination
paths. Stage-only installs only the absent versioned runtime/helper and must skip the fixed selector/unit
collision checks and ALL selector/unit writes. Report `selected=false`; the separate bootstrap
transition consumes the staged tree, never calls the default installer, and verifies its complete
tree against the source bundle plus helper identity before mutation. Stage-only is not selection
or authority to activate anything.

There are two distinct reviewable records. Before staging, a source/staging plan derived from
the committed archive binds HEAD, archive/spec/unit/helper-source hashes, compile flags and
requested fixed destinations. The V2 plan records every archive member's path, type, size, and
SHA-256; the WSL receiver compares every extracted member with that reviewed map before it hands
the bundle to either installer. A separate non-secret target inventory binds the source HEAD, an
observation no older than five minutes, and compiler selector/resolved path/metadata/digest.
Windows checks its pin and freshness, then WSL repeats them after transfer and verifies the actual
compiler bytes before building the helper. This reviewed plan and source/test gate are prerequisites
to artifact installation.
After staging, a separate read-only `prepare` operation binds the actual complete installed tree,
compiled helper digest/metadata and current old selector/unit baseline. Its exact manifest digest
must be reviewed before selection. A prepared selection manifest cannot retroactively authorize
earlier staging. Neither manifest is a GPT approval, authority delegation or activation permit.

Use a write-ahead journal under a root-owned, mode-0700, no-follow transition directory with
exclusive lock. Before any replacement, persist the exact old and new fingerprints, retained
old bytes/link target, ordered paths and manifest digest; fsync the journal and containing
directory. For each path persist/fsync `intent`, recheck current old fingerprint, rename the
prepared file/link, fsync its parent directory, verify new fingerprint, then persist/fsync
`complete`. A missing completion record never proves a rename did not happen. Recovery checks
EVERY path against old AND new fingerprints, regardless of progress flags: old means untouched
or already restored, new means eligible for exact old restoration, anything else means unresolved
and prohibits writes/start. Refuse an unfinished prior journal on normal apply; explicit recovery
requires its exact original manifest digest and the same inactive/unconfigured preconditions.
Persist/fsync restore intent and completion around each restoration too. Snapshots and journal
are retained, never deleted by successful apply/recovery. No process-crash test is authorized;
later source tests use deterministic injected exceptions only.

The Git source/archive owns revision identity; the root-owned manifest owns the deployment's immutable digest record; systemd owns active unit/process state; the root-controlled Store remains the sole assignment/lease authority; and each root config references purpose-separated key paths without transporting secret bytes in the bundle. No cross-service atomic transaction is assumed. During bootstrap selection, the selector and each fixed-name unit file are changed only while the host is unconfigured and all affected units are inactive. Atomicity applies per rename only. A root-owned journal records progress across the selector and unit replacements. A partial transition fails closed: keep services stopped, inspect which exact renames completed, and restore the prior selector and each old unit file from the verified snapshot before any start. If rollback cannot be proven, leave services inactive and stop for recovery; never claim a collectively atomic replacement. Never infer success from a command exit alone: re-read selector, files, ownership, digests, unit states, and Store/claim disposition.

If the host differs from its reviewed baseline, an unexpected config/key or Store mutation is observed, a key or required signature is unavailable, or any per-path replacement/rollback cannot be proven, stop before modifying that dependency. Store UNKNOWN alone does not block inactive artifact staging/selection, but it blocks any Store initialization, migration, or activation. Preserve all prior runtime/helper artifacts and evidence. No automatic retry may reinterpret an ambiguous dispatch result or reactivate production dispatch.

## Rollback

Before the selector/unit transition, rollback is simply to leave the old selector and units untouched; newly installed versioned artifacts remain retained and inactive. After transition starts but before any service start, use the journal to restore the old selector and each unit file through individual atomic renames, verify their hashes and inactive state, and retain the new immutable tree for diagnosis. These operations are recoverable as a sequence, not one atomic transaction. Once any service starts, do not use this bootstrap rollback as a live downgrade: first reconcile Supervisor/Store/Runner claims and outcomes under the existing recovery contract, then use a separately reviewed and authorized stop/rollback procedure. Never delete or overwrite the old runtime or helper.

## Acceptance and verification plan

The design is accepted when the bundle is deterministic for the exact reviewed HEAD and contains no secret material; schema templates map exactly to existing loaders; Store UNKNOWN/EXISTING states cannot trigger initialization or migration; artifact staging preserves prior artifacts; bootstrap selection refuses a configured host, active/job-bearing units, nonempty S2 cgroups, stale baseline, collision, digest mismatch, and incomplete rollback metadata; the journal recovers interrupted per-path replacements; and no unit is activated by preparation or selection. Configured-host upgrades remain unsupported and must be refused. After implementation is complete, assigned functional/e2e test owners should verify archive/hash binding, schema rejection, no-overwrite behavior, interrupted transition recovery, per-path selector/unit rollback, inactive-unit invariants, refusal on configured hosts, and permitted mapped runtime evidence. No tests, checks, provisioning, migration, or service activation were run for this design artifact.

## Ownership and remaining gate

Codex owns the manifest/schema-preparation and reversible transition implementation plus permitted evidence. GPT-PM owns architecture/source adjudication and the exact-head final gate. The operator is the sole human owner for any human attestation and for genuine key-custody actions. GPT-PM accepted bounded machine trust in principle, but the precise versioned issuer/attestor contracts, independent measurement provenance, key custody/revocation, and separate production authority gate remain incomplete. Until those contracts are reviewed and their applicable evidence is genuine and verified, activation and production dispatch remain blocked, and S2 remains open.

GPT-PM adjudicated the machine issuer/attestor architecture under request `a3e130f0-9aec-4304-b001-388a45c0be55` (reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`): bounded machine trust is accepted in principle, but production signing/attestation remain held pending corrected provenance, independent measurements, and separate authority review. This decision does not authorize production keys, replace the active E5 contract, or activate services. The design must be amended with the precise versioned trust contracts before those components are used.
