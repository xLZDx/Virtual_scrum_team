# Change 0543: add bounded S2 machine source contracts

## Scope and decision basis

Sprint: S2. Implementation is limited to pure validation of proposed, externally signed
delegation/assignment records and collection/hash/evaluation of read-only host observations.
The current human E5 v1 contract remains authoritative. This source change adds no signing
service, private-key creation/provisioning, Supervisor dispatch path, E5 PASS, config installation
or runtime activation.

GPT-PM returned MODIFY for request `a3e130f0-9aec-4304-b001-388a45c0be55`, correlated reply
`0b0b8a4d-0816-4146-ba21-71857b5de49d`. Its exact response is in
`docs/sdlc/evidence/s2-machine-authority-adjudication-20261029.md`. The two MAJOR findings remain
open until the corrected contract and source receive focused review and GPT-PM verification.
Security review authorized pure schema/signature-verification helpers and read-only observation
completeness only. The proposed external assignment record and trust purpose do not exist in the
current repository and must not be described as existing authority.

## Source changes

- `tools/vst/machine_authorization.py` defines closed candidate schemas for the delegation policy,
  external signed assignment authorization, and root-configured trust registry. The policy pins
  a distinct operator key ID; the assignment carries both operator authorization key ID and the
  intended delegated issuer key ID/purpose; both operator and machine keys carry revocation IDs.
  It rejects
  unknown/missing keys, malformed identifiers/digests/signatures, invalid times, mismatched
  purpose/key/policy bindings, and revocation. Verification uses the existing bounded OpenSSL
  public-key helper. Assignment matching compares one caller-supplied authenticated read-only
  Store snapshot; the module performs no Store I/O, task enumeration, mutation or signing.
- `tools/vst/machine_observations.py` defines bounded read-only WSL command/proc collection and a
  fixed Windows PowerShell snapshot attempt. It preserves raw observations and errors, hashes
  canonical records, and returns only `OBSERVATIONS_COMPLETE` or `UNKNOWN`. The Windows effective
  rule normalizer is intentionally unsupported, so a Windows snapshot remains UNKNOWN. No result
  is an E5 PASS, policy verdict, trusted collector signature, or Supervisor input.

The assignment verification helper accepts exactly one caller-supplied Store snapshot and
compares the signed fields with it. It does not itself authenticate how the caller obtained that
snapshot; no production caller is wired. The policy verifier also requires the root trust config
to pin the machine key to the digest of the complete canonical signed policy. The E5 observation
bundle currently emits unsigned source receipts and fixed same-time metadata; its evaluator always
returns `UNKNOWN` because no pinned collector trust or complete policy normalizer exists.

## Verification state and limitations

No tests/checks, collection, build, key operation, provisioning, migration, or activation was
performed for this change. The modules have not been independently reviewed. Their schemas are
candidate source contracts; no matching authority keys/configs exist. The assignment helper trusts
that its caller obtained the supplied Store snapshot through the authenticated Supervisor read
boundary. That integration is not implemented here. Windows normalized effective-firewall and
WSL/Hyper-V evidence is unsupported; both machine findings and S2 remain open. Changes are
uncommitted.
