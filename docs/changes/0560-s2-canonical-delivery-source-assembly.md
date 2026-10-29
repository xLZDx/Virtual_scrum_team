# Change0560: Assemble the current S2 delivery tree in the canonical checkout

Sprint: 39b7cc253f5d

## Baseline and method

All active source work was first committed at3b14f20584fbe8fed1d758753343ea8d132a5706 on
s4-canonical-continuation. That branch and every original commit remain preserved locally; no
rebase, squash, reset, branch/ref deletion, new checkout directory or worktree was performed.
Codex switched the same D:/Repo/Virtual_scrum_team checkout to existing s2-canonical-continuation,
initially43f772d97f9ae7f7a13532fc4750996a75b425aa. This branch had70 commits over the recorded main.
The two existing untracked evidence files were preserved; their contents were not read or staged.

This is an explicit S2 snapshot import, not a claim that the mixed branch's396+ commits were all
S2 or individually replayed onto this branch. Existing full source history remains in its original
refs. The linked JSON manifest lists the source head, original destination base, selected paths
and original Git blob IDs, with the purposeful scope adjustments below. New developers can trace
the imported implementation through retained local source history and the selected S2 records.

## Selected scope

-38 tools/vst runtime/documentation paths, excluding pilot.py and worker_adapter.py.
-29 VST test/helper paths, excluding test_s3 files. Existing restricted tests remain present but
  are not authorized to execute; use only the final allowed selector list after source freeze.
-Six shared QA-path runtime tools required by S2: stage installer, Windows wrapper, narrow helper
  installer/C source, staging planner and bootstrap selector. The S4 QA runner/package is excluded.
-S2 change/evidence/design/phase records, core program ledgers and the shared registry generator.
  Existing historical core log entries are provenance, not newly accepted S3/S4 execution.

The source Store includes shared refactoring introduced during the older S3 work. S2 now requires
its connection-taking epoch helper and generic operation lookup; those are retained explicitly as
shared infrastructure. Four unreferenced S3-only wrappers are withheld: acquire_epoch_idempotent,
resume_epoch_idempotent, charge_idempotent and stop_attempt_fenced. The associated S3 pilot and
adapter remain only in the retained mixed/source refs. Generic HandWrittenWorker timeout
hardening remains useful to S2's existing bounded worker and adds no external candidate feature.

No private evidence or untracked staging-plan candidate is imported as approval. The document
registry is regenerated from this branch's actual tracked/staged files, not copied wholesale
from the mixed tree. Agentic_Framework remains associated with existing S2 phase7; no phase8
approval is copied or generated.

## Verification and next action

No tests, test collection, checks, build, CI, provisioning, runtime signing or service activation
were performed during assembly. Source is ready for designated test-role collection/authoring
and permitted execution after Codex records this source/delivery freeze. Historical results do
not establish acceptance at the assembled tree. Functional/E2E tests and relevant specialist
reviews must find/fix any shared-file dependency or integration defect before fresh GPT-PM gate
and the single S2 PR. S3–S5 wait for S2 closure.
