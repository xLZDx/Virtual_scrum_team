# U3-1 GPT-PM code review scope

Task: U3-1, inventory and landing plan of the pushed branches. Base fa26e3c (main after U2), head = current HEAD (two commits). Review the delta only: tools/qa/branch_inventory_check.py, docs/sdlc/u3/branch_inventory_rules.json, docs/sdlc/u3/BRANCH_INVENTORY.md, docs/sdlc/u3/MAIN_COVERS_U3_3_TO_U3_6.md.

Delivers: a read-only map of five pushed branches (s4-canonical-continuation, s4-native-qa-runner, s4-reproducible-qa-automation, s4-e2e-snapshot-20261025-180e330, s5-bounded-aeve-evidence) against origin/main. Every file of every branch (three-dot name-status diff) is classified exactly once by a rule (LAND / EVIDENCE_ONLY / DROPPED / ALREADY_ON_MAIN) with a reason; the checker fails on unclassified, multi-matched, dead-glob, empty-branch and stale-inventory cases and is bound to exact tip SHAs. Result: LAND is empty on all five branches. MAIN_COVERS_U3_3_TO_U3_6.md maps the acceptance text of U3-3, U3-4, U3-5 and U3-6 to the code already on main (S4) with file-level evidence and states what is open (U3-5 gate wiring, U3-2 executor interface, re-earned counts NOT_RUN).

Already fixed after one read-only review (python-reviewer: 2 MAJOR, 7 MINOR): inventory comparison is no longer vacuous; non-conflicting edits are classified explicitly after reading the diffs; git calls bounded and SHA-pinned.

Ask: verify (a) the checker enforces what the rules claim (completeness, exactly-once, freshness), (b) no LAND-worthy file is hidden behind a false reason, (c) the claims in MAIN_COVERS_U3_3_TO_U3_6.md against the cited code. The checker proves classification, not that each reason is true for every file; tests NOT_RUN (operator forbids pytest); evidence is static review plus the checker's own runs.

Ask: the complete BLOCKER/MAJOR set for this delta only.
