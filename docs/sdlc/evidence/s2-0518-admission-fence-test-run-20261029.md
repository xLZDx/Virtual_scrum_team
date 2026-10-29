# S2-0518 focused signed-dispatch and admission-fence test run — 2026-10-29

## Scope and final result

The `e2e-runner` executed only the four focused synthetic S2 modules below. The accepted run used
committed HEAD `cec0dbf3249b5734bdae52f644ac790e07d869f8` and passed **105 tests** in **3.97 seconds**.
This evidence covers the signed dispatch instruction, Store-backed Pub/Sub contract, dispatch-owner
relay framing and ambiguous-result behavior, and the persistent systemd admission fence. It does
not prove systemd activation, production credentials, E5 provenance, real dispatch, or full S2
acceptance.

Exact pytest invocation:

```text
pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py
```

The Windows `D:\Repo\Virtual_scrum_team` checkout is not mounted at `/mnt/d` in the selected WSL
distribution. To execute POSIX-only tests without changing or creating a Git worktree, each attempt
used `git archive HEAD` from that canonical checkout and extracted the committed snapshot into an
ephemeral `/tmp/vst-s2-test-*` directory in WSL. That directory was removed after each run. No test
or source file was edited by the e2e-runner, and the pre-existing untracked
`s2-functional-test-run.md` was not opened, changed, staged, or removed.

## Environment and exact-head evidence

- Distribution: WSL `Ubuntu-24.04`; process ran as POSIX root (`euid=0`), with `/root` mode `0700`.
- Python: `3.12.3`; pytest: `7.4.4`; OpenSSL executable: `/usr/bin/openssl`.
- Test fixture generated disposable synthetic Ed25519 keys under `/root` and cleaned them through
  fixture teardown. No production key was read or created.
- No dependencies were downloaded or installed.

SHA-256 hashes from the accepted committed source tree:

| File | SHA-256 |
|---|---|
| `tests/vst/conftest.py` | `1DC787672061D0243A883FB5E44837633742A7D6DE68A013DE6D6C26BEE82EB7` |
| `tests/vst/s2_dispatch_instruction_fixtures.py` | `F71CDCEE6BB1960AB0F76C4EC500E370ED9472E1F34F8452E99BBDCA6C6C1ACB` |
| `tests/vst/test_s2_signed_dispatch_instruction.py` | `ECEF9E6EBEEA512BF14527B9E9D98A759AC52478C474D58CD944BDBCFCBA56F5` |
| `tests/vst/test_s2_store_backed_pubsub.py` | `0F49DB4CD7981D35FA899032FB86C302D02512EACF6EE66CBF2CC2B19FEC153A` |
| `tests/vst/test_s2_dispatch_owner_service.py` | `98CF17E281C346490001937372DEF4C68185D935CC708A94268AFB9217973387` |
| `tests/vst/test_s2_dispatch_owner_latch.py` | `0704BD6BD80D031951FD98356F082D052236F898C7477BF68688A825D849EED6` |

## Attempts and triage

The source-code changes were unchanged across the three attempts; the two failures were repaired in
test-only commits before the final run. No failure was classified as a flake, and no test was
quarantined or weakened.

| HEAD | Result | Failure classification and evidence |
|---|---|---|
| `65c29f7b70023c7611f86b4a6ea77d90c3231423` | Collection stopped: **0 tests executed**, 1 collection error, exit 1. | **Test defect.** `test_s2_owner_service_rejects_untrusted_systemd_activation_descriptor` parametrized `env` and unused `reason`, but declared only `(monkeypatch, env)`. Pytest reported `function uses no argument 'reason'`. Fixed by the test author in a later test-only commit. The failing test source SHA-256 was `05FF756C51D6B019F2A74B6139B0F0CDF9007A52653CBC47C73EE2A738DBC85B`. |
| `a1fa0b022eeafaf0973e58d3f8dd564cb2362453` | **100 passed, 5 failed**, exit 1, 4.86 seconds. | All five were test-source defects; the complete traceback for the legacy-event case was not retained because the tool truncated the original output. Details are listed below. The test author corrected these cases in a later test-only commit. |
| `cec0dbf3249b5734bdae52f644ac790e07d869f8` | **105 passed**, 0 failed, exit 0, 3.97 seconds. | Accepted focused run after the test-source repairs. |

The five failures at `a1fa0b0` were:

1. `test_malformed_or_expanded_envelope_is_refused_even_with_signature[noncanonical-time-canonical UTC]` — **test defect**. The test expected a message matching `canonical UTC`; the implementation raised `dispatch instruction expiry is not canonical`. The assertion text was corrected to match the contract failure.
2. `test_legacy_unsigned_store_event_fails_closed_during_history_replay` — **test defect**. The test called `Store.verify_event_chain()` and expected semantic dispatch-event validation. That method verifies the cryptographic chain and anchor; schema/replay validation occurs during Store startup/reconciliation. The full pytest traceback was not retained, so its exact final assertion text is `NOT_RETAINED`; the classification follows the test call at `tests/vst/test_s2_signed_dispatch_instruction.py` and the current `Store` validation path. The test author changed the test to exercise replay.
3. `test_s2_supervisor_service_requires_fixed_shared_trust_registry_path` — **test defect**. Its fixture omitted fields required by the current Supervisor config schema, so it failed at `Supervisor service config fields do not match its schema` before reaching the intended fixed-registry-path assertion. The fixture was completed.
4. `test_s2_owner_service_public_key_requires_root_owner_group_and_mode[key-not-regular]` — **test defect**. The negative fixture marked the path metadata as non-regular but its mocked `fstat` still returned a regular file, so the expected rejection was not exercised. The mock now carries the intended file type.
5. `test_s2_dispatch_owner_loader_refuses_existing_admission_latch` — **test defect**. The test tried to patch `service_module.os.lexists`; the implementation calls `os.path.lexists`. Pytest reported `AttributeError: <module 'os' (frozen)> has no attribute 'lexists'`. The test now patches the correct function.

For failure 2, the captured source confirms `_validate_dispatch_intent_event` rejects the legacy
event shape and Store startup/reconciliation invokes that semantic validation. Because the full
trace was not retained and the test was not rerun at `a1fa0b0`, this report does not claim an exact
failure message for that attempt. The corrected test passed as part of the `cec0dbf` run.

## Limits and next gate

The run validates synthetic source contracts only. `systemd-analyze verify`, unit activation,
root-owned `/etc` latch creation, service/socket lifecycle, production signer custody, trusted
production coordinator, live WSL E5 provenance, real dispatch, and all S2 restricted selectors were
not run. The admission-fence behavior still needs independent specialist review and focused
GPT-PM adjudication at the exact source head. S2 remains NOT APPROVED; S3 remains unstarted.
