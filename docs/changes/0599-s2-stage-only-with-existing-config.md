# Change 0599 — Permit safe immutable staging beside existing S2 config

Date: 2026-10-30

Owner: Codex

Backlog task: S2-4.3, ordered child of S2-4

## Acceptance delta

The selected Ubuntu 24.04 WSL target already has `/etc/vst-runner` as `root:root` mode `0755`,
while the S2 runtime services are inactive and `/run/vst-runner` and `/run/vst-supervisor` are
absent. The existing StageOnly path rejected every existing config directory, which prevented
staging a new immutable source revision even though staging does not alter the selector, config,
units, or services.

## Implementation

- `tools/vst/runtime_bundle.py` now validates an existing StageOnly config directory with `lstat`:
  it must be a real directory owned by UID 0 with no group/world write bit. Absence remains valid;
  symlinks, non-directories, unsafe ownership/mode, and inspection errors fail closed.
- Both `tools/qa/install_wsl_runtime.ps1` and
  `tools/qa/install_wsl_runner_runtime.sh` use this validator from the verified source bundle
  before publishing any runtime/helper. Existing config content is not read or changed.
- The existing StageOnly requirements remain: runtime socket paths absent, all relevant systemd
  units inactive or not-found, no jobs, and empty service cgroups. StageOnly still leaves the
  runtime selector unchanged and installs no systemd units.

## Verification

The designated `functional-test-reviewer` ran:

```text
python -m pytest -q tests/vst/test_s2_runtime_stage_policy.py
8 passed, 1 warning; exit 0
```

The warning is pytest-asyncio's Python 3.14 deprecation notice. Tests cover absent and safe root
directories and rejection of symlink, regular file, non-root owner, group/world writable modes,
and `lstat` failure.

The read-only security review found no concrete false-accept, symlink, or import-path issue. The
verified bundle import occurs after bounded extraction and source-manifest validation. Review does
not establish a live StageOnly run.

## Acceptance disposition and next action

- **S2-4.3 StageOnly policy:** code, focused unit tests, and source review complete.
- **Live source staging:** not yet run. Next, generate a fresh plan and target inventory for the
  current committed source, then invoke the normal StageOnly installer. It must preserve the
  existing config and selector and publish only the new versioned source/helper.
- **S2-4 runtime acceptance:** remains `IN PROGRESS`; current E5, a real captured probe invocation,
  bootstrap/issuer/owner/Runner journey and final S2 acceptance remain open.
