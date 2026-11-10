# U2-5 GPT-PM code review scope

Task: U2-5, truthful coverage report. Base 40b12ad (U2-3 accepted), head = current HEAD (two commits). Review the delta only: tools/uc/coverage_report.py (new) and docs/unified/UNIFIED_CORE_TDD.md section 5.4.

Delivers: a deterministic per-role coverage report (uc.coverage-report.v1) over a validated U1 role result, with a closed verdict vocabulary (CLEAN_LOCAL, FINDINGS, PARTIAL_CODE_ONLY, MODEL_RESIDUAL_OPEN, BLOCKED, NOT_COVERED), text and markdown renderings, and a whole-word English and Russian pass-token scanner. Any rendering of a report that has a role which is not fully clean (status CLEAN, class LOCAL, empty residual and uncovered) is refused if it contains a pass token; the only exemption is the structurally recorded CLEAN_LOCAL cell of a fully clean role. The guarantee holds for any dict passed to the public renderers (contract-pattern revalidation, ASCII only, NFKC second pass), table digest is checked, ids containing pass words fail closed.

Already fixed after two read-only reviewer passes (python 1 conditional MAJOR: guarantee only held for self-built dicts; functional-test none).

Settled, do not reopen: json format is machine data and not scanned (documented); availability limit for ids containing pass words is intended fail-closed; the scanning tests are task U2-6. Tests NOT_RUN (operator forbids pytest); evidence is static review only.

Ask: the complete BLOCKER/MAJOR set for this delta only.
