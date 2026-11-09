# S4-E GPT-PM code review scope

Task: S4-E synthetic seeded-failure fixture catalog (one task). Base fd99821 (S4-D approved and pushed), head is the branch head at request time.
Delta: tests/qa/seeded_failure/catalog.json (new), tests/qa/test_s4_seeded_failure_catalog.py (new; the filename is mapped to the seeded-failure category by the accepted tools/qa/build_registry.py), docs/qa/categories.json (generated). No product source and no QA tooling logic is changed.

What it delivers (plan S4.5.2, AC-12, AC-13): eight fixtures SF-001..SF-008, each a controlled input record fed to the UNCHANGED product interface with a non-approving outcome: stale HEAD (gate NO_GO), missing required receipt (MODIFY), invalid signature (MODIFY), out-of-scope diff (diffgate FAIL OUT_OF_SCOPE_PATH), skipped required test ID (QA accounting NOT_PASSED), artifact digest mismatch (MODIFY), tampered event chain on a copy of a real store (verify_event_chain False), stale epoch (MODIFY). Each test first checks that the input sha256 equals the committed catalog value (so the catalog cannot drift silently), then asserts the observed rejection equals the committed expected rejection and is non-approving. A shape test checks 8 unique entries and that every linked test_id exists. No patching, monkeypatching or source rewriting; the module docstring states this is NOT mutation testing and proves only these fixtures.

Settled, do not reopen: Windows-only, WSL NOT_RUN, trust model of S4-B, no mutation runs, no big suites, accepted S4-A..S4-D.

Known limits (accepted, please do not treat as findings of this delta): the expected_rejection strings were produced once from the observed behavior of the current product, so they pin current behavior and are not an independent oracle; SF-005 exercises the QA accounting through _resolve_cases only; SF-007 must drop the append-only trigger on a copy of the database first, which models an attacker with file access; a wrong-event-key fixture is covered by an existing test in tests/vst/test_e3_store.py; the evidence-envelope content and the no-skip gate that consumes these results are S4-F.

Evidence (test agents, no big suites): the new module 9 passed in 0.96 s on fd99821 (author agent, one run) and a confirmation run by a second agent on the final head 0d6f9b6 (see the report in core/DECISION_LOG.md); real_manifest passes on the final head. NOT_RUN: mutation runs, WSL, full S4-A/S4-B files, the real lanes.

Ask: find the complete BLOCKER/MAJOR set for this delta only.
