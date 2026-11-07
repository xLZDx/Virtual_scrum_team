# S2 frozen-source specialist reviews — 2026-10-29

Sprint: 39b7cc253f5d

Owner: Codex (coordination), GPT-PM (independent final adjudication).
Reviewed HEAD: d3f326f37a40936402d3933d5266e0ffb01017f0.
Product freeze: 67d1d55e5556c6936516f3404202faecba1e6707; later commit contains
only tests/documentation. Base: origin/main6117ba24b08a260b42402db6da0bf767864e1c04.

Actual fresh-context profiles: database-reviewer, security-reviewer, code-reviewer;
each gpt-6-luna, medium effort. No simulated reviewer, edits, tests, checks, build,
CI or runtime operation. Each returned its exact revision and scope limitations.
First code-reviewer launch was refused with `agent thread limit reached`; this was
capacity, not model/provider unavailability. A later actual launch succeeded after
the database role finished. Protected artifacts were excluded from all review tasks.

## Database and transaction review

Actual agent: /root/s2_frozen_database_review. Verdict: no valid BLOCKER/MAJOR
in the declared transaction scope. The agent reviewed full new relevant functions
against origin/main, not just the later small fix delta. Evidence locations:

- store.py:2752 and2840: fresh atomic bootstrap, idempotent operation, anchor/commit
  guards, exact replay without authority renewal.
- store.py:3901,4028,4108,4132,4153,4616 and dispatch_issuance.py: immutable issuance
  rows/NOTE families, canonical SQL JSON adapter, frozen/STARTED/single-sign states.
- root_dispatch_issuer.py:126: ambiguity becomes UNKNOWN without automatic re-sign.
- store.py:1488,1532,1595,1633: exact grant association, delegated origin refusal,
  current checks and legacy/direct compatibility.
- store.py:5093,5153,5485: claim/reserve transaction and narrow own-PENDING exception.

Manual source review only. Public test records were inherited evidence, not tests
reproduced by this role. No production Store/key/service or E5 proof was produced.

## General code and reliability review

Actual agent: /root/s2_frozen_code_review. Verdict: no valid BLOCKER/MAJOR or
material minor finding in the requested full new path. It traced bootstrap, root
issuer, Store/Supervisor/RPC, current providers, exact grant claim/reservation,
ambiguous signing outcomes, retry/error/resource behavior and authenticated framing
against origin/main, including the implementation already present in the e987a24
snapshot. The review was not restricted to the later147-line correction delta.

A wording correction is retained: STARTED/single-sign claim precedes signing;
Runner execution reservation occurs after the signed grant has been persisted and
claimed. The reviewer explicitly clarified its initially ambiguous phrase: issuance-intent
reservation precedes the STARTED signer claim; Runner execution reservation is a
separate later action. The source is issue_frozen_dispatch in
root_dispatch_issuer.py: reserve_dispatch_issuance, start_dispatch_issuance, signer;
reserve_runner_execution occurs after acceptance, grant persistence and Runner claim.

The source blobs tested at67d1d55 are unchanged in reviewed HEADd3f326f; tests used
recorded overlays later committed in0565. This is preserved blob-level source
provenance, not a claim of a new test run at the documentation commit or runtime.

## Security review

Actual agent: /root/s2_frozen_security_review. The first summary described the small
e987a24..67d1d55 delta. Codex requested full new source against origin/main; the
agent completed the expansion and superseded that limited summary. No reachable
BLOCKER/MAJOR found in full assignment_basis.py, dispatch_issuance.py,
root_dispatch_issuer.py, Store assignment/issuance/grant/runner guards,
Supervisor/service peer/RPC/live-config paths and stage/bootstrap/helper trust code.

Explicit inspected regions: store.py:1386-1706,2475-2566,2752-2983,3901-4235,
4616-4684,5144-5225,5485-5521; supervisor.py:146-308,587-702,721-993;
supervisor_service.py:174-287,593-699,761-1107; installer fixed destinations,
no-overwrite and archive checks; bootstrap fingerprints; worker_exec.c:90-194
identity/capability/environment drop. Design/I01 GO was contract context, not code
approval. Actual installation, compiler output, host permissions and runtime remain
unproven. The same actual role then completed the remaining mandatory transport trust slice:

- dispatch_owner_service.py:49-166,174-207,213-284 and owner_client.py:35-85:
  fixed socket/config/key boundary, signed envelope and no ambiguous admission retry.
- dispatch_owner_latch.py:20-120 and store.py:1773-1975: root-only latch,
  pending/ack reconstruction and exact outcome/result association.
- dispatcher_service.py:38-73, store.py:1977-2075 and service.py:277-287:
  filtered intents, generation/audience-bound cursor, bounded role/grant request.
- runner_service.py:153-330,439-475, execution_grant.py:275-513 and
  store.py:5153-5233,5485-5555: fixed helper, peer/grant identity, mandatory
  confirmed claim/reservation and fail-closed ambiguous execution.
- signer.py:183-205,236-423,454-495, sandbox.py:24-66 and worker_exec.c:90-194:
  key/config/ledger peer boundary, exact grant-bound signing, separate worker access
  and UID/GID/capability/no_new_privs transition.
- preflight.py:133-207,244-281 and runner_fence.py:46-119,417-565:
  signed run/spec/nonce/operator attestation and root-bound generation fence.

Supplemental verdict: no reachable BLOCKER/MAJOR and no concrete source-path
coverage gap in that declared mandatory slice. No actual runtime claims or test
execution were added. This is not a generic exhaustive repository audit.

## Acceptance limits and next steps

1. All three declared specialist reviews are complete with zero confirmed source
   BLOCKER/MAJOR. Codex records scoped source consensus at the reviewed exact HEAD;
   later source changes require targeted re-review and designated regressions.
2. Codex reconciles permitted live Windows observations separately; unsigned metadata
   cannot establish current E5 or installed policy/signature authority.
3. Codex submits the full exact package and non-secret runtime proposal to GPT-PM.
   No approval file is written by Codex and no source review authorizes activation.
4. Genuine current E5, restricted-case disposition and final S2 delivery remain open;
   S3–S5 stay queued behind S2. No test skip or NOT_RUN is upgraded by this review.
