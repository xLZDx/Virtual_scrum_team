# S2-M01 exact-head DiffGate inventory evidence

Date: 2026-10-26  
Repository: `D:\Repo\Virtual_scrum_team`  
Exact committed HEAD: `f0bbac8d64d3abd1aa261dabec1954ca4f0c17a2`  
Branch: `s4-canonical-continuation`  
Test owner: designated `e2e-runner`, GPT-6 Luna

## Test runs

Python 3.14.3; HEAD and status before/after each run were unchanged. The only status entry was the preserved pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md`. Every run emitted one `pytest-asyncio` deprecation warning: `asyncio.get_event_loop_policy` is slated for removal in Python 3.16.

| Command | Result | Duration |
|---|---|---:|
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_diffgate.py -k "runner_"` | Exit 0; 5 passed, 17 deselected | 14.25 s |
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_diffgate.py` | Exit 0; 22 passed | 15.69 s |
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_contract_gate.py -k diff_gate` | Exit 0; 5 passed, 38 deselected | 0.74 s |
| `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_runner_lifecycle.py::test_runner_derives_three_distinct_heads_and_has_no_caller_evidence_overrides tests/vst/test_s2_runner_lifecycle.py::test_runner_rejects_caller_supplied_head_parser_key_or_commands` | Exit 0; 7 passed | 5.21 s |

## Independent exact-head reviews

Both agents reviewed the S2-M01 change at the exact HEAD above, ran no tests/checks, and made no edits.

| Role | Model/effort | Result |
|---|---|---|
| `security-reviewer` | GPT-6 Luna / medium | No valid BLOCKER/MAJOR/MINOR. Confirmed ordinary+ignored union, deterministic sort/dedup, mode/hash/length/content binding, path scope and preserved symlink/nonregular/blocked checks. |
| `code-reviewer` | GPT-6 Luna / medium | No valid finding. Confirmed production caller wiring, rename behavior and the five signed temp-Git collector-to-gate cases. |

## Acceptance limits

These results close the source defect identified by GPT-PM as S2-M01 at the source/mock level. A fresh exact-head GPT-PM review is pending. Windows/POSIX platform behavior, sandbox resource/egress enforcement and policy-restricted runtime scenarios remain separately open or `NOT_RUN`.
