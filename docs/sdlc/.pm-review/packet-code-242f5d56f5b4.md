# PM-GPT code review request
Project root: D:\Repo\Virtual_scrum_team
Reviewed range: origin/main...242f5d56f5b48603141d148d71d724bec7fb2b37
Exact HEAD under review: 242f5d56f5b48603141d148d71d724bec7fb2b37
Reply format: first line `VERDICT: APPROVE|MINOR|MAJOR|BLOCKER`, then one finding per line as `SEVERITY | basis | claim | evidence | required change`.
Approve only if the exact head is safe to push. Verify claims against the diff.

## Evidence file: verify-evidence.json (sha256 ceac716c1d613e2ed6c52d503bac8e51a75bcebb10c19769fe5d3680a502e908)
{
  "tested_head": "0da595e6574856ed0c85a181941e822031b80787",
  "runs": [
    {
      "command": "& 'C:\\Python314\\python.exe' -m pytest -q tests/vst/test_s2_assignment_bootstrap.py tests/vst/test_s2_dispatch_issuance_contract.py tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_machine_source_contracts.py",
      "total": 68,
      "passed": 62,
      "failed": 0,
      "errors": 0,
      "skipped": 6,
      "log": "Windows, exit code 0; pytest output: 62 passed, 6 skipped, 1 warning in 1.16s. The six skips are POSIX-only root-owned OpenSSL/machine authorization fixtures; they are NOT_RUN on Windows, not passes.",
      "tested_head": "524a2d69aa4bc709b7777b131edd79c8fe24250e"
    },
    {
      "tested_head": "62bb632909205fe21a6b61b4ac5b56dbc8176285",
      "command": "& 'C:\\Python314\\python.exe' -m pytest -q tests/vst/test_s2_assignment_bootstrap.py tests/vst/test_s2_dispatch_issuance_contract.py tests/vst/test_s2_assignment_basis.py tests/vst/test_s2_machine_source_contracts.py",
      "total": 68,
      "passed": 62,
      "failed": 0,
      "errors": 0,
      "skipped": 6,
      "log": "Windows, exit code 0; pytest output: 62 passed, 6 skipped, 1 warning in 1.09s. Six POSIX-only root-owned OpenSSL/machine authorization cases skipped; they are NOT_RUN on Windows, not passes."
    },
    {
      "tested_head": "56cd816b1b03b39c3f4b4a70ecf00d96ef95d321",
      "command": "wsl.exe -d Ubuntu-24.04 --user root -- sh -lc 'set -eu; if ! mountpoint -q /mnt/d; then mkdir -p /mnt/d; mount -t drvfs D: /mnt/d; fi; grep -F \"D: /mnt/d \" /proc/mounts; cd /mnt/d/Repo/Virtual_scrum_team; printf \"HEAD=\"; git rev-parse HEAD; git rev-parse HEAD | grep -Fx 56cd816b1b03b39c3f4b4a70ecf00d96ef95d321; python3 --version; python3 -m pytest --version; sha256sum tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py; /usr/bin/time -f \"DURATION_SEC=%e\" python3 -m pytest -q tests/vst/test_s2_signed_dispatch_instruction.py tests/vst/test_s2_store_backed_pubsub.py tests/vst/test_s2_dispatch_owner_service.py tests/vst/test_s2_dispatch_owner_latch.py'",
      "total": 130,
      "passed": 130,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "log": "Ubuntu 24.04 WSL; Python 3.12.3; pytest 7.4.4; exit 0; 17.58s pytest duration (19.38s wall). The corrected test file SHA-256 matches committed blob in dcb5d63; see docs/sdlc/evidence/s2-cross-generation-outcome-recovery-rerun-56cd816-worktree-20261029.md.",
      "test_blobs": {
        "tests/vst/test_s2_signed_dispatch_instruction.py": "13b436675383e98449520c15c640a87fcb84370ade534475b5ad2c63ece8b76f",
        "tests/vst/test_s2_store_backed_pubsub.py": "435262304ca08fef9ed371748fa8184086ada46a8f016b4751a997db37f228e7",
        "tests/vst/test_s2_dispatch_owner_service.py": "fc7e194cb45700446438c776281be789f8ad0551edc5c506887af35af020df71",
        "tests/vst/test_s2_dispatch_owner_latch.py": "dd747aa5c42cf4745197c77b0138c2e71bdd9690ed3d779d00969142382d35f1"
      }
    },
    {
      "tested_head": "00312f0b845f5f914254eab33be2fa8224f53159",
      "command": "node --test tests/vst/test_af_attachment_review.mjs",
      "total": 35,
      "passed": 35,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "log": "Windows; Node.js v24.13.1; exit 0; 178.55s. AFAT-01–12 functional cases. Test SHA-256 1c42e35d6ae8b790e5c722f44217620b53f018b82809f7d6fea99f5450243c5d; source SHA-256 9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e.",
      "test_blobs": {
        "tests/vst/test_af_attachment_review.mjs": "1c42e35d6ae8b790e5c722f44217620b53f018b82809f7d6fea99f5450243c5d"
      },
      "source_blobs": {
        "tools/af_attachment_review.mjs": "9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e"
      },
      "evidence": "Execution reported by actual functional-test-reviewer agent; no files edited."
    },
    {
      "tested_head": "00312f0b845f5f914254eab33be2fa8224f53159",
      "command": "node --test tests/af/test_s2_attachment_adapter_e2e.mjs",
      "total": 2,
      "passed": 2,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "log": "Windows; Node.js v24.13.1; exit 0; approximately 19.6s. Authenticated loopback transport, durable receipt handling, and dump-only prompt generation. Test SHA-256 9cc0b44f6fca5b4a0ff7b9f843866b24f0f9e8178fee4575f405049f9c9ddd07; source SHA-256 9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e.",
      "test_blobs": {
        "tests/af/test_s2_attachment_adapter_e2e.mjs": "9cc0b44f6fca5b4a0ff7b9f843866b24f0f9e8178fee4575f405049f9c9ddd07"
      },
      "source_blobs": {
        "tools/af_attachment_review.mjs": "9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e"
      },
      "evidence": "Execution reported by actual e2e-runner agent; no files edited."
    },
    {
      "tested_head": "2befed5515455c4dbf022cad68e839a8a2ce799c",
      "command": "wsl.exe -d Ubuntu-24.04 --user root -- sh -lc <recorded command in docs/sdlc/evidence/s2-exacthead-branch-refresh-2befed5-20261029.md>",
      "total": 130,
      "passed": 130,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "log": "Ubuntu 24.04 WSL; Python 3.12.3; pytest 7.4.4; exit 0; pytest 5.95s, wall 6.67s. Exact command, SHA-256 values, and output are recorded in the linked evidence file.",
      "evidence": "docs/sdlc/evidence/s2-exacthead-branch-refresh-2befed5-20261029.md"
    },
    {
      "tested_head": "2befed5515455c4dbf022cad68e839a8a2ce799c",
      "command": "node --test tests/vst/test_af_attachment_review.mjs",
      "total": 35,
      "passed": 35,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "log": "Windows; Node.js 24.13.1; exit 0; duration 127.395s. Test SHA-256 5f11eea71b36d96336f6301452ad559ece56c90889a6bc2cf9c137304e93b4a7; test Git blob 6bacf543ec6971c5f1d421648140bdbf793fad9f. Exact-head actual functional-test-reviewer run.",
      "evidence": "docs/sdlc/evidence/s2-exacthead-branch-refresh-2befed5-20261029.md"
    },
    {
      "tested_head": "2befed5515455c4dbf022cad68e839a8a2ce799c",
      "command": "node --test tests/af/test_s2_attachment_adapter_e2e.mjs",
      "total": 2,
      "passed": 2,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "log": "Windows PowerShell; Node version not captured; exit 0; 13.643s Node duration / 13.783s wall. Test SHA-256 9cc0b44f6fca5b4a0ff7b9f843866b24f0f9e8178fee4575f405049f9c9ddd07. Fixture output is not a real GPT-PM review.",
      "evidence": "docs/sdlc/evidence/s2-exacthead-branch-refresh-2befed5-20261029.md"
    },
    {
      "tested_head": "206a746fdae942fd6ab6f36c882bb0c3d18ec539",
      "command": "python tests/af/test_s2_review_source_fidelity.py -v",
      "total": 5,
      "passed": 5,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "log": "Windows NT 10.0.26300.0; Python 3.14.3; Git 2.53.0.windows.1; PowerShell; exit 0; duration 30.164s. Attachment size 5766789; SHA-256 833efc361a34266767e331ebf6a2724cecba3e03512e4443ddf6cd661d93311b. Test SHA-256 f3b44778a9a89bb298c9f68b5f64bbbf517cd4e022f12691686129b1e998b220; verifier SHA-256 91f66464a3adecc01ef554731fe71ea6c836f5f68fbd9caf10be9b2596d8a962. Exact committed HEAD.",
      "evidence": "docs/sdlc/evidence/s2-review-redaction-independent-review-2befed5-20261029.md"
    },
    {
      "tested_head": "0da595e6574856ed0c85a181941e822031b80787",
      "command": "node --test tests/vst/test_af_attachment_review.mjs",
      "total": 38,
      "passed": 38,
      "failed": 0,
      "errors": 0,
      "skipped": 0,
      "log": "Actual functional-test-reviewer run; Windows NT 10.0.26300.0; PowerShell; Node v24.13.1; Git 2.53.0.windows.1; exit 0; duration 149843.3314 ms. Tester confirmed test and adapter Git blobs matched exact HEAD before and after; no tracked files changed. Test SHA-256 5FA69F2F34722AD96FEFAF2A2C8A98C9B18D29298F5E726FDDC0BEFBC30FAEA1; adapter SHA-256 1933B1775C87E21088C82BC435B36C056A1795E306334716B26724E07DD08631.",
      "test_blobs": {
        "tests/vst/test_af_attachment_review.mjs": "6349f338312cdc144c8f62e0a55d5095b00ba198"
      },
      "source_blobs": {
        "tools/af_attachment_review.mjs": "75c61d538d5e00f3ae926c8f2023d34f1e54c852"
      },
      "evidence": "docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md"
    }
  ],
  "not_run": [
    {
      "item": "Current E5 and Windows host policy observation at tested_head",
      "reason": "No host collection or signed run-bound E5 observation was performed in this test run. The latest sanitized public observation at source d3f326f reports the fixed PowerShell 7 context cannot resolve Get-NetFirewallProfile and effective-rule/endpoint/path/cross-source normalization is incomplete; state remains UNKNOWN, not zero counts or PASS."
    },
    {
      "item": "Real installed runtime, Store freshness/migration, production root keys/configuration, signing, or service activation",
      "reason": "No install, Store migration/freshness, production root key/configuration, signing, or service activation occurred. Current source plan is UNSIGNED_REVIEW_CANDIDATE with activation NOT_AUTHORIZED_BY_THIS_PLAN, Store UNKNOWN, and target inventory/compiler provenance NOT_VERIFIED. The separate read-only Ubuntu metadata artifact is bound to source 524a2d69 and was not recollected at 62bb632; it reports /var/lib/vst-runner absent, ten fixed config paths absent, three of six unit files absent, and all six queried units inactive. Metadata is not runtime approval."
    },
    {
      "item": "Real process/worker kill, crash/restart/recovery, mutation campaign, E8 bake-off, and restricted S4/policy selectors",
      "reason": "Excluded actual worker/process kill, crash, recovery, mutation, E8 and S4/policy acceptance scenarios remain prohibited and NOT_RUN. Permitted in-process callback/SQLite reopen and pre-spawn injected-timeout fixtures are explicitly separate. Bounded metadata collector child handling is not evidence for excluded worker cleanup/crash acceptance."
    },
    {
      "item": "Fresh GPT-PM exact-head decision for the current S2-1 code attachment",
      "reason": "Pending. The prior correlated PM review request 4fb1b534-e56e-46da-8a0c-1a0366d9597e reviewed code HEAD 206a746fdae942fd6ab6f36c882bb0c3d18ec539 and returned MAJOR/HOLD; it is stale for this code head. The current packet records the committed wrapper fix, 38/38 exact-head functional evidence, and expanded independent static review. A fresh GPT-PM verdict must be obtained through AF/PM Bridge; no approval is asserted here."
    }
  ],
  "findings": {
    "open_blocker": 0,
    "open_major": 0
  },
  "reviewers": [
    {
      "role": "database-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "NO_CODE_BLOCKER_MAJOR"
    },
    {
      "role": "security-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "NO_CODE_BLOCKER_MAJOR"
    },
    {
      "role": "code-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "NO_CODE_BLOCKER_MAJOR"
    },
    {
      "role": "security-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "41/41 mapped source positions statically assessed PASS; no confirmed defect; runtime/production acceptance remains unproven"
    },
    {
      "role": "code-reviewer",
      "model": "gpt-6-luna",
      "effort": "low",
      "verdict": "No material issue in exact-source verifier after removal of per-line hashes; source identity only, not code approval"
    },
    {
      "role": "functional-test-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "5/5 focused verifier tests passed at exact HEAD 206a746fdae942fd6ab6f36c882bb0c3d18ec539"
    },
    {
      "role": "functional-test-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "38/38 passed at exact code HEAD 0da595e6574856ed0c85a181941e822031b80787; test and adapter blobs matched HEAD before/after."
    },
    {
      "role": "code-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "Full changed-scope static review and wrapper follow-up found no additional confirmed BLOCKER/MAJOR; this is not GPT-PM approval or runtime evidence."
    },
    {
      "role": "security-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "No confirmed reachable BLOCKER/MAJOR in assigned S2 source/trust-boundary scope; static only, runtime identity/E5 unproven."
    },
    {
      "role": "database-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "No confirmed database/concurrency BLOCKER/MAJOR in assigned Store/migration source scope; no live-Store or migration execution."
    },
    {
      "role": "reliability-reviewer",
      "model": "gpt-6-luna",
      "effort": "medium",
      "verdict": "No confirmed reliability BLOCKER/MAJOR in assigned Runner/recovery/service scope; static review, platform-bound selectors NOT_RUN."
    }
  ],
  "runtime_source_plan": {
    "path": "docs/sdlc/evidence/s2-runtime-source-plan-62bb632-20261029.json",
    "sha256": "9ebe75e52b7f7af7e50bce560818d1f3466a9241dc64e052770355187405c75",
    "payload": {
      "activation": "NOT_AUTHORIZED_BY_THIS_PLAN",
      "archive_files": {
        "docs/SANDBOX_SPEC.md": "7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997",
        "tools/qa/install_wsl_runner_runtime.sh": "b9d3e116f2c466e40307ea6701115773c9fffcc1591d10df445d07af4e8be3fa",
        "tools/qa/install_wsl_worker_helper.sh": "9e1d70c6df5a3ba195ba67581d4cf0485f1d0207ca0ddebecd7e9025883cead1",
        "tools/qa/worker_exec.c": "ea76231fe4b3ae99902be7be43d3a7a970f9ea28c7b27258097f0ceb9d20d951",
        "tools/vst/__init__.py": "01c1c19343f8da7f605775ecbf7909d6e8aad7b3bd17a08065f1d712f8a6db9f",
        "tools/vst/assignment_basis.py": "c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de",
        "tools/vst/bootstrap_runtime.py": "4b5823643c77d2f7ce64cd499a61ebea4bb0a222f2a261e822edb386a2c44bfc",
        "tools/vst/contracts.py": "bf01d990a94cd71887f8d9f81019333f3bf43d5950a655de3646e9bb3d585ea4",
        "tools/vst/diffgate.py": "3be2f59327b3b95701e26e7d441b1e47374467daab1f9e68d158f2f5cd8bb8b8",
        "tools/vst/dispatch_instruction.py": "b2d0194c69b678cc108f78b6c4b1cf6fd20a1fdcbdb4869e5b6548c4883a1e05",
        "tools/vst/dispatch_issuance.py": "e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a",
        "tools/vst/dispatch_owner_client.py": "d825f1cdc320a5babc419e89f9f181961da8426c3d3a2a915257091d9d1641b1",
        "tools/vst/dispatch_owner_latch.py": "390c5314cc150462b47ecb3dc3c363fc8d3d6a59e99e35dd6f2e613fb0cfb419",
        "tools/vst/dispatch_owner_service.py": "483241d6e18d25a073a75fde8c3ebe65925bcb17bd5536b5b7ffe7056484bd8e",
        "tools/vst/dispatch_owner_transport.py": "134ece4fd7e20b947ee3e91ea08909b359e03542bc0243c77e753b54591d4de4",
        "tools/vst/dispatcher_service.py": "0f23727307c14aed691ab2d0ae338eef472453f5eabd4f85de70e916692c2fc3",
        "tools/vst/execution_grant.py": "f99810d04664f6d95e336be2138001c2e255e6ae9e8eb531b806d745fc4c7c43",
        "tools/vst/gate.py": "562474f756cd897b9239fc1573870e15924c547547412be2ab8813d23a71600f",
        "tools/vst/lifecycle.py": "db81de532229cca96855be286ae5565acff31e0910be09afbc39885132e47a34",
        "tools/vst/machine_authorization.py": "8c031f5547874b4811264e400d0b28166f1ca7b3d962ee0d04e75ba9d140e8ff",
        "tools/vst/machine_observations.py": "9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11",
        "tools/vst/preflight.py": "08393eb2f85691b1bdc18e06256cefc7dc6a0aa1f50aa2ba23086b8662e7b049",
        "tools/vst/root_dispatch_issuer.py": "049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9",
        "tools/vst/runner.py": "02c60162ed1bbda61e1341d055aa893ce1cf52c3bbecbc545e7e67eb902a07ee",
        "tools/vst/runner_fence.py": "32c682eddb78747b91e319cee365e2e12c54edda3096316992e5d0fe025d67ab",
        "tools/vst/runner_service.py": "8e1e2196914dc14a45957f94a57a0ac460f9809184fbe2ceed8df1329c4420d9",
        "tools/vst/runtime_bundle.py": "ae95afdd47f66cb3cd7192e3d4d3d892f5fc23e2c269b435561ae913272de293",
        "tools/vst/sandbox.py": "b5946426d9749a00c76bfc666a0a6f2edb30e74e9985bf0b796caba08fe3b803",
        "tools/vst/schemas/README.md": "be51b507d0406efd805ddd4a5518450c0ecf2d29135a39b1a44b2ab5f9bba3d0",
        "tools/vst/signer.py": "948b2db9562a6886640f1baacece08a99fb76fea4afa43b4ac3ad4246a2f2070",
        "tools/vst/signing.py": "41584757abb70db96d45859ba107e588a6796eeae14223a0159901a17d48630f",
        "tools/vst/slice.py": "8e81e0ecbbd301fabefcbda3299d4f8b1415aa86c9b0a90795428dafcff3eb2f",
        "tools/vst/store.py": "d0a5516531b0941654a5b262e24d2ee5d9513de888f0c8f9b2b1176ac09a7a12",
        "tools/vst/supervisor.py": "62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71",
        "tools/vst/supervisor_service.py": "14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2",
        "tools/vst/systemd/README.md": "bff939afec2dd5e4f4b46d18b2d4fe9ac9bcd1dc6525f97934b10174a235cb63",
        "tools/vst/systemd/vst-dispatch-owner.service": "606aff7a866d0182d891e42df66e26160540372a8120480b13fef10e45fe9cfb",
        "tools/vst/systemd/vst-dispatch-owner.socket": "a7855aefc05a04df1b51b798e2cf82c060716d638391573ac0b232de24724b6e",
        "tools/vst/systemd/vst-dispatcher.service": "ed12e2f7d5ee2a7177139682a91d5ba714679497e7c0f50c565b2141302a6c16",
        "tools/vst/systemd/vst-runner.service": "4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be",
        "tools/vst/systemd/vst-signer.service": "33ed12ee7174c9136493cfba3cd4176a1c48ac9515afb79d5eb0740ff6d3502d",
        "tools/vst/systemd/vst-supervisor.service": "aa64d16b7801f32146808706acffaa0ca9086653e5e3e9f5f5dac1bc07ab822c"
      },
      "archive_sha256": "c9ff878678a4c7cb8d76b103f66d7f00cbb69865ea7de07f4a16425e14d7f5b7",
      "helper": {
        "binary_sha256": null,
        "build_recipe_sha256": "9e1d70c6df5a3ba195ba67581d4cf0485f1d0207ca0ddebecd7e9025883cead1",
        "compiler_path": "/usr/bin/cc",
        "compiler_provenance": "NOT_VERIFIED",
        "gid": 988,
        "mode": "4750",
        "path": "/usr/local/libexec/vst-s4-worker-exec-62bb632909205fe21a6b61b4ac5b56dbc8176285",
        "source_sha256": "ea76231fe4b3ae99902be7be43d3a7a970f9ea28c7b27258097f0ceb9d20d951",
        "uid": 0
      },
      "permitted_operation": "stage-only-after-source-tests-and-exact-plan-review",
      "runtime_path": "/opt/vst-runtime-62bb632909205fe21a6b61b4ac5b56dbc8176285",
      "sandbox_spec_sha256": "7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997",
      "schema": "VST_S2_RUNTIME_SOURCE_PLAN_V1",
      "selection": "separate-post-staging-manifest-review-required",
      "source_head": "62bb632909205fe21a6b61b4ac5b56dbc8176285",
      "status": "UNSIGNED_REVIEW_CANDIDATE",
      "store_disposition": "UNKNOWN",
      "target_inventory": "NOT_VERIFIED",
      "unit_sha256": {
        "vst-dispatch-owner.service": "606aff7a866d0182d891e42df66e26160540372a8120480b13fef10e45fe9cfb",
        "vst-dispatch-owner.socket": "a7855aefc05a04df1b51b798e2cf82c060716d638391573ac0b232de24724b6e",
        "vst-dispatcher.service": "ed12e2f7d5ee2a7177139682a91d5ba714679497e7c0f50c565b2141302a6c16",
        "vst-runner.service": "4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be",
        "vst-signer.service": "33ed12ee7174c9136493cfba3cd4176a1c48ac9515afb79d5eb0740ff6d3502d",
        "vst-supervisor.service": "aa64d16b7801f32146808706acffaa0ca9086653e5e3e9f5f5dac1bc07ab822c"
      },
      "unresolved": [
        "current target/identity collision inventory",
        "compiler provenance",
        "source/test approval and exact staging-plan review"
      ]
    }
  },
  "runtime_metadata": {
    "path": "docs/sdlc/evidence/s2-runtime-metadata-524a2d6-20261029.json",
    "sha256": "9c69ec3ec170df20a3b119865eddd70f707ee465bb86d76f7ec5eff1b09f9094",
    "schema": "S2_RUNTIME_METADATA_READONLY_V1",
    "source_head": "524a2d69aa4bc709b7777b131edd79c8fe24250e",
    "result_summary": "Ubuntu-24.04 read-only metadata: compiler cc present/version command OK; runtime selector and target present; /var/lib/vst-runner absent; ten fixed configuration paths absent; three of six systemd unit files present and all six queried units inactive; no contents read, no staging or permission changes.",
    "payload": {
      "collected_at_utc": "2026-10-29T13:35:46Z",
      "compiler": {
        "gid": 0,
        "mode": "0777",
        "path": "/usr/bin/cc",
        "resolved_target": {
          "gid": 0,
          "mode": "0755",
          "path": "/usr/bin/x86_64-linux-gnu-gcc-13",
          "size": 1023032,
          "state": "PRESENT",
          "type": "regular-file",
          "uid": 0
        },
        "resolved_target_sha256": "1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26",
        "size": 20,
        "state": "PRESENT",
        "symlink_target": "/etc/alternatives/cc",
        "type": "symlink",
        "uid": 0,
        "version_command": {
          "exit_code": 0,
          "first_line": "cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0",
          "status": "OK"
        }
      },
      "distribution": "Ubuntu-24.04",
      "fixed_runner_config_paths": [
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/runner-service.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/supervisor-service.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/signer-service.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/dispatcher-service.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/dispatch-owner-service.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/fence.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/assignment-delegation-policy.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/dispatch-instruction-trust.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/machine-delegation-trust.json",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/vst-runner/dispatch-owner-admission-blocked.json",
          "state": "ABSENT"
        }
      ],
      "fixed_systemd_unit_files": [
        {
          "gid": 0,
          "mode": "0644",
          "path": "/etc/systemd/system/vst-supervisor.service",
          "sha256": "aa64d16b7801f32146808706acffaa0ca9086653e5e3e9f5f5dac1bc07ab822c",
          "size": 886,
          "state": "PRESENT",
          "type": "regular-file",
          "uid": 0
        },
        {
          "gid": 0,
          "mode": "0644",
          "path": "/etc/systemd/system/vst-signer.service",
          "sha256": "33ed12ee7174c9136493cfba3cd4176a1c48ac9515afb79d5eb0740ff6d3502d",
          "size": 1020,
          "state": "PRESENT",
          "type": "regular-file",
          "uid": 0
        },
        {
          "gid": 0,
          "mode": "0644",
          "path": "/etc/systemd/system/vst-runner.service",
          "sha256": "4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be",
          "size": 1605,
          "state": "PRESENT",
          "type": "regular-file",
          "uid": 0
        },
        {
          "error": "ENOENT",
          "path": "/etc/systemd/system/vst-dispatcher.service",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/systemd/system/vst-dispatch-owner.service",
          "state": "ABSENT"
        },
        {
          "error": "ENOENT",
          "path": "/etc/systemd/system/vst-dispatch-owner.socket",
          "state": "ABSENT"
        }
      ],
      "limitations": [
        "metadata only",
        "configuration contents not read",
        "unit active states are observations, not runtime approval",
        "runner data directory lstat only; Store presence or freshness UNKNOWN",
        "no staging or permission change authorized"
      ],
      "runner_data_directory": {
        "error": "ENOENT",
        "path": "/var/lib/vst-runner",
        "state": "ABSENT"
      },
      "runtime_selector": {
        "link": {
          "gid": 0,
          "mode": "0777",
          "path": "/opt/vst-runtime",
          "size": 57,
          "state": "PRESENT",
          "symlink_target": "/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976",
          "type": "symlink",
          "uid": 0
        },
        "target_lstat": {
          "gid": 0,
          "mode": "0755",
          "path": "/opt/vst-runtime-d5001797cb94113efd9a8dc26e4a15f2dc130976",
          "size": 4096,
          "state": "PRESENT",
          "type": "directory",
          "uid": 0
        }
      },
      "schema": "S2_RUNTIME_METADATA_READONLY_V1",
      "source_head": "524a2d69aa4bc709b7777b131edd79c8fe24250e",
      "systemd_is_active": {
        "exit_code": 3,
        "status": "OK",
        "units": [
          {
            "active_state": "inactive",
            "unit": "vst-supervisor.service"
          },
          {
            "active_state": "inactive",
            "unit": "vst-signer.service"
          },
          {
            "active_state": "inactive",
            "unit": "vst-runner.service"
          },
          {
            "active_state": "inactive",
            "unit": "vst-dispatcher.service"
          },
          {
            "active_state": "inactive",
            "unit": "vst-dispatch-owner.service"
          },
          {
            "active_state": "inactive",
            "unit": "vst-dispatch-owner.socket"
          }
        ]
      },
      "transport": "stdin to /usr/bin/python3.12 -I -S; no filesystem mount"
    }
  },
  "provenance": {
    "framework_schema": "D:/Repo/Agentic_Framework/tools/af/evidence.py",
    "current_public_reviews": {
      "path": "docs/sdlc/evidence/s2-frozen-source-reviews-d3f326f-20261029.md",
      "sha256": "9b3982b17d5ce6465cf5cfbca1072e99559068baa1d0aa7efce7bf4c2946a850",
      "reviewed_head": "d3f326f37a40936402d3933d5266e0ffb01017f0",
      "findings": "three actual reviews: database-reviewer, security-reviewer, code-reviewer; all gpt-6-luna/medium; no valid code BLOCKER/MAJOR in declared scope; not full S2 approval"
    },
    "inherited_public_test_reports": [
      {
        "path": "docs/sdlc/evidence/s2-final-functional-e987a24-20261029.md",
        "sha256": "51ab94cb61591e51b0497081c6237e4e478d33827bdbd57827b6d84114f277a9",
        "execution_head": "67d1d55e5556c6936516f3404202faecba1e6707",
        "note": "prior-head functional and supplemental E7 results only; not run at 524a2d69"
      },
      {
        "path": "docs/sdlc/evidence/s2-final-e2e-e987a24-20261029.md",
        "sha256": "8a9c503df7b9b3e07039e3d629c4988ff698b14e167ab198da88d15ebcbf6b40",
        "execution_head": "67d1d55e5556c6936516f3404202faecba1e6707",
        "note": "prior-head E2E and WSL counterpart only; not run at 524a2d69"
      }
    ],
    "current_test_blobs": {
      "tests/vst/test_s2_assignment_bootstrap.py": "8d6c50da428ac68de95a9587caa4609e506427f95350c1b2022e8869b168cd70",
      "tests/vst/test_s2_dispatch_issuance_contract.py": "397007d580a77abae7f7b7461ff2d6efb6ce3f2821e7006c30f04293d5be011b",
      "tests/vst/test_s2_assignment_basis.py": "77f9c8724a84511b1882c9a3834ff4518fd8fef406df142b46a7de222dac5533",
      "tests/vst/test_s2_machine_source_contracts.py": "93cd62e6b4c8f9aa2db758b90b6fd00e1e4b3552e193dd3936351df25d4c73ef",
      "tests/vst/test_s2_signed_dispatch_instruction.py": "13b436675383e98449520c15c640a87fcb84370ade534475b5ad2c63ece8b76f",
      "tests/vst/test_s2_store_backed_pubsub.py": "435262304ca08fef9ed371748fa8184086ada46a8f016b4751a997db37f228e7",
      "tests/vst/test_s2_dispatch_owner_service.py": "fc7e194cb45700446438c776281be789f8ad0551edc5c506887af35af020df71",
      "tests/vst/test_s2_dispatch_owner_latch.py": "dd747aa5c42cf4745197c77b0138c2e71bdd9690ed3d779d00969142382d35f1",
      "tests/vst/test_af_attachment_review.mjs": "1c42e35d6ae8b790e5c722f44217620b53f018b82809f7d6fea99f5450243c5d",
      "tests/af/test_s2_attachment_adapter_e2e.mjs": "9cc0b44f6fca5b4a0ff7b9f843866b24f0f9e8178fee4575f405049f9c9ddd07",
      "tests/af/test_s2_review_source_fidelity.py": "798aed2b9df50e3d985d6721cf103817d8cbccb9"
    },
    "current_source_blobs": {
      "tools/vst/assignment_basis.py": "c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de",
      "tools/vst/store.py": "d0a5516531b0941654a5b262e24d2ee5d9513de888f0c8f9b2b1176ac09a7a12",
      "tools/vst/dispatch_issuance.py": "e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a",
      "tools/vst/root_dispatch_issuer.py": "049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9",
      "tools/vst/supervisor.py": "62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71",
      "tools/vst/supervisor_service.py": "14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2",
      "tools/vst/machine_observations.py": "9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11",
      "tools/vst/machine_authorization.py": "8c031f5547874b4811264e400d0b28166f1ca7b3d962ee0d04e75ba9d140e8ff",
      "tools/af_attachment_review.mjs": "9cdb51192e8fcb037cedd8980cd819b35fbc76c02f076adcb0071f3d3ab1b54e",
      "tools/verify_s2_review_source_fidelity.py": "8cce81cd2ff70a79f48be47db8a1b6d05608ab3d"
    },
    "prior_runtime_source_plan": {
      "path": "docs/sdlc/evidence/s2-runtime-source-plan-524a2d6-20261029.json",
      "sha256": "ad5e32ce72e9d601ae0da765a31bd1d425461f3ecf2f20d1cbff8389d094b876",
      "payload": {
        "activation": "NOT_AUTHORIZED_BY_THIS_PLAN",
        "archive_files": {
          "docs/SANDBOX_SPEC.md": "7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997",
          "tools/qa/install_wsl_runner_runtime.sh": "b9d3e116f2c466e40307ea6701115773c9fffcc1591d10df445d07af4e8be3fa",
          "tools/qa/install_wsl_worker_helper.sh": "9e1d70c6df5a3ba195ba67581d4cf0485f1d0207ca0ddebecd7e9025883cead1",
          "tools/qa/worker_exec.c": "ea76231fe4b3ae99902be7be43d3a7a970f9ea28c7b27258097f0ceb9d20d951",
          "tools/vst/__init__.py": "01c1c19343f8da7f605775ecbf7909d6e8aad7b3bd17a08065f1d712f8a6db9f",
          "tools/vst/assignment_basis.py": "c2159f18cf25597118d13623b4ecf24fcd1e40626d03ca32fa1ec8fb920f51de",
          "tools/vst/bootstrap_runtime.py": "4b5823643c77d2f7ce64cd499a61ebea4bb0a222f2a261e822edb386a2c44bfc",
          "tools/vst/contracts.py": "bf01d990a94cd71887f8d9f81019333f3bf43d5950a655de3646e9bb3d585ea4",
          "tools/vst/diffgate.py": "3be2f59327b3b95701e26e7d441b1e47374467daab1f9e68d158f2f5cd8bb8b8",
          "tools/vst/dispatch_instruction.py": "b2d0194c69b678cc108f78b6c4b1cf6fd20a1fdcbdb4869e5b6548c4883a1e05",
          "tools/vst/dispatch_issuance.py": "e3e062042b615d633914bf957b5901647ff644fe319c8b07de461ed0a6b81c4a",
          "tools/vst/dispatch_owner_client.py": "d825f1cdc320a5babc419e89f9f181961da8426c3d3a2a915257091d9d1641b1",
          "tools/vst/dispatch_owner_latch.py": "390c5314cc150462b47ecb3dc3c363fc8d3d6a59e99e35dd6f2e613fb0cfb419",
          "tools/vst/dispatch_owner_service.py": "483241d6e18d25a073a75fde8c3ebe65925bcb17bd5536b5b7ffe7056484bd8e",
          "tools/vst/dispatch_owner_transport.py": "134ece4fd7e20b947ee3e91ea08909b359e03542bc0243c77e753b54591d4de4",
          "tools/vst/dispatcher_service.py": "0f23727307c14aed691ab2d0ae338eef472453f5eabd4f85de70e916692c2fc3",
          "tools/vst/execution_grant.py": "f99810d04664f6d95e336be2138001c2e255e6ae9e8eb531b806d745fc4c7c43",
          "tools/vst/gate.py": "562474f756cd897b9239fc1573870e15924c547547412be2ab8813d23a71600f",
          "tools/vst/lifecycle.py": "db81de532229cca96855be286ae5565acff31e0910be09afbc39885132e47a34",
          "tools/vst/machine_authorization.py": "8c031f5547874b4811264e400d0b28166f1ca7b3d962ee0d04e75ba9d140e8ff",
          "tools/vst/machine_observations.py": "9f3932c4496f3316ba0d4666fce72d36658e117fe79cc1c137b90a2fcccb7b11",
          "tools/vst/preflight.py": "08393eb2f85691b1bdc18e06256cefc7dc6a0aa1f50aa2ba23086b8662e7b049",
          "tools/vst/root_dispatch_issuer.py": "049e1c207bf1b19d4db50c4be0103a56307de1c677c75f017bdd6b74cac3bba9",
          "tools/vst/runner.py": "02c60162ed1bbda61e1341d055aa893ce1cf52c3bbecbc545e7e67eb902a07ee",
          "tools/vst/runner_fence.py": "32c682eddb78747b91e319cee365e2e12c54edda3096316992e5d0fe025d67ab",
          "tools/vst/runner_service.py": "8e1e2196914dc14a45957f94a57a0ac460f9809184fbe2ceed8df1329c4420d9",
          "tools/vst/runtime_bundle.py": "ae95afdd47f66cb3cd7192e3d4d3d892f5fc23e2c269b435561ae913272de293",
          "tools/vst/sandbox.py": "b5946426d9749a00c76bfc666a0a6f2edb30e74e9985bf0b796caba08fe3b803",
          "tools/vst/schemas/README.md": "be51b507d0406efd805ddd4a5518450c0ecf2d29135a39b1a44b2ab5f9bba3d0",
          "tools/vst/signer.py": "948b2db9562a6886640f1baacece08a99fb76fea4afa43b4ac3ad4246a2f2070",
          "tools/vst/signing.py": "41584757abb70db96d45859ba107e588a6796eeae14223a0159901a17d48630f",
          "tools/vst/slice.py": "8e81e0ecbbd301fabefcbda3299d4f8b1415aa86c9b0a90795428dafcff3eb2f",
          "tools/vst/store.py": "d0a5516531b0941654a5b262e24d2ee5d9513de888f0c8f9b2b1176ac09a7a12",
          "tools/vst/supervisor.py": "62871979e5f1fbdd7e087202027781e60193463e3b2fbd78c57c062e3a37ab71",
          "tools/vst/supervisor_service.py": "14b84e52268bf041fb437eb170ca39b2efc16cf69061ce88055f75147e4231e2",
          "tools/vst/systemd/README.md": "bff939afec2dd5e4f4b46d18b2d4fe9ac9bcd1dc6525f97934b10174a235cb63",
          "tools/vst/systemd/vst-dispatch-owner.service": "606aff7a866d0182d891e42df66e26160540372a8120480b13fef10e45fe9cfb",
          "tools/vst/systemd/vst-dispatch-owner.socket": "a7855aefc05a04df1b51b798e2cf82c060716d638391573ac0b232de24724b6e",
          "tools/vst/systemd/vst-dispatcher.service": "ed12e2f7d5ee2a7177139682a91d5ba714679497e7c0f50c565b2141302a6c16",
          "tools/vst/systemd/vst-runner.service": "4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be",
          "tools/vst/systemd/vst-signer.service": "33ed12ee7174c9136493cfba3cd4176a1c48ac9515afb79d5eb0740ff6d3502d",
          "tools/vst/systemd/vst-supervisor.service": "aa64d16b7801f32146808706acffaa0ca9086653e5e3e9f5f5dac1bc07ab822c"
        },
        "archive_sha256": "e985858501b4b0fa00ebba8eae6d2234aabd5f301937fa205e0bdad4f6f77df3",
        "helper": {
          "binary_sha256": null,
          "build_recipe_sha256": "9e1d70c6df5a3ba195ba67581d4cf0485f1d0207ca0ddebecd7e9025883cead1",
          "compiler_path": "/usr/bin/cc",
          "compiler_provenance": "NOT_VERIFIED",
          "gid": 988,
          "mode": "4750",
          "path": "/usr/local/libexec/vst-s4-worker-exec-524a2d69aa4bc709b7777b131edd79c8fe24250e",
          "source_sha256": "ea76231fe4b3ae99902be7be43d3a7a970f9ea28c7b27258097f0ceb9d20d951",
          "uid": 0
        },
        "permitted_operation": "stage-only-after-source-tests-and-exact-plan-review",
        "runtime_path": "/opt/vst-runtime-524a2d69aa4bc709b7777b131edd79c8fe24250e",
        "sandbox_spec_sha256": "7a0bcaa3eb7ca76b9771e0b7f49892eaa0cfa744ce4e523f5f94b997fed61997",
        "schema": "VST_S2_RUNTIME_SOURCE_PLAN_V1",
        "selection": "separate-post-staging-manifest-review-required",
        "source_head": "524a2d69aa4bc709b7777b131edd79c8fe24250e",
        "status": "UNSIGNED_REVIEW_CANDIDATE",
        "store_disposition": "UNKNOWN",
        "target_inventory": "NOT_VERIFIED",
        "unit_sha256": {
          "vst-dispatch-owner.service": "606aff7a866d0182d891e42df66e26160540372a8120480b13fef10e45fe9cfb",
          "vst-dispatch-owner.socket": "a7855aefc05a04df1b51b798e2cf82c060716d638391573ac0b232de24724b6e",
          "vst-dispatcher.service": "ed12e2f7d5ee2a7177139682a91d5ba714679497e7c0f50c565b2141302a6c16",
          "vst-runner.service": "4915925e88b11fdf23fd10af5f3520eb921496dbd9a727743139bc91a9e3b8be",
          "vst-signer.service": "33ed12ee7174c9136493cfba3cd4176a1c48ac9515afb79d5eb0740ff6d3502d",
          "vst-supervisor.service": "aa64d16b7801f32146808706acffaa0ca9086653e5e3e9f5f5dac1bc07ab822c"
        },
        "unresolved": [
          "current target/identity collision inventory",
          "compiler provenance",
          "source/test approval and exact staging-plan review"
        ]
      }
    },
    "latest_test_execution": {
      "tested_head": "206a746fdae942fd6ab6f36c882bb0c3d18ec539",
      "command": "python tests/af/test_s2_review_source_fidelity.py -v",
      "result": "Windows NT 10.0.26300.0; Python 3.14.3; Git 2.53.0.windows.1; PowerShell; exit 0; duration 30.164s. Attachment size 5766789; SHA-256 833efc361a34266767e331ebf6a2724cecba3e03512e4443ddf6cd661d93311b. Test SHA-256 f3b44778a9a89bb298c9f68b5f64bbbf517cd4e022f12691686129b1e998b220; verifier SHA-256 91f66464a3adecc01ef554731fe71ea6c836f5f68fbd9caf10be9b2596d8a962. Exact committed HEAD.",
      "test_blobs": {
        "tests/af/test_s2_review_source_fidelity.py": "798aed2b9df50e3d985d6721cf103817d8cbccb9"
      },
      "source_blobs": {
        "tools/verify_s2_review_source_fidelity.py": "8cce81cd2ff70a79f48be47db8a1b6d05608ab3d"
      }
    },
    "latest_exact_head_review": {
      "head": "00312f0b845f5f914254eab33be2fa8224f53159",
      "base": "6117ba24b08a260b42402db6da0bf767864e1c04",
      "request_id": "d2492272-ed6c-4eb7-9584-6bfe44af868e",
      "job_id": "0396e9f8-6cdc-45e7-a769-f6c9e806f7f2",
      "user_turn_id": "44287481-997b-4555-8ed7-4003ba640b03",
      "reply_id": "60978efd-accd-52a3-a4be-e5049ae4cf68",
      "correlated": true,
      "send_phase": "sent",
      "attachment_size_bytes": 5753229,
      "attachment_sha256": "42c2621ae9382d2870cb231a25a96e8d758871520d6ed786efe824ba5ff406fb",
      "gpt_verdict": "NOT REVIEWED — EXECUTION ENVIRONMENT UNAVAILABLE",
      "formal_approval": false,
      "af_result": "NOT_APPROVED; parser verdict UNRECOGNIZED because reply begins with ChatGPT wrapper text instead of required VERDICT line",
      "evidence": "docs/sdlc/evidence/s2-exacthead-branch-refresh-00312f0-20261029.md"
    }
  },
  "process_incidents": [
    {
      "role": "e2e-runner",
      "source": "actual agent disclosure and committed public E2E report",
      "event": "A broad rg command emitted matching excerpts from the protected pre-existing untracked evidence artifact despite the explicit exclusion instruction.",
      "disposition": "No contents reproduced in this packet. Agent reported no modification; the artifact was not staged by Codex and remains untracked. Subsequent searches were constrained."
    },
    {
      "role": "functional-test-reviewer",
      "source": "actual agent disclosure during final committed-head evidence refresh",
      "event": "An earlier broad workspace rg command also emitted matching excerpts from the same protected artifact despite the explicit exclusion instruction.",
      "disposition": "No contents reproduced in this packet. Agent reported no modification or further read. Codex cannot independently verify an untracked protected file content without violating its read restriction; it remains excluded from staging."
    }
  ],
  "latest_test_execution": {
    "tested_head": "0da595e6574856ed0c85a181941e822031b80787",
    "command": "node --test tests/vst/test_af_attachment_review.mjs",
    "total": 38,
    "passed": 38,
    "failed": 0,
    "errors": 0,
    "skipped": 0,
    "log": "Actual functional-test-reviewer run; Windows NT 10.0.26300.0; PowerShell; Node v24.13.1; Git 2.53.0.windows.1; exit 0; duration 149843.3314 ms. Tester confirmed test and adapter Git blobs matched exact HEAD before and after; no tracked files changed. Test SHA-256 5FA69F2F34722AD96FEFAF2A2C8A98C9B18D29298F5E726FDDC0BEFBC30FAEA1; adapter SHA-256 1933B1775C87E21088C82BC435B36C056A1795E306334716B26724E07DD08631.",
    "test_blobs": {
      "tests/vst/test_af_attachment_review.mjs": "6349f338312cdc144c8f62e0a55d5095b00ba198"
    },
    "source_blobs": {
      "tools/af_attachment_review.mjs": "75c61d538d5e00f3ae926c8f2023d34f1e54c852"
    },
    "evidence": "docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md"
  },
  "latest_exact_head_review": {
    "head": "2befed5515455c4dbf022cad68e839a8a2ce799c",
    "base": "6117ba24b08a260b42402db6da0bf767864e1c04",
    "request_id": "ad64e813-a507-4b4a-8601-d9fa1a8276b9",
    "job_id": "9a75f58f-f517-4354-92c2-eae954f31c74",
    "user_turn_id": "d0c0bdbe-d249-44d2-a87c-7b1889f338fe",
    "reply_id": "c46b1b10-9b56-5d7c-bcf9-9f4b950dfa69",
    "correlated": true,
    "send_phase": "sent",
    "attachment_size_bytes": 5766789,
    "attachment_sha256": "833efc361a34266767e331ebf6a2724cecba3e03512e4443ddf6cd661d93311b",
    "gpt_verdict": "MAJOR — exact-source HOLD",
    "formal_approval": false,
    "af_result": "NOT_APPROVED; no exact-head approval",
    "findings": [
      "S2-REVIEW-01: source expressions are redacted in the exact attachment, preventing source-fidelity verification",
      "S2-REVIEW-02: full adversarial coverage cannot be certified from the redacted package"
    ],
    "evidence": "docs/sdlc/evidence/s2-exacthead-review-2befed5-20261029.md"
  }
}


## Evidence file: verify-evidence.md (sha256 8cc648290d8796b0e8148fcad61d1b892583d9788d8ea582efad5ddf3420586c)
# S2 verification evidence and remaining acceptance

Sprint: 39b7cc253f5d

Product sprint: existing S2. Framework phase: 7 Verify. This is an evidence record, not an
approval file. Overall S2 remains NOT APPROVED; production/runtime criteria below are unresolved.

## Provenance and verification layers

Continuation baseline: `9c1be0f`. Runtime journal correction: `5724ba8`. Read-only authenticated
assignment API: `c2b1cd2`; current run/generation correction: `3d5f6c2048238a79fb92ddf805bc562b4b392a63`.
Later documentation changes do not imply these tests executed at a different source revision.
The primary agent coordinated tests and assessed coverage but did not author or execute them.

Reconciliation addendum (2026-10-29): the complete original epic/deferred-item denominator and
the 0552/0553 decision boundary are mapped in [S2 original epic coverage reconciliation](S2_ORIGINAL_EPIC_COVERAGE_MATRIX.md).
The corrected historical schema-v5 fixture has its own two-selector result in
[s2-legacy-v5-fixture-run-20261029.md](evidence/s2-legacy-v5-fixture-run-20261029.md); it is
maintenance evidence and does not combine with the component rows below or establish final-head
S2 acceptance. GPT-PM's recovered correlated source reply and exact limits are recorded in
[the bootstrap and issuer adjudication](evidence/s2-bootstrap-source-and-root-issuer-adjudication-20261029.md).
Unsigned host/guest observations remain UNKNOWN as detailed in
[s2-machine-observations-20261029.md](evidence/s2-machine-observations-20261029.md). The root-bound
issuer design is linked separately at [S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md](S2_ROOT_BOUND_DISPATCH_ISSUER_DESIGN.md);
it is design/source preparation only and does not close its issuance-state finding.

The implementer reported one accidental `git diff --check` invocation during this continuation
with no output. This report was not independently reproduced and is not a test, build, runtime,
or acceptance result. It does not alter the exact commands and owners reported below.

| Actual role / model / effort | Source and command scope | Recorded result | Boundary |
|---|---|---|---|
| functional-test-reviewer / gpt-6-luna / medium | Three new runtime-bundle/source-plan/machine-contract test files; exact source/hash references in s2-bootstrap-functional-run-20261029.md | Windows 30 passed / 6 POSIX skips; WSL 36 passed, exit 0 | Real synthetic Ed25519 keys and public verification in WSL; detached candidate contracts, no production authority |
| e2e-runner / gpt-6-luna / medium | Two bootstrap/stage-only test files at c2b1cd2; s2-bootstrap-e2e-run-20261029.md | WSL 16 passed; Windows 8 passed / 8 POSIX skips | Disposable filesystem and mocked systemd boundaries; real harmless Python argv mapping; ordinary partial-write exceptions, no process crash |
| functional-test-reviewer / gpt-6-luna / medium | test_s2_assignment_basis.py plus two explicitly named safe Store regressions at 3d5f6c2; s2-assignment-basis-functional-run-20261029.md | Windows 23 passed; WSL 23 passed, exit 0 | Real disposable Store read transactions and synthetic future handoff; no authenticated production writer or configured peer |

The three rows are separate commands at their identified revisions; do not present them as one
full-suite or final deployed-head run. Runtime-bundle and journal components unchanged by the
run/generation correction retain their recorded component-level evidence. All exact commands,
tool versions, hashes, skipped cases and limitations are in the linked records.

## Independent review and corrections

| Actual reviewer / model / effort | Findings and disposition | Remaining scope |
|---|---|---|
| code-reviewer (s2_runtime_code_review) / gpt-6-luna / medium | Two valid MAJORs: partial preparation journal and partial retention copy could strand retry. Fixed at 5724ba8, reproduced then passing by E2E owner, focused source recheck on 3d5f6c2 resolved both. Argument-index finding explicitly retracted; actual subprocess test confirms existing indexing. | Source/fixture proof only |
| security-reviewer (s2_runtime_security_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in reviewed runtime/candidate-contract diff 9c1be0f..7e9c519 | Production trust and E5 unchanged |
| database-reviewer (s2_basis_database_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in read-only source diff 5724ba8..3d5f6c2; one consistent read transaction and rollback-only close, chain/anchor/journal/probe/live-authority checks | Future writer needs atomic conn-taking helpers and explicit failure contract |
| security-reviewer (s2_basis_security_review) / gpt-6-luna / medium | No reachable BLOCKER/MAJOR in the same read-only source; optional issuer-only operation, trusted current policy/run/generation | Future writer and real deployment are not accepted by this source review |
| database-reviewer and security-reviewer focused design rechecks / gpt-6-luna / medium | Fresh-only writer addendum resolves the previously reported transaction, eligibility, authenticated caller and replay/legacy design gaps; no remaining design-level MAJOR in the reviewed slice | Explicit GPT-PM SOURCE decision still required before writer implementation; production is separate |

Focused tests also found duplicate embedded guard, independent revocation-ID conflation, and
stale Supervisor run/generation acceptance. Fixes 0544, 0545 and 0549 are linked to their negative
regressions. An exploratory historical schema-v5 selector is incompatible with the pre-existing
schema-v6 baseline; its unchanged hard-coded assertion and failed command remain recorded, not
hidden or counted as new-feature coverage. Codex owns its backlog reconciliation.

## Acceptance matrix

| Criterion / meaning | State | Evidence/completed work | Remaining acceptance | Dependency/blocker | Owner | Next step |
|---|---|---|---|---|---|---|
| S2-1 / signed admission and recovery | Source/test acceptance retained; task delivery still open | Four-file WSL selection 130/130 at `2befed5`; source-fidelity verifier 5/5 at committed HEAD `206a746`; adapter functional/E2E 35/35 and 2/2 at `2befed5`; prior adapter regression 38/38 at `6952469`; exact Bridge-wrapper regression 38/38 at committed code HEAD `0da595e`. All 41 redactions map across 15 exact Git blobs/lines, with no confirmed defect from independent security assessment. GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` closed S2-REVIEW-01 but left S2-REVIEW-02 open because full adversarial coverage was not established in that review. Its persisted reply uses a `ChatGPT said:` wrapper, now handled only with a matching request ID. | Fresh GPT-PM exact-head decision, then normal task push; installed runtime, systemd/kernel identity, production configuration and E5 remain unproven | Previous PM disposition remains `MAJOR/HOLD`; the new code-review sweep and committed-head test are evidence for re-adjudication, not approval | Codex owns implementation/evidence and PM request; GPT-PM owns the formal decision | Refresh local AF packet to current source/test evidence and request one fresh correlated exact-head review |
| Current branch changed-code test refresh / AF attachment transport | Exact test results recorded; test outputs are not GPT-PM approval | At `2befed5`: adapter functional 35/35, adapter E2E 2/2, four-file WSL selection 130/130. At exact committed HEAD `6952469`: 38/38 for inner-header parser. At exact committed HEAD `0da595e`: 38/38 for exact PM Bridge wrapper, test and adapter matched Git blobs before/after. Prior PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` used a 5,842,177-byte input with SHA `0e7e8be1ebd52f8f27f7581c4fef999c9ba0efc2f486aa3ef86e6e660a2e5cd9`; adapter rejected its reply with `review_status=NOT_RUN`, `verdict=UNRECOGNIZED`, `receipt_written=false`. | Fresh PM review and normal push remain; no approval file or runtime activation | Previous PM disposition remains HOLD; current code is committed/tested, but no fresh exact-head decision exists | `functional-test-reviewer` owns tests; Codex owns evidence; GPT-PM adjudicates | Submit new exact-head attachment through corrected adapter and inspect actual correlated result before push |
| S2-2 / authenticated owner transport | Prior source/test accepted | Existing 34-case WSL transport record, explicitly mocked kernel identity | Real activated endpoint to Runner | Genuine configured runtime and authority | Codex | Execute only mapped permitted runtime scenarios after gates |
| S2-3 / exact bundle and bootstrap preparation | Implemented, source-tested, independently reviewed | Source plan generator, stage-only path, manifest/selector/journal and fixes; compiler/known-path metadata | Exact current source-plan review, inactive artifact staging and post-stage manifest review | Current plan is unsigned; no actual install/selection occurred | Codex; GPT-PM adjudicates | Regenerate exact plan after source freeze, submit source/test/review bundle |
| S2-4 / authenticated assignment and runtime provenance | Read-only basis implemented/tested; full criterion OPEN | One-snapshot journal/probe/lease/run/generation proof and issuer-role refusal | Authenticated bootstrap writer, precise policy, issuer, genuine current E5 and real journey | Writer source held pending corrected contract review; production/E5 not authorized | Codex; GPT-PM adjudicates; operator owns exact production policy/reserved trust acts | Review fresh-only writer transaction contract and obtain bounded SOURCE decision |
| S2-5 / exact-head gate and delivery | OPEN | Correlated architecture decisions and actual role evidence retained | Fresh full S2 acceptance and exact-head GPT-PM approval, then one sprint PR | S2-3/S2-4 runtime acceptance unresolved | GPT-PM; Codex coordinates | Submit complete evidence only when prerequisites established; never self-approve |
| Restricted scenarios / process-kill, crash/recovery, mutation, E8 and policy selectors | NOT_RUN | Explicit restrictions preserved | No pass or waiver inferred | Prohibited execution | Operator for any changed scope; Codex preserves status | Leave NOT_RUN; obtain only a precise authorized disposition if required for acceptance |

## Ordered remaining work

1. Codex obtains independent focused DB/security review of the fresh-only writer transaction
   addendum, then GPT-PM's explicit bounded source decision. No new human owner or external
   coordinator is required; per-task operator signatures are retired from the proposed design.
2. Complete only newly authorized source, then mapped tests and direct specialist review. Keep
   new writer and issuer disabled until exact policy/runtime gates are satisfied.
3. Regenerate source staging plan for the final code revision; GPT-PM reviews it with compiler and
   current target metadata before staging. Review actual tree/helper/old-state fingerprints in a
   separate post-stage selection manifest. Neither plan is an approval or activation permit.
4. Establish genuine current runtime/E5/authority evidence under the accepted contract; restricted
   scenarios remain NOT_RUN. Finish S2 acceptance and exact-head gate before S3 implementation.

Current human E5 verifier is unchanged; unsigned machine observations always remain UNKNOWN.
No production signing key/service, Store migration, dispatch activation, push, PR or merge is
claimed by this record.


## Post-integration current source verification — 2026-10-29

Sprint: 39b7cc253f5d

Source freeze: `67d1d55e5556c6936516f3404202faecba1e6707` on
`s2-canonical-continuation` in `D:\Repo\Virtual_scrum_team`.
The earlier writer-HOLD matrix above is historical and superseded for SOURCE by
GPT-PM's I01 SOURCE GO and the implementation/fixes through change 0564. It remains
correct that installed runtime, current E5 and final Phase 8 are not thereby proven.
No existing external coordinator is required: the bounded assignment/issuer source
is implemented in Store/Supervisor and the operation-ID-only authenticated route.

### Current permitted evidence

The actual functional and E2E roles are `gpt-6-luna`, medium effort. Their public
records retain exact commands, overlay hashes, environment, failed prior revisions
and current results. Tests are synthetic source/Store/RPC or explicit dedicated-WSL
permission boundaries, not production service activation. Results must not be added
across overlapping groups or revisions.

| Current selection | Source / result | Evidence and limit | Owner / next acceptance |
|---|---|---|---|
| Four functional modules, Windows | 67d1d55: 62 passed, 6 skipped | `evidence/s2-final-functional-e987a24-20261029.md`; six POSIX-only signed-key fixture cases are not Windows passes. | Codex reviews exact evidence; POSIX counterpart below. |
| Same four functional modules, WSL | 67d1d55: 68 passed | E2E reported terminal success with exact overlay hashes, including private-root fixture correction. | Codex reconciles the final E2E public command record. |
| Full delegated issue-to-reservation path and negative integration controls | 67d1d55 WSL: 26 passed | Completed issuance, admission/replay, exact grant persistence/replay, claim/reserve, duplicate refusal, live revocation and missing-link refusal. | Codex obtains fresh independent source reviews. |
| Legacy schema-v5 and TP28 regressions | 67d1d55 WSL: 7 passed | Current legacy/direct compatibility remains permitted without delegated downgrade. | Codex retains separate exact selector evidence. |
| POSIX anchor and worker/reviewer identity boundary | 67d1d55 WSL: 10 passed | Dedicated existing WSL fixture only; not production credentials or Windows ACL proof. | Codex preserves the platform limitation. |
| Windows allowed E1/E3/E6 and integration selection | 67d1d55: 97 passed, 26 skipped | E2E current report; skips are 25 POSIX-only integration cases and one POSIX reviewer case. | Codex maps each allowed result to original acceptance; no skip promoted. |
| Bundle/source plan/bootstrap/stage-only fixture groups | Prior 8beffcc: WSL 36 passed; Windows 28 passed, 8 skipped | Product paths and test modules unchanged by Store-only 0564. Historical scoped evidence, not a claim of a new run or installed bundle. | Codex includes source/blob identity in review; GPT-PM reviews exact staging candidate later. |
| Additional allowed E7 pub/sub, owner and idempotency contracts | 67d1d55: Windows 40 passed / 17 skipped; WSL 35 passed; separate WSL latch 7 passed | Exact nodes and fixtures in both public role reports. Windows POSIX skips have an explicitly separate WSL counterpart, not a Windows pass. | Codex obtains independent review; no real service/process operation is inferred. |
| Allowed E7 lifecycle, breaker and simulated recovery contracts | 67d1d55 Windows: 34 passed across six exact invocations | Source-inspected callbacks, synthetic keys, disposable SQLite and in-process threads. Real process recovery is NOT_RUN. | Local bare-Git/fake-PR fixture and pre-spawn injected timeout also passed; actual termination, remote providers and runtime remain NOT_RUN. |

### Remaining real acceptance and ordered closure

1. Allowed E7 regression mapping and current public records are complete for the
   permitted source scope. Codex commits the package with change record 0565; the
   source/test blobs, not an invented cumulative count, identify this evidence.
2. Codex launches fresh actual general-code, database and security/reliability reviews
   for the exact source package. Fix all confirmed code BLOCKER/MAJOR findings in a
   focused batch and run only designated direct regressions.
3. Codex prepares the exact final non-secret source staging plan and current target/
   compiler metadata. GPT-PM adjudicates the bounded source/runtime package before
   any actual staging, key/policy installation, runtime signing or service activation.
4. Current E5 still requires genuine run-bound evidence under the accepted contract.
   Operator owns any reserved human attestation; Codex owns permitted preparation and
   collection. No signature, policy installation or activation is inferred here.
5. Restricted actual termination/crash/mutation/E8 scenarios remain NOT_RUN. Codex
   supplies exact remaining scope; GPT-PM adjudicates acceptance and the operator
   owns any genuine scoped waiver or restriction change. A waiver cannot erase FAIL.
6. Only after acceptance and fresh exact-head GPT approval may Codex push/open the
   single S2 PR. S3–S5 remain ordered behind S2 closure. No self-written approval.


### Frozen-source specialist consensus and live observation

All three actual fresh-context reviewers completed their declared full new S2
source surfaces at d3f326f37a40936402d3933d5266e0ffb01017f0. Confirmed code
BLOCKER:0; MAJOR:0. See
`evidence/s2-frozen-source-reviews-d3f326f-20261029.md` for roles, exact scopes,
base, line evidence, initial capacity rejection and corrected security-scope sweep.
These findings do not claim an exhaustive generic audit or runtime acceptance.

The six committed test blobs at d3f326f match the exact SHA-256 overlays recorded
for current67d1d55 execution. The only tools/vst or tools/qa path changed between
those commits is tools/vst/schemas/README.md; product source did not change.

Permitted live Windows collection was actually attempted with fixed PS7, no fallback.
`Get-NetFirewallProfile` is unavailable in that restricted PS7 context although the
NetSecurity2.0.0.0 module is discoverable. An explicit native import also failed;
its precise exception is UNKNOWN, not an asserted permission error or source bug.
No complete snapshot/counts exist; normalization remains unsupported. Raw host data
is private and not part of this packet. Public sanitized record:
`evidence/s2-windows-live-observations-d3f326f-20261029.md`.

Requested GPT-PM adjudication is the exact code package and residual acceptance,
not a claim that S2 is fully done. If a bounded runtime step is authorized, state
its exact scope separately: stage an immutable versioned tree and helper from the
reviewed source/compiler recipe only, preserve the selected old runtime and units,
collect post-stage fingerprints, then review that transition manifest before any
selector/config/keys/service signing or activation. No source-plan JSON grants
permission. Existing compiler/path inventory is dated evidence and must be refreshed
for the actual stage. Genuine E5 and restricted-case disposition remain explicit;
Codex will not invent an operator signature/waiver or an external coordinator.


## Evidence file: review-record.md (sha256 a786723c536e72372270a50ff53cfba50b30534980fc9fb56c278b5868954d16)
# S2 phase 5 document review

Sprint: `39b7cc253f5d` (existing S2). Baseline: `9c1be0fbe42b48f7a9cd547be36af23413fcfc8e`.
Reviewed working-tree requirements/backlog/design/test-plan and candidate machine trust design.

## Actual independent reviews

| Agent / profile / effort | Finding | Focused resolution / disposition |
|---|---|---|
| s2_phase5_arch / architect / gpt-6-luna / medium | Staging previously coupled selector/unit install; journal had rename-to-record interruption window | design.md now specifies explicit stage-only path, separate transition, fsynced write-ahead intent/completion and recovery by old/new fingerprints for every path. Architect rechecked both and returned GO for bounded runtime implementation. |
| s2_phase5_code / code-reviewer / gpt-6-luna / medium | Machine assignment purpose described as existing; assignment/E5 closed schemas absent; stale owner wording | Machine implementation held; Codex owns correction. Backlog now distinguishes candidate machine policy authorization, active human E5 and bounded delegated setup. Reviewer returned GO for independent runtime manifest/staging/transition. |
| s2_machine_security_design / security-reviewer / gpt-6-luna / medium | Same new-authority/schema gap; signed Store chain alone does not establish upstream authority | Candidate machine design remains unapproved and is being corrected. No production signer/key/activation is authorized. Pure schemas/read-only preparation require precise contracts first. |
| s2_phase4_writer / technical-writer / gpt-6-luna / low | Candidate machine acceptance needs explicit traceability; do not infer existing signed assignment events | Runtime plan aligned by functional-test-reviewer; machine implementation remains held until exact fields/verification are defined and reviewed. |
| s2_plan_align / functional-test-reviewer / gpt-6-luna / medium | Bootstrap-only test map must match absent configs, inactive units, UNKNOWN Store and per-path recovery | Updated TP-06 through TP-13 and actual machine adjudication boundary. Planning only, no executable tests or execution. |

## Bounded phase exit

GO to phase 6 for runtime manifest, explicit stage-only install, and separate bootstrap-only
transition. This is permission to implement reviewed design, not evidence that source exists or
runtime is verified. All services stay inactive, existing Store stays unopened, old artifacts
remain retained. Configured-host upgrades are refused. Keep machine issuer/E5 implementation
held until its candidate schemas are corrected; that independent hold does not stop runtime work.

No test/check/build/provisioning/activation was performed for this review. GPT-PM's architecture
reply is MODIFY (exact correlated evidence in s2-machine-authority-adjudication-20261029.md), not
overall S2 approval. Final exact-head code gate remains open. No approval files were hand-written.


## S2 post-functional source reviews — current at d3f326f

Sprint: 39b7cc253f5d

Actual fresh-context database-reviewer, security-reviewer and code-reviewer ran
on gpt-6-luna medium after designated tests completed. Full declared new S2 source
was compared with origin/main, including bootstrap/issuer integration already in
the snapshot port; the small later fix delta alone was insufficient. Security
finished the additional owner/dispatcher/Runner/signer/latch/fence trust surfaces.
No confirmed code BLOCKER/MAJOR remains in those reviewed scopes. Detailed evidence
and manual-review limits are in
[evidence/s2-frozen-source-reviews-d3f326f-20261029.md](evidence/s2-frozen-source-reviews-d3f326f-20261029.md).
Reviewers ran no tests/checks/build/CI and wrote no source. Prior design/runtime
HOLD statements are historical; current source implementation/review is established,
while installed trust, service behavior, genuine current E5 and final Phase8 remain
separate. This record is not GPT approval and writes no approval artifact.


## Evidence file: test-plan.md (sha256 b6c0f475d38db34d82e01632e29e929098626eecf8552334dbe9995f84bb629e)
# S2 focused functional and runtime test plan

Sprint: `39b7cc253f5d` — active project sprint S2  
Status: planning only; S2 coding is still in progress. No tests were authored or executed for this plan.

## Purpose and evidence boundary

This plan maps future tests to the accepted S2 stories and numbered acceptance criteria in `docs/sdlc/backlog.md`. It covers the accepted Store-authorized path: `DispatchOwnerService` → authenticated Supervisor/Store admission → Store-filtered Pub/Sub → `StoreBackedDispatcher` → Runner. Store remains the only assignment and lease authority. It does not add another coordinator, scheduler, or assignment authority.

The recorded source/test evidence is bounded:

| Story | Recorded evidence | What it establishes | What it does not establish |
|---|---|---|---|
| S2-1, `S2-PROV-M03-R01` | GPT-PM source/test acceptance at `c855ca4`; the linked M03 run record reports 130 passed, 0 failed in Ubuntu 24.04 WSL with Python 3.12.3/pytest 7.4.4. | Source/test behavior for cross-generation historical-result recovery at that revision. | Installed runtime, systemd identity, kernel credentials, current-head equivalence, production issuer/E5, or full S2 acceptance. |
| S2-2 | GPT-PM transport decision `b0f60d46-42b7-486a-b2f0-5d2253780f55`; `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md` records 34 passed, 0 skipped, 0 failed at HEAD `20fda2c`. | One local AF_UNIX socketpair request/half-close/EOF/response/ACK path through the real `DispatchOwnerService._handle()` method. | Live systemd socket activation, actual PID 1 credentials, kernel peer credentials, pidfd, socket filesystem metadata, provisioned identities/configuration, Store, Runner, or production owner-to-Runner behavior. Those properties were mocked or absent. |

These historical results are not rerun or promoted to current-head proof by this plan. Source/test acceptance of S2-1 and S2-2 is distinct from S2 runtime acceptance. Current disposition remains S2-3 open, S2-4 blocked by `S2-DISPATCH-M01` (MAJOR/OPEN), and S2-5 pending; S2 is NOT APPROVED and S3 remains unstarted (`docs/sdlc/backlog.md`, `docs/sdlc/requirements.md`).

## Execution order and ownership

1. Codex completes accepted S2 source coding, including the immutable bundle/schema validation and inactive-only exact-revision transition described in `docs/sdlc/design.md`. The runtime transition code is not complete, so test authorship and execution must wait.
2. After coding is complete, `functional-test-reviewer` authors the focused source-level tests in this matrix. `e2e-runner` owns permitted runtime selectors and reports exact command, source HEAD, environment, and result. Neither role may convert a prohibited or unavailable scenario into a pass.
3. Run source-level cases first. Proceed to permitted runtime qualification only after the exact non-secret bundle has been reviewed by GPT-PM under the recorded conditional scope, required configuration/identities exist, and the Store has been read-only classified. Store disposition `UNKNOWN` blocks initialization; only a separately gated fresh schema-v6 Store may be initialized. Existing Store migration remains behind its separate gate.
4. Keep affected services inactive through bundle preparation and artifact transition. The initial transition is only for an unconfigured host: `/etc/vst-runner` and runtime socket directories must be absent; all six affected units/socket must be inactive, with no queued systemd jobs or populated VST cgroups. A configured host is refused; upgrades remain out of scope. Each individual rename is atomic; replacing the selector and multiple units is a recoverable sequence, not a single atomic transaction. Store `UNKNOWN` permits selecting already verified inactive artifacts because selection does not open or mutate Store data; it continues to block Store initialization, migration, activation, and dispatch.
5. GPT-PM's correlated architecture decision `a3e130f0-9aec-4304-b001-388a45c0be55` (reply `0b0b8a4d-0816-4166-ba21-71857b5de49d`) is `MODIFY — DESIGN ONLY`: bounded delegation contracts, pure validators, and read-only measurement collectors may be designed/implemented. Production signing keys/services, E5 contract replacement, and activation are not authorized. The findings `S2-MACHINE-ISSUER-M01` and `S2-MACHINE-E5-M01` remain open pending design and review. This decision is not runtime evidence. See `docs/sdlc/evidence/s2-machine-authority-adjudication-20261029.md`.
5. After mapped tests and permitted runtime evidence, relevant specialist reviews, and fixes, GPT-PM reviews the exact final head and correlated evidence. A changed head requires a fresh exact-head decision (S2-5 / REQ-006).

## Acceptance-mapped test matrix

“Existing” refers only to the cited historical source/test evidence. “Planned” means not yet authored or run. Runtime rows are conditional on their prerequisites. Every test must assert externally observable state (Store events/lease, selected link/unit bytes, process/unit activity, or actual Runner outcome), not just helper return values.

| ID / acceptance mapping | Future scenario and falsifiable assertion | Evidence layer / status | Owner and prerequisite |
|---|---|---|---|
| TP-01 — S2-1 AC-1; REQ-001/002 | For each unsigned, invalid-signature, expired, wrong-purpose, or mismatched request/task/slot/attempt/epoch/run/key binding instruction, assert rejection occurs before durable dispatch intent; Store assignment, lease, and event chain remain unchanged. Include a valid instruction as the positive control. | Existing source coverage is present in `tests/vst/test_s2_signed_dispatch_instruction.py` and related S2 source suite; specific scenarios/result must be reconciled to the accepted M03 test record. Do not claim installed-runtime coverage. | `functional-test-reviewer`; after source coding complete; use deterministic valid/invalid signed fixtures. |
| TP-02 — S2-1 AC-2; REQ-004 | Replay a previously accepted outcome after generation change: matching complete historical envelope returns only the immutable historical result from one verified snapshot; absent, mismatched, corrupt, or unresolved history fails closed. Assert no duplicate append, lease mutation, new grant/admission, or Runner launch. | Historical M03 source/test evidence: 130 passed at `c855ca4`; additional rerun only if changed code or exact-head regression requires it. Existing named source tests include `test_s2_operation_recovery.py` and `test_s2_persistent_runner_service.py`; their recorded outcomes are not assumed from filenames. | `functional-test-reviewer`; source change complete; disposable isolated Store fixture. |
| TP-03 — S2-1 AC-3 / S2-2 AC-3; REQ-006 | Evidence/reporting check: label source tests and mocks as source/test only; assert the report records exact test HEAD, command, environment, pass/skip/fail counts, and explicit unproven runtime properties. | Existing records are historical evidence; no new test needed unless evidence-generation code changes. | Codex reconciles records; GPT-PM adjudicates final exact-head claim. |
| TP-04 — S2-2 AC-1/2; REQ-002/003 | Valid one-frame request follows existing authenticated Supervisor/Store admission and Store-backed dispatch, with no assignment created by transport. For malformed, partial, duplicated, EOF/ambiguous, or response-loss cases, assert fail-closed outcome and no unsigned fallback or second request on the same connection. | Transport source/test acceptance is recorded: WSL `test_s2_dispatch_owner_transport.py`, 34 passed at `20fda2c`; actual local socketpair and `_handle()` path only. New coverage is conditional on code changes. | `functional-test-reviewer`; isolated socketpair and deterministic service fixture. |
| TP-05 — S2-2 AC-2; REQ-003 | On ambiguous admission/outcome, assert caller receives an explicit unresolved/fail-closed result and subsequent retry cannot duplicate durable dispatch or bypass Store filtering. | Planned regression coverage if the final code changes the ambiguity path; must not be inferred from the 34-case transport run. | `functional-test-reviewer`; source coding complete; injected deterministic response loss, no process-kill/crash scenario. |
| TP-06 — S2-3 AC-1; REQ-005/006 | Build a bundle from one exact source HEAD; assert manifest binds repository identity, full source HEAD, archive SHA-256, sandbox spec digest, six unit hashes, helper revision/source/binary digests, paths, schema, intended owner/group/modes, Store disposition, and transition baseline. Assert no secret bytes are present; changing a bound input changes validation. | Planned. Bundle implementation and schema validator are incomplete; no tests authored/run. | `functional-test-reviewer`; after Codex completes bundle/schema implementation. Use non-secret fixtures only. |
| TP-07 — S2-3 AC-1; REQ-005 | Reject missing/unknown fields, malformed digests/HEADs, and placeholder credentials. `UNKNOWN` Store rejects initialization, migration, and activation but does not by itself reject inactive artifact selection, which neither opens nor changes Store data. Existing Store must never silently become `FRESH`. | Planned; no bundle tests yet. | `functional-test-reviewer`; same prerequisite as TP-06. Do not mutate or initialize a real Store in unit tests. |
| TP-08 — S2-3 AC-2/3/4; REQ-005 | An unreviewed/changed bundle fails authorization preconditions. Fresh schema-v6 Store initialization is permitted only under its explicit reviewed gate; existing/unknown Store cannot initialize or migrate. Assert no issuer key or E5 signature is synthesized. | Planned pure contract tests; no provisioning, Store initialization/migration, key generation, or signing. | `functional-test-reviewer` tests validators/preconditions; GPT-PM reviews exact bundle. |
| TP-09 — S2-3 design acceptance; REQ-005/006 | Install only absent immutable destinations with no-replace semantics. Verify exact artifacts and owner/group/mode/digests; collisions or mismatches refuse without overwrite. Old runtime/helper remain intact. | Planned after installer coding. | `functional-test-reviewer`, disposable filesystem only; never mutate actual WSL `/opt` in a unit test. |
| TP-10 — S2-3 design acceptance; REQ-005/006 | Bootstrap transition refuses configured hosts (`/etc/vst-runner` or runtime socket dirs exist), active affected units/socket, queued systemd jobs, populated VST cgroups, stale selector/unit fingerprints, unresolved claims, unverified artifacts, or collisions. Assert all baseline bytes remain unchanged on precondition failure. Store `UNKNOWN` alone does not reject artifact-only inactive selection. | Planned; transition is not implemented. | `functional-test-reviewer`; disposable filesystem/systemd shims only; no real activation or Store writes. |
| TP-11 — S2-3 design acceptance; REQ-005/006 | In an unconfigured disposable host model with exact old/new runtime and helper fingerprints, install the new immutable artifacts and replace selector plus six fixed-name units through individually atomic renames. Assert final digests match the reviewed manifest, prior artifacts remain, and no enable/start occurs. Do not assert multi-path atomicity. | Planned; no implementation or tests. Proves transition logic only. | `functional-test-reviewer` after source completion; `e2e-runner` may observe real inactive state only after bundle review and authorized provisioning. |
| TP-12 — S2-3 design acceptance; REQ-005/006 | Inject failures between selector/unit renames. Assert a durable journal records completed steps, services remain inactive, and recovery restores each exact prior selector/unit byte set and hashes or fails closed for read-only recovery. Retain new immutable artifacts. | Planned deterministic fault-injection tests. Real process-kill/crash/power-loss remains prohibited and `NOT_RUN`. | `functional-test-reviewer` after transition code; injected failures only. |
| TP-13 — S2-3/S2-4 boundary; REQ-005 | Preparation/transition never start/enable services, create/activate issuer keys, sign/replace E5, enable dispatch, or mutate/migrate Store. Assert no such command/write occurs. `UNKNOWN` Store blocks all Store-changing and activation actions. | Planned source-level assertions; not production safety evidence. | `functional-test-reviewer` after relevant coding. Production activation remains separately gated by accepted authority, fresh run-bound evidence, and runtime review. |
| TP-14 — S2-4 AC-1/4; REQ-003/005 | Conditional permitted runtime journey: from a genuinely authorized owner request through the installed authenticated endpoint and existing Supervisor/Store/filter/dispatcher to the real Runner. Capture exact HEAD, systemd identity, root-controlled config, current run-bound provenance, selected E5 format/binding/nonce/spec digest, Store assignment/lease, and Runner result. Positive result must correspond to one authorized assignment. | **NOT_RUN / blocked.** Current transport test does not reach systemd, Store, or Runner. `S2-DISPATCH-M01` remains MAJOR/OPEN. | `e2e-runner` executes only after exact bundle review, accepted authorization format/policy, provisioned identities/configuration and current run-bound evidence. Current human E5 v1 remains mandatory unless a separately reviewed/approved machine format is explicitly selected. Operator owns the exact production policy authorization/reserved custody; Codex gathers permitted evidence; GPT-PM adjudicates. |
| TP-15 — S2-4 AC-2; REQ-001/003/005 | In the permitted runtime journey, refuse missing/unauthenticated issuer or trust key, wrong owner, expired/revoked/badly bound instruction, stale lease/epoch/generation, mismatched payload, duplicate, or ambiguous result. Assert no unauthorized/duplicate Runner execution and Store authority remains unchanged. | **NOT_RUN / blocked** until TP-14 prerequisites. No synthetic identity may be reported as production acceptance. | `e2e-runner`; same prerequisites as TP-14. Synthetic negative fixtures may be used only within the separately accepted mapped test scope and must be labeled synthetic. |
| TP-16 — S2-4 AC-3; REQ-006 | Report restricted process-kill, crash/recovery, mutation, E8, and policy selectors exactly as `NOT_RUN`; assert no skipped/synthetic result is counted as pass. | **PROHIBITED — NOT_RUN.** No execution or test authoring for these selectors. | Codex preserves this status in the evidence record; no test-role execution. |
| TP-17 — S2-5 AC-1/2/3; REQ-006 | After all accepted evidence and fixes, reconcile the final Git HEAD with the exact test commands/results and reviewer evidence; any subsequent code change makes approval stale. Verify acceptance record distinguishes accepted source/test stories from carried runtime/gates. | Planned closure evidence, not an executable test. No final overall GPT-PM approval recorded. | Codex assembles exact-head evidence; GPT-PM owns final exact-head approval. S2 remains NOT APPROVED and S3 unstarted until approval/acceptance. |

## Explicitly prohibited or unavailable coverage

The following remain `NOT_RUN`, not pass, skip, waiver, or implied coverage:

- Process kill, crash recovery, mutation, E8, and all restricted policy selectors (S2-4 AC-3; REQ-006).
- Real systemd/PID 1 peer authentication, production credentials/keys, current signed E5, and installed production configuration until their genuine prerequisites and separate authorization exist.
- Existing Store migration and production service activation/dispatch. Store disposition is currently `UNKNOWN`; do not infer that it is fresh.
- Any scenario that would create/impersonate an issuer or trust key, fabricate an operator-root signature, overwrite/delete an existing runtime/helper, or create a second assignment authority.
- GPT-PM permits bounded delegation-contract design, pure validators, and read-only measurement collectors only; production signing keys/services and E5 contract replacement remain unauthorized (`docs/sdlc/evidence/s2-machine-authority-adjudication-20261029.md`).

If a permitted scenario cannot run, record `NOT_RUN` with the exact unavailable prerequisite/error, revision, and owner. Never replace it with a synthetic pass. Test evidence is complete only for the mapped acceptance criterion and exact revision that the test actually exercised.

## References

- `docs/sdlc/requirements.md` — REQ-001 through REQ-006, constraints, and current blockers.
- `docs/sdlc/backlog.md` — S2-1 through S2-5, numbered acceptance criteria, current disposition, and DoD.
- `docs/sdlc/design.md` — exact bundle, inactive revision transition, rollback, and activation boundaries.
- `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md` — exact transport command, revision, environment, result, and limitations.
- `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md` and linked `s2-cross-generation-outcome-recovery-test-run-20261029.md` — M03 source/test acceptance and limits.
- `docs/sdlc/evidence/s2-runtime-bundle-inventory-20261029.md` — point-in-time WSL inventory; not provisioning or current E5 acceptance.
- `docs/sdlc/evidence/s2-machine-authority-adjudication-20261029.md` — correlated design-only machine authority ruling; not production signer authority or runtime evidence.
- `docs/sdlc/evidence/s2-assignment-basis-functional-run-20261029.md` — focused synthetic assignment-basis source tests, exact run command/result, freshness defect/fix, hashes, and evidence limits.

### Additional source-contract coverage for the active S2 candidate scope

These cases extend TP-06 through TP-13 and trace the GPT-PM bounded source authorization to
REQ-005/006 and S2-3/S2-4. The new machine schemas remain candidates. No test is authored or run
until Codex completes all in-scope source work and records a source freeze.

| ID / acceptance mapping | Focused falsifiable assertion | Layer / status | Owner / prerequisite |
|---|---|---|---|
| TP-18 — S2-3 AC-1; REQ-005/006 | `prepare_wsl_runtime_plan.py` accepts only canonical repository root and exact committed 40-hex HEAD. Repeated preparation over unchanged HEAD produces identical canonical bytes and binds archive/spec/all six unit/helper source+build recipe hashes; changed HEAD or absent required archive member refuses. Assert it labels compiler, target inventory and binary digest UNKNOWN, creates no file, and emits no approval/activation claim. | Planned pure source test; not authored/run. | `functional-test-reviewer`, after source freeze. Mock only Git subprocess in temporary repo for negative cases; exercise exact real archive API with immutable recorded HEAD. |
| TP-19 — S2-3 AC-1; REQ-005/006 | `runtime_bundle.validate_manifest` rejects missing/unknown/duplicate fields, bool-as-int, malformed digest/HEAD/path, inconsistent expected helper identity and unsupported old/current selector/unit fingerprint shapes. Canonical manifest hash remains stable. | Planned pure validator test; module/API still in implementation. | Same owner after final API freeze; derive valid fixture from closed schema, never privilege real paths. |
| TP-20 — S2-3 AC-2/3; REQ-005/006 | Stage-only preflight refuses each present config/socket sentinel, active/activating/failed/unloaded unit, malformed/failed systemd job inventory, affected queued job, unreadable/nonempty cgroup, and cgroup symlink. Parse list-jobs as JOB/UNIT/TYPE/STATE. Positive fixture has inactive loaded units or documented not-found and empty/no cgroups. | Planned isolated source-level embedded-Python test; not authored/run. | `functional-test-reviewer` after both installer code is frozen; mocks must model actual systemctl output and assert no selector/unit write. `e2e-runner` does later real observation only after reviewed staging manifest. |
| TP-21 — S2-3 AC-2/3; REQ-005/006 | Direct distro `--stage-only` invocation repeats the host predicates; valid stage retains exact immutable runtime/helper, reports selected=false and units-installed=0, and never reads/writes selector or fixed units. Existing exact versioned artifact is idempotent; mismatch refuses without overwrite. | Planned disposable filesystem/source harness; not authored/run. | Same owner after shell installer API freeze. No WSL installation or mutation in unit tests. |
| TP-22 — S2-3 design; REQ-005/006 | `bootstrap_runtime` preparation hashes complete staged runtime/helper plus old selector and six unit fingerprints without mutation; rejects manifest digest mismatch and configured host. Apply requires external exact manifest digest, current pristine bootstrap conditions and retained journal, changes each path by individual rename, verifies all new bytes/metadata, emits no start/reload. | Planned isolated system command/filesystem harness; not authored/run. | Same owner after runtime bundle/selector API freeze. Do not construct an accepted digest by invoking apply; prepare and apply are separate. |
| TP-23 — S2-3 design; REQ-005/006 | Inject ordinary exceptions before/after each rename, fsync, and journal state update. Recovery compares every path with old/new digest irrespective recorded state; restores exact old values or absence and retains new artifacts. Any third-party bytes cause zero recovery writes. Successful group replacement is never asserted collectively atomic. | Planned deterministic fault injection only. Process kill, power-loss, crash recovery remain prohibited `NOT_RUN`. | Same owner after source freeze; do not use real root paths, systemd, WSL or Store. |
| TP-24 — S2-3/S2-4 candidate delegation; REQ-005/006 | `machine_authorization` exact policy and external assignment validators bind operator key purpose, separate authorization signer key and intended machine issuer key, project/repo/sprint/manifest, principal, task tuple, expiry/revocation. Mismatch, stale current Store snapshot, wrong purpose, unknown field or duplicate key fails closed. Test signatures only with synthetic public/private fixtures; do not connect signing service. | Planned pure validator/source test; candidate API still in implementation. | Same owner after source freeze. The external signed assignment schema is new, not an existing signed Store event. No real authorization or provisioned trust is implied. |
| TP-25 — S2-3/S2-4 machine observation candidate; REQ-005/006 | `machine_observations` accepts only exact raw-bundle and source schema; duplicate/missing source, incomplete command, changed hash, unsupported platform, malformed type, inconsistent host/WSL metadata return UNKNOWN/INCOMPLETE/UNSUPPORTED. `OBSERVATIONS_COMPLETE` means schema collection completeness only; there is no PASS output or route into current Supervisor human E5 verifier. | Planned pure fixture test; collector not executed. | Same owner after source freeze. Never collect host observations as a test, sign E5, replace v1, create keys, or assert production. |

No tests, checks, provisioning, migration, service activation, or production dispatch were performed for this planning artifact. The focused assignment-basis candidate tests and their exact results are recorded separately below; they do not establish production authentication or runtime acceptance.

### Authenticated assignment-basis candidate source tests

At source HEAD `3d5f6c2048238a79fb92ddf805bc562b4b392a63`, the read-only assignment-basis candidate source is present. The focused tests use disposable SQLite state and synthetic journal rows that model a future writer; they do not prove that an authenticated production assignment writer, trusted root policy, issuer peer, or current production provenance exists.

| ID / acceptance mapping | Focused falsifiable assertion | Evidence layer / status | Owner / prerequisite |
|---|---|---|---|
| TP-26 — S2-3/S2-4 candidate; REQ-005/006 | For one exact synthetic operation ID, resolve the canonical handoff and current task/owner/lease/probe basis, return the closed response, and show the query uses one locked Store read snapshot and changes no table, event, operation, lease, probe, or other DB state. | `tests/vst/test_s2_assignment_basis.py`: 21 passed as part of the final 23-test command at source `3d5f6c2`. | `functional-test-reviewer`; synthetic fixtures only. No production writer, issuer, key, or authority claim. |
| TP-27 — S2-3/S2-4 candidate; REQ-005/006 | Refuse malformed/unknown or legacy operation IDs; mismatched task-manifest, policy, principal, payload, row/event actor or duplicate event; stale epoch/lease/probe/runner; changed/missing/expired root policy; wrong RPC role or caller-selected request fields. Also refuse otherwise valid unexpired handoff/probe data from a previous Supervisor run or service generation instead of relabeling it with the current generation. | Final focused run passed. The previous-run defect was reproduced at `c2b1cd2` (one test failed with `DID NOT RAISE`) and fixed at `3d5f6c2`; both prior-run and prior-generation regressions pass on the fix. | Codex owns source correction; `functional-test-reviewer` owns focused tests. No production authentication or runtime claim. |
| TP-28 — S2-1 regression; REQ-001/005 | Keep existing `execution_grant_basis` and verified startup-history semantics intact while using the extracted locked helper. Run only named safe selectors exercising those paths; do not select entire runtime/service test files. | The final command included `test_store_completion_appends_the_receipt_chain_and_replays_only_exact_complete_receipt` and `test_store_refuses_preflight_consumption_before_verified_startup_history`; both passed. A four-file S2-1 recovery regression at code HEAD `56cd816` exposed a direct-Store fixture missing `key_fingerprint`; after supplying the trusted synthetic fingerprint, that selection passed 130/130 at both `56cd816` and exact HEAD `2befed5`. Commit `dcb5d63` contains the corrected fixture. Exact current-head command, environment, hashes, and limitations are in `docs/sdlc/evidence/s2-exacthead-review-2befed5-20261029.md`. | `e2e-runner` executed the focused WSL selection. No full suite or restricted runtime scenarios. Current-head source/test execution does not establish installed runtime or exact-head GPT-PM approval. |
| TP-29 — S2-1 exact-review source fidelity; review evidence integrity | For the immutable review attachment, bind exact full base/HEAD and attachment size/SHA-256; match the complete attachment diff to the exact raw Git diff; map each redaction through ordered hunks to exact blobs and lines; fail closed on tampering; preserve CRLF and embedded fences; emit no source values or per-line fingerprints. | `tests/af/test_s2_review_source_fidelity.py`: 5 passed via `python tests/af/test_s2_review_source_fidelity.py -v`, with committed-baseline HEAD `2befed5515455c4dbf022cad68e839a8a2ce799c`; verifier and test file were uncommitted at execution. The run mapped all 41 markers across 15 files. Full provenance, test hash, and limits: `docs/sdlc/evidence/s2-review-redaction-independent-review-2befed5-20261029.md`. | Source fidelity and static invariant review are evidence for GPT-PM re-adjudication; they are not GPT-PM approval, runtime evidence, or authorization to push. | Focused tests are fixture/offline and use the exact local PM attachment; they do not prove production behavior. | `functional-test-reviewer` authored/executed focused tests; Codex owns implementation/evidence; GPT-PM owns re-adjudication. |
| TP-39 — S2-1 exact-head AF correlation; REQ-006 | For a correlated PM Bridge response with the exact `ChatGPT said:` transport wrapper, require a leading UUIDv4 `REQUEST_ID` that exactly matches persisted intent before accepting one top-level verdict. Reject wrapper without ID, mismatched/duplicate/malformed IDs, arbitrary wrapper/preamble, missing/repeated verdicts; mismatch must not create a receipt or approval artifact. | `functional-test-reviewer`: `node --test tests/vst/test_af_attachment_review.mjs`, 38 passed, 0 failed/cancelled/skipped at exact committed HEAD `0da595e6574856ed0c85a181941e822031b80787`, duration 149843.3314 ms. Tester verified test and adapter Git blobs matched before/after; no tracked edits. Full output, environment, hashes, PM response and limits: `docs/sdlc/evidence/s2-af-correlated-reply-parser-20261029.md`. | Test/regression evidence is exact-head; no GPT-PM approval is implied. | Fresh correlated PM review of the current exact head remains. | `functional-test-reviewer` owns execution; Codex owns adapter/evidence; GPT-PM owns review decision. |

### Fresh bootstrap and integrated I01 issuer source contract (S2-3/S2-4 candidate)

These cases derive from accepted S2-3 AC-1/4, S2-4 AC-2/3, the fresh-only bootstrap contract in change0552, and I01-SRC-01 through I01-SRC-05 in the correlated GPT-PM source adjudication. They are planned only: the assigned source batch is still in progress. No test code or execution is authorized until Codex records the final S2 source freeze and gives the test-role GO. Use disposable SQLite/filesystem/RPC fixtures and synthetic keys only where a signature-format test is essential; never provision or activate a real root key or run production requests.

| ID / acceptance mapping | Focused falsifiable scenario and observed contract | Original epic trace | Layer / state / owner and prerequisite |
|---|---|---|---|
| TP-29 — S2-3 AC-1/4; REQ-005/006; change0552 fresh-only bootstrap | Through the Store transaction boundary, start with a valid fresh synthetic policy/request and assert one complete bootstrap: story/task, exact manifest budget (including `cost_cap=0`, `spent=0`), epoch advance, attempt-1 lease, handoff, immutable operation and linked event all commit together. Inject each deterministic pre-commit validation failure and assert the database snapshot is unchanged across every affected table/event. A failure before commit must not leave a partial assignment. | E6 (Store isolation/assignment boundary); E7 (durable lifecycle/idempotency). | Disposable SQLite integration fixture; planned, not authored/run. `functional-test-reviewer`, after root's explicit final S2 code-freeze GO. No real Store. |
| TP-30 — S2-3 AC-1/4; REQ-005/006; change0552 fresh-only bootstrap | Repeat the exact bootstrap operation/request and assert the byte-identical stored result is returned with no additional task/story/event/lease/handoff/operation effects. Reuse the operation identity with changed request, policy digest, peer identity or manifest and assert conflict/refusal with no state change. | E7 (idempotency and duplicate-effect prevention). | Disposable SQLite integration fixture; planned, not authored/run. Same owner and freeze gate. |
| TP-31 — S2-3 AC-1/4; REQ-005/006; change0552 fresh-only bootstrap | For each prior-history condition (existing story/task, relevant event, lease, receipt, budget row, terminal marker, handoff, or noninitial attempt), assert bootstrap refuses rather than adopts, resumes, retries, renews or switches assignment; assert preexisting bytes/state are preserved. Include valid pristine state as positive control. | E6 (assignment isolation); E7 (replay/recovery safety). | Disposable SQLite boundary fixture; planned, not authored/run. Same owner and freeze gate. No manually seeded state may be described as proof of process-crash behavior. |
| TP-32 — S2-3 AC-1/4; REQ-005/006; change0552 fresh-only bootstrap | At exact cost boundary, prove a zero-cost manifest bootstraps with `cost_cap=0` and `spent=0`; separately exercise over-cap/invalid budget and exhausted-attempt/occupied-slot inputs and assert refusal with no partial state. Preserve the documented existing `spent > cap` rule; do not silently substitute `spent >= cap` or change legacy `acquire_lease` behavior. | E6 (budget and lease invariants); E7 (valid transition boundaries). | Disposable SQLite integration fixture; planned, not authored/run. Same owner and freeze gate. |
| TP-33 — S2-4 AC-2; REQ-001/005; I01-SRC-03/04; issuer design key-class contract | With synthetic trust material, assert immutable key class/purpose/fingerprint binding survives restart/read verification. `LEGACY_V1` retains its accepted path; `DELEGATED_V1` requires a fully correlated verified issuance; missing/unclassified, purpose mismatch, fingerprint drift, altered class, missing/corrupt/mixed-family journal or attempted downgrade fails closed. Observe admission refusal and unchanged assignment/lease/event state. | E1 (key/signature boundary); E3 (durable integrity/reconciliation); E7 (fail-closed lifecycle). | Store/Supervisor source integration with disposable journal; planned, not authored/run. `functional-test-reviewer` after source freeze. No real root key, provisioning, or runtime signing. |
| TP-34 — S2-4 AC-2; REQ-001/005; I01-SRC-01/03/05; issuer journal contract | For one immutable assignment-operation identity, assert reserve creates exactly one INTENT and only one caller can durably create STARTED; the signer-call seam is reached at most once for that identity. Exact frozen replay before STARTED can proceed only under the defined same identity; after STARTED, an absent completion reduces to UNKNOWN and retry does not call signer again. Changed handoff, policy, run, generation, key, expiry or unsigned bytes is CONFLICT. | E3 (journal integrity); E7 (idempotency and ambiguous external outcome). | Deterministic Store integration plus injected signer-call counter, planned, not authored/run. Same owner/freeze gate. Do not kill/terminate a process or claim literal crash proof from seeded journal rows. |
| TP-35 — S2-4 AC-2; REQ-001/005; I01-SRC-01/03; grant provenance binding | Persist exact signed grant bytes and assert their operation and accepted dispatch identity link to the same completed issuance and immutable handoff. Exercise exact grant replay, altered bytes, absent/mismatched linkage, and issuance/payload collision; only exact replay succeeds, with no second durable grant/admission or Runner authority. | E1 (authorization binding); E6 (assignment-to-execution provenance); E7 (duplicate/recovery behavior). | Store/Supervisor integration using synthetic signature fixtures and outcome assertions; planned, not authored/run. Same owner/freeze gate; no real signing. |
| TP-36 — S2-4 AC-2; REQ-001/003/005; I01-SRC-02/04; admission transaction | For both new delegated admission and exact replay, make current task/owner epoch, lease, manifest, attempt/receipt gap, consumed probe, active run, service generation or current policy stale/mismatched. Assert both branches refuse within the transaction and leave Store state unchanged; valid current authority admits exactly once. Historical replay may return only the persisted fact and cannot create execution authority. | E1 (dispatch verification); E6 (atomic admission); E7 (idempotent replay). | Store transactional integration, planned, not authored/run. Same owner/freeze gate. |
| TP-37 — S2-4 AC-2; REQ-001/003/005; I01-SRC-01/04; grant and Runner boundaries | At grant persistence, grant replay, durable Runner claim and reservation seams, independently stale or change current policy/revocation, generation, key registry, run/probe, lease/owner, or exact grant-to-issuance link between earlier read and write. Assert the same connection-taking current-authority predicate is re-evaluated at each write boundary and no grant/claim/reservation is written on failure. Positive control reaches only the authorized matching boundary. | E1 (authority); E6 (Runner execution boundary); E7 (claim/replay consistency). | Store/Supervisor/Runner source integration with deterministic transaction seam; planned, not authored/run. Same owner/freeze gate. |
| TP-38 — S2-3/S2-4 AC-2; REQ-005/006; I01-SRC-04/05; issuer service boundary | Assert issuer configuration is absent/default-off by default and exposes no issuance route; when explicitly configured in an isolated RPC fixture, only the exact authenticated `delegated_issuer` role and operation-ID-only request can reach the bounded root operation. Wrong role, extra caller-selected task/policy/key/run fields, malformed operation ID or disabled feature refuses without Store/signing effects. Root policy/key purpose separation and immutable source-derived tuple remain observable. | E1 (identity and capability boundary); E2 (service/RPC isolation); E6 (authority boundary). | RPC integration fixture, planned, not authored/run. Same owner/freeze gate. No real process identity, root policy install, key provisioning or activation. |

**Coverage limits and execution boundary:** These planned cases are source-level or disposable-fixture contracts. They do not prove real process-kill/crash recovery, host filesystem durability under power loss, systemd/PID 1 credentials, production root-key custody, real root signing/provisioning/activation, E5, or a production owner-to-Runner journey. Those remain `NOT_RUN`; process kill/crash, mutation, E8 and restricted policy selectors remain prohibited. Never seed `STARTED`/`UNKNOWN` rows and call that literal runtime crash proof. After source freeze, the functional-test-reviewer and e2e-runner may finalize exact node selectors against stabilized APIs; no E2E/runtime selector is authorized by this planning update. Existing TP-01–TP-28 and historical result records remain unchanged and are not promoted to the current source head.


## Evidence file: requirements.md (sha256 854c5b6f7f65a6cfec8c149b52ba1beeffc27e75f7a14da0182834f903aa23ea)
# S2 Requirements Reconciliation

Sprint: 39b7cc253f5d — active project sprint: S2

The Agentic_Framework phase-1 record is attached to the already active S2. It does not create a new product sprint or authorize starting S3. This document consolidates the existing S2 scope and acceptance state; it does not add product scope or reopen the accepted architecture.

## Context and goal

S2 delivers a bounded, authenticated path for dispatching work that has already been assigned by the existing Store, and establishes the evidence needed to qualify its runner boundary. The Store remains the sole task, assignment, and lease authority. The accepted coordinator path is the existing `DispatchOwnerService`, authenticated Supervisor/Store admission, Store-filtered Pub/Sub, and `StoreBackedDispatcher`. No external coordinator, second scheduler, or assignment authority is required. [S1: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”.]

## Scope

**In scope:** source-level signed-instruction verification and owner relay for already-authorized work; fail-closed admission and outcome handling; bounded runtime configuration/evidence under the recorded authorization; truthful S2 acceptance and exact-head review.

**Out of scope:** granting production signing authority, provisioning production issuer/attestor keys, activating production dispatch or E5, migrating an existing Store, running restricted process-kill, crash/recovery, mutation, E8, or policy selectors, or starting S3 before S2 closes. Bounded source preparation for an explicitly machine-labelled delegation contract, pure validators, and read-only measurement collectors is authorized within S2 under the GPT-PM adjudication below. Preparation does not itself authorize signing, replace active E5 verification, or permit activation.

## Requirements

### Machine-delegation adjudication amendment (2026-10-29)

GPT-PM returned `MODIFY` for request `a3e130f0-9aec-4304-b001-388a45c0be55`,
correlated reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`. The exact harvested response is
preserved in `evidence/s2-machine-authority-adjudication-20261029.md`. Machine issuance and
machine E5 are permissible in principle. Codex owns preparing the explicit delegation policy,
assignment-provenance contract, independent measurement topology, versioned schemas and bounded
pure validators/read-only collectors; GPT-PM owns adjudicating the two reported MAJOR findings.
Private-key-bearing production signing services, production signing-key provisioning, replacement
of the current operator E5 contract and activation remain held. A concrete operator-authorized
policy is required before granting production powers; a prepared policy is not an authorization
or a human signature. The earlier unknowns below describe the current runtime contract, not a
requirement to locate a nonexistent external coordinator or to request another generic GO.

| ID | Requirement | Source and priority | Current evidence/state |
|---|---|---|---|
| REQ-001 | A dispatch instruction MUST be accepted only after independent root-Supervisor verification of its purpose-specific signature and bindings for request ID, task, slot, attempt, epoch, run ID, key ID, absolute UTC expiry, version, algorithm, and purpose. Invalid, expired, mismatched, or unsigned instructions MUST fail closed. | Accepted S2 contract in `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; S2 goal. | Verifier/client source is recorded as committed; `core/STATE.md` records source/test acceptance. This does not prove production issuer/key provisioning or runtime acceptance. |
| REQ-002 | The Store MUST remain the sole authority for task assignment, leases, and durable dispatch state; the signer/transport MUST NOT assign work or provide an alternate scheduler. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope. | Architecture is adjudicated and accepted. Production integration remains incomplete under REQ-005. |
| REQ-003 | The owner relay MUST deliver only already-authorized signed instructions through the accepted authenticated Supervisor/Store and Store-filtered dispatch path, with ambiguous outcomes handled fail-closed and without unsigned fallback. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope. | Existing bounded architecture and transport-only source/test scope are recorded as accepted. The qualified production owner-to-Runner journey remains open. |
| REQ-004 | Runner admission and recovery MUST preserve the accepted fail-closed boundary: unresolved or ambiguous dispatch outcomes MUST NOT permit an unauthorized or duplicate execution, and the existing admission fence MUST remain effective across the recorded recovery path. | `core/BACKLOG.md`, S2 section, including `S2-PROV-M03-R01` source/test closure and changes 0518/0522. | `S2-PROV-M03-R01` is recorded closed for source/test only. Installed systemd behavior and production runtime remain unverified. |
| REQ-005 | S2 production-runtime acceptance MUST be supported by an authenticated owner identity and root-controlled configuration, an authorized production instruction issuer/trust key, current run-bound E5/runtime evidence, and a qualified real owner-to-Runner journey. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 closure boundary. | `S2-DISPATCH-M01` is MAJOR/OPEN. Current production integration, current signed E5, and service/runtime qualification are not established. |
| REQ-006 | Evidence and approval MUST identify the exact reviewed source revision. Source/test results, synthetic fixtures, or prior-head records MUST NOT be represented as installed-production or current-runtime acceptance. S2 MUST remain NOT APPROVED and S3 unstarted until its required acceptance and exact-head gate are satisfied. | `core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 scope and closure queue. | Current records explicitly distinguish source/test closure from runtime acceptance and state S2 is NOT APPROVED; S3 remains unstarted. |

## Non-functional requirements and constraints

- **Security:** fail closed on invalid provenance and ambiguous admission; keep signer authority distinct from Store assignment authority. [REQ-001–REQ-004; sources above.]
- **Runtime isolation:** use the accepted authenticated identities, root-controlled configuration, and bounded runtime profile; do not claim isolation from mocked peer credentials or transient test units. [REQ-004–REQ-005; `core/STATE.md`, current S2 coordinator/runtime adjudication.]
- **Numeric service targets:** UNKNOWN. The active S2 records do not establish a numeric dispatch-latency, availability, throughput, or recovery-time target. No target is invented here.
- **Restricted verification:** process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN` under the recorded restrictions. A skipped or unrun selector is not a pass. [`core/STATE.md`, current S2 coordinator/runtime adjudication; `core/BACKLOG.md`, S2 closure boundary.]
- **Data safety:** fresh schema-v6 Store initialization is conditionally allowed by the recorded adjudication; migration of an existing Store requires a separate gate. [`core/STATE.md`, current S2 coordinator/runtime adjudication.]

## Facts, assumptions, and unknowns

### Facts

- GPT-PM accepted the existing bounded coordinator architecture; no external coordinator path is required. [`core/STATE.md`, current S2 coordinator/runtime adjudication.]
- Transport-only source/test scope has recorded GPT-PM acceptance; the recorded functional and WSL runs are source/test evidence, not production-runtime proof. [Same state section; `core/BACKLOG.md`, S2 section.]
- S2 remains `NOT APPROVED`; `S2-DISPATCH-M01` remains `MAJOR/OPEN`; current signed E5, service/runtime qualification, and final exact-head approval remain open. [Same state section.]
- The operator is the sole human owner. Service identities are technical isolation identities, not project owners. [Same state section.]

### Assumptions

- This artifact belongs to the existing active S2 because the project state and backlog identify S2 as active. The framework sprint ID above is recorded as its phase-1 tracking ID, not evidence of a new sprint. [This mapping follows the parent-task instruction and the active S2 records; framework state is tracked separately.]
- Historical test counts and acceptance matrices at earlier revisions are not promoted to current-head evidence. The latest current-state summary governs this reconciliation.

### Unknowns that block S2 closure

| ID | Unknown / missing acceptance evidence | Owner | Next action |
|---|---|---|---|
| UNKNOWN-001 | No production issuer delegation policy/key is installed or evidenced. GPT-PM accepts bounded machine issuance in principle, subject to the concrete provenance contract and separate production authority decision. Codex MUST NOT self-authorize production powers or create production keys. | Codex prepares a precise policy and source contract; GPT-PM adjudicates its architecture; operator authorizes the exact production delegation and key custody if activation is later desired. | Implement/review the bounded machine issuer contract and idempotent Store-assignment provenance. Keep production signing held until the exact delegation is authorized, key custody is established, and its trust chain is verified. |
| UNKNOWN-002 | No production machine-attestor policy, independently verified current run-bound measurement provenance, root configuration, or qualified real owner-to-Runner journey is evidenced. Machine E5 is acceptable only under its explicit versioned trust domain and independent measurement contract; the current human verifier is not silently replaced. | Codex prepares versioned schemas, pure validators and read-only collectors; GPT-PM adjudicates provenance; operator authorizes any concrete production delegation/key custody. | Implement the measurement and verification contract; collect only genuine permitted observations. Keep E5 activation held until independent collector identities, evidence freshness/binding, exact policy, and applicable authority are verified. |
| UNKNOWN-003 | Exact-head GPT-PM final approval for the completed S2 code, mapped tests, and relevant specialist reviews is not recorded. | GPT-PM; Codex owns coordination and submission. | After coding and permitted test/review work are complete, submit the exact final revision and correlated evidence for the required gate; any later code change requires a fresh gate. |

## Traceability and acceptance boundary

`REQ-001`–`REQ-004` describe the accepted bounded source contract. Their recorded source/test evidence does not close production-runtime acceptance. `REQ-005` is currently unmet and is tracked by `S2-DISPATCH-M01` (MAJOR/OPEN). `REQ-006` prevents premature sprint closure or S3 work. Restricted selectors remain `NOT_RUN`; no waiver or pass is inferred from their absence. Once runtime evidence and all permitted source/test/review work are reconciled, GPT-PM must adjudicate the exact final revision before S2 can be reported closed.

## Glossary

- **E5:** the project’s sandbox/runtime inventory and provenance acceptance item; current S2 requires fresh run-bound evidence, and any operator-root-signed attestation must be genuine.
- **Exact-head gate:** GPT-PM approval correlated to the precise final Git revision and its evidence.
- **Store:** the existing durable authority for task assignment, leases, and dispatch state.
- **`NOT_RUN`:** a scenario was not executed; it is not a pass.


## Evidence file: backlog.md (sha256 60ba51687fa420c1611c0094e204b473ff782534eaca2bfca8426d6c1c4b3bc6)
# S2 backlog and acceptance plan

Sprint identity: Agentic_Framework sprint `39b7cc253f5d`, mapped to the already active project sprint **S2**. This is a tracking association, not a new sprint. S3 remains unstarted.

## Current source update — change0556

The fresh-only authenticated assignment bootstrap is implemented in change0552 (`45dcf47`);
the detached issuance/verifier contract is change0553 (`e44f48d`). GPT-PM request
`c7a8e23e-91f5-489c-a096-c813d84c3b12`, correlated reply
`7c3e4eb6-3300-5c5b-ba5c-85aaa10d0487`, returned **GO for bounded integrated SOURCE** and
accepted the corrected I01 design as implementation-ready. This supersedes the earlier source
HOLD for the issuer; it does not supersede runtime, key provisioning, real signing, E5, forbidden
selector or final S2 gates. Codex is implementing the specialized journal, root-Supervisor v1
issuer and transaction-bound admission/grant/runner guards. There is no missing external
coordinator or unassigned owner. Required I01-SRC-01 through I01-SRC-05 are recorded in
`evidence/s2-i01-integrated-source-adjudication-20261029.md` and design change0554.

The historical schema-v5 fixture item below is resolved by change0551 and its designated
six-case fixture evidence; it is not a current product blocker. Final S2 tests still wait until
all in-scope coding is complete. Historical story/epic rows retain their original evidence scope.

## Sprint goal

Deliver and qualify the existing Store-authorized signed dispatch path through the real Runner boundary, while preserving fail-closed behavior and keeping production dispatch disabled until the required runtime evidence and exact-head approval exist.

**Scope boundary:** use the accepted `DispatchOwnerService` → authenticated Supervisor/Store admission → Store-filtered Pub/Sub → `StoreBackedDispatcher` path. Store remains the sole task, assignment, lease, and durable dispatch authority. No new scheduler, coordinator product, assignment authority, or external coordinator is needed. Do not migrate an existing Store, enable production dispatch, invent a production issuer/trust key or independent operator-signed E5/network-policy attestation, or run restricted process-kill, crash/recovery, mutation, E8, or policy selectors. Keep those restricted selectors `NOT_RUN`.

**Prioritization rule:** finish the highest-risk dependency chain in order: establish source/test correctness first; prepare and review the exact non-secret runtime bundle next; collect permitted runtime evidence and qualify real owner-to-Runner integration; then run the final exact-head gate. A later item cannot substitute for missing evidence in an earlier item.

## Prioritized S2 stories

The machine-delegation decision is now recorded, rather than pending: request
`a3e130f0-9aec-4304-b001-388a45c0be55`, reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`,
`MODIFY`; exact response in `evidence/s2-machine-authority-adjudication-20261029.md`.
Within S2-3, Codex prepares the concrete issuer-provenance and independent measurement contracts,
pure validators and read-only collectors. GPT-PM adjudicates corrections to both reported MAJORs.
This does not activate a replacement E5 contract or authorize production signing keys/services.
Operator authorization of the exact production delegation policy remains distinct from Codex's
preparation. No new external coordinator or human owner is required.

| Priority / story | Requirement trace | Owner | State at recorded evidence | Dependency / next action |
|---|---|---|---|---|
| S2-1 — Fail-closed signed instruction, Store admission, and recovery | REQ-001, REQ-002, REQ-004 | Codex | **Source/test acceptance retained; task delivery OPEN before push.** The original `S2-PROV-M03-R01` closure is at `c855ca4`; regression correction is committed in `dcb5d63`. At HEAD `0da595e`, the four-file WSL selection passed 130/130 at `2befed5`, source-fidelity verifier passed 5/5 at `206a746`, prior adapter functional passed 38/38 at `6952469`, and the exact Bridge-wrapper regression passed 38/38 on `0da595e`. The verifier maps all 41 redactions across 15 files; independent security review found no confirmed source defect. GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` resolved S2-REVIEW-01 but retained S2-REVIEW-02 as `MAJOR/HOLD`; the persisted correlated reply has a `ChatGPT said:` wrapper before `REQUEST_ID`. Change 0577 requires the matching ID after that wrapper; code/test reviews found no additional confirmed BLOCKER/MAJOR. | Refresh local AF packet and obtain fresh GPT-PM exact-head adjudication, then normal push. Static/source tests do not establish installed runtime, production identity, E5, or restricted scenarios. Codex owns correction/evidence; GPT-PM owns formal review. Do not begin S2-2 before S2-1 is pushed. |
| S2-2 — Authenticated owner transport to the existing Store-backed dispatcher | REQ-002, REQ-003 | Codex | **Accepted — source/test scope.** GPT-PM transport decision `b0f60d46-42b7-486a-b2f0-5d2253780f55`; WSL transport evidence reports 34 passed, 0 skipped/failed. Kernel peer credentials, pidfd, filesystem metadata, installed systemd identity, and production runtime were not proven by that test. | Source scope is closed. Carry its limits into runtime qualification; do not count the mocked metadata as production acceptance. |
| S2-3 — Immutable non-secret runtime bundle and bounded WSL qualification preparation | REQ-004, REQ-005, REQ-006 | Codex; GPT-PM adjudicates the reviewed bundle | **Open / next.** Existing records authorize bounded Ubuntu 24.04 WSL preparation conditionally, after source/test review and exact bundle review. No current acceptance record in the reconciled sources establishes that the final bundle has been reviewed or runtime qualification completed. | Codex prepares the exact non-secret configuration/artifact bundle and collision rechecks, then obtains GPT-PM review before any conditional provisioning. Fresh schema-v6 Store initialization is conditionally allowed; migration of an existing Store is a separate gate. |
| S2-4 — Production provenance and permitted real owner-to-Runner journey | REQ-001, REQ-003, REQ-004, REQ-005 | Codex for preparation, authorized provisioning and evidence; GPT-PM for contract adjudication; operator for exact production delegation authorization and reserved key custody/human signature | **Not accepted.** `S2-DISPATCH-M01` remains MAJOR/OPEN. Current runtime provenance and real owner-to-Runner acceptance are not evidenced. | Codex corrects the proposed machine contracts and obtains GPT-PM review. After exact delegation-policy authorization and source/bundle gates, Codex performs only the specifically permitted provisioning/collection. Current human E5 stays required until an explicitly accepted machine version is selected. Never invent a signature, authority or successful measurement. |
| S2-5 — Final S2 review, exact-head approval, and sprint acceptance | REQ-006 | GPT-PM owns approval; Codex owns coordination and evidence submission | **Open.** No final GPT-PM approval for the complete S2 code, mapped test results, permitted runtime evidence, and relevant specialist reviews is recorded. | After S2-1 through S2-4 evidence is reconciled, obtain fresh relevant specialist reviews and submit the precise final Git head with correlated evidence to GPT-PM. Any subsequent code change invalidates that approval. Then record accepted/rejected/carried stories in `docs/sdlc/acceptance.md`. Do not begin S3 before S2 closes. |

## Numbered acceptance criteria

These criteria make the existing requirements testable; they do not add product scope. Source/test evidence and installed-runtime acceptance are separate.

### S2-1 — Signed instruction and recovery source contract

1. **Given** an instruction with any invalid, unsigned, expired, purpose-mismatched, or request/task/slot/attempt/epoch/run/key binding, **When** the root Supervisor verifies it, **Then** it rejects before durable dispatch intent and leaves Store assignment/lease authority unchanged. (REQ-001, REQ-002)
2. **Given** an ambiguous admission or a previously accepted outcome replayed after generation change, **When** the existing recovery path handles it, **Then** it follows the accepted read-only historical-result rule or fails closed; it does not append a duplicate event, mutate a lease, grant new admission, or launch a duplicate Runner. (REQ-004)
3. **Given** the recorded source/test evidence at the accepted revisions, **When** this story is assessed, **Then** it is labeled source/test accepted only and is not represented as proof of systemd, kernel identity, or production runtime behavior. (REQ-006)

**Recorded result:** source/test acceptance is retained; delivery is not closed until the task commit is pushed. `S2-PROV-M03-R01` evidence is linked from `core/BACKLOG.md` and `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`. The fixture correction is in `dcb5d63`. The four-file WSL selection passed 130/130 at `56cd816` and exact HEAD `2befed5`; adapter functional/E2E passed 35/35 and 2/2 at that HEAD. The source-fidelity verifier passed 5/5 focused tests and maps all 41 redactions. Independent review found no confirmed source defect; source identity and static invariants are documented in `docs/sdlc/evidence/s2-review-redaction-independent-review-2befed5-20261029.md`. GPT-PM re-adjudication remains pending; no approval or push is claimed. |

### S2-2 — Owner transport source/test contract

1. **Given** a valid signed instruction for work already authorized by Store, **When** the accepted owner transport path forwards it, **Then** the existing authenticated Supervisor/Store path performs admission and the existing Store-backed dispatcher relays it; transport does not create or assign work. (REQ-002, REQ-003)
2. **Given** malformed, partial, duplicated, or ambiguous transport input/outcome, **When** the owner service handles it, **Then** it fails closed without unsigned fallback or a second request on the same one-frame connection. (REQ-003)
3. **Given** the recorded WSL transport run, **When** reporting its result, **Then** report 34 passed, 0 skipped, 0 failed for that source/test run and explicitly retain mocked peer credentials, pidfd, and filesystem metadata as unproven runtime properties. (REQ-006)

**Recorded result:** accepted at source/test scope under GPT-PM request `b0f60d46-42b7-486a-b2f0-5d2253780f55`; exact run record: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`. This result is not production-runtime acceptance.

### S2-3 — Reviewed runtime bundle and bounded preparation

1. **Given** the accepted source/test scope and current repository revision, **When** Codex prepares runtime inputs, **Then** the review bundle identifies the exact source/artifact revision and contains configuration values and hashes without exposing secret contents. (REQ-005, REQ-006)
2. **Given** the GPT-PM conditional WSL authorization, **When** preparation reaches provisioning, **Then** it proceeds only after GPT-PM has reviewed the exact immutable bundle and the stated source/test gate is satisfied. (REQ-005)
3. **Given** an empty Store or an existing Store, **When** initialization is planned, **Then** only the conditionally allowed fresh schema-v6 initialization may proceed under its reviewed gate; an existing Store migration remains stopped for its separate gate. (REQ-006)
4. **Given** any need for a production instruction issuer/trust key or independent operator-root-signed E5/network-policy attestation, **When** runtime preparation requests those inputs, **Then** Codex neither generates nor impersonates them; the missing genuine authority is recorded explicitly. (REQ-005)

**Current result:** not yet accepted in the reconciled sources. Next: Codex prepares the non-secret bundle and collision rechecks; GPT-PM reviews it before conditional WSL provisioning.

### S2-4 — Permitted runtime and production integration

1. **Given** a reviewed bundle and genuinely provisioned authorized identities/configuration, **When** the permitted runtime qualification is executed, **Then** evidence identifies the exact revision, effective service identity, root-controlled configuration boundary, current run-bound provenance, and real owner-to-Runner result. (REQ-004, REQ-005, REQ-006)
2. **Given** missing or unauthenticated production issuer/trust-key provenance, owner identity, root configuration, or current E5/runtime evidence, **When** S2 acceptance is evaluated, **Then** `S2-DISPATCH-M01` remains MAJOR/OPEN and production dispatch remains disabled. (REQ-005)
3. **Given** any selector explicitly restricted by the current adjudication, **When** runtime coverage is reported, **Then** process-kill, crash/recovery, mutation, E8, and policy selectors remain `NOT_RUN`; no skip or synthetic test is counted as a pass. (REQ-006)
4. **Given** runtime observations that do not include a genuine independent signer, **When** provenance is recorded, **Then** Codex reports observations as observations and does not claim an operator-root-signed E5/network-policy attestation. (REQ-005, REQ-006)

**Current result:** open. Codex owns corrected machine-contract design, bounded source and authentic measurements; GPT-PM adjudicates both reported MAJORs. The operator authorizes the exact proposed production delegation policy and retains reserved custody/human-attestation actions. Current human E5 remains authoritative until an explicit accepted machine replacement is selected; no human artifact is impersonated.

### S2-5 — Exact-head gate and sprint decision

1. **Given** completed source, mapped test, permitted runtime, and relevant specialist-review evidence, **When** final approval is requested, **Then** GPT-PM's approval names/correlates to the exact final Git head and evidence set. (REQ-006)
2. **Given** any code change after that approval, **When** sprint closure is reconsidered, **Then** the approval is stale and a fresh exact-head gate is required. (REQ-006)
3. **Given** missing runtime acceptance, a remaining valid code BLOCKER/MAJOR, or missing exact-head approval, **When** S2 status is recorded, **Then** S2 stays NOT APPROVED and S3 stays unstarted. (REQ-005, REQ-006)

**Current result:** open. Next: after all prior criteria are evidenced, Codex submits the exact head and correlated evidence to GPT-PM and writes sprint acceptance from the verdict.

## Definition of Ready

- The story traces to one or more `REQ` identifiers in `docs/sdlc/requirements.md`.
- Acceptance criteria are numbered, falsifiable, and identify whether source/test or runtime evidence is required.
- The accepted architecture and relevant GPT-PM authorization are linked; dependencies and restrictions are explicit.
- The exact evidence source and responsible project owner (Codex, GPT-PM, or operator) are named.

S2-1 and S2-2 are ready and already accepted for their bounded source/test scope. S2-3 is the next executable item under its conditional bundle-review gate. S2-4 cannot be accepted until its genuine provenance and runtime prerequisites exist. S2-5 is a closing gate, not a substitute for unfinished stories.

## Definition of Done

- All in-scope source changes are committed with a dedicated linked change record in the same commit; the accepted source/test revisions and evidence are identified.
- Required mapped tests are authored/executed by the designated test roles after coding is complete; exact commands, revision, environment, results, and limitations are recorded. Unavailable or restricted scenarios are `NOT_RUN`, never `PASS`.
- Relevant specialist reviews are completed on the exact final diff; valid BLOCKER/MAJOR findings are resolved and rechecked.
- Runtime acceptance, if required by the story, is backed by current run-bound evidence from the authorized environment; mocks and source tests are not promoted to production proof.
- GPT-PM gives fresh approval for the exact final head and correlated evidence before push/PR. A later code change requires a new approval.
- `docs/sdlc/acceptance.md` records each S2 story as accepted, rejected, or carried with evidence and reason. One PR is used for S2. S3 begins only after S2 acceptance and required gates are complete.

## Current sprint disposition

| Story | Decision | Evidence / limitation |
|---|---|---|
| S2-1 | Source/test accepted; delivery open, exact-head approval and push pending | Four-file WSL suite 130/130; source-fidelity suite 5/5 at `206a746`; adapter functional 38/38 at exact committed HEAD `6952469`. GPT-PM request `4fb1b534-e56e-46da-8a0c-1a0366d9597e` resolved S2-REVIEW-01 but retained S2-REVIEW-02 MAJOR/HOLD. The correlated-reply parser fix and end-to-end matched/mismatch cases are committed; fresh PM review and push remain. Runtime remains unproven. |
| S2-2 | Accepted — source/test only | GPT-PM transport decision `b0f60d46-42b7-486a-b2f0-5d2253780f55`; WSL run record `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md` (34 passed; peer credentials, pidfd, filesystem metadata mocked). |
| S2-3 | Carried / next | Exact bundle review and conditional WSL preparation/qualification are not evidenced as complete in the reconciled sources. Codex prepares; GPT-PM adjudicates the exact bundle. |
| S2-4 | Carried — genuine provenance/runtime evidence incomplete | `S2-DISPATCH-M01` is MAJOR/OPEN. Codex owns machine-contract correction, bounded preparation and measurements; GPT-PM owns contract review; operator owns exact production policy authorization and reserved custody/human-signature actions. Current human E5 is unchanged. Restricted selectors remain `NOT_RUN`. |
| S2-5 | Carried — final gate pending | No final exact-head GPT-PM approval for full S2 is recorded. Codex coordinates the submission after S2-3/S2-4 and reviews complete. |

### Focused test maintenance note

Historical item, resolved in change0551: Codex reconciled the exploratory selector `test_pre_0473_schema_v5_pending_recovery_event_survives_fresh_reconciliation_and_allows_only_authorized_successor` in `tests/vst/test_s2_persistent_runner_service.py`. It assumes a Store with `PRAGMA user_version == 5`, while both baseline `9c1be0f` and current source declare schema version 6. The selector is outside TP-26/27 acceptance and was excluded from the final focused assignment-basis run; do not silently change its historical fixture or count its failure against the accepted S2 candidate tests. Resolution: the designated functional-test reviewer restored a true schema-v5 fixture and reported six passing cases over two selectors; see `evidence/s2-legacy-v5-fixture-run-20261029.md`. Include its permitted regression only after the final S2 code freeze.

## Required evidence references

- Requirements and current limitation register: `docs/sdlc/requirements.md`.
- Current S2 coordinator/runtime adjudication and correlated decisions: `core/STATE.md`, “Current S2 coordinator/runtime adjudication — 2026-10-29”; `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`.
- S2 source/test backlog and M03 source/test closure: `core/BACKLOG.md`, “S2 — signed dispatch-instruction provenance and owner relay”; `docs/sdlc/evidence/s2-cross-generation-outcome-recovery-exact-source-review-20261029.md`.
- Transport test details and limits: `docs/sdlc/evidence/s2-dispatch-owner-transport-wsl-run-20261029.md`.



## Evidence file: design.md (sha256 6febd304cda3079dbc21888ece272d5ae8e4942d769d2e4104f8830fbbf32959)
# S2 exact runtime bundle and revision transition

Sprint: `39b7cc253f5d` (active S2)
Design scope: source/config preparation and a reversible, bootstrap-only artifact transition from the observed runtime `d5001797cb94113efd9a8dc26e4a15f2dc130976` to source revision `9c1be0fbe42b48f7a9cd547be36af23413fcfc8e`. This transition is supported only while the host remains unconfigured; upgrades of configured hosts are refused and deferred to a separately reviewed design.

## Goal and non-goals

Prepare the smallest reproducible, non-secret deployment description and a safe way to select the exact initial runtime revision on the observed unconfigured host, while retaining the previous revision. Keep all S2 services inactive until their separately gated configuration and activation prerequisites pass verification.

This design does not create or impersonate an instruction issuer, sign E5, execute provisioning, migrate or initialize a Store, activate a service, dispatch work, or close S2. It does not add a scheduler, coordinator, or assignment authority: GPT-PM accepted the existing bounded `DispatchOwnerService` → authenticated Supervisor/Store → filtered Pub/Sub → `StoreBackedDispatcher` path; production M01 remains open pending real authorized runtime evidence (`docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`). The machine issuer/attestor source design is accepted in principle only; production signing and attestation remain gated by the separate trust-contract review recorded by GPT-PM.

## Current behavior and evidence

The point-in-time WSL inventory records `/opt/vst-runtime` resolving to the immutable `d5001797…` directory, and Supervisor, Runner, and Signer units loaded but inactive. It found no Store database by immediate-entry metadata inspection, so Store disposition remains **UNKNOWN**, not “fresh” (`docs/sdlc/evidence/s2-runtime-bundle-inventory-20261029.md`). The observed identity and UID/GID availability is not a reservation; repeat collision checks immediately before any authorized identity creation.

`tools/qa/install_wsl_runtime.ps1` packages the committed HEAD and writes a root-only source manifest containing schema, full HEAD, and archive SHA-256. `tools/qa/install_wsl_runner_runtime.sh` installs a versioned `/opt/vst-runtime-<HEAD>` tree with a matching manifest and checks systemd unit bytes. Both installers deliberately fail closed if `/opt/vst-runtime` already selects a different revision or an installed unit differs. They install immutable artifacts; they do not implement revision switching, rollback, or service activation. The old runtime and versioned worker helper are retained and must not be overwritten or deleted. `docs/sdlc/S2_VERSIONED_WORKER_HELPER_DESIGN.md` records the same no-overwrite rule for the helper. The inventory shows `/etc/vst-runner`, `/run/vst-supervisor`, and `/run/vst-runner` absent, and the observed relevant loaded units inactive. This supports only a first-deployment transition while those preconditions still hold; it is not evidence for a configured-host upgrade.

Service loaders are strict contracts, not config generators: Supervisor requires its exact field set (`tools/vst/supervisor_service.py`), Runner binds the full helper commit, source digest, binary digest, and exact versioned helper path (`tools/vst/runner_service.py`), Signer has a separate key/ledger contract (`tools/vst/signer.py`), Dispatcher has fixed Supervisor/Runner socket paths (`tools/vst/dispatcher_service.py`), and Dispatch Owner accepts only the fixed principal/OpenSSL contract plus a root-controlled trust registry (`tools/vst/dispatch_owner_service.py`). `tools/vst/systemd/README.md` documents the root-owned config paths, service identities, startup preflight, inactive-by-default operator peer, schema-v6 migration gate, and unit ordering.

## Design

Keep the deployment description separate from secrets and executable authority. Add one canonical, non-secret bundle manifest during source/config preparation. It binds:

- repository identity, full source HEAD, exact archive SHA-256, `docs/SANDBOX_SPEC.md` digest, source-manifest schema, and hashes of all six shipped systemd unit files;
- the exact runtime and worker-helper paths, full helper HEAD, helper source and binary digests, and the expected root/group/mode metadata;
- each service config's schema/field set and intended absolute path, owner, group, and mode; fixed service UID/GID and socket/cgroup relationships; and the required unit start order;
- Store disposition as `UNKNOWN`, `FRESH`, or `EXISTING`, with evidence reference. `UNKNOWN` blocks Store initialization, migration, and service activation. It does not block selecting inactive code artifacts because the bootstrap transition neither opens nor changes Store data. An existing Store is read-only inspected and any migration remains behind its separate gate;
- key purpose, custody owner, and expected key-file path only. Never include private key bytes, passwords, tokens, or signing material. Public trust entries may name a verified public-key path and key ID, but must not be fabricated to make validation pass;
- the prior selected runtime, prior unit digests, and rollback target so the transition is reviewable and recoverable.

Config examples produced at this stage are explicitly non-installable templates: values for runtime keys, issuer identity, signed probe, operator attestation, and unresolved Store disposition remain absent. Do not write placeholder JSON into privileged config paths. A schema validator should reject missing values and any unknown field before installation; the existing loaders remain the final runtime contract.

### Ordered operational stages

1. **Source and config preparation (non-privileged).** Finish source changes and their required test/review gates first. Rebuild the archive from the canonical checkout at the exact reviewed HEAD; record archive, sandbox-spec, helper, and unit digests. Prepare the manifest and non-installable schema templates. Reconcile it with the accepted conditional PM scope in `docs/sdlc/evidence/s2-coordinator-runtime-adjudication-20261029.md`. No WSL state changes.
2. **Artifact staging (conditional GO only).** Recheck host identity and exact old runtime, helper, and unit fingerprints. Require `/etc/vst-runner`, `/run/vst-supervisor`, and `/run/vst-runner` absent; require all six S2 service/socket units inactive, no systemd jobs for them, and no nonempty S2 service cgroups. Verify that the exact new versioned runtime and helper destinations are absent, then install them with no-replace semantics and verify owner, group, mode, manifests, and every digest. Do not create identities, configs, sockets, or Store data in this stage. Store remains UNKNOWN and unopened. Keep every old immutable artifact. Any failed precondition or destination collision aborts before selector or unit changes.
3. **Bootstrap artifact selection (new code required).** Add a separate explicit root transition operation limited to that unconfigured state. It rechecks every staging precondition immediately before mutation and verifies exact old selector/link and fixed-name unit bytes plus exact staged runtime/helper fingerprints against the reviewed manifest. It must refuse if any service config/runtime/socket directory exists, any relevant unit is active/has a job, an S2 cgroup is nonempty, any baseline fingerprint differs, or a destination is unexpected. Preserve old selector and unit bytes as a verified rollback snapshot. Replace the selector and each unit file through same-filesystem temporary files and atomic rename; each individual rename is atomic, while the multi-path set is not one atomic transaction. Record completed replacements in a root-owned transition journal before proceeding to the next path. Re-read and verify all selected paths and fingerprints. Never start, enable, or reload a service as part of selection. This design explicitly refuses configured-host upgrades; support for them needs a later independent cutover/rollback design.
4. **Configuration and Store classification (separately gated).** Only after artifact selection, recheck identities and inspect Store using the authorized procedure. Install exact root-owned configuration only when all values and trust references are known. Store UNKNOWN continues to block initialization, migration, and activation; an EXISTING Store remains read-only until its separate migration gate. Do not generate issuer authority or attestation keys as a side effect of artifact selection.
5. **Service activation (blocked).** Keep units disabled/inactive and production dispatch fail-closed until an authorized issuer policy/key and the applicable accepted machine or human E5 trust contract exist, plus authentic fresh run-bound host/probe evidence passes against the exact sandbox-spec and policy digests. A machine attestation must be explicitly machine-labelled, sourced from independent trusted measurements, and accepted under its own versioned trust domain; it must never masquerade as a human signature. Then, only within the accepted mapped scope and separate activation gate, execute the precise unit activation and runtime E2E sequence. Restricted process/crash/mutation/policy selectors remain `NOT_RUN`.

## State ownership and failure behavior

### Staging and journal implementation contract

Use two different manifests. The reviewed pre-stage source plan binds source HEAD, archive,
sandbox spec, helper source/build recipe, shipped unit bytes and fixed target paths. It does not
claim installed-runtime or compiler-result provenance. After stage-only finishes, a read-only
target-host `prepare` emits a second canonical manifest with the actual complete new tree and
helper binary digests plus the exact old selector/unit/runtime baseline. GPT-PM must review that
second manifest's digest before selector mutation; a locally calculated digest is not approval.

Add an explicit `--stage-only` argument to the distro runtime installer and a corresponding
`-StageOnly` argument to the Windows handoff. Launch the selector with Python `-B -I -S` and
load it from the fixed full-versioned runtime path so importing it cannot create `__pycache__`
inside the immutable measured tree. The repository wrapper must disable bytecode before import.
Default install behavior stays fail-closed and
unchanged. Stage-only validates the same source archive, host restrictions and immutable tree,
installs only the absent versioned runtime/helper, and must skip the fixed selector/unit
collision checks and ALL selector/unit writes. Report `selected=false`; the separate bootstrap
transition consumes the staged tree, never calls the default installer, and verifies its complete
tree against the source bundle plus helper identity before mutation. Stage-only is not selection
or authority to activate anything.

There are two distinct reviewable records. Before staging, a source/staging plan derived from
the committed archive binds HEAD, archive/spec/unit/helper-source hashes, compile flags and
requested fixed destinations; compiler identity and any missing prerequisites remain explicit,
not invented. This reviewed plan and source/test gate are prerequisites to artifact installation.
After staging, a separate read-only `prepare` operation binds the actual complete installed tree,
compiled helper digest/metadata and current old selector/unit baseline. Its exact manifest digest
must be reviewed before selection. A prepared selection manifest cannot retroactively authorize
earlier staging. Neither manifest is a GPT approval, authority delegation or activation permit.

Use a write-ahead journal under a root-owned, mode-0700, no-follow transition directory with
exclusive lock. Before any replacement, persist the exact old and new fingerprints, retained
old bytes/link target, ordered paths and manifest digest; fsync the journal and containing
directory. For each path persist/fsync `intent`, recheck current old fingerprint, rename the
prepared file/link, fsync its parent directory, verify new fingerprint, then persist/fsync
`complete`. A missing completion record never proves a rename did not happen. Recovery checks
EVERY path against old AND new fingerprints, regardless of progress flags: old means untouched
or already restored, new means eligible for exact old restoration, anything else means unresolved
and prohibits writes/start. Refuse an unfinished prior journal on normal apply; explicit recovery
requires its exact original manifest digest and the same inactive/unconfigured preconditions.
Persist/fsync restore intent and completion around each restoration too. Snapshots and journal
are retained, never deleted by successful apply/recovery. No process-crash test is authorized;
later source tests use deterministic injected exceptions only.

The Git source/archive owns revision identity; the root-owned manifest owns the deployment's immutable digest record; systemd owns active unit/process state; the root-controlled Store remains the sole assignment/lease authority; and each root config references purpose-separated key paths without transporting secret bytes in the bundle. No cross-service atomic transaction is assumed. During bootstrap selection, the selector and each fixed-name unit file are changed only while the host is unconfigured and all affected units are inactive. Atomicity applies per rename only. A root-owned journal records progress across the selector and unit replacements. A partial transition fails closed: keep services stopped, inspect which exact renames completed, and restore the prior selector and each old unit file from the verified snapshot before any start. If rollback cannot be proven, leave services inactive and stop for recovery; never claim a collectively atomic replacement. Never infer success from a command exit alone: re-read selector, files, ownership, digests, unit states, and Store/claim disposition.

If the host differs from its reviewed baseline, an unexpected config/key or Store mutation is observed, a key or required signature is unavailable, or any per-path replacement/rollback cannot be proven, stop before modifying that dependency. Store UNKNOWN alone does not block inactive artifact staging/selection, but it blocks any Store initialization, migration, or activation. Preserve all prior runtime/helper artifacts and evidence. No automatic retry may reinterpret an ambiguous dispatch result or reactivate production dispatch.

## Rollback

Before the selector/unit transition, rollback is simply to leave the old selector and units untouched; newly installed versioned artifacts remain retained and inactive. After transition starts but before any service start, use the journal to restore the old selector and each unit file through individual atomic renames, verify their hashes and inactive state, and retain the new immutable tree for diagnosis. These operations are recoverable as a sequence, not one atomic transaction. Once any service starts, do not use this bootstrap rollback as a live downgrade: first reconcile Supervisor/Store/Runner claims and outcomes under the existing recovery contract, then use a separately reviewed and authorized stop/rollback procedure. Never delete or overwrite the old runtime or helper.

## Acceptance and verification plan

The design is accepted when the bundle is deterministic for the exact reviewed HEAD and contains no secret material; schema templates map exactly to existing loaders; Store UNKNOWN/EXISTING states cannot trigger initialization or migration; artifact staging preserves prior artifacts; bootstrap selection refuses a configured host, active/job-bearing units, nonempty S2 cgroups, stale baseline, collision, digest mismatch, and incomplete rollback metadata; the journal recovers interrupted per-path replacements; and no unit is activated by preparation or selection. Configured-host upgrades remain unsupported and must be refused. After implementation is complete, assigned functional/e2e test owners should verify archive/hash binding, schema rejection, no-overwrite behavior, interrupted transition recovery, per-path selector/unit rollback, inactive-unit invariants, refusal on configured hosts, and permitted mapped runtime evidence. No tests, checks, provisioning, migration, or service activation were run for this design artifact.

## Ownership and remaining gate

Codex owns the manifest/schema-preparation and reversible transition implementation plus permitted evidence. GPT-PM owns architecture/source adjudication and the exact-head final gate. The operator is the sole human owner for any human attestation and for genuine key-custody actions. GPT-PM accepted bounded machine trust in principle, but the precise versioned issuer/attestor contracts, independent measurement provenance, key custody/revocation, and separate production authority gate remain incomplete. Until those contracts are reviewed and their applicable evidence is genuine and verified, activation and production dispatch remain blocked, and S2 remains open.

GPT-PM adjudicated the machine issuer/attestor architecture under request `a3e130f0-9aec-4304-b001-388a45c0be55` (reply `0b0b8a4d-0816-4146-ba21-71857b5de49d`): bounded machine trust is accepted in principle, but production signing/attestation remain held pending corrected provenance, independent measurements, and separate authority review. This decision does not authorize production keys, replace the active E5 contract, or activate services. The design must be amended with the precise versioned trust contracts before those components are used.
