# S2 coordinator and runtime adjudications — 2026-10-29

## Coordinator architecture decision

- Project: `Virtual_scrum_team`, Sprint S2.
- Declared repository HEAD: `20fda2cbf26274192652a1c829a19f6b1844e9c4`.
- PM Bridge request: `4c9dbf2b-c220-4b14-9df6-91efbcd53b22`.
- Correlated reply: `8053ccbc-d74b-417d-b762-44b364d71303`.
- Job: `8c47c9ef-7193-4a98-a150-c1b5efb6b0d0`.
- User turn: `09039316-22db-4c80-9d24-52bbd3d96379`.
- Verdict: **ACCEPT — EXISTING BOUNDED COORDINATOR ARCHITECTURE; M01 STILL OPEN**.

GPT-PM accepted the source path already in the repository: the signed-instruction owner relay,
authenticated Supervisor RPC, Store as sole task/assignment/lease authority, filtered Store Pub/Sub,
and `StoreBackedDispatcher` forwarding the exact grant to Runner. No external coordinator, second
scheduler, or assignment authority is required. The operator is the sole human owner; technical
service accounts are isolation identities, not additional users.

GPT-PM found no architecture BLOCKER or new source MAJOR in the reviewed boundary. It stated that a
transport-only client may forward one exact previously authorized envelope unchanged. It must not
select tasks, create or change assignments/leases, construct authorization, sign, create keys, retry
an ambiguous submission, or bypass Supervisor validation. The current turn added that bounded
client in `tools/vst/dispatch_owner_transport.py`. The first focused PM source review returned
MODIFY with two findings: missing request half-close and unauthenticated socket endpoint. Codex
fixed both, added systemd PID1/root peer checks and response-to-envelope binding, and added mapped
tests. The later correlated source/test decision (request
`b0f60d46-42b7-486a-b2f0-5d2253780f55`) returned ACCEPT, resolved both transport findings, and
preserved production M01 as open. A current PM Bridge job-status lookup recovered the durable
correlation: job `68efb4e6-a296-4fd7-bcfc-2c6fe2568d5c`, reply
`d555b078-5647-46eb-bfc1-dd99654d634f`, `correlated=true`. The job lifecycle is `uncertain` because
the parked wait deadline elapsed; the recovered stored reply contains the exact request ID and
ACCEPT verdict. The initial send-and-await return did not expose the reply ID, which is why this
later status reconciliation was needed.

The designated functional-test reviewer reported 33 passed and 1 Windows skip. The designated
`e2e-runner` then ran `python3 -m pytest -q -rs
tests/vst/test_s2_dispatch_owner_transport.py` as root in Ubuntu-24.04 WSL, Python 3.12.3 / pytest
7.4.4: **34 passed, 0 failed, 0 skipped, exit 0**. This exercised a real local AF_UNIX socketpair
and the actual `DispatchOwnerService._handle()` framing/SHUT_WR/EOF/response/ACK path. Kernel
credentials, pidfd and filesystem metadata remained mocked. The first WSL attempt exposed a test-only
constant mismatch (`6` rather than Linux `SHUT_WR`); the test owner corrected it, and the final run
passed. D: was mounted within the WSL invocation because automount is disabled. HEAD and porcelain
status were unchanged; no runtime provisioning, migration, service activation or production dispatch
occurred. Code/security review and test-mapping review found no actionable findings.

### Exact M01 closure boundary

`S2-DISPATCH-M01` remains **MAJOR / OPEN** until evidence shows a genuinely authorized production
instruction submitted by the correct provisioned peer, durably accepted by root Supervisor/Store,
delivered through the filtered dispatcher, and passed to Runner using the exact grant/claim path.
Evidence must include a permitted successful journey and fail-closed cases for incorrect owner,
expired/revoked authorization, stale lease/epoch/generation, mismatched payload, duplicate request,
and ambiguous result, preserving history-only recovery and ACK semantics. Source review plus
synthetic fixtures can close a source subfinding only; they cannot replace real identities,
configuration, peer credentials, cgroups, runtime evidence or genuine authorization.

Remaining prerequisites are an authorized instruction issuer and public trust key, provisioned
owner identity/root config, a qualified source-to-runtime E2E journey, and current runtime/E5
evidence. Keep production dispatch disabled until accepted. Do not ask the operator to locate an
external coordinator or nonexistent human assignment source.

## Runtime authorization adjudication

- Declared repository HEAD: `20fda2cbf26274192652a1c829a19f6b1844e9c4`.
- Target: dedicated `Ubuntu-24.04` WSL2 distribution only.
- PM Bridge request: `eb6da1cc-029b-4754-b463-1eb31f79ea97`.
- Correlated reply: `03cbad69-5e1a-4563-b08f-c63bdeeccdc7`.
- Job: `01c12be0-6c0a-43b1-a79a-450e548c99ea`.
- User turn: `99532f45-ff14-4d43-920b-14d2b9a02aeb`.
- Verdict: **MODIFY — CONDITIONAL GO; EXISTING OPERATOR AUTHORITY RECOGNIZED**.

GPT-PM considered the operator's dedicated-WSL selection, narrow worker-helper approval, repeated
GO for autonomous work, and current explicit confirmation of sole ownership. It directed Codex not
to ask for generic GO again. It recognized authorization for bounded preparation/provisioning in
the named WSL, subject to technical preconditions:

| Action | Disposition |
|---|---|
| Refresh name/UID/GID collision checks; prepare exact non-secret configuration bundle | GO |
| Create planned service identities; install root-owned non-secret config and exact committed runtime | Conditional GO after source/test review and exact bundle review |
| Initialize a fresh schema-v6 Store | Conditional GO |
| Migrate an existing supported older Store | Separate migration gate; inspect first, preserve all data/chain/anchor |
| Generate distinct local service keys within private destinations | Conditional GO, with purpose separation and least privilege |
| Generate production instruction-issuer authority/key | NO-GO until issuer authority/custody is separately established |
| Activate exact S2 units; run permitted mapped E2E | Conditional GO after source/runtime readiness and configuration review |
| Collect authentic probe and host/network observations | GO |
| Claim a human-signed E5 attestation without its authorized signer | NO-GO; Codex must not impersonate the operator |
| Run prohibited crash/kill/mutation/policy selectors | NO-GO; retain `NOT_RUN` |

The provisioning plan is not yet a complete exact-current-source installation bundle. The exact
ordered sequence is: (1) complete source/test and independent review gates; (2) prepare and review
one immutable, non-secret manifest containing exact source/artifact digests, identities, modes,
socket rules, Store disposition, key purpose/custody and startup/rollback order; (3) repeat identity
collision checks; (4) provision only after the exact bundle is accepted; (5) inspect Store
read-only—initialize schema v6 only if fresh, stop for a separate gate if an existing Store needs
migration; (6) install exact artifacts and verify ownership/digests; (7) collect authentic runtime
observations; (8) activate only exact approved units and run permitted E2E; (9) obtain genuine
operator-root-signed network-policy attestation before claiming E5/acceptance.

The PM review is an authorization-scope adjudication, not execution or acceptance. At response time
no WSL account/file/key/service/test operation had been performed as part of that review. No
production dispatch, service activation, E5 signature, push, PR, merge or deployment is claimed.

## Current-turn provenance and owners

- Current HEAD at both PM requests: `20fda2cbf26274192652a1c829a19f6b1844e9c4`.
- Current-turn source addition: `tools/vst/dispatch_owner_transport.py`; later accepted by the
  focused source/test review above. Final source and committed blob hashes belong in change record
  0538.
- Test path: `tests/vst/test_s2_dispatch_owner_transport.py`. Windows run: 33 passed / 1 WSL-only
  skip. WSL run: 34 passed / 0 skipped, including real AF_UNIX socketpair + owner handler. This
  does not prove actual systemd peer credentials or production runtime behavior.
- Existing pre-existing untracked `docs/sdlc/evidence/s2-functional-test-run.md` remains excluded,
  unstaged and unmodified.
- Codex owns source, non-secret bundle and permitted evidence. GPT-PM owns architecture and exact
  final gate. The operator is the sole human owner and the only person who may provide any required
  authentic human signature/attestation or establish production issuer custody.
