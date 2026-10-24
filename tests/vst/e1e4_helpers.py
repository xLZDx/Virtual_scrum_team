"""Shared builders for the E1-E4 tests (valid, signed, deterministic objects)."""

from __future__ import annotations

import copy

from tools.vst import contracts, signing

KEY = b"unit-test-signing-key-0123456789"
HEAD = "a" * 40
HEAD2 = "b" * 40
ROLE = "c" * 64
EPOCH = 2
TASK = "T1"
STORY = "story-1"


class FakeClock:
    """Injectable clock; tests advance it explicitly (no sleeping)."""

    def __init__(self, start: float = 1000.0) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


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
        "timeout_sec": 600,
        "cost_cap": 100,
        "retry_cap": 1,
    }
    m.update(overrides)
    return m


def doc_manifest(**overrides) -> dict:
    """Manifest whose required slots include a Documentation slot."""
    base = manifest(
        required_receipts=[
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "doc", "receipt_type": "Documentation"},
        ]
    )
    base.update(overrides)
    return base


_COMMON = {
    "receipt_id": "r-1",
    "task_id": TASK,
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
        "commands": [{"argv": ["pytest", "-q"], "exit_code": 0}],
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
        "reviewer_principal": "reviewer-x",
        "author_principal": "author-y",
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
    """Receipt of `rtype` with derived (or overridden) result and NO signature."""
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


def resign(r: dict, key: bytes = KEY) -> dict:
    body = {k: v for k, v in r.items() if k != "signature"}
    out = dict(body)
    out["signature"] = signing.sign(body, key)
    return out


def happy_receipts() -> list[dict]:
    return [receipt("TestRun"), receipt("StaticAnalysis"), receipt("IndependentReview")]
