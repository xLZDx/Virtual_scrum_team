# Change 0544: remove duplicate stage-only guard

Removed a duplicated `if not stage_only:` line from the embedded Python bootstrap in
`tools/qa/install_wsl_runtime.ps1`. The remaining guard correctly scopes only the existing
runtime selector and fixed-name unit collision checks; versioned runtime/helper checks remain
unconditional.

The phase-7 E2E role found this syntax defect while validating the stage-only integration. The
assigned test agent owns ongoing test execution. This focused fix was not tested independently;
no other files were changed and nothing was committed.
