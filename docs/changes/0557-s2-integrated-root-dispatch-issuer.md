# Change 0557: S2 integrated root dispatch issuer source

## Scope and authorization

This source change follows the bounded I01 GO recorded in `docs/sdlc/evidence/s2-i01-integrated-source-adjudication-20261029.md` (request `c7a8e23e-91f5-489c-a096-c813d84c3b12`, correlated reply `7c3e4eb6-3300-5c5b-ba5c-85aaa10d0487`). It adds a default-off root dispatch signing path using the existing v1 instruction bytes and existing SQLite operation/event journal. It does not provision keys, enable production signing, or claim S2 acceptance.

## Source changes

- `tools/vst/store.py` adds specialized reservation, signer-start, completion, UNKNOWN, and read-verification operations for `VST_S2_ROOT_DISPATCH_ISSUE_V1`. The existing generic external idempotency operation is not used. Startup validates the issuance journal structure, event order, row binding, immutable intent and envelope shape; startup deliberately does not infer cryptographic completion.
- `tools/vst/root_dispatch_issuer.py` freezes the assignment handoff, policy, signer fingerprint, unsigned v1 envelope, TTL and safety slack before the signer. It calls OpenSSL outside Store transactions, verifies the result with the pinned public key, then asks Store to persist the verified completion. A failure after the started marker is recorded as UNKNOWN where possible.
- `tools/vst/supervisor.py` adds an operation-ID-only root API. It obtains the current root policy and service generation and reads the exact Store-backed authenticated handoff before invoking the signer.
- `tools/vst/supervisor_service.py` adds an optional issuer configuration (disabled when absent) and an authenticated `delegated_issuer` RPC restricted to one assignment operation ID. Key files use fixed root paths and existing root-file permission checks.

## Decisions and compatibility

The dispatch instruction v1 wire format and trust-registry entry shape are unchanged. Existing configuration without `root_dispatch_issuer` remains disabled. No schema, migration, table, daemon, scheduler, or event-chain trigger change was introduced.

## Source-condition disposition

- **SRC-01, grant provenance:** delegated acceptance stores the issuance operation key and exact envelope digest. Dispatch-grant operation payloads bind those values and retain the exact signed execution-grant result. Runner claim and reservation join the supplied grant bytes to that operation and its accepted dispatch/issuance; task tuple matching alone is insufficient.
- **SRC-02, atomic admission/replay:** new delegated acceptance and exact delegated idempotent replay run the same locked current owner, lease, manifest, probe, receipt-gap and budget predicates. Historical outcome replay remains observational.
- **SRC-03, verified journal:** issuance has its own event family, strict order/multiplicity/field/row checks, separate from generic internal and external operation families. Event chain and external anchor are checked. Startup checks structure only; COMPLETED is returned only after a root-owned verifier validates the exact v1 signing bytes against the pinned key fingerprint outside SQL. A sealed in-process context binds that verification to the same durable envelope at use.
- **SRC-04, snapshots/current authority:** admission, delivery validation, grant create/replay, runner claim and runner reservation repeat current Store predicates on the same connection used for the relevant read/write boundary. Root policy and generation providers are re-read at authorization boundaries. Issuance reserve, STARTED and completion writes also recheck the current handoff, policy, generation, probe, owner, lease, manifest, receipt gap and budget.
- **SRC-05, crash-safe signer:** all fields and expiry are frozen before reservation. Only the transaction that appends the unique STARTED marker may enter OpenSSL. A failure after STARTED records UNKNOWN where possible; no retry signs that identity again. Existing operation replay reads the persisted frozen intent and never computes a new expiry.

No tests, checks, builds, runtime commands, private-key operations, or key provisioning were run. Functional/E2E evidence and independent DB/security review remain `NOT_RUN`/pending for the post-coding phase. The issuer stays default-off; this source change does not activate runtime signing or close S2 Phase 8.

## Provenance

At the initial assigned baseline, `git rev-parse HEAD` returned `0cef101ee70be03b0436d82fad459916a79ee65b`; the assigned source and detail files had no scoped pre-existing diff. Parent-session commits advanced the shared HEAD to `4314957986c56ad0a0babb5994390bb67993a4c3` during implementation; this continuation preserved those commits and continued only the assigned source paths. At final source handoff the shared HEAD was observed at `b5862d517d6c6589a85b8750dd4313ab95238bfd`; the provenance of that concurrent HEAD movement is not attributed here. The initial implementation checkpoint was partial; this updated record reflects the later integrated source work.
