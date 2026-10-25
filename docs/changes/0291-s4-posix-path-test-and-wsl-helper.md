# 0291 S4 POSIX helper path fixture and WSL helper installation

**Date:** 2026-10-25  
**Executor:** Codex coordinating the functional-test reviewer  
**Focused-run HEAD:** `211b823d140037fca13e8d91a15d4302813db1b4`

## What changed

- Updated one test double to use `PurePosixPath` for the fixed WSL helper executable, preserving the exact POSIX separators in its command assertion.
- Installed the previously authorized root harness at `/usr/local/libexec/vst-s4-root-harness.py` in the dedicated `Ubuntu-24.04` WSL distribution.

## Why

The test runs under Windows Python but models a Linux-only helper invocation. Windows `Path` rewrites POSIX separators, so the test must use a POSIX path type. The root helper is needed for the later WSL root-profile acceptance run.

## Verification state

- At exact HEAD `211b823d140037fca13e8d91a15d4302813db1b4`, Python 3.14.3, the focused run returned 107 passed, 1 failed, 1 warning in 226.58 seconds (exit 1). The remaining failure was the Windows path-separator expectation; no product-source failure was reported.
- Before installation, the fixed helper path and `/usr/local/libexec` directory were absent in `Ubuntu-24.04`. A first transfer attempt created a 5-byte partial file; its SHA-256 and size were verified as the file created by that attempt. It was replaced only after verifying that exact partial-file hash, using the committed source bytes.
- Final installation: `/usr/local/libexec` is root:root mode `0755`; helper is root:root mode `0644`; installed SHA-256 is `044e4577e7d8f6d2bde55735896b0ed8002f6bcb12b51957a295e3d093f8911a`, matching the committed `tools/qa/root_harness.py` source at installation time.
- The test-only POSIX-path correction is unverified. The helper itself has not been executed. No test registry refresh was done for this source change.
- `C:\Python314\python.exe tools/build_document_registry.py` exited 0 and wrote `governance/DOCUMENT_REGISTRY.md` (267 lines). This is documentation-index generation only.

## Next step

Commit the test-only correction, regenerate the selector registry for the new exact test source, then rerun the three focused modules through `functional-test-reviewer`. If focused tests pass, have `e2e-runner` execute the assigned WSL root-profile categories and matrix at a candidate whose helper source SHA matches the installed helper.
