# Change0563: Preserve legacy grants and normalize stored issuance rows

Sprint: 39b7cc253f5d

## Falsifying evidence at6f4ad200

The test owner recorded a current Windows safe-selector run with92 passed,22 skipped and7
failed: the six true schema-v5 fixtures and TP28 direct completion all failed while preparing
legacy/direct execution grants because the new delegated guard demanded a dispatch_grant row
for every grant. A separate36-node POSIX fixture run reported20 passed and16 failed. Fourteen
positive issuer paths failed because the Store adapter passed canonical SQLite JSON text to a
pure reducer whose typed result is a dictionary. The other failures included the same TP28
regression and an extracted-fixture permission defect, not a product permission fix. Results
are separate overlapping candidate runs and must not be added together.

## Compatibility with fail-closed delegated provenance

Both the public delegated-target lookup and runner locked guard now distinguish historical
legacy/direct grants from delegate-origin work. With no exact dispatch_grant association, an
immutable authenticated assignment handoff or accepted DELEGATED_V1 record for the task still
requires the association and refuses the grant. Configuration disablement cannot erase those
facts or downgrade that task. Only the prior direct-grant path with no delegated origin returns
to its existing signature/generation/lease/probe/budget/receipt checks. Existing exact associations
still receive their previous full byte-level operation/dispatch/issuance checks.

The origin helper is a refusal classifier over verified Store history, never positive authority.
It does not treat a missing link as permission for delegated work. Malformed history fails closed.
Required negative regression: a delegate-origin task with missing or altered grant association
remains refused, alongside the old positive legacy cases.

## Stored-to-pure representation boundary

The central Store issuance reducer adapter parses result JSON text once, requires its canonical
encoding to match the stored bytes, then passes the typed value to the unchanged strict pure
reducer. It does not loosen the PENDING sentinel, row schema, event ordering, fingerprint or
cryptographic completion requirements. Existing typed internal values remain supported.

## Verification and fixture limits

Source changed only after the test owners' commands ended and execution was held. No tests,
checks, build, CI, keys, signatures or runtime services were operated by this source batch.
The E2E owner separately corrects its extraction root permissions so its read-only reviewer can
import the fixture package; target worktree/Store/key permissions are not relaxed. Post-fix
legacy, complete positive issuer/grant/claim/reserve and missing-delegated-link regressions
remain for the designated test roles at the new frozen source revision.
