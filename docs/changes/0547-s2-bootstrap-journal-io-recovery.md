# Change 0547: make bootstrap journal preparation and recovery retryable

## Scope and starting state

Baseline for the owned source files: initial `git status --short` returned no entries for
`tools/vst/bootstrap_runtime.py`, `tools/vst/runtime_bundle.py`, and this change-record path;
these files are the ongoing local S2 implementation. This focused correction changes only
`tools/vst/bootstrap_runtime.py` and adds this record. No protected evidence or other checkout
was accessed.

## Failure windows corrected

Journal preparation now occurs in a unique root-owned mode-0700 `.preparing-<manifest>-<nonce>`
directory. It durably writes the exact manifest and `preparing` state before copying any unit
snapshots. Only after all snapshots, the ready journal state, each file and the directory are
synced does `renameat2(RENAME_NOREPLACE)` publish the directory under its final transaction ID.
The selector and unit files remain untouched until publication succeeds. The ordinary apply scan
validates and retains unpublished preparation directories but does not treat them as armed
transactions, so an I/O failure during the first manifest/state/snapshot write cannot trap future
apply or recovery attempts. Retries use a new nonce and never remove or overwrite a partial
preparation. Final journal name collisions refuse safely.

When restoring a previous regular unit, recovery now writes the selected new bytes to a fresh,
exclusive random retained path, verifies its digest, and syncs the retained directory before
restoring the previous bytes. A failed short write leaves its partial copy retained; the next
attempt chooses a different no-replace name. If failure occurs after a complete retained copy but
before replacement, retry may retain another copy, then safely finish. No partial copy is treated
as valid, and no file is deleted. Existing full-set old/new preflight remains before any recovery
write. A previously absent unit is still restored by atomic rename into the retained quarantine.

## Verification status and handoff

No tests, checks, compilation, provisioning or runtime command were run. The functional/E2E role
is adding deterministic ordinary-I/O exception cases after source coding freezes; no process-kill
or power-loss selector was authorized. Hand off these two correction points for fresh focused
review; test owners then verify partial preparation retry, failed partial retention retry,
durability ordering, no fixed-path mutation before journal publication, and whole-set recovery
preflight. The runtime selector remains source-only and does not open Store, activate services or
close S2.
