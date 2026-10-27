# S3 Temporal exact-pin license source screen — 2026-10-27

## Scope and provenance

Read-only inspection of the license files at the exact commits already pinned for the S3 comparator. This records what the upstream files say; it is not a legal opinion, an acquisition approval, or a complete dependency license inventory. No candidate source or artifact was acquired, copied into this repository, built, installed, or executed.

## Observed source facts

- Temporal Server commit `af08a5e5f2dd40f545f2afac7780daaa6987001e` has a root `LICENSE` whose heading is “The MIT License” and whose copyright lines name Temporal Technologies Inc. (2025) and Uber Technologies, Inc. (2020). It includes the MIT notice-retention condition and “AS IS” warranty language.
- Temporal Python SDK commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94` has a root `LICENSE` headed “The MIT License”; its copyright line names Temporal Technologies Inc. (2022). It includes the MIT notice-retention condition and “AS IS” warranty language.
- The Python SDK's `.gitmodules` identifies `temporalio/bridge/sdk-core` as the `https://github.com/temporalio/sdk-rust.git` submodule. The pinned gitlink commit `e163abd6dc19040064986a63c8b8cf4756ffd320` has `LICENSE.txt` headed “The MIT License”; its copyright line names Temporal Technologies, Inc. (2021). It includes the MIT notice-retention condition and “AS IS” warranty language.

These facts cover the three pinned repository-level license files only. They do not determine applicable terms for transitive Go, Python, Rust, generated, or bundled dependencies; nor do they establish redistribution obligations, organizational compatibility, export restrictions, or legal acceptability.

## Decision ownership and remaining work

- Codex: retain these exact-pin upstream references and continue source-only provenance/compatibility screening without acquiring or executing the candidate.
- Operator: decide whether the identified top-level license evidence is sufficient for the project's legal/acquisition disposition and provide any required organizational approval. No legal conclusion is made here.
- GPT-PM: adjudicate the architecture independently of license disposition.

G03 provenance/compatibility and the candidate comparison remain open. This screen does not close or downgrade them.

## Primary sources

- [Temporal Server LICENSE at the pinned commit](https://github.com/temporalio/temporal/blob/af08a5e5f2dd40f545f2afac7780daaa6987001e/LICENSE)
- [Temporal Python SDK LICENSE at the pinned commit](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/LICENSE)
- [SDK-Core gitlink LICENSE at the pinned commit](https://github.com/temporalio/sdk-rust/blob/e163abd6dc19040064986a63c8b8cf4756ffd320/LICENSE.txt)
- [Python SDK submodule declaration at the pinned commit](https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/.gitmodules)
