# Change0561: Fix frozen identity and reload current issuer trust

Sprint: 39b7cc253f5d

## Falsifying evidence at assembled source e987a24

The actual functional-test-reviewer's issuer-inclusive run reported43 passed,3 failed and6
Windows POSIX skips. All three failing positive issuer cases stopped because the frozen intent
omitted assignment_operation_id, although the exact closed schema requires it. A separate
nonissuer command had39 passed and6 skips; these overlapping runs are not a combined total.
The same role's source inspection confirmed SRC04's missing current key/config providers:
service startup loaded the registry and issuer metadata into cached dictionaries without a
file-backed use-time reload. Both defects are corrected in this batch.

## Behavior changes

- dispatch_issuance.py freezes the exact authenticated handoff assignment_operation_id along with
  deterministic issuance identity; no expiry, key or wire-field change is introduced.
- Supervisor accepts root_dispatch_issuer_provider and dispatch_instruction_trust_provider.
  An enabled issuer requires both; missing/unavailable/removed/disabled/changed issuer metadata
  or trust-registry data fails closed for delegated use.
- The service loader supplies real root-file readers, not cached-object lambdas: current issuer
  settings come from the controlled service configuration; the fixed trust registry is reread
  and must remain root:root mode0644. Derived paths and signer metadata remain fixed.
- Issuance reserve/STARTED/completion, admission/replay, delivery/grant and runner claim/reserve
  guards refresh current metadata through those providers. Crypto and PEM reads remain outside
  SQL; the SQL guard reads only bounded root-controlled configuration/registry metadata.
- Configurations without an enabled issuer retain legacy constructor behavior. Historical exact
  completed receipt/outcome observation does not become new delegated execution authority.

## Provenance and limits

Codex applied the single frozen-field correction; the existing implementation-engineer role
implemented the provider fix in supervisor.py and supervisor_service.py only. Test roles owned
all test-file changes and preserved their negative assertions. The E2E role also found stale
historical node IDs; its46-selector output lacked a retained final handle/result and is honestly
NOT_RECORDED, never PASS. All those processes were confirmed terminal before source changed.

No test, check, build, CI, key or runtime operation was performed by this source-fix batch. Test
roles rerun permitted cases after this new freeze, update enabled-issuer constructor fixtures
with independent live providers, and extend the full positive grant/claim/reserve journey.
Prior failures remain recorded; source approval and complete S2 acceptance remain pending.
