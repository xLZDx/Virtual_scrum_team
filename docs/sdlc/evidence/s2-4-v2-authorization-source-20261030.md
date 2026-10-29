# S2-4 bounded V2 authorization source evidence — 2026-10-30

## Scope and disposition

This record covers one bounded S2-4 source slice: V2 closed-schema validators, distinct
signature-purpose checks, synthetic-signature verification, and a root-Supervisor read-only
comparison between one signed authorization and one Store assignment snapshot. The design
clarification was approved by GPT-PM request `70c7fd31-463d-47ad-b95b-dd8916d7218c` as a design
decision only. It does not approve privileged signing/issuance, provider provisioning, production
keys/configuration, activation, dispatch, machine E5, or full S2-4 acceptance.

The test run was against the working tree based on Git HEAD
`34da3392d3390a7c08f2360e9a74deae19f8e77f`; the code and test files were not committed at test
time. File SHA-256 values below identify the tested source snapshot. The resulting commit is
expected to contain these exact file bytes.

## Implemented source

- `tools/vst/machine_authorization.py`: closed V2 policy, trust-config and assignment schemas;
  distinct V2 purposes; policy and assignment signature validation; expiry/revocation/scope
  checks; and a pure comparator for a verified authorization against a Store snapshot.
- `tools/vst/supervisor.py`: `verify_machine_assignment_authorization_v2` takes only an
  authorization ID from its caller, obtains policy/trust/authorization through configured
  providers, checks the authenticated issuer peer and active root assignment policy, obtains the
  current Store snapshot internally, and compares the signed tuple. It fails closed when providers
  or root authority are absent.
- `docs/sdlc/S2_DELEGATED_MACHINE_TRUST_DESIGN.md`: records the exact V2 contract and limits.
- `tests/vst/test_s2_machine_authorization_v2.py`: synthetic-key and disposable-Store coverage.

This verifier is not wired to an RPC route and does not issue or activate dispatch. The existing V1
caller-selected operation-ID path remains a separate open integration finding; no fallback,
production trust, or E5 replacement is claimed.

## Test evidence

Owner: `functional-test-reviewer` (the only role authorized here to author and execute the tests).
The primary session did not author or run these tests.

Windows command:

```powershell
& 'C:\Python314\python.exe' -m pytest -q tests/vst/test_s2_machine_authorization_v2.py
```

Result: **2 passed, 11 skipped**, exit 0, Python 3.14.3. The 11 skips are POSIX-only synthetic
signature/Supervisor cases. The run emitted an existing `pytest-asyncio` deprecation warning.

Ubuntu-24.04 WSL command (D: mounted read-only inside the same root process; fixtures stay in
`/root`):

```text
wsl.exe -d Ubuntu-24.04 -u root -- bash -lc 'set -e; mkdir -p /mnt/d; mountpoint -q /mnt/d || mount -t drvfs D: /mnt/d -o ro; cd /mnt/d/Repo/Virtual_scrum_team; PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/vst/test_s2_machine_authorization_v2.py'
```

Result: **13 passed in 0.79s**, 0 skipped, exit 0, no warnings. These are focused source/fixture
tests using disposable synthetic keys and Store state, not production identity or runtime evidence.
An earlier WSL attempt failed because the per-process D: mount was not visible in a separate WSL
process; the corrected single-process command above passed. A previous fixture iteration also
removed the wrong trust-config key; the test author corrected it to remove `revocations`, and the
final complete run passed.

## Independent review

- `code-reviewer`: final read-only review of the current V2 source diff; no actionable finding.
- `security-reviewer`: final read-only review; no actionable new security finding in the bounded
  verifier. Confirmed limits: no RPC route, production providers/keys absent, and the legacy V1
  caller-selected operation-ID path remains open.
- These are source reviews, not production-security or runtime approvals. The custom reviewer role
  profiles use `gpt-6-luna`; the launch exposed no explicit effort value.
- `git diff --check` returned no output. No build, migration, Store mutation, production command,
  dispatch activation, or restricted process-kill/crash/mutation/E8/policy selector was run.

## Tested worktree identity

```text
08ADFE05C496469406AF9538B12A2A23E2F21DFDEFE6DC528E6D4A985BFF092F  tools/vst/machine_authorization.py
A97BD9A5A77D986FEB59563C8F746936D11841F124442030CD2A5741610A6508  tools/vst/supervisor.py
379AFE43D033BAEC84154D34D00ABA44026DD6847A5519B0CE66E2758859E5C9  docs/sdlc/S2_DELEGATED_MACHINE_TRUST_DESIGN.md
CFA8135256107ADCAF23033ED488D18F031A61C2E081B0F7F6F946B317EF722E  tests/vst/test_s2_machine_authorization_v2.py
```

## Remaining acceptance and owner

S2-4 remains **OPEN / not accepted**. Codex owns the next bounded issuer-integration proposal and
source delivery; GPT-PM owns its contract adjudication and any exact-head code decision; the
operator owns reserved production delegation authorization and human-attestation/key-custody
acts. The legacy V1 caller-selected route must be disabled or bound by the separately approved
issuer integration. Current human E5 remains mandatory. Production identity/configuration,
current run-bound provenance, and a real owner-to-Runner journey remain unproven. Restricted
scenarios stay `NOT_RUN`. S2-5 and S3 do not start until this active task is delivered and the
ordered backlog permits them.

## Exact-head GPT-PM code decision

- Review request: `b53d89ab-aca1-4432-87d3-5b139592f575`; durable job:
  `5ab58c00-1f88-4e4e-b393-1d3cdff2f7d8`; correlated user turn:
  `ab51b798-259d-4b63-bb8e-d64ea144350e`; correlated reply:
  `0477831c-98fa-5e91-8416-5b5b4ff7cacd`; `correlated=true`.
- Exact reviewed code HEAD: `aa3496322ca7b05955dd60dfee7decd8056f34ee`.
- Verdict: **APPROVE — bounded S2-4 source/test task accepted**, 0 BLOCKER and 0 MAJOR in the
  requested scope. GPT-PM accepted the attached file hashes and reported Windows 2 passed/11
  skipped and Ubuntu-24.04 WSL 13 passed/0 skipped. The review did not independently execute tests.
- Full S2-4 is explicitly **NOT APPROVED**. The V1 caller-selected operation-ID route, V2 issuance
  journal/downstream admission integration, production key/trust configuration, runtime signer
  binding, dispatch activation, current machine E5 and real owner-to-Runner journey remain outside
  the verdict. Current human E5 stays mandatory and restricted selectors remain unqualified.
- The approval permits preparation of a separately gated issuer-integration task. It does not
  authorize privileged signing implementation, key/config provisioning, service activation,
  dispatch, Store migration, E5 replacement, runtime acceptance, or S2 closure.
