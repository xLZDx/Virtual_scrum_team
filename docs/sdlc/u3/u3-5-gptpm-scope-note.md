# U3-5 GPT-PM code review scope

Task: U3-5, wire the no-skip QA verifier (tools/qa/gate_check.py) into the VST gate. Base b29150d (U3-2 accepted), head = current HEAD. Review the delta only: tools/qa/gate_bridge.py, docs/sdlc/u3/GATE_BRIDGE.md, tests/qa/test_u3_gate_bridge.py (tests are NOT_RUN; judge by reading), the one-line entry in tools/qa/build_registry.py.

Delivers: make_qa_artifact_resolver(repo_root, expected_head, registry, fallback) for the existing artifact_resolver hook of tools/vst/gate.py. It returns a sha256 only for an APPROVABLE QA report (check_report) and for its sibling stdout/stderr (sliced by the recorded tail range); every other QA-directory spelling returns None; the fallback sees only provably plain non-QA paths and must return 64 lowercase hex. qa_gate_reasons gives diagnostics through the same read path. tools/vst/gate.py and its authority model are unchanged.

Already fixed after three read-only reviews (python 1 MAJOR, security 2 MAJOR, tests 2 MAJOR): QA-ownership by allowlist and normpath, typed EVIDENCE_TOO_LARGE, per-resolver snapshot, tail-range requirement, inode check, reason redaction, tamper and link tests.

Settled, do not reopen: no caller of gate.evaluate is wired in this task (the hook is the contract); the receipt/path-list comparison is the recorded U2 open limit; reports are candidate-attested (TRUST_MODEL); no rotation of append-only evidence (documented lock-out past the caps); no mutation or test run; AEVE untouched. Tests NOT_RUN (pytest forbidden); evidence is static.

Ask: the complete BLOCKER/MAJOR set for this delta only.
