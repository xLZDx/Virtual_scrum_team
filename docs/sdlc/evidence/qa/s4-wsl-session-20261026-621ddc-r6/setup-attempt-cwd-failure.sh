set -euo pipefail
in=/tmp/vst-s4-621ddc01-inbound-r4.tar.gz
[ ! -e "$in" ] || { echo 'inbound path already exists'; exit 31; }
cat > "$in"
actual_size=$(/usr/bin/stat -c %s "$in")
actual_sha=$(/usr/bin/sha256sum "$in" | /usr/bin/cut -d' ' -f1)
printf 'PAYLOAD_BYTES=%s PAYLOAD_SHA256=%s\n' "$actual_size" "$actual_sha"
[ "$actual_size" = 5366579 ]
[ "$actual_sha" = 6f6bd31687c75237c3def4fdb3acb011bb591534675ace5e98833a995b270d7f ]
mkdir -p /tmp/vst-s4-621ddc01-inbound-r4
/usr/bin/tar -xzf "$in" -C /tmp/vst-s4-621ddc01-inbound-r4
repo=/tmp/vst-s4-candidate/repo
idtarget=/tmp/vst-s4-621ddc01-identity-deps
seedtarget=/tmp/vst-s4-621ddc01-seeded-deps
idscratch=/tmp/vst-s4-621ddc01-identity-scratch
seedscratch=/tmp/vst-s4-621ddc01-seeded-scratch
[ ! -e /tmp/vst-s4-candidate ] && [ ! -e "$idtarget" ] && [ ! -e "$seedtarget" ] && [ ! -e "$idscratch" ] && [ ! -e "$seedscratch" ]
/usr/bin/mkdir -p /tmp/vst-s4-candidate
/usr/bin/git init -q "$repo"
/usr/bin/git -C "$repo" fetch -q /tmp/vst-s4-621ddc01-inbound-r4/candidate.bundle refs/heads/s4-canonical-continuation
/usr/bin/git -C "$repo" checkout -q --detach FETCH_HEAD
head=$(/usr/bin/git -C "$repo" rev-parse HEAD)
status=$(/usr/bin/git -C "$repo" status --porcelain)
manifest=$(/usr/bin/sha256sum "$repo/docs/qa/categories.json" | /usr/bin/cut -d' ' -f1)
printf 'HEAD=%s\nSTATUS=%s\nREGISTRY_SHA256=%s\n' "$head" "$status" "$manifest"
[ "$head" = '621ddc01d1b5bbf701ccced7bb073c26e89c8c07' ]
[ -z "$status" ]
[ "$manifest" = '7b03dd4ac32b671a5e9a9a95a04c717dd6af2628dfda5d485d712788a4f2dd7a' ]
/usr/bin/chown -R 997:988 /tmp/vst-s4-candidate
/usr/bin/getent passwd 997
/usr/bin/getent group 988
/usr/bin/test -x /usr/bin/setpriv
/usr/bin/test -x /usr/bin/python3.12
old=/usr/local/libexec/vst-s4-worker-exec
oldsha=$(/usr/bin/sha256sum "$old" | /usr/bin/cut -d' ' -f1)
oldstat=$(/usr/bin/stat -c '%u:%g:%a' "$old")
oldver=$(/usr/bin/env -i PATH=/usr/bin:/bin "$old" --version)
printf 'OLD_HELPER_SHA256=%s OLD_HELPER_STAT=%s OLD_HELPER_VERSION=%s\n' "$oldsha" "$oldstat" "$oldver"
[ "$oldsha" = '6973df62818be76759f87e1231b6a5dfea4b64c08f16fb19f1b6c77975818e68' ]
[ "$oldstat" = '0:988:4750' ]
[ "$oldver" = 'schema=1 head=4fe150326a36faf401b045cfa1b9a2e64d89436b source_sha256=8c1a5986c8e081a05a3291b65f082fbd3a0dd0f93109a6395dd2bf57d43beb21' ]
backup=/usr/local/libexec/vst-s4-worker-exec.previous-4fe150326a36faf401b045cfa1b9a2e64d89436b
[ ! -e "$backup" ]
/usr/bin/mv -- "$old" "$backup"
/usr/bin/chmod 0750 "$backup"
set -o pipefail
/usr/bin/env -i PATH=/usr/bin:/bin GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_PAGER=cat /usr/bin/git --no-replace-objects --no-pager -c safe.directory="$repo" -c core.fsmonitor=false -c core.hooksPath=/dev/null -C "$repo" show 621ddc01d1b5bbf701ccced7bb073c26e89c8c07:tools/qa/install_wsl_worker_helper.sh | /usr/bin/env -i PATH=/usr/bin:/bin /bin/sh -s -- 621ddc01d1b5bbf701ccced7bb073c26e89c8c07 "$repo"
newsha=$(/usr/bin/sha256sum "$old" | /usr/bin/cut -d' ' -f1)
newstat=$(/usr/bin/stat -c '%u:%g:%a' "$old")
newver=$(/usr/bin/env -i PATH=/usr/bin:/bin "$old" --version)
printf 'NEW_HELPER_SHA256=%s NEW_HELPER_STAT=%s NEW_HELPER_VERSION=%s\n' "$newsha" "$newstat" "$newver"
/usr/bin/mkdir -p "$idscratch" "$seedscratch"
/usr/bin/chown -R 997:988 "$idscratch" "$seedscratch"
runner=/usr/bin/setpriv
common_env=(/usr/bin/env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/vst-s4-621ddc01-pycache)
if "$runner" --reuid=997 --regid=988 --clear-groups "${common_env[@]}" /usr/bin/python3.12 -m tools.qa.prepare_dependencies --repo-root "$repo" --wheelhouse /tmp/vst-s4-621ddc01-inbound-r4/wheelhouse --dependency-target "$idtarget"; then idprep=0; else idprep=$?; fi
printf 'IDENTITY_PREP_EXIT=%s\n' "$idprep"
if [ "$idprep" -eq 0 ]; then
  if "$runner" --reuid=997 --regid=988 --clear-groups "${common_env[@]}" PYTHONPATH="$idtarget" /usr/bin/python3.12 -m tools.qa.run --category identity --repo-root "$repo" --dependency-target "$idtarget" --dependency-wheelhouse /tmp/vst-s4-621ddc01-inbound-r4/wheelhouse --scratch-root "$idscratch" --run-id s4-identity-20261026-wsl-621ddc-r1 --expected-head 621ddc01d1b5bbf701ccced7bb073c26e89c8c07 --report-path docs/sdlc/evidence/qa/identity.report.jsonl --stdout-path docs/sdlc/evidence/qa/identity.stdout.txt --stderr-path docs/sdlc/evidence/qa/identity.stderr.txt; then idrun=0; else idrun=$?; fi
else idrun=125; fi
printf 'IDENTITY_RUN_EXIT=%s\n' "$idrun"
if "$runner" --reuid=997 --regid=988 --clear-groups "${common_env[@]}" /usr/bin/python3.12 -m tools.qa.prepare_dependencies --repo-root "$repo" --wheelhouse /tmp/vst-s4-621ddc01-inbound-r4/wheelhouse --dependency-target "$seedtarget"; then seedprep=0; else seedprep=$?; fi
printf 'SEEDED_PREP_EXIT=%s\n' "$seedprep"
if [ "$seedprep" -eq 0 ]; then
  if "$runner" --reuid=997 --regid=988 --clear-groups "${common_env[@]}" PYTHONPATH="$seedtarget" /usr/bin/python3.12 -m tools.qa.run --category seeded-failure --repo-root "$repo" --dependency-target "$seedtarget" --dependency-wheelhouse /tmp/vst-s4-621ddc01-inbound-r4/wheelhouse --scratch-root "$seedscratch" --run-id s4-seeded-failure-20261026-wsl-621ddc-r1 --expected-head 621ddc01d1b5bbf701ccced7bb073c26e89c8c07 --report-path docs/sdlc/evidence/qa/seeded-failure.report.jsonl --stdout-path docs/sdlc/evidence/qa/seeded-failure.stdout.txt --stderr-path docs/sdlc/evidence/qa/seeded-failure.stderr.txt; then seedrun=0; else seedrun=$?; fi
else seedrun=125; fi
printf 'SEEDED_RUN_EXIT=%s\n' "$seedrun"
printf 'CANDIDATE_HEAD='; /usr/bin/git -C "$repo" rev-parse HEAD
printf 'CANDIDATE_STATUS='; /usr/bin/git -C "$repo" status --porcelain
printf 'MOUNTINFO_SHA256='; /usr/bin/sha256sum /proc/self/mountinfo | /usr/bin/cut -d' ' -f1
printf 'WSL_UID='; /usr/bin/id -u 997
printf 'WSL_GID='; /usr/bin/getent group 988
/usr/bin/mkdir -p /tmp/vst-s4-621ddc01-out
for c in identity seeded-failure; do for x in report.jsonl stdout.txt stderr.txt; do src="$repo/docs/sdlc/evidence/qa/$c.$x"; [ ! -e "$src" ] || /usr/bin/cp "$src" "/tmp/vst-s4-621ddc01-out/$c-$x"; done; done
/usr/bin/tar -czf /tmp/vst-s4-621ddc01-artifacts.tar.gz -C /tmp/vst-s4-621ddc01-out .
printf 'ARTIFACTS_BASE64_BEGIN\n'
/usr/bin/base64 -w0 /tmp/vst-s4-621ddc01-artifacts.tar.gz
printf '\nARTIFACTS_BASE64_END\n'


