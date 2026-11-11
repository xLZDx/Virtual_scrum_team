# U6-1 GPT-PM scope note

Base: 8c9ab2c (U6-0 approved). Task U6-1: install/rollback runbook with an exercised rollback proof.

- tools/vst/rollback_exercise.py: snapshot hash (sorted rel posix paths, NUL and length framing, .git excluded at any depth, symlinks/junctions/reparse points refused) and exercise_rollback; proof = before == after_rollback and after_change != before. Fail closed: expected failures become error codes, never exceptions.
- docs/sdlc/u6/RUNBOOK.md: install, role-table pin, schema rollback, code-change rollback, verification, known limits. Every command was matched to the repo by reading; none was run (NOT_RUN).
- Tests are NOT_RUN (operator prohibition); reviewed statically by python-reviewer and functional-test-reviewer; one remediation batch applied (2 MAJOR + minors).
- Known limits: parents of root are not checked for links; hashing is not concurrency-safe (tree must be quiescent); chunked hashing not done; failed change or snapshot failure after change skips rollback.
- tools/qa/build_registry.py and docs/qa/categories.json: registry bookkeeping only.
