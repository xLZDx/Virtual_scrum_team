# S3-B Candidate audit evidence: VST-028

## Date: 2026-11-07
## Scope: Security and sandbox-compatibility audit for S3 worker candidates (BMad Loop v0.10.0 and pilot.py on s3-worker-pilot)

## 1. BMad Loop license review

### Public metadata (GitHub API, no clone)
- Repository: https://github.com/OStashio/BMad-Loop
- Tag: v0.10.0 → commit 8d33e927d42158e034ba28043d1ce4c9ee237716
- License field: **NOASSERTION** (in repo metadata)
- pyproject.toml on main (0.13.2): declares **MIT**
- Status: **LICENSE MISMATCH OPEN** — NOASSERTION in repo vs MIT in source

### Action required
- [ ] Verify actual LICENSE file in tag v0.10.0 
- [ ] Check for any license restrictions/conditions not declared
- [ ] Confirm MIT is valid for our use case

---

## 2. Pilot.py security review (S3-A adapter code)

### Critical findings from code review (citation verification 2026-11-07)

#### MAJOR-001: Unvalidated candidate_head in _validate_response
**Location:** tools/vst/pilot.py:964-991
**Claim:** A SUCCEEDED worker response is accepted without checking the commit.
**Finding:** Identity checks exist (epoch, fence, request fields) but NO validation that:
  - candidate_head exists in git repository
  - candidate_head descends from base_head
  - diff base_head..candidate_head stays within allowed_paths

**Risk:** Vendor adapter returns arbitrary 40-hex without git evidence. Store holds durable "worker succeeded at head X" with no verification. 

**Recommendation:** Add git validation before accepting SUCCEEDED:
  - git cat-file -e <head>^{commit}
  - git merge-base --is-ancestor base_head head  
  - git diff --name-only base_head head ⊆ allowed_paths

**Status:** NOT_VERIFIED

#### MAJOR-002: Retry failure in resume_epoch_idempotent leaves story stuck
**Location:** tools/vst/pilot.py:872-877 (partial evidence)
**Finding:** resume_epoch_idempotent durably advances epoch. If supervisor fails post-epoch:
  - Retry re-validates prior fence against NEW epoch → BLOCKED (FENCE_REJECTED)
  - Retry hits prior-epoch check before replay logic
  - Result: new epoch held by owner with no lease, misreported "stale fence"

**Risk:** Recovery path permanently disabled after transient supervisor error.

**Recommendation:** Move replay check before epoch validation. Persist intent record on post-epoch failure.

**Status:** NOT_VERIFIED

### Sandbox-compatibility assessment

#### Process containment (S2-4E baseline)
- Owner→Runner auth: Windows Job Object (confirmed S2-4E)
- File access: bounded to sandboxed workspace
- Environment variables: inherited from sandbox
- **Status:** Inherited from S2 baseline, not re-audited in S3

#### Failure scenarios
- Unvalidated candidate_head could escape sandbox path restrictions
- Stuck retry state could prevent graceful shutdown

**Status:** DEPENDENT on MAJOR-001/002 remediation

---

## Conclusion
**S3-B audit readiness:** 2 MAJOR blockers in adapter security (unvalidated input, retry failure). Sandbox-compatibility depends on fixing these. License review open.

**Next step:** Operator decision on whether to remediate MAJOR-001/002 before S3 completion or accept as design limit.
