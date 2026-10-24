"""Shared builders for the E1-E4 tests (valid, signed, deterministic objects).

Remediation A: keys are >= 32 bytes and distinct per role (worker, supervisor,
operator); manifests carry author_principal / required_tests / allowed_commands
/ required_rules; receipts carry manifest_sha256; waivers are operator-signed.
"""

from __future__ import annotations

import copy

from tools.vst import contracts, signing

# Three distinct keys, each >= 32 bytes (asserted in test_e1_contracts).
KEY = b"worker-key-0123456789-abcdefghij!!"
SUPERVISOR_KEY = b"supervisor-key-0123456789-abcdefgh"
OPERATOR_KEY = b"operator-key-0123456789-abcdefghij"
WRONG_KEY = b"wrong-key-0123456789-abcdefghijkl"

HEAD = "a" * 40
HEAD2 = "b" * 40
ROLE = "c" * 64
EPOCH = 2
TASK = "T1"
STORY = "story-1"
AUTHOR = "author-y"
REVIEWER = "reviewer-x"
SUPERVISOR_SLOT = contracts.SUPERVISOR_SLOT
TEST_ARGV = ["pytest", "-q"]


class FakeClock:
    """Injectable clock; tests advance it explicitly (no sleeping)."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _derived_manifest_fields(m: dict) -> dict:
    """Default required_tests / allowed_commands / required_rules for the slots of m.

    Every TestRun slot gets tests t1,t2 (accepting the first acceptance id) and
    the command `pytest -q`; every StaticAnalysis slot gets rule R1. Robust to
    deliberately malformed overrides (non-dict slot entries are skipped).
    """
    slots = m.get("required_receipts")
    slots = [s for s in slots if isinstance(s, dict)] if isinstance(slots, list) else []
    acc = m.get("acceptance")
    first = acc[0] if isinstance(acc, list) and acc and isinstance(acc[0], str) else "AC-1"
    tests, commands, rules = [], [], []
    for s in slots:
        name, rtype = s.get("slot"), s.get("receipt_type")
        if not isinstance(name, str):
            continue
        if rtype == "TestRun":
            tests.append({"slot": name, "test_id": "t1", "acceptance": [first]})
            tests.append({"slot": name, "test_id": "t2", "acceptance": [first]})
            commands.append({"slot": name, "argv": list(TEST_ARGV)})
        elif rtype == "StaticAnalysis":
            rules.append({"slot": name, "rule_id": "R1"})
    return {"required_tests": tests, "allowed_commands": commands, "required_rules": rules}


def manifest(**overrides) -> dict:
    m = {
        "task_id": TASK,
        "project_id": "proj",
        "phase": 4,
        "story_id": STORY,
        "base_head": HEAD,
        "scope": ["src/app.py", "tests/test_app.py"],
        "forbidden_actions": ["push"],
        "owner_role": "implementer",
        "role_sha256": ROLE,
        "skills": [{"id": "skill-a", "sha256": "d" * 64}],
        "model_policy": "sonnet-medium",
        "tools": ["Read", "Edit"],
        "acceptance": ["AC-1", "AC-2"],
        "required_receipts": [
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "static", "receipt_type": "StaticAnalysis"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        "author_principal": AUTHOR,
        "timeout_sec": 600,
        "cost_cap": 100,
        "retry_cap": 1,
    }
    m.update(overrides)
    for name, value in _derived_manifest_fields(m).items():
        if name not in overrides:
            m[name] = value
    return m


def doc_manifest(**overrides) -> dict:
    """Manifest whose required slots include a Documentation slot (plus review)."""
    kwargs = {
        "required_receipts": [
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "doc", "receipt_type": "Documentation"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ]
    }
    kwargs.update(overrides)
    return manifest(**kwargs)


def mhash(m: dict) -> str:
    """manifest_sha256 of a (valid) manifest."""
    return contracts.manifest_sha256(m)


MANIFEST_SHA = mhash(manifest())


_COMMON = {
    "receipt_id": "r-1",
    "task_id": TASK,
    "manifest_sha256": MANIFEST_SHA,
    "slot": "tests",
    "attempt": 1,
    "prev_receipt_sha256": None,
    "candidate_head": HEAD,
    "epoch": EPOCH,
    "runner_id": "runner-1",
    "role_sha256": ROLE,
    "resolved_model": "sonnet-5.5",
    "invocation_id": "inv-1",
    "created_at": "2026-10-24T00:00:00Z",
}

_TYPE_DEFAULTS = {
    "TestRun": {
        "expected_test_ids": ["t1", "t2"],
        "executed_test_ids": ["t1", "t2"],
        "skipped_test_ids": [],
        "xfail_test_ids": [],
        "commands": [{"argv": list(TEST_ARGV), "exit_code": 0}],
        "covered_acceptance": ["AC-1"],
        "artifact_digests": {},
    },
    "StaticAnalysis": {
        "coverage": "FULL",
        "covered_rules": ["R1"],
        "unsupported_rules": [],
        "covered_acceptance": [],
    },
    "IndependentReview": {
        "reviewer_principal": REVIEWER,
        "author_principal": AUTHOR,
        "covered_acceptance": ["AC-2"],
        "findings": [],
        "signed_verdict": "APPROVE",
    },
    "Documentation": {
        "check_description": "doc check",
        "covered_acceptance": [],
    },
}

_DEFAULT_SLOT = {
    "TestRun": "tests",
    "StaticAnalysis": "static",
    "IndependentReview": "review",
    "Documentation": "doc",
}


def unsigned_receipt(rtype: str = "TestRun", **overrides) -> dict:
    """Receipt of `rtype` with derived (or overridden) result and NO signature.

    Bound to manifest() via manifest_sha256 unless `manifest_sha256=` is given.
    """
    r = copy.deepcopy(_COMMON)
    r["slot"] = _DEFAULT_SLOT[rtype]
    r["receipt_type"] = rtype
    r["result"] = "PASS"
    r.update(copy.deepcopy(_TYPE_DEFAULTS[rtype]))
    explicit_result = "result" in overrides
    r.update(copy.deepcopy(overrides))
    if "receipt_id" not in overrides:
        r["receipt_id"] = f"r-{r['slot']}-{r['attempt']}"
    if not explicit_result:
        probe = dict(r)
        probe["result"] = "PASS" if rtype == "Documentation" else "FAIL"
        r["result"] = contracts.derive_result(probe)
    return r


def receipt(rtype: str = "TestRun", key: bytes = KEY, **overrides) -> dict:
    """Fully valid signed receipt (signature over everything else)."""
    r = unsigned_receipt(rtype, **overrides)
    r["signature"] = signing.sign(r, key)
    return r


def bound(m: dict, rtype: str = "TestRun", key: bytes = KEY, **overrides) -> dict:
    """Signed receipt bound to manifest `m` (use with non-default manifests)."""
    return receipt(rtype, key, manifest_sha256=mhash(m), **overrides)


def supervisor_receipt(
    text: str = "WORKER_LOST",
    attempt: int = 1,
    prev: str | None = None,
    key: bytes = SUPERVISOR_KEY,
    **overrides,
) -> dict:
    """Documentation receipt in the reserved supervisor slot (supervisor-signed).

    WORKER_LOST -> INCONCLUSIVE; any other marker -> BLOCKED, unless overridden.
    """
    kw = {
        "slot": SUPERVISOR_SLOT,
        "attempt": attempt,
        "prev_receipt_sha256": prev,
        "check_description": text,
        "runner_id": "supervisor",
        "receipt_id": f"sup-{attempt}",
        "result": "INCONCLUSIVE" if text == "WORKER_LOST" else "BLOCKED",
    }
    kw.update(overrides)
    return receipt("Documentation", key, **kw)


def resign(r: dict, key: bytes = KEY) -> dict:
    body = {k: v for k, v in r.items() if k != "signature"}
    out = dict(body)
    out["signature"] = signing.sign(body, key)
    return out


def waiver_body(**kw) -> dict:
    """Unsigned waiver covering slot 'tests' / AC-1, bound to manifest(), HEAD, EPOCH."""
    w = {
        "record_id": "W-1",
        "operator": "operator-ivan",
        "task_id": TASK,
        "epoch": EPOCH,
        "head": HEAD,
        "manifest_sha256": MANIFEST_SHA,
        "waived_slots": ["tests"],
        "waived_acceptance": ["AC-1"],
        "expires_epoch": EPOCH,
    }
    w.update(kw)
    return w


def signed_waiver(key: bytes = OPERATOR_KEY, label: bytes = signing.WAIVER_LABEL, **kw) -> dict:
    """Waiver signed by `key` under `label` (defaults: operator key, WAIVER_LABEL).

    Field overrides are applied BEFORE signing, so a binding failure is tested
    with a cryptographically valid waiver.
    """
    w = waiver_body(**kw)
    w["signature"] = signing.sign(w, key, label)
    return w


def happy_receipts() -> list[dict]:
    return [receipt("TestRun"), receipt("StaticAnalysis"), receipt("IndependentReview")]


# ---------------------------------------------------------------- store helpers
# Remediation B: Store(path, clock, *, event_key), register_task before leases,
# supervisor_key on lease acquisition. These helpers keep the E3/E4/E5 call
# sites short; they never hide the key arguments that the tests exercise.

EVENT_KEY = b"event-key-0123456789-abcdefghijkl!"
OTHER_EVENT_KEY = b"other-event-key-0123456789-abcdefgh"
STORY2 = "story-2"
OWNER_TTL = 100.0
WORKER = "runner-1"  # equals the runner_id of every default receipt


def open_store(path: str, clock=None, *, event_key: bytes = EVENT_KEY, **kw):
    """Store on `path` (imported lazily so E1/E2 never need the store)."""
    from tools.vst.store import Store

    return Store(path, clock if clock is not None else FakeClock(), event_key=event_key, **kw)


def new_env(path: str, clock=None, *, slots: int = 2, register: bool = True):
    """(store, clock, epoch): slots, open story STORY, owner-a at OWNER_TTL, T1 registered."""
    clock = clock if clock is not None else FakeClock()
    store = open_store(path, clock)
    store.init_slots(slots)
    store.open_story(STORY, "proj", 4)
    epoch = store.acquire_epoch(STORY, "owner-a", OWNER_TTL)
    if register:
        store.register_task(manifest())
    return store, clock, epoch


def lease(store, epoch: int, task: str = TASK, worker: str = WORKER, attempt: int = 1,
          ttl: float = 30, story: str = STORY, supervisor_key: bytes = SUPERVISOR_KEY) -> None:
    """acquire_lease with the keyword supervisor_key filled in."""
    store.acquire_lease(task, story, worker, epoch, attempt, ttl, supervisor_key=supervisor_key)
