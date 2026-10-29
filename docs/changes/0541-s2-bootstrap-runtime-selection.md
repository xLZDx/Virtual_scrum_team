# Change 0541: prepare exact S2 bootstrap runtime selection

## Purpose and provenance

Implement the reviewed phase-6 runtime-only design in canonical checkout
`D:\Repo\Virtual_scrum_team`; no per-sprint worktree is used. AF sprint
`39b7cc253f5d` tracks existing S2. The source/stage plan review and the post-stage selector
manifest are distinct. The selector manifest digest supplied to `apply` must come from the
external exact-manifest review; computing that digest here is not approval.

## Changed paths and behavior

- `tools/vst/runtime_bundle.py` defines a closed canonical non-secret manifest contract and a
  candidate builder from the staged exact runtime. It binds source/archive/spec revisions, old
  runtime and selector, complete new runtime tree, helper source/binary/path/identity, six old/new
  unit fingerprints, and fixed parent metadata. Duplicate, unknown, missing, noncanonical and
  mismatched fields fail closed.
- `tools/vst/bootstrap_runtime.py` provides the root-only prepare/apply/recover entry point and
  `tools/qa/select_wsl_bootstrap_runtime.py` is the canonical-repository wrapper. The immutable
  runtime package contains the implementation under `tools/vst`, allowing a fixed full-versioned
  module path at execution.
- Apply requires the externally supplied exact manifest SHA-256, absent config/runtime socket
  paths, all six units inactive with no jobs or populated service cgroups, unchanged root-owned
  parents, exact old selector/unit/runtime and staged new artifact fingerprints. It does not open
  Store, install config, create keys, enable/start/reload services or issue tasks.
- Every selector/unit replacement is one same-directory atomic operation, not a collective
  transaction. A root-only write-ahead journal syncs intent before each rename and completion
  after filesystem sync. Recovery checks the whole set against old/new states before any write;
  unknown third-party bytes refuse the whole recovery. Restored prior file snapshots and displaced
  new files are retained; an absent prior unit is restored by moving the new file to a retained
  quarantine, not deleting it. Configured-host upgrades are not supported.

## Review and verification state

This source is not yet independently reviewed or test-verified. Per workspace test ownership, the
functional-test-reviewer/e2e-runner author and execute mapped tests only after all S2 coding is
complete. No tests, build, provisioning, migration, Store access, service activation, or runtime
selection command was run while authoring this source. The source/stage installer path is being
implemented separately. Required follow-up: code review the whole change; hand the schema/API and
failure matrix to the test owners after source completion; fix all valid BLOCKER/MAJOR findings;
produce the exact source archive/manifest and obtain the required GPT-PM gates before any
real staging or selection.

Machine issuer/E5 contracts remain separate candidate work; GPT-PM's two MAJOR findings are not
closed by this runtime selector. Production keys, machine E5 selection, service activation, and
S2 acceptance remain open. Restricted process-kill/crash/mutation/E8/policy selectors remain
`NOT_RUN`.
