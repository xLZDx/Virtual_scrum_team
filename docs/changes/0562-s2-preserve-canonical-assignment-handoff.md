# Change0562: Keep validation metadata outside canonical handoff identity

Sprint: 39b7cc253f5d

## Falsifying evidence

At sourcea20283da75a1900b2ee297cd4215b87ac3c9059f, e2e-runner's exact12-ID POSIX fixture
command reported7 passed and5 failed. The WSL payload SHA was
7f6a69a725a2afcae066d657f15b8b25437d4a03dbc9b2588f9cc99de9b6eab1. The positive issuer path
rejected snapshot.handoff because validate_handoff adds derived payload_sha256, while the
issuance contract correctly requires only the exact closed stored handoff fields. The negative
cases did not prove a working positive path. No runtime production authority was exercised.

## Change and invariants

Store.authenticated_assignment_basis still validates the handoff digest, canonical operation
payload, policy, generation/run, probe, manifest, owner and lease in one verified read snapshot.
Its handoff member now returns the exact already-validated stored result instead of the enriched
local validation object. Derived payload digest remains available internally for its original
integrity check; no verifier or schema rule is weakened.

The issuance transaction's current-handoff equality likewise compares its frozen identity to
handoff_result, the exact stored object. It separately compares the derived validation digest
to the immutable operation row payload digest. This corrects both occurrences of the same
representation mismatch. Unknown/missing source fields still fail the closed validator before
any object is returned; no arbitrary caller field is stripped to force acceptance.

## Verification state

The test owners paused affected execution before this source edit. This batch ran no tests,
checks, build, CI, key generation, signing or service commands. It is a two-site source fix,
not an acceptance claim. Designated roles add/retain the exact-wire snapshot regression and
rerun the complete positive delegated path at the new source identity, preserving prior results.
