# Change 0423: record current S2 Windows/WSL system snapshot

## What changed

- Added a dated, read-only Windows and WSL configuration snapshot at repository HEAD `c528913`.
- Linked the evidence from the S2 backlog/state and RU/EN continuation report without changing any acceptance verdict.

## Why

The accepted task asks Codex to collect permitted S2 Windows/POSIX/system evidence. This snapshot refreshes the point-in-time host and WSL observations while explicitly preserving the distinction between configuration and runtime acceptance.

## Affected paths

- `docs/sdlc/evidence/s2-readonly-static-system-recheck-20261027-0423.md`
- `core/BACKLOG.md`
- `docs/sdlc/STATE.md`
- `reports/S2_S5_CONTINUATION_2026-10-27.html`
- `reports/S2_S5_CONTINUATION_2026-10-27.ru.html`
- `governance/DOCUMENT_REGISTRY.md` (generated)
- `docs/changes/0423-record-current-s2-system-snapshot.md`

## Provenance and decisions

- Starting HEAD: `c528913afc43223d8a5ff81916f349f97001d36c`, branch `s4-canonical-continuation`, canonical checkout `D:\Repo\Virtual_scrum_team`.
- Initial status contained only protected untracked `docs/sdlc/evidence/s2-functional-test-run.md`; that file was not changed, staged, or removed.
- The existing Ubuntu-24.04 WSL2 distro was started by the read-only inventory command and subsequently observed stopped. No new distro or worktree/fork directory was created.
- Windows ActiveStore firewall profiles were enabled with inbound Block and outbound Allow. The Ubuntu static snapshot was taken as root and observed automount/interop disabled, no Windows drive mounts in the filtered output, no Docker socket, nftables input/output `policy drop` with loopback-only accepts, IPv4 forwarding `1`, and IPv6 forwarding `0`.
- These facts do not demonstrate worker identity, process containment, immutability, persistent policy, or end-to-end egress. No packets, tests, process-kill, crash/recovery, or mutation scenarios were run.

## Verification and acceptance

- Documentation hygiene passed: `python tools/build_document_registry.py`, `python C:/Users/koros/.claude/tools/report_conform.py reports --check`, `git diff --cached --check`, and `python tools/build_document_registry.py --check` all succeeded.
- This is a static observation only. S2 Phase 8 remains NOT APPROVED, and restricted scenarios remain NOT_RUN.

## Ordered next steps and owners

1. Codex: complete documentation hygiene and commit the evidence update locally.
2. Codex: continue permitted evidence only where it can close a named S2/S3 acceptance gap; otherwise preserve the present NOT_RUN boundaries.
3. GPT-PM: return the pending S3 architecture adjudication; Codex verifies and records the correlated reply.
