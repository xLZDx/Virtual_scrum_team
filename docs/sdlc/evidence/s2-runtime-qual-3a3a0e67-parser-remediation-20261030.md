# S2-4.12c — systemd status parser follow-up — 2026-10-30

Project: `Virtual_scrum_team`  
Current task: S2-4.12c, runtime qualification  
Source HEAD: `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`

## Previous one-shot outcome

GPT-PM authorization `268fd73c-51e0-477a-83c1-5fcd724a5467` was consumed by exactly one direct host invocation under attempt identity `dc22ee55-1f57-44e1-9590-b4e85e6e5db0`. Its exact launcher hash was `6c6e0c6e41bf67c3c170cc08492b45b0c4ae18888741a7fd5d95d7ba6cf16fa1`.

The invocation reached Ubuntu-24.04 WSL, passed HEAD/source-pin/config/boot/runtime predicates, and stopped at `all_9_units_loaded_inactive_dead_no_pid`. All nine `systemctl show` calls exited zero. Captured `--value` arrays were eight service arrays `[`"0","loaded","inactive","dead",""`]` and the socket array `[`"loaded","inactive","dead",""`]`. This suggests (but does not itself prove beyond the exact recorded HOLD) a launcher parser mismatch: it assumed a fixed field order and required `MainPID` for the socket. Evidence and raw artifact hashes are in `s2-runtime-qual-268fd73c-outcome-20261030.md`.

No unit start, root preflight, Owner-to-Runner claim/probe, TestRun, retry, or persistent target mutation occurred. The temporary D: mount was verified read-only and unmounted successfully. The authorization is consumed; do not repeat it.

## Bounded code delta prepared for review

The launcher now requests named `systemctl show` properties without `--value`, parses `key=value` fields by property name, requires `MainPID=0` for `.service` units, and treats MainPID as not applicable for the `.socket` while still requiring `LoadState=loaded`, `ActiveState=inactive`, `SubState=dead`, and empty `Job`. It records the parsed properties/raw lines and per-unit predicate verdicts. No runtime source, configuration, test, or project code was changed.

A new attempt identity and output prefix were assigned to avoid reusing the consumed `dc22ee55` evidence path:

- Attempt identity: `3a3a0e67-5577-4383-8e1b-5bf803727558`
- Launcher SHA-256: `752fbd27920c2514ce77781e417785154605edf16658690b0f7c356d84060c1a`
- Source HEAD and six pinned runtime sources remain as in the prior reviewed candidate; the runtime tuple is unchanged.

This candidate has not been executed. Focused exact-source GPT-PM review and a new correlated single-use authorization are required before another runtime invocation. TestRun and preflight remain `NOT_RUN`.

S2-4 remains `IN PROGRESS`; S2-5 remains queued; overall S2 remains `NOT APPROVED`.


## Independent static review and exact-byte candidate

A read-only `code-reviewer` inspected the `systemctl` parser against all nine captured property arrays (no tests or launcher execution). It found one MINOR fail-open edge: `props.get('Job', '') == ''` would treat a missing property as empty. Although the separate successful `list-jobs` predicate mitigated this, Codex tightened the check to require the `Job` key to exist and equal the empty string. The reviewer confirmed service/socket PID handling matches the captured arrays and other required fields fail closed.

The corrected candidate's SHA-256 is `5b03f670ec0f5adb01508d63d9f27582bde40fc66d0a8b490299721b621389db` (29,899 bytes). It preserves attempt identity `3a3a0e67-5577-4383-8e1b-5bf803727558`, the source/runtime tuple and one-child stdin transport. This candidate has not been executed. Focused exact-source GPT-PM review and a new correlated single-use authorization are still required.


## GPT-PM exact-source verdict — request `d8e9f261-44ab-4229-8c1d-baad9ea8f286`

GPT-PM returned `APPROVED — PARSER FINDING RESOLVED` for the attached exact launcher SHA-256 `5b03f670ec0f5adb01508d63d9f27582bde40fc66d0a8b490299721b621389db`. The hash matched. GPT-PM verified named-property parsing, the service/socket PID distinction, strict present-and-empty `Job`, all fixed nine unit names, preserved source HEAD/pins/runtime tuple/stdin transport/one-child/retry-zero/stage ordering, and zero remaining BLOCKER/MAJOR in this scope. The independent MINOR edge is resolved.

GPT-PM found the attached file is 29,899 bytes; this evidence record was corrected from the earlier declared 29,501 bytes. The exact launcher may be submitted for a separate new one-shot runtime authorization; no execution is authorized by this review. The prior `268fd73c` authorization remains consumed.


## New runtime authorization — request `8ee40d1a-27a4-4e1b-9129-292a58959aa3`

GPT-PM returned `CONDITIONAL GO — AUTHORIZED` for exactly one direct `e2e-runner` host invocation under attempt identity `3a3a0e67-5577-4383-8e1b-5bf803727558`, retry cap zero, exact launcher SHA `5b03f670ec0f5adb01508d63d9f27582bde40fc66d0a8b490299721b621389db`, size 29,899 bytes, and source HEAD `7d1d16f6348e6c00a5a568b5cfbc8caf309194b9`. It binds the immutable run/bootstrap/nonce/selector tuple and six source pins. The only authorized sequence is fresh status and identity checks; if all pass, root preflight → one durable Owner-to-Runner claim/probe → the single exact manifest-bound TestRun selector. Any failed/incomplete/ambiguous predicate consumes the authorization and stops the chain. No retry, restricted selectors, key/credential inspection, migration, persistent WSL change, production activation, or deployment is authorized. The runner's exact outcome is recorded separately when returned.
