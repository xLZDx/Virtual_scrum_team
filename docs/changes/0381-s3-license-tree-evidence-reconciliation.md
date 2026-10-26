# Change 0381: reconcile S3 exact-tag license evidence

## What changed

- Reconciled the new S3 pinned-server metadata note with the earlier exact-tag source-tree audit already retained in `s3-temporal-server-go-license-source-followup-2026-10-25.tsv`.
- Clarified that six conventional notice/license paths were searched in the exact dependency tree and absent, while legal status remains `NOT_VERIFIED`.

## Why

The new read-only note originally described only the current-turn raw URL checks and failed to cite the stronger prior in-scope tree inventory. This update removes that evidence conflict without upgrading an open legal decision.

## Verification and limits

- Existing TSV records the exact `v0.1.0` dependency tree identity and checked paths: `LICENSE`, `LICENSE.md`, `LICENCE`, `COPYING`, `NOTICE`, and `COPYRIGHT`.
- Current-turn official raw paths for `LICENSE`, `LICENSE.txt`, and `COPYING` returned HTTP 404.
- No source or artifact was acquired, no legal determination was made, and no tests/build ran.
- Exact dependency legal status remains `NOT_VERIFIED`; operator retains the legal/acquisition decision.
