---
name: release-documentation
description: Produce accurate technical and user documentation, ADRs and release notes from the real code and accepted stories. Use for TDD authoring and at sprint/release close.
---

# release-documentation

## Apply when
A design needs a TDD, a decision needs an ADR, or a sprint/release needs user-facing notes.

## Method
1. Take facts only from code, accepted stories, acceptance evidence and change records; verify commands, paths, flags and endpoints against the source.
2. TDD: requirement -> story -> acceptance -> test map; design summary; interfaces; failure modes; rollout/rollback.
3. ADR: context, decision, consequences, alternatives rejected.
4. Release notes: what users can now do, changes in behavior, known limits, migration steps; link the sprint report.
5. Write for the stated reader; all text committed to git is English.

## Required output
Docs under `docs/` with changed paths listed; stale docs found but not changed, with reason.

## Do not
Document unimplemented behavior as done; invent commands; rewrite settled documents without cause.
