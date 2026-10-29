# Change 0574: remediate S2-1 exact-head source-fidelity review gap

## Why

The S2-1 fixture correction and source/test acceptance are already committed, but the enforced normal push path still needs exact-head code approval. GPT-PM reviewed the full-range attachment for HEAD `2befed5` and returned `MAJOR/HOLD` because the generated review input replaces code expressions with `[REDACTED]`. This is an evidence-fidelity blocker, not a confirmed defect in the S2-1 correction.

## What changed

- Reconciled the S2-1 backlog, TP-28, and verification matrix with the exact-head test results and correlated review disposition.
- Added `docs/sdlc/evidence/s2-exacthead-review-2befed5-20261029.md` with test provenance, exact review identity, attachment hash, source-fidelity evidence, and limitations.
- Added `tools/verify_s2_review_source_fidelity.py`, a read-only exact-base/HEAD and immutable-attachment verifier. It matches the full diff in order, maps redactions through hunk cursors, and emits blob IDs/line positions without source values or per-line fingerprints.
- Added `tests/af/test_s2_review_source_fidelity.py`; the functional-test-reviewer reported 5/5 focused tests passing at HEAD `2befed5`.
- Added `docs/sdlc/evidence/s2-review-redaction-source-fidelity-run-2befed5-20261029.json` and `docs/sdlc/evidence/s2-review-redaction-independent-review-2befed5-20261029.md`: all 41 positions map to exact blobs/lines; independent security review assessed all positions with no confirmed source defect, retaining fixture/runtime and production limits.
- Updated `docs/sdlc/evidence/s2-review-redaction-source-fidelity-2befed5-20261029.md` to identify the earlier duplicate-shape count as preliminary and link the exact ordered position map.
- Verified the tracked source blob for `tools/af_attachment_review.mjs` is `f5743fd787417f0208d0bd6a211092a2d4b7f890`; the committed parser constructs its acknowledgement prefix from the label and a colon, while the review attachment replaces that expression with `[REDACTED]`. The native review path applies secret redaction before attachment creation. No product/runtime source or secret-redaction policy was changed; the new source code is the isolated read-only review verifier described above.

## Verification and review

- `e2e-runner`: four focused WSL S2 regression files, 130 passed, 0 failed/skipped, at HEAD `2befed5`; Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4.
- `functional-test-reviewer`: `node --test tests/vst/test_af_attachment_review.mjs`, 35 passed, 0 failed/skipped at HEAD `2befed5`; Node.js 24.13.1.
- `e2e-runner`: `node --test tests/af/test_s2_attachment_adapter_e2e.mjs`, 2 passed, 0 failed/skipped at HEAD `2befed5`.
- `functional-test-reviewer`: `python tests/af/test_s2_review_source_fidelity.py -v`, 5 passed against uncommitted source at baseline HEAD `2befed5` and again at exact committed HEAD `5b7984e`; environment and test/verifier hashes are in `docs/sdlc/evidence/s2-review-redaction-independent-review-2befed5-20261029.md`.
- `security-reviewer`: 41 exact mapped positions reviewed at base/HEAD; no confirmed defect. `code-reviewer`: verifier re-review found no material issue after removing per-line hashes. Neither is GPT-PM approval.
- GPT-PM request `ad64e813-a507-4b4a-8601-d9fa1a8276b9`, job `9a75f58f-f517-4354-92c2-eae954f31c74`, reply `c46b1b10-9b56-5d7c-bcf9-9f4b950dfa69`: `MAJOR/HOLD`; no formal approval.
- No approval file, push, runtime activation, or S2-2 change was made.

## Closure boundary

S2-1 remains the current task. The controlled source-fidelity procedure and independent assessment are complete; GPT-PM re-adjudication is still required. Do not disable or bypass secret redaction. After GPT-PM grants valid exact-head approval, complete any required AF verification and ordinary push. S2-2 must remain untouched until that push succeeds.
