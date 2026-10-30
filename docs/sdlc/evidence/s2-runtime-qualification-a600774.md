# S2-4 runtime qualification checkpoint

Date: 2026-10-30
Owner: Codex
Execution role for runtime tests: `e2e-runner`
Status: **IN PROGRESS — current run and owner-to-Runner receipt not established**

## Accepted scope

S2-4 requires current source-bound runtime evidence, a real owner-to-Runner result, and measured
run-bound environment evidence. Source/test results and a prior probe report do not satisfy these
runtime criteria. The only permitted Runner selector remains
`tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment`
with one attempt and no retry after an ambiguous outcome. Process-kill, crash/recovery, mutation,
E8, and policy selectors remain `NOT_RUN`.

## Prior reported observation — not current acceptance

The inherited record for source `a600774` reported a successful probe for run
`s2-runtime-20261030-e91cc4b17e7b474b86b29d749247e791`, nonce
`79538b5074ea4eee9442f284db4d6e8f`, invocation
`a441f02f468c4fc2b6151c5468cc65cf`, MainPID `370`; it reported seven checks passed, zero enumerated
sockets, denied host-path access, and a non-root process in the intended private network namespace.
The inherited report listed attestation SHA-256
`18e2eb4f54fdf621db0f6e169fbef7fcb1cd59bf17f59d74ad21f71fdceb0afc` and root-evidence SHA-256
`2124b611e2e3e4c72d6cd21e2b75c171662619f5f27d1dbd416a8e6ff52f0e53`. This run has ended, its
preflight file is absent, and its outcome is not reused as current evidence or a Runner receipt.

## Resolved source-contract issue

An earlier diagnosis against the old `a600774` runtime described a Runner-signed probe as a startup
prerequisite. That requirement was removed by accepted S2-4.1; S2-4.2 provides root capture of the
unsigned measured inventory plus the separately signed network-policy attestation. See
`docs/changes/0597-s2-4-remove-runner-probe-signature.md` and
`docs/changes/0598-s2-4-root-capture.md`. The staged `f685cc9` and current `80c2b81` source follow
that contract. Do not reintroduce a Runner probe key/signature or treat it as an open blocker. The
root-owned mode-0600 preflight record and separate attestation remain runtime evidence requirements.

## Current read-only target status

At `2026-10-30T02:43:06.339898+00:00`, `e2e-runner` captured the exact source-bound inventory
`docs/sdlc/evidence/s2-runtime-target-inventory-80c2b81deac364ed6466600fd46af47aafe805e2.json`,
SHA-256 `ef7fc473efc734ae2e5be1b4e0181f4bf2d70939c045f2a720301fcae119412d`. Source/requested head
is `80c2b81deac364ed6466600fd46af47aafe805e2`. The selector still points to `a600774`; all nine
S2 units are inactive and no jobs are pending. The Store and current preflight file are absent.
`/usr/bin/cc` resolves to root-owned GCC 13, mode `0755`, SHA-256
`1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26`. The inventory read no
private key bytes and made no target changes.

## Next action

Publish the exact source plan and fresh target inventory for `80c2b81`, then execute only the
bounded StageOnly publication. After verifying the staged payload, rebind the non-secret runtime
configuration to the accepted source, obtain a current root-captured E5 measurement, and run the
single permitted owner-to-Runner selector once. Do not initialize an existing Store, dispatch
production work, or rerun a request after an ambiguous outcome.
