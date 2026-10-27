# S3 static candidate comparison — 2026-10-27

## Scope

This is a source-and-record comparison of the three S3 options. It is not the required same-fixture runtime comparison, a final worker selection, or a `TOP` decision. No external candidate source or artifact was acquired, built, installed, or executed. Prohibited process-kill, crash, and mutation cases remain `NOT_RUN`.

## Evidence matrix

| Candidate | Identity / architecture evidence | Material residual risk | Same-fixture runtime state | Current disposition |
|---|---|---|---|---|
| Hand-written VST worker | Local adapter and pilot exist in `tools/vst/worker_adapter.py`, `pilot.py`, and `slice.py`. Prior designated E2E evidence reports 9 adapter and 9 synthetic pilot selectors passing at recorded HEAD `7816aeb` (`VST-029`). | Full S2 sandbox acceptance, cross-process locking, real worker crash/STOP recovery, and production isolation are not established by synthetic fixtures. | `NOT_RUN` for real isolated worker comparison, crash/process-kill, external candidate behavior, and full sandbox proof. | `LOCAL_CONTRACT_BASELINE` only. It is not an active engine or a `QUALIFIED_FALLBACK`; production routing and automatic candidate fallback remain out of scope. |
| BMad Loop | Pin `v0.13.2`, source commit `4a5c45390ff46c0fc28d316004ffe0ed7c8eea60`; source review records project-declared shell hooks and plugins executing under the BMad process with inherited environment/worktree. | Full transitive license/dependency/artifact closure and sandbox compatibility remain `NOT_VERIFIED`; executable project inputs require a proven boundary. | `NOT_RUN`; no candidate was acquired or executed. | Keep as a read-only comparator only; no evidence supports a sandboxed pilot yet. |
| Temporal server + Python SDK | Provisional pins: server `af08a5e5f2dd40f545f2afac7780daaa6987001e`, SDK `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`, Rust source gitlink recorded as `e163abd6dc19040064986a63c8b8cf4756ffd320`. Source screen records the bridge default `tls-ring` and selected source-declared feature requests. | Exact-version dependency notice for `nexus-proto-annotations@v0.1.0` remains `NOT_VERIFIED`; selected runtime closure, independent source-to-wheel verification, general compatibility, server persistence/listener profile, and S2 sandbox fit remain open. | `NOT_RUN`; GPT-PM permits read-only audit only. Acquisition/build/install/execution remain NOT APPROVED. | Retain as the provisional durable-engine comparator only. No candidate win or `TOP` decision. |

## Comparison result

The hand-written worker has the strongest in-repository contract alignment and synthetic evidence, but lacks accepted platform/runtime proof. BMad has a project-input execution surface whose containment has not been demonstrated. Temporal offers a pinned durable-workflow engine and a documented narrow compatibility fact, but adds a server/SDK/native bridge profile whose selected runtime closure, legal notice, artifact provenance, and isolation fit are not closed. These are source/evidence observations, not measured performance or runtime-security conclusions.

The acceptance contract and required scenario denominator are already defined candidate-independently in `docs/S3_WORKER_PILOT_PLAN_2026-10-24.md` sections 3 and 5, including AC-1–AC-15 and the same-fixture scenario denominator. This evidence artifact is the current static status, not a substitute for that contract. The hand-written candidate has bounded synthetic results only; BMad and Temporal have no shared-fixture runtime result. The shared-fixture comparison is therefore still `NOT_RUN` for all candidates.

The only defensible current choice is **no final winner**. The provisional Temporal audit selection is not acquisition or execution approval. The required shared-fixture comparison depends on S2 acceptance, closed candidate legal/provenance/compatibility gates, a fresh run-bound sandbox probe, and any separate acquisition/execution authorization. No `TOP` label is supported. “Fallback” in older notes means only a retained in-repository contract baseline; it must not imply an active or production-qualified fallback.

## Next actions and owners

1. Codex continues permitted read-only audit and records remaining source/profile evidence.
2. GPT-PM adjudicates the architecture and final comparison package.
3. The operator owns legal/acquisition authorization and the final worker choice.
4. After S2 and candidate gates are accepted, the designated `functional-test-reviewer` and `e2e-runner` execute the same permitted fixture for each authorized candidate; prohibited scenarios remain `NOT_RUN`.
