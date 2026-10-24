# 0037 S2 parser catalog validation fix

## What

Rejects v2 mandatory command parser id/version/SHA-256 triples that do not exist in the trusted built-in parser catalog.

## Why

The first focused S2 functional run exposed three negative cases where `validate_task_manifest_v2` accepted an unknown parser id, untrusted version, or non-catalog digest. A manifest must not select an implementation merely by supplying arbitrary identity strings.

## Affected contract

- `tools/vst/contracts.py`: v2 manifest validation now performs exact tuple membership in `TRUSTED_PARSER_CATALOG`; v1 validation is unchanged.

## Verification state

The defect was reported by the functional-test agent on code HEAD `b2b168e71000323443882988cd24af2cdbabf4df`; its command was `C:\Python314\python.exe -m pytest -q tests/vst/test_s2_contract_gate.py tests/vst/test_s2_diffgate.py`, with 30 passing and 3 failing cases. The test tree was dirty with agent-authored new tests. The implementation agent used `gpt-6-luna` at low effort and ran no checks. The correction requires a test-agent rerun and is not verified on this commit yet.
