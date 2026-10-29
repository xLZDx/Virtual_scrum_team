# Windows PowerShell 7 live observation — 2026-10-29

Sprint: 39b7cc253f5d

## Result

**State: UNKNOWN / incomplete observation.** The fixed collector was invoked on source HEAD `d3f326f37a40936402d3933d5266e0ffb01017f0` with explicit profile `powershell-7`. Its PowerShell child returned nonzero, so no usable snapshot or counts were collected. The collector also reports that effective-rule, endpoint, path and Windows/WSL correlation normalization is not implemented. This is not an E5 attestation, policy verdict, or production approval.

| Item | State | Evidence | Remaining acceptance / owner / next action |
|---|---|---|---|
| Fixed PowerShell 7 collector | UNKNOWN | `collect_windows_observations(profile="powershell-7")`; command snapshot absent; collector `collection_complete=false`; sanitized errors: `UNKNOWN / command returned nonzero exit status` and `UNKNOWN / complete effective-rule, endpoint, path and Windows-WSL correlation normalization is not implemented`. | Codex: inspect the collector process failure through an authorized private diagnostic path; preserve UNKNOWN until bounded collection succeeds. |
| Firewall / Hyper-V / WSL counts | NOT_AVAILABLE | No snapshot was returned; no counts were derived. | Codex: only report counts after a successful snapshot. No inference from missing output. |
| E5 / cross-source policy | UNKNOWN | No signed receipt, accepted observation contract, normalized effective-policy evaluation, or human attestation was produced by this observation. | GPT-PM: adjudicate evidence contract after a complete, authenticated source is available. Operator owns any human E5 attestation or reserved production authorization. |

## Provenance and privacy

- Current source HEAD: `d3f326f37a40936402d3933d5266e0ffb01017f0`.
- Collector source: `tools/vst/machine_observations.py`, SHA-256 `9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11`.
- Exact API call used the explicit `powershell-7` profile. The collector selects the fixed executable `C:\Program Files\PowerShell\7\pwsh.exe`, passes `-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Restricted`, uses a fixed embedded read-only script, a 5-second child timeout, a 1 MiB per-command output bound, and a restricted environment. No fallback profile was attempted.
- Raw observation SHA-256: `e7a3babff955b49619f096762f541efdaf90a375d7cc88d9a8f5e0fe2bf38351`; 1,620 bytes. It was retained only in a newly created file under `.git/vst-private-evidence/`, outside the worktree and index. Its ACL is protected, with one explicit access entry for the current user; no raw output or host policy data is published here.
- The sanitized report omits raw stderr, firewall rules, addresses, application paths, WSL distribution identifiers and command output. Counts are unavailable rather than zero.
- No E5 signing, key/configuration/provisioning change, service activation, network probe, build, test, or CI was performed. The collector's own bounded child handling may terminate its child on timeout/output overflow; this run ended with the child returning nonzero and did not invoke any production service operation.

## Next steps

1. Codex reviews the sanitized child failure using only the new private record and source; do not expose raw host output.
2. If a narrowly scoped read-only retry is justified, use the same fixed PowerShell 7 profile and bounded collector API, retaining raw output privately and publishing only sanitized status.
3. Keep Windows policy and E5 status UNKNOWN until source provenance, complete normalization, and the required human attestation are independently established.

## Sanitized diagnosis update

The private record's bounded PowerShell stderr was classified without publishing its text. It contains a “not recognized” failure associated with the fixed `Get-NetFirewallProfile` invocation in the embedded script at `tools/vst/machine_observations.py:191`. The sanitized PowerShell error class is **CommandNotFoundException**; no HRESULT or provider-specific error code was present in the retained error fields. A separate bounded, read-only diagnostic used the same fixed PowerShell 7 executable and restricted environment: `NetSecurity` module discovery succeeded (version `2.0.0.0`), but `Get-Command -Module NetSecurity -Name Get-NetFirewallProfile` found no exported command. The diagnostic returned no stderr and exited successfully.

**Classification: host/module command unavailable in the selected PowerShell 7 execution context; no evidence of a permission denial or source-code exception.** The module is discoverable, but its target cmdlet is not exposed in this context. The collector correctly returned UNKNOWN and did not fall back to PowerShell 5.1. Source line 191 is the failing fixed snapshot stage. This diagnosis does not establish whether a different Windows PowerShell module edition would expose the cmdlet, nor does it upgrade collection completeness or E5 status. The raw record remains private; no command output, policy text, rule/address data, or host identifiers were added here.

### Explicit native module import follow-up

A bounded follow-up attempted `Import-Module NetSecurity -SkipEditionCheck -ErrorAction Stop`, followed by a lookup for the exact `Get-NetFirewallProfile` cmdlet, using the same fixed PowerShell 7 executable, restricted environment, noninteractive flags, and five-second command bound. The module had previously been found by `Get-Module -ListAvailable` as version `2.0.0.0`; explicit import did not make the target cmdlet available. The bounded process returned exit code 1 with 318 bytes of stderr, but emitted no safely extractable exception class, `FullyQualifiedErrorId`, or provider code in the redacted diagnostic. A second catch-only attempt to retrieve the exception type reached the five-second timeout; it produced no diagnosis and was not retried.

This leaves the precise import failure **UNKNOWN**. It does not support a permission-denial conclusion, nor does it establish a source defect. The current evidence is: the fixed collector context cannot resolve `Get-NetFirewallProfile`; the module manifest is discoverable, but the target cmdlet is unavailable; explicit import failed within the bounded attempt. Keep Windows collection and E5 UNKNOWN. Further resolution depends on an authorized host/module profile that exposes the cmdlet or a separately reviewed collector implementation; do not widen the timeout or use a fallback profile under this evidence run.
