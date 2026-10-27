# S3 Temporal SDK feature-profile screen — 2026-10-27

## Scope

Read-only inspection of the official Temporal Python SDK source at pinned commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`. No SDK source, wheel, or dependency was downloaded into the repository; no package was installed, built, or executed.

## Source observations

- The pinned `pyproject.toml` declares `temporalio` 1.34.0, Python `>=3.10`, and direct runtime requirements `nexus-rpc==1.4.0`, `protobuf>=3.20,<8`, `types-protobuf>=3.20,<8`, and `typing-extensions>=4.2,<5`. `python-dateutil` is conditioned on Python `<3.11`.
- The same file defines numerous optional integrations (including gRPC, OpenTelemetry, Pydantic, agent frameworks, and cloud integrations) and a large development dependency group. These are not evidence that the S3 pilot should select those extras.
- `uv.lock` uses Python/platform resolution markers for Python 3.10–3.14 and emscripten. It is a multi-environment lock, not a selected Linux x86-64 Python 3.12 runtime closure.
- The pinned Rust bridge crate declares default feature `tls-ring`; `fips` is an optional feature that selects `tls-aws-lc` and `aws-lc-rs`.
- The bridge's direct path dependencies request `temporalio-client` features `envconfig` and `experimental`; `temporalio-common` features `envconfig` and `otel`; and `temporalio-sdk-core` features `ephemeral-server`, `envconfig`, and `prometheus`. The client and SDK-core disable their default features, while `temporalio-common` does not state `default-features = false` in this declaration.
- The pinned Cargo lock is 3,553 lines. This source screen did not resolve the actual feature graph for a chosen platform/profile or independently establish the runtime artifact contents.

## Primary sources

- [Pinned Python project metadata](https://raw.githubusercontent.com/temporalio/sdk-python/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/pyproject.toml)
- [Pinned Rust bridge manifest](https://raw.githubusercontent.com/temporalio/sdk-python/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/Cargo.toml)
- [Pinned Python lock](https://raw.githubusercontent.com/temporalio/sdk-python/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/uv.lock)
- [Pinned Rust lock](https://raw.githubusercontent.com/temporalio/sdk-python/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/temporalio/bridge/Cargo.lock)

## Acceptance disposition

This narrows the source-declared default feature shape but does not establish the S3 selected runtime profile, complete feature-resolved dependency/license closure, reproducible build, wheel provenance, server/SDK compatibility beyond the separately documented narrow fact, or runtime fit. The provisional audit pin remains unchanged; acquisition, build, install, and execution remain NOT APPROVED. S3-G02/G03 remain open.

Owner: Codex owns technical profile/dependency evidence; GPT-PM adjudicates architecture; the operator owns legal and acquisition decisions. Next: define the target Linux/Python profile after the existing gates close, then resolve dependency features and provenance only through an authorized audit/acquisition path.
