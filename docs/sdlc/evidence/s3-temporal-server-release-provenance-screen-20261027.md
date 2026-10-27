# Temporal Server v1.32.1 release metadata screen — 2026-10-27

## Scope and provenance

Read-only inspection of the official GitHub release assets page for the already pinned Temporal Server `v1.32.1` release. No release asset or checksum file was downloaded, no checksum was independently computed, and no server was built, installed, or executed. This is published release metadata, not independent artifact verification or acquisition authorization.

## Observed release metadata

The official expanded assets page lists:

| Asset | Published SHA-256 | Displayed size |
|---|---|---:|
| `checksums.txt` | `2a59896f80e27864c7a817ed54aec9d8f5fd2b82d9a794e09951ec243503f70c` | 606 bytes |
| `temporal_1.32.1_linux_amd64.tar.gz` | `4260448d650c1ba7ee7683ff0c93d5c6a1709260e3a7ef543bfa34e06cff6051` | 95.6 MB |

The tag/release page separately labels source commit `af08a5e5f2dd40f545f2afac7780daaa6987001e` as GitHub-verified. These page claims do not establish that downloaded bytes match the published hashes, that `checksums.txt` is separately signed, or that the Linux binary was built from the pinned source commit. The source-to-binary and reproducible-build questions therefore remain open.

## Acceptance and ownership

- Codex: retain this bounded metadata evidence and continue permitted read-only provenance/compatibility work.
- Operator: decide legal/acquisition disposition before any candidate artifact is obtained.
- GPT-PM: adjudicate architecture; this metadata does not change the accepted design-only decision or grant runtime approval.

S3 remains a read-only comparator. No acquisition, installation, build, execution, or S3 acceptance is inferred.

## Primary source

- [Official Temporal Server v1.32.1 release assets](https://github.com/temporalio/temporal/releases/expanded_assets/v1.32.1)
- [Official Temporal Server v1.32.1 release and GitHub-verified source commit](https://github.com/temporalio/temporal/releases/tag/v1.32.1)
