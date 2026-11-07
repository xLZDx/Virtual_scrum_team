# S2-3 M-S2-3-03 existing-runtime regression

- Run ID: `3ec0a90d53d142829ce7e5d05a184602`.
- Tested commit: `043980f64b4cc2ac7c42719251f2fb8258660377`.
- Inputs were fetched from `git show HEAD:<path>` only. Pre- and post-run SHA-256 checks matched
  each Git-show input.
- Environment: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4.
- Exact command: `python -m pytest -q tests/vst/test_s2_stage_only_install.py -k existing_runtime`.
- Result: **4 passed, 8 deselected, 0 skipped**, 0.04 seconds, exit code 0.
- Manifest SHA-256: `96f3b9c736ecd63536a811514cb80ad0f43be8199c0dc4eae3b40c4910eea4a1`.
- Transfer archive SHA-256: `478beda7ad1ecc5123fa7df67f549c70767f289da8dba2f716a56196ea3d9433`.
- Transfer root `/run/vst-test-3ec0a90d53d142829ce7e5d05a184602` was path/UID-checked and cleaned.
- The selection verifies shell argument order and tuple unpack, accepts an existing runtime with a
  matching schema-3 provenance marker, and refuses changed `inventory_sha256` or `head` values.
- The transfer contained 11 manifest entries: 10 committed repository inputs and one empty
  harness-created `tests/__init__.py` package marker. `tests/vst/__init__.py` was also verified as
  the empty committed Git blob.
- No installer, live runtime, system service, Store, key, E5, dispatch, or production operation
  was performed.

## Committed input SHA-256 values

| Path | SHA-256 | Git provenance |
|---|---|---|
| `tests/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Harness-created empty marker |
| `tests/vst/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Empty committed blob `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` |
| `tests/vst/conftest.py` | `1dc787672061d0243a883fb5e44837633742a7d6de68a013de6d6c26bee82eb7` | Blob `5a0830a7a1062027bc5c47b9c3601cd98fe19fa6` |
| `tests/vst/s2_dispatch_instruction_fixtures.py` | `f71cdcee6bb1960ab0f76c4ec500e370ed9472e1f34f8452e99bbdca6c6c1acb` | Blob `3c1309e9a832950810c3e78701337dd35dee7e94` |
| `tests/vst/test_s2_stage_only_install.py` | `8a07fa1b04881bfbc16586766979f96dbe74b30e18d3504e46637295fda0f9ec` | Blob `77e398f37f097b8d2db61cf9dfe549058b3f805d` |
| `tools/qa/install_wsl_runner_runtime.sh` | `1fde9f863b9b10ca4bcde318e3652fe6196787b917b32caa9c8a8b8eba504267` | Blob `ba60fd5c354dd61007a9caf4646c9129a05ab567` |
| `tools/qa/install_wsl_runtime.ps1` | `a3fb4973443c65b3e989acdf7efb3e3860cb95ca1eed5b8408ca3f035fbafeec` | Blob `3951a0ef7f17ed5d3e5024477da408225a229f8b` |
| `tools/vst/__init__.py` | `01c1c19343f8da7f605775ecbf7909d6e8aad7b3bd17a08065f1d712f8a6db9f` | Blob `ce335cb6357868a491c2c4f74cbf863a8dd1236f` |
| `tools/vst/contracts.py` | `bf01d990a94cd71887f8d9f81019333f3bf43d5950a655de3646e9bb3d585ea4` | Blob `c94411a7f5f88445a746a67d241c5cd17eee80ee` |
| `tools/vst/dispatch_instruction.py` | `b2d0194c69b678cc108f78b6c4b1cf6fd20a1fdcbdb4869e5b6548c4883a1e05` | Blob `43a8d2e49e6109bcc1b692c51b9840a8d3b4a389` |
| `tools/vst/execution_grant.py` | `f99810d04664f6d95e336be2138001c2e255e6ae9e8eb531b806d745fc4c7c43` | Blob `38147ba8fc322c3bda179b5483d81f8374a609b5` |
