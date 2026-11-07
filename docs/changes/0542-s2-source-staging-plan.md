# Change 0542: prepare a non-secret S2 source staging plan

## Why and scope

The observed host has an older inactive runtime. Staging and selecting a replacement need
different evidence: source/archive inputs before staging, actual binary/tree fingerprints before
selection. A post-staging manifest must not retroactively authorize installation.

## Implementation

Added `tools/qa/prepare_wsl_runtime_plan.py`. It reads the canonical checkout's exact committed
HEAD and produces deterministic JSON from the same LF-normalized Git archive path set used by
the Windows handoff. The plan binds archive, spec, all six units, helper source/build recipe and
fixed versioned destinations. Unsafe/duplicate archive members and missing artifacts refuse.
Compiler provenance, target inventory, Store classification and compiled binary remain explicitly
unverified. The candidate grants no signing, selection or activation authority and writes no file.
Working-tree changes are not source inputs; no alternate checkout is created or inspected.

## Verification state

Coding phase: not executed or tested. The designated functional-test reviewer owns deterministic
archive, wrong revision/root, missing/duplicate artifact and truthfulness cases after all in-scope
coding finishes. No archive build, WSL install, compilation, service activation or test was run by
the primary agent for this change. Existing helper installer and runtime loaders stay authoritative.

Owner: Codex. Exact source/test and staging-plan review: GPT-PM. Missing production trust and
current E5 are not solved by this unsigned plan.
