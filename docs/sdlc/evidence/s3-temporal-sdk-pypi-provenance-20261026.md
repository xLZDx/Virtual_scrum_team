# S3 Temporal Python SDK PyPI provenance update — 2026-10-26

## Scope

Read-only inspection of the official PyPI release page for `temporalio==1.34.0` and PyPI's official attestation-consumer documentation. No wheel, source archive, or candidate was downloaded, built, installed, or executed.

Pinned SDK source: `temporalio/sdk-python` commit `a4c2bb38c3bad43498dfa6bd849e8d85bb684e94`.

## Current PyPI evidence

The current PyPI page marks all eight 1.34.0 release files as having provenance metadata. For the Linux x86-64 `manylinux_2_17` wheel, the page lists SHA-256 `540761f738bdfe5cb5bd7240b659e116a0b5094b94282aef09b8d8c2d66e9c52`; it says the attestation was signed by GitHub Actions and verified by PyPI, identifies the publishing repository as `temporalio/sdk-python`, identifies the publishing commit as the pinned SDK commit above, and links the release workflow and a specific GitHub Actions run.

Sources:

- Official PyPI release page and per-file attestation: <https://pypi.org/project/temporalio/1.34.0/>
- PyPI instructions for consuming attestations: <https://docs.pypi.org/attestations/consuming-attestations/>
- Pinned SDK release workflow: <https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/.github/workflows/release-publish.yml>
- Pinned SDK source metadata: <https://github.com/temporalio/sdk-python/blob/a4c2bb38c3bad43498dfa6bd849e8d85bb684e94/pyproject.toml>

## Reconciliation and limits

This supersedes the earlier read-only observations in changes 0203 and 0206 that the inspected PyPI metadata had `provenance=false`. PyPI's current page now displays provenance for all eight release artifacts. This is positive publisher/source linkage evidence for the published SDK artifact, but this audit did not download the wheel or provenance JSON and did not independently cryptographically verify the attestation. PyPI's own documented verification flow downloads both artifact and provenance and verifies them; that action is not authorized before the separate acquisition decision.

Disposition: **S3-G02 partial evidence** for the published Python SDK wheel only. The selected runtime wheel still needs to be fixed as part of the build/profile decision and independently verified after acquisition is authorized. This does not establish reproducible source builds, Rust Core input closure, the Temporal server binary provenance, server Go dependency closure, or the complete pilot SBOM. S3-G01's exact-version `nexus-proto-annotations@v0.1.0` license/notice gap and S3-G03's full compatibility/runtime questions remain open. No candidate acquisition or execution is approved.

Owner: Codex records the evidence and later performs the authorized verification; GPT-PM adjudicates the architecture gate; the operator retains legal/acquisition authority. Next: finish read-only audit, then request the separate acquisition decision; only after approval may the exact artifact and attestation be downloaded for cryptographic verification.
