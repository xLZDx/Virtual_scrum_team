# Change 0551: Reconcile S2 evidence and original epic coverage

## State and provenance

Documentation reconciliation against canonical checkout baseline
`6a6d7886746379e2b68218bd8d4fba01edf0bf56`. The working tree already contained concurrent
S2 source, test-fixture, state and documentation changes at task start. Those changes are inherited;
their authorship is not verified. This task edited `DECISION_LOG.md`, `LESSONS_LOG.md`, and
`verify-evidence.md`, generated the registry from the explicit index inputs, and staged/committed
the listed scope. The matrix, issuer design, public evidence, and legacy fixture repair were
already present at baseline; their authorship is unverified.
Protected `docs/sdlc/evidence/s2-functional-test-run.md` and `.git/vst-private-evidence/` were not
read or staged.

## Reconciled evidence

- Included the already-present `docs/sdlc/S2_ORIGINAL_EPIC_COVERAGE_MATRIX.md` to map the original E1–E8 and D1–D2
  acceptance denominator to available evidence. It distinguishes historic/component passes,
  skips, restricted `NOT_RUN` work, runtime authority, and current acceptance. It does not add
  overlapping counts into a project-wide total.
- Included the already-present GPT-PM recovered correlated reply in
  `docs/sdlc/evidence/s2-bootstrap-source-and-root-issuer-adjudication-20261029.md` as the source
  for the bounded bootstrap `GO — SOURCE` and issuer `MODIFY` decision. The transport was recorded
  uncertain, but the exact correlated reply was recovered without resending. Production authority,
  keys, provisioning, activation, E5 and final S2 approval were excluded.
- Included the already-present root-bound issuer design and its required crash-consistent issuance protocol. It
  remains a design proposal pending exact source reviews and GPT-PM verification; no signer or
  activation is claimed.
- Included the already-present public machine observations as unsigned diagnostics. Windows fixed collection and
  normalization remain incomplete; the partial PowerShell 7 snapshot is not a substitute; WSL
  collection is not authenticated cross-source policy evidence. E5 remains UNKNOWN.
- Included the already-present focused historical schema-v5 fixture repair evidence: the functional-test-reviewer
  reported the exact two selectors passing, 6 passed / 0 failed / 0 skipped. This is fixture
  maintenance evidence on a disposable database, not full-suite or S2 acceptance.
- Updated `verify-evidence.md`, `DECISION_LOG.md`, and `LESSONS_LOG.md` with pointers, decision
  status, provenance distinctions, and lessons. Corrected the 0552 record's verification line:
  the implementer reported one accidental `git diff --check` invocation with no output. This
  report was not independently reproduced and is not a test or acceptance result. The corrected
  0552 wording remains unstaged for coordination with that record's owning commit.

## Verification and limits

- No tests, checks, build, CI, migration, runtime provisioning, activation, or collection were
  performed for this documentation reconciliation. Registry generation is a deterministic
  documentation artifact operation only.
- `tools/build_document_registry.py` reads the Git index. It was run after staging the explicit
  intended registry inputs. Registry source paths were staged explicitly; no blanket add was used.
- S2 remains NOT APPROVED. Production signing authority, current E5, restricted scenarios, final
  exact-head reviews/approval, and runtime acceptance remain open with the owners identified in
  the verification matrix. S3–S5 implementation remains sequenced after S2 acceptance.

## Changed scope

- `docs/changes/0551-s2-evidence-and-original-epic-reconciliation.md`
- `docs/sdlc/verify-evidence.md`
- `docs/sdlc/S2_ORIGINAL_EPIC_COVERAGE_MATRIX.md`
- `docs/sdlc/S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md`
- `docs/sdlc/evidence/s2-bootstrap-source-and-root-issuer-adjudication-20261029.md`
- `docs/sdlc/evidence/s2-legacy-v5-fixture-run-20261029.md`
- `docs/sdlc/evidence/s2-machine-observations-20261029.md`
- `core/DECISION_LOG.md`
- `core/LESSONS_LOG.md`
- `governance/DOCUMENT_REGISTRY.md`
- `tests/vst/test_s2_persistent_runner_service.py` (inherited repaired fixture; included as
  evidence-linked scope, not claimed as authored in this task)

The concurrently modified 0552/0553 source and change records, staging-plan JSON, state files,
protected evidence, and private raw evidence are excluded from this change's commit.
