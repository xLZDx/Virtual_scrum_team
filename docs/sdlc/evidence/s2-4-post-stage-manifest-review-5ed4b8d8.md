# S2-4 post-stage manifest review

- PM Bridge request: `5ed4b8d8-1c5f-4e45-9e92-cb14df136fe7`.
- Correlated reply: `315cc40b-9e06-5641-88fc-4ab2ecdd93de` (`correlated=true`).
- Review disposition: **APPROVE — post-stage manifest consistency only; 0 BLOCKER, 0 MAJOR**.
- Reviewed manifest: `s2-runtime-post-stage-manifest-ee69f9fbf074a4c73d2d5d1da81c627a57d06071.json`, SHA-256 `fafaf93158fee300f1b62ea53e8712e8c600b89a7d0b350399de62989cddcc52`.
- Companion post-state SHA-256: `eae2eb9599cc9696b077d9fee5edd624455b17832e5b8bab61eef6c585d14ba1`.
- Companion StageOnly result SHA-256: `d379de13487692c51220554a6cdafeb78241e17c919c284386f4a08b235c8c03`.
- GPT-PM independently verified all three attachment hashes and found the StageOnly result's post-state hash matches the attached post-state.

## Scope and result

GPT-PM confirmed matching source HEAD, source plan, target inventory, source archive, sandbox specification, compiler identity, helper identity/hash/mode, retained previous selector, and all six prospective unit-file identities. The differing proposed Supervisor unit hash is not a StageOnly contradiction: the installer reported zero unit installations and the post-state reported all nine units inactive/dead, no pending jobs, and Store absent.

This approval concerns the artifact's identity and consistency as a record of bounded StageOnly publication. It does **not** approve runtime selection, configuration/key/Store changes, systemd unit installation/reload, service start/enable, E5/probes, Owner-to-Runner, TestRun, restricted selectors, production activation, or S2 closure. S2-4 remains **IN PROGRESS**.

## Tree-hash follow-up

GPT-PM noted that the attached post-state did not independently recalculate the manifest's two complete runtime-tree digests. A subsequent read-only WSL verification addressed that evidence gap:

- The current staged runtime's 47 source-map entries were walked and each path, type, file SHA-256, size, root ownership, mode, and link count was compared with the committed source plan; result: `MATCH_SOURCE_PLAN`.
- `runtime_bundle.tree_sha256('/opt/vst-runtime-ee69f9fbf074a4c73d2d5d1da81c627a57d06071')` returned `a56032e1c58bb04b41e7fe6c31fb60c3df7ca6663aa059b537718524e1450f0f`, matching the manifest.
- The same read-only function returned `dccfb2ed1e065e24d60b6cbe9a7f04534cb318ac5964e3039c88c789158d7882` for the previous selected runtime, also matching the manifest.
- This follow-up read runtime source files only. It did not read configuration or key contents and made no target mutation.

The exact outputs are captured in `s2-4-post-stage-content-verification-ee69f9f-20261030.json`.

## Acceptance boundary and next action

This closes StageOnly publication and post-stage manifest consistency only. Current run-bound E5, a permitted real Owner-to-Runner result, and report-bound TestRun remain `NOT_RUN`; S2-4 is not delivered. The next step is for Codex to prepare a fresh, exact runtime-qualification scope bound to the staged source and current target identity, then obtain its separate one-shot adjudication before any selection or activation. S2-5 remains queued.
