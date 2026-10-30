# S2-4.7 — Preserve existing configuration during runtime selection

Date: 2026-10-30
Task: S2-4 runtime qualification
Project owner: Codex
Status: implemented and focused-test reviewed; target selection not yet run

## Acceptance delta

The Ubuntu-24.04 target already contains `/etc/vst-runner` as a root-owned, non-writable
directory. The selector changes only the `/opt/vst-runtime` link and its fixed systemd units;
it does not install, read, or alter configuration files or Store data. Refusing any existing
configuration directory prevented the current qualification from advancing.

## Change

- Generalized the existing root-directory metadata check and used it in the selector as well
  as the source staging path. Only an absent directory or a real root-owned directory without
  group/world write permission is accepted.
- Kept `/run/vst-supervisor` and `/run/vst-runner` absence, inactive-unit, pending-job and
  empty-cgroup checks unchanged.
- Kept the separate runtime-configuration candidate out of this selector change; it remains
  uncommitted and must be rebound to the accepted runtime source before activation.

## Verification

- `functional-test-reviewer`, Windows, checkout HEAD
  `e4fc1ec16ec01628ed974a91174c461fbefa1a78`, focused pytest invocation:
  `& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_bootstrap_runtime.py::test_selector_allows_existing_root_config_dir_but_still_requires_inactive_units tests/vst/test_s2_bootstrap_runtime.py::test_selector_fails_closed_before_systemctl_when_existing_config_dir_is_unsafe tests/vst/test_s2_runtime_stage_policy.py tests/vst/test_s2_stage_only_install.py::test_stage_only_runtime_bundle_import_does_not_change_exact_source_members tests/vst/test_s2_runtime_config_bundle.py::test_bundle_manifest_covers_every_payload_with_exact_bytes_and_safe_scope tests/vst/test_s2_runtime_config_bundle.py::test_public_material_matches_standalone_public_keys_and_probe_run_binding`:
  12 passed, 2 POSIX-only skips, one existing pytest-asyncio deprecation warning. The runtime-config
  assertions and candidate payload edits remain separate uncommitted bundle work and are not
  included in this selector commit.
- `functional-test-reviewer`, Ubuntu-24.04 WSL/Python 3.12, isolated temporary input copy:
  `$payload | wsl.exe -d Ubuntu-24.04 --user root -- python3 -B -c $shim`; the two new POSIX
  selector tests passed (2/2). The wrapper set `PYTHONDONTWRITEBYTECODE=1`; the temporary directory
  was removed; target services and files were not changed.
- `code-reviewer`: no actionable BLOCKER/MAJOR. It confirmed the config is metadata-checked
  without reading/modifying config files or Store state, and the runtime/cgroup safeguards
  remain.
- Separate read-only target inventory: selector remains on `a600774`; source `f685cc9` is
  staged but not selected; all eight S2 units are inactive. The current candidate configuration
  still names `a600774`, so it must be rebound to a source that implements the accepted
  no-Runner-key contract before configuration installation.

## Remaining

No runtime selection, configuration installation, service start, bootstrap request, test task,
Store write, or dispatch was performed. Next: publish this selector change, create an exact
source plan and fresh target inventory for its committed revision, then continue the permitted
runtime qualification. Restricted process-kill, crash/recovery, mutation, E8 and policy selectors
remain `NOT_RUN`.
