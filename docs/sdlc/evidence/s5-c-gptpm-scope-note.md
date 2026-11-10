# S5-C GPT-PM code review scope

Task: S5-C (VST-040), bounded read-only analyzer adapter and deterministic snapshot hashing. Base fcd7236 (S5-B accepted), head = current HEAD. Review only tools/vst/analyzer_adapter.py (new).

Delivers (plan docs/S5_AEVE_GATE_PLAN_2026-10-24.md E3/E4, AC-5..AC-8): deterministic VST-side code, no model calls, that validates an explicit scope, hashes the tracked scope as git blob content, runs `aeve analyze` from D:\Repo\AEVE in a bounded subprocess (neutral cwd, isolated interpreter, scrubbed env, caps, Windows Job Object tree kill), parses AEVE output into a closed report using AEVE's real g2 rule inventory (anything else UNSUPPORTED; non-.py or uncovered scope files force UNSUPPORTED, never FULL), verifies HEAD == candidate_head and a clean tree before and after, and assembles (never signs) the analyzer_authority payload; it refuses assembly while any binding is unknown.

Already fixed after two read-only reviewer passes (python-reviewer 7 MAJOR, security-reviewer 5 MAJOR): candidate code execution via cwd, tree kill, false-clean coverage, head binding, case aliasing, untyped exceptions.

Settled, do not reopen: signing is S5-B (accepted); gate wiring is S5-E; AEVE has no scope/profile option and analyzes the whole git root (scope filtering applies to findings); OS-level network denial and resource limits are NOT_RUN (S2 sandbox). Tests NOT_RUN (operator forbids pytest); evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.

## Verification round (after GPT-PM round 1, reply 3319eee9, MAJOR x4)
Base: cdf5e1e. Fixed: git invocations use capped streaming with kill and typed refusal (GIT_OUTPUT_LIMIT, GIT_KILL_FAILED); Windows analyzer starts suspended, is assigned to a kill-on-close Job Object and resumed only afterwards, fail closed (CONTAINMENT_FAILED, TERMINATION_FAILED); analyzer_files must cover every importable file under each pythonpath entry except explicit documented exclusions, links refused; version_file must be pinned, verified before and re-read after the run. Ask: verify these four and regressions they caused only.
