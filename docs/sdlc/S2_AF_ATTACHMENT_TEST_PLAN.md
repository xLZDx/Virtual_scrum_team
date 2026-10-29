# S2 AF attachment transport test plan

Sprint: 39b7cc253f5d

State: adapter implementation is frozen at SHA-256
`9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e`; functional and
E2E test files are authored and execution has not started.

Source contract: `docs/sdlc/S2_AF_ATTACHMENT_REVIEW_CONTRACT.md`, SHA-256
`4e4b97fc1eff2e1005c9a82eb9af768a9b493c80e71d18e16e6069eef81ca4ae`.

This plan defines falsifiable source-fixture coverage for the project-owned
`tools/af_attachment_review.mjs` adapter. It does not authorize framework or PM Bridge
changes, live AF requests, a new checkout, production staging, key/configuration changes,
or service activation. The functional and E2E roles authored separate test files; neither
has run a test command yet.

## Boundaries and test layers

| Layer | Boundary and permitted fixture | What it can establish | What it cannot establish |
|---|---|---|---|
| Functional unit/contract tests | Existing exported pure helpers or a narrow test harness around the adapter; fake configured `review.js`, fake durable-job client, deterministic prompt bytes, temporary file and temporary intent store. No production bypass flag. | Exact bytes, hashes, intent/retry transitions, validation and fail-closed behavior, attachment manifest/source matching, and absence of inline-send/fallback calls. | AF daemon behavior, durable job truth, formal reviewer correlation, AF decision or approval. |
| E2E adapter integration | The actual adapter debug-dump passthrough invokes native `review.js` with a synthetic repository and proves dump-only/no-send behavior. A separate adapter run uses injected synthetic native prompt and project identity with the real PM Bridge HTTP client and wire-envelope helpers against a loopback fake implementing the supported attachment/job contract. | Native prompt generation without transport; complete attachment transmission, authentication-header use, small inline request body, durable snapshot verification and fail-closed verdict flow at the adapter/client boundary. | A full `af_cli.py pm-review` invocation, active shared daemon behavior, real GPT response, AF approval or production runtime. |
| Final formal AF job | Separately authorized final CLI job after the complete new HEAD package is ready and the verified transport is confirmed. | The actual correlated reviewer result for that exact packet and full input hash. | Production staging or runtime authorization; the result remains bounded to the formal review request. |

Do not mock around the adapter's identity, hashing, durable-intent or acceptance checks.
Fakes may replace only the native reviewer entry point and existing authenticated AF
client boundary. Use temporary files and synthetic packet content; never include the
private full S2 prompt, credentials, raw environment, or a real provider response in test
artifacts.

## Acceptance cases

The case identifiers below are local trace labels for this plan, not new backlog story IDs.
The implementation owner may map them to final pytest/node IDs after the API exists.

| Case | Contract behavior | Falsifiable setup and assertion | Layer / status |
|---|---|---|---|
| AFAT-01 — Native dump-only generation | Delegate canonical prompt generation to configured native `review.js` in dump-only mode and preserve native debug-dump behavior. | Fake native entry point records arguments and emits deterministic UTF-8 bytes. Assert dump-only was selected; every output byte is unchanged; the old inline-send path is never invoked. A dump/generation error yields no transport call. | Functional; planned, not authored/run. |
| AFAT-02 — One complete attachment | Send the complete prompt as one file attachment, not a short inline body, truncation, or chunks. | Use deterministic synthetic UTF-8 bytes larger than 4 MiB. Fake transport captures the attachment bytes and descriptor. Assert byte-for-byte equality, one attachment, exact byte count and SHA-256; short instruction contains no substituted/truncated prompt. | Functional and E2E fake transport; planned, not authored/run. |
| AFAT-03 — Immutable prompt identity | Bind exact prompt bytes to tested HEAD, base, size, SHA-256 and durable request UUID before sending. | Assert intent exists before transport invocation. Change bytes, HEAD, base, or an existing identity field under the same request UUID and assert refusal before a send. Re-read/check the frozen file immediately before send and reject if bytes changed. | Functional with temporary file/intent store; planned, not authored/run. |
| AFAT-04 — Exact retry after uncertainty | Retry an uncertain send only under the same immutable identity and request UUID; never silently create an independent request. | Fake transport records one uncertain delivery and exposes recovery through the existing durable-job lookup. Assert recovery/identical retry uses the original request UUID and exact attachment hash. Changed prompt or identity conflicts; no new UUID or second independent review job is submitted. | Functional; planned, not authored/run. |
| AFAT-05 — Capability and routing refusal | Require the existing compatible authenticated daemon and file-attachments capability; preserve repository-authoritative routing. | Fake client reports missing/false attachment capability, incompatible contract, authentication failure or wrong route. Assert fail-closed before send; no inline, clipboard, browser, chunking or alternate-client fallback. | Functional; planned, not authored/run. |
| AFAT-06 — Exact durable request context | Accept only a real durable job snapshot matching request, project and conversation. | Return snapshots with wrong request/project/conversation, absent status, failed status, or send phase other than `sent`. Assert refusal and no acceptance callback. Caller-supplied metadata cannot override the durable snapshot. | Functional with fake durable-job client; planned, not authored/run. |
| AFAT-07 — Attachment proof from durable evidence | Require the durable snapshot's manifest to identify the exact attachment name/path/size/SHA-256 and match local frozen bytes. | Test absent manifest, wrong name/path/size/hash, forged caller descriptor, changed local file after send, multiple/extra attachment, and inconsistent manifest. Assert refusal; canonical input hash is projected only from verified attachment evidence matching local bytes. | Functional; planned, not authored/run. |
| AFAT-08 — Durable correlation and reply | Require succeeded/sent status, `userTurnId`, `replyId`, `correlated: true`, and an actual durable reply bound to the same request. | Independently vary each required field: missing/null identifier, false/missing correlation, wrong request/reply association, missing reply, or stale job. Assert no verdict acceptance. An await timeout followed by a matching peek may recover the durable result but null correlation remains uncorrelated and cannot approve. | Functional and loopback E2E; planned, not authored/run. |
| AFAT-09 — Reviewer acknowledgments | Require actual reply acknowledgments for exact `REVIEW_HEAD` and `REVIEW_INPUT_SHA256`. | Assert exact matching acknowledgments pass this gate; missing, malformed, stale-head, wrong-hash, contradictory, or metadata-only acknowledgments fail closed. Do not treat the short instruction hash as the full input hash. | Functional and loopback E2E; planned, not authored/run. |
| AFAT-10 — Verdict handling | Reuse the existing strict native verdict parser and reject HOLD, absent verdict and contradictory verdict/evidence. | Exercise exact PASS/approval-form verdict in the fake response only as parser input; also test HOLD, missing verdict, multiple conflicting verdicts, unsupported verdict and correct hash with wrong head. Assert only the native parser's accepted verdict reaches the existing `_accept` check; failure never writes approval. | Functional and loopback E2E; planned, not authored/run. |
| AFAT-11 — AF remains the sole approval writer | Adapter transports and verifies evidence; AF performs its unchanged `_accept` and expected full-input-hash checks. | Spy on the adapter's filesystem boundary and use a fresh temporary project. Assert no adapter write to `gate-approval.md`, `approval.json`, provider-receipt or authorization paths; only the AF-owned acceptance path may write a test approval after all existing AF checks succeed. | Functional ownership assertion plus E2E through AF's native hook; planned, not authored/run. |
| AFAT-12 — Audit representation | Audit metadata explicitly describes the attachment representation and verified durable job identity. | Assert audit output records attachment name, byte count, SHA-256 and verified request/job correlation without replacing them with short-body metadata or exposing credentials/raw environment. | Functional; planned, not authored/run. |

## Coverage and execution gate

The cases map directly to sections 1–6 of the accepted attachment review contract:

| Contract section | Plan cases | Completion evidence required |
|---|---|---|
| 1. Native dump-only prompt generation/no old inline send | AFAT-01 | Focused functional tests plus E2E dump-only subprocess and adapter/client-boundary integration prove native prompt output and that the loopback send carries the full attachment, with no live transport in the dump-only case. |
| 2. Immutable prompt, HEAD/base/hash/size/request identity | AFAT-02–04 | Tests observe exact bytes, pre-send durable intent, changed-identity rejection and same-UUID uncertain retry. |
| 3. Existing authenticated client and attachment capability | AFAT-05 | Negative capability/routing tests prove no fallback or send. |
| 4. Durable job, attachment manifest, correlation and reply | AFAT-06–09 | Fake job metadata cannot substitute for durable evidence; each false/missing binding fails. |
| 5. Strict verdict and canonical full-input-hash projection | AFAT-07–10 | Positive parser control plus HOLD/missing/conflict/hash/head negatives; no approval on a negative case. |
| 6. AF-only approval writer and audit representation | AFAT-11–12 | Adapter write-boundary assertions and native AF E2E; approval files are never authored by the adapter. |

Execution starts only after the implementation owner reports complete adapter coding and
root issues a source-freeze GO. The `functional-test-reviewer` owns source-fixture tests
and their exact commands/results; the E2E role owns the native AF hook/CLI integration
with loopback fake transport. The tests must report exact HEAD, test hashes, command,
counts, skips, failures/errors, and `NOT_RUN` scenarios. No test code, test execution,
lint, build, broad checks, CI, or actual AF/GPT request has been performed as part of this
planning phase.

The final formal AF CLI request is a separate end step, not a test fixture. It may be
submitted only after the complete adapter package is reviewable and the existing
authenticated attachment transport is verified. Its result must be correlated to that
exact request and full prompt hash. An uncorrelated HOLD, attachment delivery, send status,
or test pass is never approval.

## Explicit `NOT_RUN` scope

- Actual AF/GPT requests and real reviewer responses: reserved for the separate final
  formal AF CLI job after adapter coding/review; fake responses are not formal approval.
- Framework or PM Bridge implementation/configuration changes, daemon restarts, alternate
  client paths and new checkouts: outside scope.
- Production staging, selector changes, signing keys, service/configuration installation,
  runtime activation, E5, real Store migration/freshness and reserved host actions: remain
  independently held.
- Any process crash/kill, worker recovery experiment, mutation campaign, E8 or S4/policy
  selector: prohibited and `NOT_RUN`.
- Full-prompt plaintext in repository evidence, test logs or test fixtures: prohibited;
  use synthetic deterministic bytes and record only size/hash.
