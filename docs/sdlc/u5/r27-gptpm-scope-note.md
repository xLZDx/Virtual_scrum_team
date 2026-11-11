# R-27 GPT-PM code review scope

Task: R-27 (register item of docs/sdlc/u6/RETROSPECTIVE.md). Base: origin/main 38aaa3c. Review the delta only: tools/vst/patch_proposals.py (`_scan_attribute_text`, `_attribute_tokens`, `_CONFIG_HAZARDS` attr entry), tests/vst/test_u5_patch_proposals.py (NOT_RUN; judge by reading), docs/sdlc/u5/PATCH_PROPOSALS.md, REAL_CHANGE.md, RETROSPECTIVE.md rows R-01/R-27, core logs, docs/qa/categories.json.

Operator decision 2026-11-11: allow the line-ending attributes `text`, `eol=lf|crlf`, `-text`, `!text`, `text=auto`, `-eol`, `!eol`; keep refusing `filter`, `ident`, `working-tree-encoding`, `crlf`, `export-subst`, `diff=`/`merge=` with a value, any other `text`/`eol` spelling.

Reviewer remediation already applied (one batch, from python-reviewer, security-reviewer, functional-test-reviewer): lines split at LF only and blanks are exactly space/tab/CR/LF; files holding \v, \f, \x1c-\x1e, U+0085, U+2028, U+2029 are refused; a quoted pattern with a backslash or no closing quote is refused; config `[attr]` section refused (attr.tree). Known residual: the scan is a denylist, unknown attributes such as `whitespace` pass (the apply step uses --whitespace=nowarn).

Tests: written, NOT_RUN (operator ban). The real AEVE-driven change (U5-7 driver) has not been re-run.

Ask: the complete BLOCKER/MAJOR set for this delta only.
