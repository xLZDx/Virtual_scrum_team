# S2 WSL archive line-ending reproduction — exact HEAD `9a5c41d` — 2026-10-28

## Scope and result

This record captures read-only Git archive comparisons at committed HEAD
`9a5c41de5ce2878558402665eafaa0a80c09d177` and read-only inspection of the existing WSL helper.
No installer retry, WSL mutation, helper replacement, or commit was performed.

The host installer had been changed to set `core.autocrlf=false`, but that setting alone does not
prevent CRLF conversion under this repository's `* text=auto` attribute and the host's Windows Git
configuration. The helper script in the resulting archive still had 149 CRLF sequences and
`set -eu\r\n` on line 2. Adding `core.eol=lf` produced an LF-only archive member matching the raw
committed script blob.

## Reproduction

Both comparisons used the committed source at HEAD `9a5c41de5ce2878558402665eafaa0a80c09d177` and
the same archive path set:

```text
tools/vst
tools/qa/install_wsl_runner_runtime.sh
tools/qa/install_wsl_worker_helper.sh
tools/qa/worker_exec.c
docs/SANDBOX_SPEC.md
```

With only the setting present in the committed host installer:

```text
git -c core.autocrlf=false --no-replace-objects archive --format=tar 9a5c41de5ce2878558402665eafaa0a80c09d177 -- <paths above>
```

The `install_wsl_worker_helper.sh` member had SHA-256
`cd3031fab777bf286876087058cc613788499c69d62c5d97632a1fcbbe592bc1`, 7332 bytes, line 2
`set -eu\r\n`, and 149 CRLF sequences.

With both settings:

```text
git -c core.autocrlf=false -c core.eol=lf --no-replace-objects archive --format=tar 9a5c41de5ce2878558402665eafaa0a80c09d177 -- <paths above>
```

The full archive SHA-256 was
`9f613418037e2cc3bf2415c39e18b2a7d10bbf5ad308b9db7635b63c97518181`. Its helper member SHA-256
was `ef14f99d1eed7b3af6624015c55404ea1927bec2387e53c5cc67fe749a5cf1cc`, matching the raw
committed blob. The member was LF-only: line 2 `set -eu\n`, zero CRLF and zero bare-CR bytes.

The comparison was performed in memory using Python's `subprocess`, `tarfile`, and `hashlib`; it did
not write an archive or extracted files. This confirms the additional Git setting repairs line
endings in the archive comparison; it does not claim that the committed installer has been updated
to use both settings or that runtime installation succeeded.

## Existing WSL helper — read-only state

The existing fixed path was inspected without changing it:

```text
Path: /usr/local/libexec/vst-s4-worker-exec
stat: 0:988:4750 (root owner, group 988, setuid mode 4750)
SHA-256: a9d381acab8cbfd299be2e631caeca370f98193271df85fa8583172dbc0591dc
--version: schema=1 head=621ddc01d1b5bbf701ccced7bb073c26e89c8c07 source_sha256=8c1a5986c8e081a05a3291b65f082fbd3a0dd0f93109a6395dd2bf57d43beb21
```

`tools/qa/install_wsl_worker_helper.sh` builds the requested head-bound helper in a temporary
directory. If the fixed destination already exists, the script requires its SHA-256 to equal the
newly built binary and then checks its embedded version. A mismatch exits before `chown` or
`chmod`; it does not overwrite or unlink the existing binary. Only when the destination is absent
does the script install a staged copy and publish it using a no-replace hard link. The existing
621ddc01 helper therefore does not satisfy the current head's identity and must be preserved; the
installer will refuse to replace it.

No WSL installer retry or other WSL mutation was performed for this evidence record. The earlier
attempt's reported `/run/vst-deploy-...` source stage was absent during subsequent read-only
inspection; no manual deletion was performed. The exact failure and environment snapshot remain in
`s2-wsl-installer-preflight-7120e2c-20261028.md`.

## Acceptance boundary and next action

The archive comparison is implementation diagnosis only. It is not system/runtime acceptance, does
not establish an E5 inventory or operator signature, and does not authorize replacing the existing
root-owned setuid helper. Codex owns a reviewed exact-head archive/helper deployment correction;
the e2e-runner may retry only after that correction is committed and its no-overwrite behavior is
verified. GPT-PM owns exact-head adjudication. Any run-bound E5 operator attestation remains a real
operator signature and must not be inferred from this evidence.
