# S2-4 non-secret runtime-config functional tests

## Scope and disposition

This record covers only functional tests for the prepared `docs/sdlc/runtime-config`
candidate. It is not an installation, service-start, production issuer, real probe, E5, or
owner-to-Runner acceptance record. The bundle itself declares `PREPARED_NOT_INSTALLED`.

The focused suite verifies the 32 payload-file byte hashes and 9 declared units; source,
policy, task-manifest, and bootstrap-request cross-bindings through the existing
`validate_task_manifest`, `validate_policy`, and `validate_bootstrap_request` functions;
the configured-model file digest and reviewer-registry unsigned-body digest bindings; public
key file bindings; the three exact `[Unit]` rate-limit override files; secret-free candidate
bytes; and fail-closed identity, request-shape, and timeout behavior of the candidate probe
entrypoint with all host I/O and collection replaced by deterministic fakes.

The initial task-manifest adapter candidate had a real defect: its hook method was declared as
`pytest_runtest_logreport(self, r)`. The first focused run on pytest 8.4.2 rejected parameter
`r` during plugin registration, before nested tests could run. Codex corrected the hook
parameter to `report` and re-bound the task/policy/bootstrap/bundle inputs. The first exact
UID-999 run then exposed a second integration defect: stdout was `.PASS <nodeid>`, while the
existing trusted parser accepts only lines beginning with `PASS `. The parser returned no
executed test IDs, so that run was not an accepted TestRun. Codex added a leading newline to
the adapter output and re-bound all dependent hashes. The final regression test invokes the
actual trusted parser and asserts that it recognizes exactly the successfully passed node ID.
After rebinding, the focused suite and exact UID-999 command passed that parser check.

## Identity and artifact hashes

- Current checkout at test time: `9021b98d6458cb09d7ea1d35942661ff1fee9587`.
- Candidate source identity: `a600774649527ff0b33eb81f4d431f8226119b2c` (declared candidate
  identity; these tests do not assert it is installed or the current checkout HEAD).
- Test selector blob identity:
  `tests/vst/test_s2_assignment_basis.py` is Git blob
  `3daa46b5c1662bd5c5a6220ce66b22f315eed76a` at both candidate base `a600774` and current
  checkout `9021b98`; it has no worktree diff. The exact viability command therefore used
  the same selected test source blob while reading the current canonical checkout read-only.
- Candidate config state: `PREPARED_NOT_INSTALLED`; the bundle lists 32 payload files and 9
  units.
- Bundle's canonical deployment-source binding digest:
  `2451f6d06b93ff34b7c1c0d891c875482ac4b21a71db5c64f7ad6c22d9cb2ba8`.
- Final bundle-manifest canonical SHA-256:
  `84397d39bcf26deacfbbfc90a3b73995d76ef346cc366bc8c7f4933f900be3fd`.
- Bundle's canonical assignment-policy digest:
  `1859bbf777b12ead6ded46581282a976a746071fc844f4f46a2d5baf6e2072cf`.
- Bundle's canonical task-manifest digest:
  `2dc6fce44a3096a0f35afd78baa70a952ae4aa2d8ad0b00f8bac166e10d4fe32`.
- Bundle's canonical runtime-transition-manifest digest:
  `6a9db55005044ba306f4135c93fa411a4ce7e0572482b32ed7ecfecbea35e50a`.
- Current `task-manifest.json` raw-byte SHA-256:
  `1a29b459d21e68d5b8ef434b66a2a2ec9fd8acc427f627417c493d9671ca71ef`.
- Current `task-manifest.json` canonical SHA-256:
  `2dc6fce44a3096a0f35afd78baa70a952ae4aa2d8ad0b00f8bac166e10d4fe32`.
- Current `bundle-manifest.json` raw-byte SHA-256:
  `064528af5637e2b1d0591191da6a34d621440da4b3a67291038b2bd141009dce`.
- Current `bundle-manifest.json` canonical SHA-256:
  `84397d39bcf26deacfbbfc90a3b73995d76ef346cc366bc8c7f4933f900be3fd`.
- Focused test source raw-byte SHA-256: `7cf6f3cac265d3811623c43f1c8ae623873789cfada0e6a1f2eac77c3d41e259`.
- `model-provenance.json` raw-byte SHA-256:
  `a78f908212da5715a951c62d17e2ec720ad6065c13164191d3aef0bf506d6303`; the file reports
  configured model `gpt-6-luna`, `provider_executed_model=NOT_VERIFIED`, and
  `provider_signed_identity=NOT_ATTESTED`.
- Reviewer-registry canonical unsigned-body SHA-256:
  `54cff371ded18ba866a7304eb41b1b5ab5d1f523305480db2076fc1969920f53`. The bound principal
  is the local technical reviewer `vst-independent-reviewer`; the use policy explicitly
  denies an external GPT-PM credential, self-approval, and final PM Bridge approval. The
  registry HMAC was verified in memory with the domain-separated helper, and a tampered
  principal was rejected. Key contents and signature bytes were never printed or exported.
- The bundle's runtime-transition identity declares helper binary SHA-256
  `40cca741389d4b711dfca45da2698846a6acc801be006456cc7af207e2dd6353` and runtime tree
  SHA-256 `6ec90c3ef82478b09f07390c0d3f38f36317efb58976cef4c060dc1968649b12`; these tests
  verify the manifest's internal bindings only, not those bytes on a target host.

## Commands and results

The final tests used the explicitly selected `Ubuntu-24.04` WSL distribution, root to mount
the repository drive read-only, Python 3.12.3, and pytest 7.4.4. D: was mounted with
`drvfs -o ro` in the same shell process that changed to the repository and ran pytest. The
suite and temporary nested pytest fixtures therefore could not alter repository files; the
nested fixtures were created under `/tmp`.

Initial WSL attempts before selecting the explicit distribution did not run tests:

```text
wsl.exe --cd /mnt/d/Repo/Virtual_scrum_team --exec env PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests/vst/test_s2_runtime_config_bundle.py
```

Result: exit 1, `env: can't execute 'python3': Permission denied`.

Attempted direct WSL interpreter command:

```text
wsl.exe --cd /mnt/d/Repo/Virtual_scrum_team --exec /usr/bin/python3 -m pytest -q -p no:cacheprovider tests/vst/test_s2_runtime_config_bundle.py
```

Result: exit 1, WSL `execvpe(/usr/bin/python3) failed: No such file or directory`. These were
default-distro invocations, not evidence that Ubuntu 24.04 was unavailable. The exact
Ubuntu-24.04 interpreter was then verified as Python 3.12.3 / pytest 7.4.4.

The initial focused run preserved the adapter finding:

```text
python -B -m pytest -q -p no:cacheprovider tests/vst/test_s2_runtime_config_bundle.py
```

Initial result: exit 1, `1 failed, 8 passed`; plugin registration raised
`PluginValidationError` because `pytest_runtest_logreport(self, r)` declared unsupported
argument `r`. This is a historical candidate result; Codex changed the argument to `report`.

Final full focused suite on the explicitly selected Ubuntu 24.04 distribution, mounting D:
read-only and running the test in the same shell process:

```text
wsl.exe -d Ubuntu-24.04 -u root -- /bin/bash -c "mount -t drvfs -o ro D: /mnt/d && cd /mnt/d/Repo/Virtual_scrum_team && /usr/bin/python3 -B -m pytest -q -p no:cacheprovider tests/vst/test_s2_runtime_config_bundle.py"
```

Final result after the trusted-parser regression and corrected manifest rebind: exit 0,
`9 passed in 2.92s`. The environment was Python 3.12.3 and pytest 7.4.4. The suite invokes
the actual trusted parser and checks the exact passed nested node ID. No unrelated suite ran.

## Exact TaskManifest command viability

The current `allowed_commands[0].argv` was loaded from
`docs/sdlc/runtime-config/task-manifest.json` and executed verbatim via `runuser -u
vst-worker`; the test was not copied into another script. The user resolves to UID 999 and
GID 989 in Ubuntu 24.04. The shell mounted D: read-only and used that same repository
snapshot. The actual nested pytest command was:

```json
[
  "/usr/bin/python3",
  "-c",
  "import sys\nsys.dont_write_bytecode = True\nimport os,pytest\nclass _PassLines:\n def __init__(self): self.phases={}\n def pytest_runtest_logreport(self,report):\n  p=self.phases.setdefault(report.nodeid,{})\n  p[report.when]=bool(report.passed and not getattr(report,'wasxfail',False))\n  if report.when=='teardown':\n   if all(p.get(x) is True for x in ('setup','call','teardown')): os.write(1,('\\nPASS '+report.nodeid+'\\n').encode('utf-8'))\n   self.phases.pop(report.nodeid,None)\nraise SystemExit(pytest.main(['-q','-s','-p','no:cacheprovider',*sys.argv[1:]],plugins=[_PassLines()]))",
  "tests/vst/test_s2_assignment_basis.py::test_assignment_basis_returns_exact_stored_wire_handoff_without_enrichment"
]
```

The launcher read this `argv` from the task manifest and executed it under the actual
`vst-worker` account:

```text
wsl.exe -d Ubuntu-24.04 -u root -- /bin/bash -c 'mount -t drvfs -o ro D: /mnt/d && cd /mnt/d/Repo/Virtual_scrum_team && /usr/bin/python3 -c "import json,os; a=json.load(open(\"docs/sdlc/runtime-config/task-manifest.json\"))[\"allowed_commands\"][0][\"argv\"]; os.execvp(\"runuser\",[\"runuser\",\"-u\",\"vst-worker\",\"--\",*a])"'
```

The first run before the adapter correction exited 0 and pytest reported one pass, but stdout
was .PASS <nodeid> and the actual trusted parser returned no IDs. That historical execution
was not an accepted TestRun. After the newline correction and manifest rebinding, the exact
manifest argv ran again as vst-worker (UID 999, GID 989). Final result: exit 0; pytest
reported 1 passed; stdout contained the progress dot and then a distinct line beginning
PASS with the selected node ID. The actual trusted parser returned exactly that one required
ID. This establishes bounded fixture-command viability only; it does not start a service or
prove the outer owner-to-Runner path, actual E5, production identity, or current signed
provenance.

## Local registry integrity verification

The actual functional-test-reviewer executed the existing `tools.vst.signing.verify`
helper with `REVIEWER_REGISTRY_LABEL` under Ubuntu-24.04/root. The key was read only
into that process from `/var/lib/vst-config-preparation/s2-20261030/network-policy.key`;
the input registry was the exact candidate JSON. Reported exit0 with boolean outcomes
`registry_hmac_valid=True` and `tampered_registry_rejected=True`. No key bytes were
exported. This is registry integrity, not a reviewer outcome or GPT-PM approval.
The agent result is the provenance for this admin check; the primary did not rerun it.

## Acceptance mapping

| Item | State | Evidence and limitation |
|---|---|---|
| Non-secret bundle byte inventory and candidate safety | PASS (local candidate only) | Focused suite verifies all 32 listed file sizes/SHA-256 values, exact inventory, candidate state, source membership, public key byte bindings, three exact [Unit] rate-limit overrides and absence of private-key PEM markers. Does not prove target-host bytes or installation. |
| TaskManifest / policy / bootstrap input cross-bindings | PASS (local candidate only) | Existing validators accept the candidate; deliberate task-digest, retry-attempt and path-scope changes are rejected. The exact selected fixture command ran as UID 999 and the actual trusted parser returned its required ID. This is command viability, not service-runtime proof. |
| Configured model and reviewer identity records | PASS for declared digest bindings and authority separation | Model bytes match the Supervisor configured-model digest; the local technical-reviewer registry body matches its recorded/task-manifest digest. The HMAC helper verifies the exact signature and rejects a tampered principal. No provider attestation or GPT-PM approval is claimed. |
| Probe-entrypoint negative behavior | PASS with fake boundaries only | Wrong worker ID, malformed request and missing-attestation timeout fail before the collector; fake clock avoids waiting and the actual collector/network probe is never called. |
| TaskManifest PASS-line adapter behavior | PASS (focused local regression) | The final 9-case suite invokes the actual trusted parser and proves it returns exactly the fully passed nested pytest node ID. The earlier .PASS concatenation defect remains recorded above. |
| Exact TaskManifest test command under configured UID | PASS (bounded command viability only) | Final manifest argv ran as vst-worker UID 999/GID 989; pytest reported one pass and the trusted parser returned exactly the required ID. This does not prove an installed service or outer runtime journey. |
| S2-4 actual installed runtime / current E5 / owner-to-Runner journey | NOT_RUN | These tests do not install configuration, start services, perform a real probe, or execute the outer owner-to-Runner journey. Codex owns authorized runtime delivery and coordinating the distinct E2E evidence. |
| Restricted process-kill, crash/recovery, mutation campaigns, E8 and policy selectors | NOT_RUN | These scenarios are outside this bounded test assignment and remain unrun. |
| GPT-PM formal exact-head approval | NOT_RUN | Local registry HMAC validity is a technical identity-integrity check, not an external GPT-PM verdict or final gate. GPT-PM owns its separate exact-head review when requested by the task flow. |

Traceability note: the TaskManifest acceptance REQ-003 remains mapped to its inner
Store-fixture TestRun. It does not close S2-4's actual service journey; separate outer
S2-4 AC1/REQ-005 evidence belongs to the E2E lane. No fixture result is relabeled as
owner-to-Runner proof.

## Ordered next actions

1. Codex: include this focused test and evidence in the current S2-4 task's detailed
   change record, commit, and normal push before starting another backlog task.
2. Codex / E2E lane: use the separately authorized runtime work to collect actual
   run-bound runtime/E5 and owner-to-Runner evidence. Do not infer it from local command
   viability or fixture tests.
3. GPT-PM: adjudicate the separate exact-head code approval when the current S2 task
   queue reaches final acceptance; the local reviewer registry is not this approval.
