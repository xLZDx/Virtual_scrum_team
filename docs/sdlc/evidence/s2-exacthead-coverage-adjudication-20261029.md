# S2 exact-head source coverage adjudication — 2026-10-29

Sprint: `39b7cc253f5d`.

## GPT-PM decision

- Base: `6117ba24b08a260b42402db6da0bf767864e1c04`.
- Exact HEAD: `242f5d56f5b48603141d148d71d724bec7fb2b37`.
- Request: `4986ec77-698e-4dd0-bdd9-7ca5c6281a46`.
- PM Bridge job: `c6ea42b2-462e-41a1-83a2-1632850c22c8`.
- Correlated reply: `541aa937-3513-570e-8b25-daaa99ae0854`.
- Exact input size/hash: 5,876,444 bytes / `f7685bce6b5e30c0e266f7e4eebf009d1f64ad9d8f6c4583a90241fbf9488b42`.
- Reply was correlated and recorded. The actual AF result was `NOT_APPROVED: verdict=MAJOR`; no exact-head approval was created.
- S2-REVIEW-01 remains resolved. GPT-PM found no confirmed BLOCKER/MAJOR in the parser correction and acknowledged the exact-head 38/38 test report, which it did not independently execute.
- S2-REVIEW-02 remains `MAJOR/OPEN`: GPT-PM had not independently established complete adversarial coverage of every changed source/test integration path. It classified this as an evidence-sufficiency limitation, not an identified implementation defect. Phase 8 is `NOT APPROVED`.

## Coverage reconciliation

The review range contains an inherited baseline review and a small later source/test delta. These must be evaluated together, while preserving their different provenance.

1. `s2-frozen-source-reviews-d3f326f-20261029.md` records actual database-, security- and code-reviewer work against the S2 source range through `d3f326f37a40936402d3933d5266e0ffb01017f0`. The reports describe Store and issuance transactions, assignment/grant/Runner guards, root issuer, Supervisor/RPC, dispatcher, worker helper, sandbox and service trust boundaries. These are inherited review records; they are not fresh reviews by the authors of this note.
2. The exact Git delta `d3f326f..242f5d5` contains six changed paths under `tools/` and `tests/`. A current `code-reviewer` (`gpt-6-luna`, medium) read each entire file and its delta, made no edits, and ran no tests. It reported no confirmed BLOCKER/MAJOR:

| Path | Direct review result |
|---|---|
| `tools/af_attachment_review.mjs` | Full file reviewed: prompt/attachment identity, hash/size, durable intent, duplicate-send protection, response correlation, acknowledgements and verdict handling; no confirmed B/M. |
| `tools/verify_s2_review_source_fidelity.py` | Full file reviewed: exact range/diff, attachment digest/size, redaction-to-blob mapping, refusal paths and inconclusive invariant handling; no confirmed B/M. |
| `tests/vst/test_af_attachment_review.mjs` | Full file reviewed: adapter branches, replay/send ambiguity, attachment integrity, correlation/acknowledgement/verdict, wrapper matching/mismatch; no confirmed B/M. |
| `tests/af/test_s2_attachment_adapter_e2e.mjs` | Full file reviewed: loopback transport, >4 MiB attachment, receipt handling and dump-only path; no confirmed B/M. |
| `tests/af/test_s2_review_source_fidelity.py` | Full file reviewed: exact mapping and refusal cases; test constants bind to historical review input/HEAD; no confirmed B/M. |
| `tests/vst/test_s2_store_backed_pubsub.py` | Full file reviewed: three repeat-intent fixtures supply the required public-key fingerprint; no confirmed B/M. |

The reviewer explicitly limited its conclusion to this six-file delta. It did not rerun or claim the inherited baseline review itself. The earlier exact-range note `s2-af-correlated-reply-parser-20261029.md` separately records a code-reviewer inventory and review of 74 changed `tests/` and `tools/` paths (30 test/helper files, 38 source/scripts and six systemd units), including complete reads of the named large Store, Runner and persistent-service tests. GPT-PM must decide whether this baseline-plus-delta evidence satisfies S2-REVIEW-02; Codex does not upgrade it to approval.

## Limits and remaining acceptance

- The current delta review is static; it does not execute tests. The separately reported exact code-head test is `node --test tests/vst/test_af_attachment_review.mjs`, 38 passed, 0 failed/cancelled/skipped at `0da595e6574856ed0c85a181941e822031b80787`; the functional-test-reviewer confirmed the test and adapter blobs matched HEAD before/after.
- No production runtime, Store migration, real key/signing, E5, service activation, crash/mutation campaign or restricted selector is proven by this source review.
- Codex owns maintaining the evidence packet and requesting re-adjudication. GPT-PM owns deciding whether it resolves S2-REVIEW-02. A fresh correlated exact-head review is required; do not hand-write an approval or push without the actual accepted review result.
- S2-2 remains queued behind S2-1 delivery.

## Follow-up GPT-PM adjudication — current S2-1 HEAD

- Request ID: `f92b750e-485d-4f97-8c28-3bb2b8bfc3db`.
- Submitted HEAD: `57c734e60787a9db14bb888116d7e808bc46970e`.
- Correlated verdict: `APPROVE — S2-REVIEW-02 resolved for S2-1 source/test acceptance`.
- GPT-PM accepted the inherited baseline plus six-path delta review as sufficient
  adversarial coverage for the declared S2-1 paths; no new BLOCKER/MAJOR was confirmed.
- GPT-PM accepted the reported absence of S2-1-path changes between `242f5d5` and
  `57c734e` for this narrow decision, while explicitly noting it did not independently
  reproduce the Git-object comparison. The decision does not certify unrelated S2-3
  changes, runtime, E5, restricted selectors or complete S2 acceptance; test results remain
  reported evidence, not tests executed by GPT-PM.
- Decision details and acceptance limits: `s2-1-coverage-adjudication-f92b750e.md`.
- S2-1 source/test acceptance is now accepted. S2-1 delivery remains current until this
  decision and affected task records are committed and normally pushed; S2-2 stays queued.
