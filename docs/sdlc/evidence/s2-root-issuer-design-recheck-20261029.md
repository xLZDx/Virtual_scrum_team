# Root issuer targeted design rechecks — 2026-10-29

Sprint: 39b7cc253f5d

Owner: Codex (coordination/source); GPT-PM (architecture/source adjudication).
Evidence source: actual collaboration tasks /root/s2_issuer_db_design and /root/s2_issuer_security_design, configured named database-reviewer and security-reviewer profiles (gpt-6-luna, medium effort). Scope: HEAD e44f48dca00802b9f6ad6c8629fe909dbe0a4a99 plus the working-tree design corrections subsequently included with change0554. No tests/checks/build/CI/edit were performed by either reviewer.

| Finding | Original evidence | Correction | Actual recheck disposition | Remaining acceptance |
| --- | --- | --- | --- | --- |
| Crypto completion | The original reducer checked envelope fields/hash but not Ed25519 against the frozen root signer. | Committed0553 requires a completion_verifier callable over copied frozen signer, exact v1 domain-prefixed signing bytes and decoded signature, returning literal True. Revised design requires root-pinned key/fingerprint, no RPC boolean/context, outside-SQL crypto with exact in-transaction identity binding. | Both reviewers: design MAJOR resolved; no remaining valid design-level BLOCKER/MAJOR in the targeted sweep. | Codex constructs and integrates trusted context; actual cryptographic tests/source reviews and GPT-PM acceptance remain. |
| Snapshot and durable authority | Earlier prose proposed a provenance pre-read followed by public execution_grant_basis in a different transaction. | One connection-taking predicate checks provenance, current policy/key/run/generation/probe/owner/lease/manifest/receipt/budget and invokes the locked grant helper; repeat on grant persistence/replay and runner claim/reserve; delivery is observation-only. | Database reviewer: design MAJOR resolved. Security reviewer: covered; delegate-to-legacy fallback expressly refused. | Codex implements exact Store/Supervisor boundaries, then designated tests and exact-source reviewers verify. |

Both reviewers recommend GO for bounded integrated SOURCE implementation of this corrected contract. This recommendation is not GPT-PM I01 adjudication, production/private-key signing authorization, key provisioning, service activation, runtime/E5 acceptance, full test acceptance or S2 closure. The prior PM reply remains authoritative until its focused remediation is adjudicated. Protected functional-test and raw private evidence were not inspected.
