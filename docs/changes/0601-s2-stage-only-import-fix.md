# Change 0601 — Keep StageOnly source bundles byte-exact during module imports

Date: 2026-10-30

Owner: Codex

Backlog task: S2-4.5, ordered child of S2-4

## Acceptance delta

The approved StageOnly invocation for source `7c7d599af03860ede7d4960301ed8d0456c360c0` exited 1
because the exact source-bundle verifier found generated Python `__pycache__` files. The imports
were adding files to the same immutable bundle whose complete member map is checked again before
publication.

## Implementation

- `tools/qa/install_wsl_runtime.ps1` now launches its WSL bootstrap interpreter with `-B` before
  the StageOnly import of `tools.vst.runtime_bundle`.
- `tools/qa/install_wsl_runner_runtime.sh` uses the same no-bytecode flag for its StageOnly import.
- The verifier still checks the complete exact archive member map; no generated-file exception was
  added.

## Verification

The designated `functional-test-reviewer` added and ran the focused regression in
`tests/vst/test_s2_stage_only_install.py`:

```text
python -m pytest -q tests/vst/test_s2_stage_only_install.py::test_stage_only_runtime_bundle_import_does_not_change_exact_source_members
2 passed, 1 existing pytest-asyncio Python 3.14 deprecation warning; exit 0
```

The selector covers both host bootstrap and WSL StageOnly import flag lists and verifies each
import leaves the exact source member set unchanged. It ran on Windows at baseline HEAD
`dc58fa7fd2a8d72892e65d5d9b0cdbcea4248e10` against the working-tree fix. It does not establish
WSL runtime publication.

## Acceptance disposition and next action

- **S2-4.5 code and focused regression:** committed and normally pushed as `f685cc9778e516b277e243a14dfa123db34ec247`.
- **S2-4.6 runtime publication:** not yet complete. The previous attempt made no target changes.
  Exact source-plan and refreshed target-inventory inputs for `f685cc9` are now captured in
  change `0602`; obtain their narrow review and rerun the existing `-StageOnly` command. Preserve
  the current selector, units, config and services.
- S2-4 runtime acceptance remains open for measured current-run evidence and the permitted real
  owner-to-Runner journey. Restricted selectors remain `NOT_RUN`.
