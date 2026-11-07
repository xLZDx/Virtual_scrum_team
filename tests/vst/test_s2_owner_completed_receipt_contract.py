"""Focused Store/Supervisor contract for read-only Owner receipt lookup.

The fixture uses only temporary SQLite state and synthetic in-process records.
It does not exercise Windows services, IPC identities, Runner processes, signing
key custody, preflight probes, or Job Objects; it is not Windows runtime proof.
"""
from __future__ import annotations

import base64
import secrets
import tempfile
import unittest
from pathlib import Path

from tools.vst.contracts import manifest_sha256
from tools.vst.dispatch_owner_client import DispatchOwnerClient
from tools.vst.store import Store
from tools.vst.supervisor import Supervisor


_OWNER = "Codex"
_TASK = "S2-4E-contract-task"
_STORY = "S2-4E-contract-story"
_RUN = "s2-4e-contract-run"
_GENERATION = "s2-4e-contract-generation"
_NOW = 1_000.0
_ZERO_SIGNATURE_B64 = base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("=")
_ZERO_SIGNATURE_HEX = "0" * 64


class _OwnerTransport:
    """Narrow in-process seam to the real Store/Supervisor read APIs."""

    def __init__(self, store: Store, supervisor: Supervisor):
        self.store = store
        self.supervisor = supervisor

    def submit_dispatch_intent(self, **_body):
        raise AssertionError("submission is outside this read-only receipt test")

    def replay_dispatch_outcome(self, *, instruction):
        return self.store.replay_dispatch_outcome(principal=_OWNER, instruction=instruction)

    def completed_dispatch_receipt(self, *, instruction):
        return self.supervisor.completed_dispatch_receipt(
            principal=_OWNER, instruction=instruction,
        )

    def ack_dispatch_intent(self, **_body):
        raise AssertionError("acknowledgement is outside this read-only receipt test")


def _manifest() -> dict:
    return {
        "task_id": _TASK,
        "project_id": "Virtual_scrum_team",
        "phase": 4,
        "story_id": _STORY,
        "base_head": "a" * 40,
        "scope": ["tools/vst/store.py"],
        "forbidden_actions": ["push"],
        "owner_role": "implementer",
        "role_sha256": "c" * 64,
        "skills": [{"id": "s2-4e-contract-fixture", "sha256": "d" * 64}],
        "model_policy": "fixture-model",
        "tools": ["Read"],
        "acceptance": ["S2-4E-OWNER-RECEIPT"],
        "required_receipts": [
            {"slot": "tests", "receipt_type": "TestRun"},
            {"slot": "review", "receipt_type": "IndependentReview"},
        ],
        "required_tests": [{"slot": "tests", "test_id": "contract-case", "acceptance": ["S2-4E-OWNER-RECEIPT"]}],
        "allowed_commands": [{"slot": "tests", "argv": ["python", "focused-contract-fixture"]}],
        "required_rules": [],
        "author_principal": _OWNER,
        "timeout_sec": 30,
        "cost_cap": 10,
        "retry_cap": 1,
    }


class OwnerCompletedReceiptContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory(prefix="vst-s2-4e-owner-receipt-")
        self.addCleanup(self._directory.cleanup)
        self._db = str(Path(self._directory.name) / "store.sqlite3")
        self._supervisor_key = secrets.token_bytes(32)
        self._store = Store(
            self._db,
            clock=lambda: _NOW,
            event_key=secrets.token_bytes(32),
            supervisor_key=self._supervisor_key,
        )
        self.addCleanup(self._store.close)
        self._store.init_slots(1)
        self._store.open_story(_STORY, "Virtual_scrum_team", 4)
        self._epoch = self._store.acquire_epoch(_STORY, _OWNER, ttl_sec=1_000)
        self._manifest = _manifest()
        self._store.register_task(self._manifest)
        self._store.acquire_lease(
            _TASK, _STORY, "runner-fixture", self._epoch, 1, 900,
            supervisor_key=self._supervisor_key,
        )
        # This is a synthetic consumed Store row solely to satisfy the Store
        # contract; it is not a sandbox observation or preflight evidence.
        self._store.ensure_preflight_consumed(_RUN, "fixture-nonce", "b" * 64, "e" * 64)
        self._instruction = {
            "version": 1,
            "algorithm": "Ed25519",
            "purpose": "VST_S2_DISPATCH_INSTRUCTION_V1",
            "request_id": "11111111111111111111111111111111",
            "task_id": _TASK,
            "slot": "tests",
            "attempt": 1,
            "epoch": self._epoch,
            "run_id": _RUN,
            "key_id": "fixture-owner-key",
            "expires_at": "2030-01-01T00:00:00Z",
            "signature": _ZERO_SIGNATURE_B64,
        }
        self._store.accept_dispatch_intent(
            principal=_OWNER,
            instruction=self._instruction,
            service_generation=_GENERATION,
            key_class="LEGACY_V1",
            key_fingerprint="f" * 64,
        )
        self._supervisor = Supervisor(self._store, operation_backend=object())
        self._owner = DispatchOwnerClient(
            principal=_OWNER,
            trust_registry={},
            openssl_path="unused-by-read-only-receipt-poll",
            transport=_OwnerTransport(self._store, self._supervisor),
        )

    def _snapshot(self) -> tuple:
        request_id = self._instruction["request_id"]
        with self._store._read_tx() as conn:
            counts = tuple(
                conn.execute(sql, params).fetchone()[0]
                for sql, params in (
                    ("SELECT COUNT(*) FROM supervisor_operations WHERE operation_key=? AND operation='dispatch_grant'", (f"dispatch-grant:{request_id}",)),
                    ("SELECT COUNT(*) FROM runner_execution_claims", ()),
                    ("SELECT COUNT(*) FROM runner_execution_events", ()),
                    ("SELECT COUNT(*) FROM receipts WHERE task_id=?", (_TASK,)),
                )
            )
        return self._store.event_anchor(), counts

    def _grant(self) -> dict:
        # Keep the Runner grant's request ID distinct from the Owner instruction
        # request ID. The Store-only fixture checks correlation, not signature trust.
        return {
            "version": 1,
            "key_id": "fixture-runner-grant-key",
            "grant_id": "22222222222222222222222222222222",
            "request_id": "33333333333333333333333333333333",
            "audience": "vst-runner-service-v1",
            "service_generation": _GENERATION,
            "manifest_sha256": manifest_sha256(self._manifest),
            "task_id": _TASK,
            "slot": "tests",
            "attempt": 1,
            "epoch": self._epoch,
            "run_id": _RUN,
            "invocation_id": "44444444444444444444444444444444",
            "runner_id": "runner-fixture",
            "resolved_model": "fixture-model",
            "model_provenance_sha256": "5" * 64,
            "execution_deadline_sec": 30,
            "issued_at": _NOW,
            "claim_expires_at": _NOW + 20,
            "expires_at": _NOW + 120,
            "signature": _ZERO_SIGNATURE_B64,
        }

    def _seed_dispatch_grant(self) -> dict:
        grant = self._grant()
        payload = {
            "request_id": self._instruction["request_id"],
            "service_generation": _GENERATION,
        }
        self._store.execute_idempotent(
            f"dispatch-grant:{self._instruction['request_id']}",
            "dispatch_grant",
            payload,
            lambda _conn: grant,
        )
        return grant

    def _receipt(self, grant: dict) -> dict:
        manifest_digest = manifest_sha256(self._manifest)
        parser_results = [{
            "argv": ["python", "focused-contract-fixture"],
            "parser_id": "fixture-parser",
            "parser_version": "1",
            "parser_sha256": "6" * 64,
            "parser_result": {
                "executed_test_ids": [],
                "skipped_test_ids": [],
                "xfail_test_ids": [],
            },
        }]
        request = {
            "request_id": grant["request_id"],
            "task_id": _TASK,
            "slot": "tests",
            "attempt": 1,
            "epoch": self._epoch,
            "manifest_sha256": manifest_digest,
            "candidate_head": "a" * 40,
            "commands": [{"argv": ["python", "focused-contract-fixture"], "exit_code": 0}],
            "parser_results": parser_results,
            "artifact_digests": {},
        }
        return {
            "contract_version": 2,
            "receipt_type": "TestRun",
            "receipt_id": "s2-4e-fixture-receipt",
            "task_id": _TASK,
            "manifest_sha256": manifest_digest,
            "slot": "tests",
            "attempt": 1,
            "prev_receipt_sha256": None,
            "candidate_head": "a" * 40,
            "epoch": self._epoch,
            "runner_id": "runner-fixture",
            "role_sha256": "c" * 64,
            "resolved_model": "fixture-model",
            "invocation_id": grant["invocation_id"],
            "result": "NOT_RUN",
            "created_at": "1970-01-01T00:16:40Z",
            "signature": _ZERO_SIGNATURE_HEX,
            "expected_test_ids": ["contract-case"],
            "executed_test_ids": [],
            "skipped_test_ids": [],
            "xfail_test_ids": [],
            "commands": [{"argv": ["python", "focused-contract-fixture"], "exit_code": 0}],
            "covered_acceptance": ["S2-4E-OWNER-RECEIPT"],
            "artifact_digests": {},
            "parser_results": parser_results,
            "diff_gate": {
                "manifest_sha256": manifest_digest,
                "candidate_head": "a" * 40,
                "diff_sha256": "7" * 64,
                "changed_paths": [],
                "verdict": "FAIL",
                "reason": "Synthetic Store receipt lookup fixture; no code test was executed.",
                "signature": _ZERO_SIGNATURE_HEX,
            },
            "runner_attestation": {
                "request": request,
                "signature": _ZERO_SIGNATURE_HEX,
            },
        }

    def test_lookup_before_grant_is_none_and_does_not_issue_or_mutate(self) -> None:
        before = self._snapshot()

        observed = self._owner.completed_receipt(self._instruction)

        self.assertIsNone(observed)
        self.assertEqual(self._snapshot(), before)

    def test_wrong_principal_or_instruction_cannot_observe_receipt(self) -> None:
        grant = self._seed_dispatch_grant()
        self._store.claim_runner_execution(grant, active_service_generation=_GENERATION)
        self._store.reserve_runner_execution(grant, active_service_generation=_GENERATION)
        before = self._snapshot()

        wrong_principal = self._supervisor.completed_dispatch_receipt(
            principal="OtherOwner", instruction=self._instruction,
        )
        changed = {**self._instruction, "task_id": "different-task"}
        wrong_instruction = self._owner.completed_receipt(changed)

        self.assertIsNone(wrong_principal)
        self.assertIsNone(wrong_instruction)
        self.assertEqual(self._snapshot(), before)

    def test_reserved_execution_is_not_reported_as_complete(self) -> None:
        grant = self._seed_dispatch_grant()
        self._store.claim_runner_execution(grant, active_service_generation=_GENERATION)
        reserved = self._store.reserve_runner_execution(
            grant, active_service_generation=_GENERATION,
        )
        self.assertEqual(reserved["state"], "EXECUTION_RESERVED")
        before = self._snapshot()

        observed = self._owner.completed_receipt(self._instruction)

        self.assertIsNone(observed)
        self.assertEqual(self._snapshot(), before)

    def test_complete_receipt_is_exactly_bound_to_owner_and_distinct_grant_ids(self) -> None:
        grant = self._seed_dispatch_grant()
        self.assertNotEqual(grant["request_id"], self._instruction["request_id"])
        self._store.claim_runner_execution(grant, active_service_generation=_GENERATION)
        self._store.reserve_runner_execution(grant, active_service_generation=_GENERATION)
        receipt = self._receipt(grant)
        self._store.complete_runner_execution(
            grant, receipt, active_service_generation=_GENERATION,
        )
        before_poll = self._snapshot()

        observed = self._owner.completed_receipt(self._instruction)

        self.assertEqual(observed, {
            "dispatch": {
                "principal": _OWNER,
                "task_id": _TASK,
                "slot": "tests",
                "attempt": 1,
                "epoch": self._epoch,
                "run_id": _RUN,
                "request_id": self._instruction["request_id"],
                "service_generation": _GENERATION,
            },
            "execution": {
                "request_id": grant["request_id"],
                "receipt": receipt,
            },
        })
        self.assertEqual(observed["execution"]["receipt"], receipt)
        self.assertEqual(
            observed["execution"]["receipt"]["runner_attestation"]["request"]["request_id"],
            grant["request_id"],
        )
        self.assertEqual(observed["dispatch"]["request_id"], self._instruction["request_id"])
        self.assertEqual(self._snapshot(), before_poll)


if __name__ == "__main__":
    unittest.main()
