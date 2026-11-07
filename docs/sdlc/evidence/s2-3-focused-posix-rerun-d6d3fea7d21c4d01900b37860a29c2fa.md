# S2-3 focused POSIX regression run

- Run ID: `d6d3fea7d21c4d01900b37860a29c2fa`
- Source Git HEAD: `c97836029a5d94ff84dee5cb15d1757efd5525c3`
- Source state: uncommitted working-tree overlay on that HEAD; the per-file hashes below bind
  the transferred inputs. This result is not a committed-head run.
- Environment: Ubuntu 24.04 WSL, Python 3.12.3, pytest 7.4.4.
- Command:
  `python -m pytest -q tests/vst/test_s2_wsl_bundle_verifiers.py tests/vst/test_s2_source_staging_plan.py tests/vst/test_s2_runtime_bundle.py tests/vst/test_s2_bootstrap_runtime.py tests/vst/test_s2_stage_only_install.py`
- Result: **54 passed, 0 failed, 0 skipped**, 2.01 seconds, exit code 0.
- Transfer root: `/run/vst-test-d6d3fea7d21c4d01900b37860a29c2fa` (cleaned after execution).
- Transfer manifest SHA-256: `8e1e71f961cac7ef2a8ec62f842cb462fb0000171e5d1c77fb0d2f71985f2243`.
- Transfer archive SHA-256: `ac0c99f217b7b1b47e7de94fab9e5e91df8d557620d95157a758bddf7137933b`.
- The runner verified all 45 transferred entries against per-file hashes before pytest: 43 repository
  files plus two empty package markers generated only in the temporary harness. After cleanup, the
  runner regenerated the canonical manifest read-only and confirmed the manifest digest was
  unchanged.
- No installer, stage-only operation, live runtime, system service, Store, key, E5, or dispatch
  operation was performed. This proves only the named fixture/source-contract tests.

## Transferred file hashes

| Path | SHA-256 | Provenance |
|---|---|---|
| `tests/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Harness-created empty marker |
| `tests/vst/__init__.py` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Harness-created empty marker |
| `tests/vst/conftest.py` | `1dc787672061d0243a883fb5e44837633742a7d6de68a013de6d6c26bee82eb7` | Repository file |
| `tests/vst/s2_dispatch_instruction_fixtures.py` | `f71cdcee6bb1960ab0f76c4ec500e370ed9472e1f34f8452e99bbdca6c6c1acb` | Repository file |
| `tests/vst/test_s2_bootstrap_runtime.py` | `a7674ce8a06b77e90287ad28261a95128f0cadef87f2be5b38a83bc85ea17b67` | Repository file |
| `tests/vst/test_s2_runtime_bundle.py` | `ac96ffcc8183ad838ba57b37f9439fe13a09215b3aead7a3131780f14ad9e893` | Repository file |
| `tests/vst/test_s2_source_staging_plan.py` | `27feaa3de30c27641d6591be34a2d4a3f69bb151c12b476fab0dd8053d57816b` | Repository file |
| `tests/vst/test_s2_stage_only_install.py` | `117a6fee0cd108ae623ea6b6baf2ece845298f44e9646950560ee4155db73883` | Repository file |
| `tests/vst/test_s2_wsl_bundle_verifiers.py` | `8c7306f3ea0f9e0193a4789b1565445ae45524af516168f34c81b2eb74860a3b` | Repository file |
| `tools/qa/install_wsl_runner_runtime.sh` | `b34f7a71ade53f3b1ca825e862fc0dd9d130d61bbdd8003a3099a235e410f963` | Repository file |
| `tools/qa/install_wsl_runtime.ps1` | `dc263b85f2d4991dc7e75fb262db5166609964ffcbd7c3d760536842a792e2db` | Repository file |
| `tools/qa/install_wsl_worker_helper.sh` | `def7ec22970b49f43676b4a32a25d24c0cdf2dcd719663e6b91a8a0cbfb3b125` | Repository file |
| `tools/qa/prepare_wsl_runtime_plan.py` | `e8bbf25d9d7a71ed4ff4ce5048fdbf65ba69f7351182124a5aef4f9accd21a57` | Repository file |
| `tools/qa/verify_wsl_runtime_stage.py` | `107921d7213184ae94a276c1e6ea8dd6811b3954f1983460b339598c77a5d4c7` | Repository file |
| `tools/qa/verify_wsl_source_bundle.py` | `79eb0b1748d97d7c06eae84f49f0625edaec26a29205aaca252566589a83ca4b` | Repository file |
| `tools/vst/__init__.py` | `01c1c19343f8da7f605775ecbf7909d6e8aad7b3bd17a08065f1d712f8a6db9f` | Repository file |
| `tools/vst/assignment_basis.py` | `c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de` | Repository file |
| `tools/vst/bootstrap_runtime.py` | `961a7707f9b05cc721d81cb94fc183f1bed24aa20f3dc7325f4383569993d208` | Repository file |
| `tools/vst/contracts.py` | `bf01d990a94cd71887f8d9f81019333f3bf43d5950a655de3646e9bb3d585ea4` | Repository file |
| `tools/vst/diffgate.py` | `3be2f59327b3b95701e26e7d441b1e47374467daab1f9e68d158f2f5cd8bb8b8` | Repository file |
| `tools/vst/dispatch_instruction.py` | `b2d0194c69b678cc108f78b6c4b1cf6fd20a1fdcbdb4869e5b6548c4883a1e05` | Repository file |
| `tools/vst/dispatch_issuance.py` | `e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a` | Repository file |
| `tools/vst/dispatch_owner_client.py` | `d825f1cdc320a5babc419e89f9f181961da8426c3d3a2a915257091d9d1641b1` | Repository file |
| `tools/vst/dispatch_owner_latch.py` | `390c5314cc150462b47ecb3dc3c363fc8d3d6a59e99e35dd6f2e613fb0cfb419` | Repository file |
| `tools/vst/dispatch_owner_service.py` | `483241d6e18d25a073a75fde8c3ebe65925bcb17bd5536b5b7ffe7056484bd8e` | Repository file |
| `tools/vst/dispatch_owner_transport.py` | `134ece4fd7e20b947ee3e91ea08909b359e03542bc0243c77e753b54591d4de4` | Repository file |
| `tools/vst/dispatcher_service.py` | `0f23727307c14aed691ab2d0ae338eef472453f5eabd4f85de70e916692c2fc3` | Repository file |
| `tools/vst/execution_grant.py` | `f99810d04664f6d95e336be2138001c2e255e6ae9e8eb531b806d745fc4c7c43` | Repository file |
| `tools/vst/gate.py` | `562474f756cd897b9239fc1573870e15924c547547412be2ab8813d23a71600f` | Repository file |
| `tools/vst/lifecycle.py` | `db81de532229cca96855be286ae5565acff31e0910be09afbc39885132e47a34` | Repository file |
| `tools/vst/machine_authorization.py` | `8c031f5547874b4811264e400d0b28166f1ca7b3d962ee0d04e75ba9d140e8ff` | Repository file |
| `tools/vst/machine_observations.py` | `9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11` | Repository file |
| `tools/vst/preflight.py` | `08393eb2f85691b1bdc18e06256cefc7dc6a0aa1f50aa2ba23086b8662e7b049` | Repository file |
| `tools/vst/root_dispatch_issuer.py` | `049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9` | Repository file |
| `tools/vst/runner.py` | `02c60162ed1bbda61e1341d055aa893ce1cf52c3bbecbc545e7e67eb902a07ee` | Repository file |
| `tools/vst/runner_fence.py` | `32c682eddb78747b91e319cee365e2e12c54edda3096316992e5d0fe025d67ab` | Repository file |
| `tools/vst/runner_service.py` | `8e1e2196914dc14a45957f94a57a0ac460f9809184fbe2ceed8df1329c4420d9` | Repository file |
| `tools/vst/runtime_bundle.py` | `45a6241637a638bc8365afe99f29072d258b882f58e8f171ce243cecfc2956d7` | Repository file |
| `tools/vst/sandbox.py` | `b5946426d9749a00c76bfc666a0a6f2edb30e74e9985bf0b796caba08fe3b803` | Repository file |
| `tools/vst/signer.py` | `948b2db9562a6886640f1baacece08a99fb76fea4afa43b4ac3ad4246a2f2070` | Repository file |
| `tools/vst/signing.py` | `41584757abb70db96d45859ba107e588a6796eeae14223a0159901a17d48630f` | Repository file |
| `tools/vst/slice.py` | `8e81e0ecbbd301fabefcbda3299d4f8b1415aa86c9b0a90795428dafcff3eb2f` | Repository file |
| `tools/vst/store.py` | `d0a5516531b0941654a5b262e24d2ee5d9513de888f0c8f9b2b1176ac09a7a12` | Repository file |
| `tools/vst/supervisor.py` | `62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71` | Repository file |
| `tools/vst/supervisor_service.py` | `14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2` | Repository file |
