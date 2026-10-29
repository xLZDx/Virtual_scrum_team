# S2 headless Windows observation runtime

## Change

The bounded subprocess adapter now creates Windows children with `CREATE_NO_WINDOW`. The Windows
observation collector runs with a fixed `C:\Windows\System32` working directory and a deliberately
small environment containing only Windows runtime roots, an empty `PATH`, and a profile-specific
`PSModulePath` pinned to the fixed system module directory (`...WindowsPowerShell\v1.0\Modules`
for Windows PowerShell 5 or `...PowerShell\7\Modules` for PowerShell 7). It does not inherit
ambient environment variables or user module-path settings. Windows process identity remains the
current process identity. Non-Windows subprocess behavior retains its prior `/` working directory
and `LC_ALL=C`, empty-`PATH` environment.

`collect_windows_observations()` accepts the explicit `windows-powershell-5` profile by default,
or the opt-in `powershell-7` profile at the fixed `C:\Program Files\PowerShell\7\pwsh.exe` path.
It does not silently switch profiles. The fixed command remains `-NoLogo`, `-NoProfile`,
`-NonInteractive`, and `-ExecutionPolicy Restricted` with the embedded read-only script. The
script addresses WSL through `C:\Windows\System32\wsl.exe`, so the intentionally empty `PATH`
does not make executable lookup depend on ambient state. The chosen profile is preserved in
`raw_command_outputs.collector_profile`, including when the process yields no output.

## Contract and limits

The existing per-command timeout and output caps are unchanged. Missing executables, host startup
errors, timeouts, and output failures remain `UNKNOWN` or `UNSUPPORTED` collection evidence. The
normalizer still reports `UNKNOWN`; `collection_complete` remains false and this collector cannot
produce an E5 attestation, policy verdict, production authority, or `PASS`. The broader Windows
rule/filter query has not been expanded or normalized. PowerShell 7 is a distinct, explicitly
selected diagnostic profile, not an equivalent or fallback replacement for Windows PowerShell 5.

## Provenance and verification

The pre-edit checkout was clean for the two assigned paths at source HEAD
`0cef101ee70be03b0436d82fad459916a79ee65b`. The in-scope observation record is
[`s2-machine-observations-20261029.md`](../sdlc/evidence/s2-machine-observations-20261029.md): it
records the Windows PowerShell 5.1 startup error `8009001d`, zero output, and a separate successful
limited PowerShell 7 profile query; the wider PowerShell 7 query exceeded its 60-second bound.
Those are recorded observations, not reproduced by this change. No collector invocation, runtime
command, test, check, build, CI action, activation, or key/config access was performed for this
change. Runtime behavior remains unverified pending the separately assigned test/evidence phase.

The PowerShell7 module path includes its fixed installation modules and the fixed Windows
system module root, so Windows-only NetSecurity cmdlets remain discoverable without inheriting
user module directories. This root integration correction was made before source freeze; actual
module loading and output remain unverified until the permitted test/evidence phase.
