PROJECT: virtual_scrum_team
SPRINT: LINK
TASK: LINK-1 (one task)

# LINK-1 GPT-PM scope note

Base: origin/main e2613e8. Head: the commit under review (explicit sha given by the review command).

- Change: a skeleton switch between two ways VST can work with AEVE. Mode `gates` is the current U1-U6 scheme and the default. Mode `router` (AEVE does the checks, VST only routes reports) is declared but refused in code (ROUTER_CAPABILITY_READY = False) until AEVE sprint S20 tasks S20-T07 (task packet) and S20-T08 (handoff verifier) exist; both are NOT_STARTED in AEVE.
- Files: catalog/link_mode.json, tools/vst/link_mode.py (load, resolve, set_mode, CLI), docs/sdlc/LINK_MODE.md, tests/vst/test_link_mode.py, a category entry in tools/qa/build_registry.py, regenerated docs/qa/categories.json (separate commit), log entries.
- Trust boundary: the catalog file is untrusted input. Load fails closed on schema, key, type, duplicate-key, NaN, non-UTF-8, BOM, lone-surrogate and router-pin violations. Refusals leave the file byte-identical. Writes are atomic (temp file in the same directory, os.replace, bounded retry on Windows winerror 5 and 32).
- Not done on purpose: nothing reads the mode yet, so VST behaviour is unchanged; router behaviour is not implemented; no integration with the review loop or final package.
- Prior review: python-reviewer found 1 MAJOR (router availability trusted from data) and 1 MAJOR (lone surrogates escaping the typed error) plus MINOR items; one remediation batch; verification round found no BLOCKER or MAJOR. functional-test-reviewer wrote the tests and hand-traced them (all PASS-by-trace, no defect in the code). One test class patches the constant to reach the otherwise unreachable WRITE_FAILED branch.
- Not run: pytest and every other check (forbidden by the operator); all test results are hand traces. Windows retry behaviour is simulated, not observed.
- Logs: core/DECISION_LOG.md and core/LESSONS_LOG.md entries in the commits.
