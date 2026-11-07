"""Focused S2-4E Store contracts for ordinary Windows mode and schema upgrade.

These tests use disposable SQLite state and never create preflight/E5 records.
They prove Store admission behavior only; they do not prove the Windows service
process path or Job Object runtime behavior.
"""
from __future__ import annotations

import base64
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.vst import contracts
from tools.vst.dispatch_instruction import (
    DISPATCH_INSTRUCTION_PURPOSE,
    dispatch_instruction_signing_bytes,
    validate_dispatch_instruction,
)
from tools.vst.store import Store, StoreError
from tests.vst.e1e4_helpers import EVENT_KEY, FakeClock, SUPERVISOR_KEY, manifest

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError:  # pragma: no cover - test environment may omit optional crypto support
    serialization = None
    Ed25519PrivateKey = None


def _store(path: str, clock: FakeClock, *, sandbox_mode: bool = False) -> Store:
    kwargs = {}
    if sandbox_mode:
        kwargs.update(
            anchor_path=f"{path}.anchor",
            sandbox_mode=True,
            supervisor_key=SUPERVISOR_KEY,
        )
    return Store(path, clock, event_key=EVENT_KEY, **kwargs)


def _task_state(store: Store) -> tuple[dict, int]:
    task = manifest()
    store.init_slots(1)
    store.open_story(task["story_id"], task["project_id"], task["phase"])
    epoch = store.acquire_epoch(task["story_id"], "test-owner", ttl_sec=1800)
    store.register_task(task)
    store.acquire_lease(
        task["task_id"], task["story_id"], "runner-1", epoch, 1, 1200,
        supervisor_key=SUPERVISOR_KEY,
    )
    return task, epoch


def _execution_grant(task: dict, epoch: int, now: float) -> dict:
    deadline = int(task["timeout_sec"])
    return {
        "version": 1,
        "key_id": "grant-key-test",
        "grant_id": "grant-s2-4e-test",
        "request_id": "request-s2-4e-test",
        "audience": "vst-runner-service-v1",
        "service_generation": "windows-test-generation",
        "manifest_sha256": contracts.manifest_sha256(task),
        "task_id": task["task_id"],
        "slot": "tests",
        "attempt": 1,
        "epoch": epoch,
        "run_id": "windows-test-run",
        "invocation_id": "invocation-s2-4e-test",
        "runner_id": "runner-1",
        "resolved_model": "test-model",
        "model_provenance_sha256": "e" * 64,
        "execution_deadline_sec": deadline,
        "issued_at": now,
        "claim_expires_at": now + 30,
        "expires_at": now + deadline + 60,
        "signature": base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("="),
    }


def _legacy_instruction(task: dict, epoch: int) -> tuple[dict, str]:
    """Create a valid ephemeral signed v1 instruction for Store-layer tests."""
    if Ed25519PrivateKey is None or serialization is None:
        raise unittest.SkipTest("cryptography is unavailable for a disposable signed instruction")
    private_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    body = {
        "version": 1,
        "algorithm": "Ed25519",
        "purpose": DISPATCH_INSTRUCTION_PURPOSE,
        "request_id": "a" * 32,
        "task_id": task["task_id"],
        "slot": "tests",
        "attempt": 1,
        "epoch": epoch,
        "run_id": "windows-store-dispatch-run",
        "key_id": "test-legacy-instruction-key",
        "expires_at": "2099-01-01T00:00:00Z",
    }
    unsigned = {**body, "signature": base64.urlsafe_b64encode(bytes(64)).decode("ascii").rstrip("=")}
    signature = private_key.sign(dispatch_instruction_signing_bytes(unsigned))
    instruction = {
        **body,
        "signature": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
    }
    validate_dispatch_instruction(instruction)
    private_key.public_key().verify(signature, dispatch_instruction_signing_bytes(instruction))
    return instruction, hashlib.sha256(public_key_bytes).hexdigest()


class StoreWindowsPreflightContractTests(unittest.TestCase):
    def test_ordinary_mode_accepts_signed_legacy_intent_and_derives_grant_basis_without_probe(self):
        clock = FakeClock(1000)
        with tempfile.TemporaryDirectory(prefix="vst-s2-4e-dispatch-") as directory:
            path = str(Path(directory) / "store.sqlite3")
            store = _store(path, clock)
            try:
                task, epoch = _task_state(store)
                instruction, fingerprint = _legacy_instruction(task, epoch)

                accepted = store.accept_dispatch_intent(
                    principal="test-owner",
                    instruction=instruction,
                    service_generation="windows-test-generation",
                    key_fingerprint=fingerprint,
                )
                basis = store.execution_grant_basis(
                    task["task_id"], "tests", 1, epoch, instruction["run_id"],
                    active_service_generation="windows-test-generation",
                    expected_owner="test-owner",
                    expected_lease_id=accepted["lease_id"],
                )

                self.assertEqual(accepted["instruction"], instruction)
                self.assertEqual(basis["run_id"], instruction["run_id"])
                self.assertEqual(basis["service_generation"], "windows-test-generation")
                with store._read_tx() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM supervisor_probes").fetchone()[0], 0)
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED'",
                        ).fetchone()[0],
                        1,
                    )
            finally:
                store.close()

    def test_sandbox_mode_still_requires_probe_for_legacy_intent_and_grant_basis(self):
        clock = FakeClock(1000)
        with tempfile.TemporaryDirectory(prefix="vst-s2-4e-sandbox-dispatch-") as directory:
            path = str(Path(directory) / "store.sqlite3")
            store = _store(path, clock, sandbox_mode=True)
            try:
                task, epoch = _task_state(store)
                instruction, fingerprint = _legacy_instruction(task, epoch)

                with self.assertRaises(StoreError) as dispatch_error:
                    store.accept_dispatch_intent(
                        principal="test-owner",
                        instruction=instruction,
                        service_generation="windows-test-generation",
                        key_fingerprint=fingerprint,
                    )
                self.assertEqual(dispatch_error.exception.kind, "probe")
                with self.assertRaises(StoreError) as basis_error:
                    store.execution_grant_basis(
                        task["task_id"], "tests", 1, epoch, instruction["run_id"],
                        active_service_generation="windows-test-generation",
                        expected_owner="test-owner",
                    )
                self.assertEqual(basis_error.exception.kind, "probe")
                with store._read_tx() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM supervisor_probes").fetchone()[0], 0)
                    self.assertEqual(
                        conn.execute(
                            "SELECT COUNT(*) FROM events WHERE kind='DISPATCH_INTENT_ACCEPTED'",
                        ).fetchone()[0],
                        0,
                    )
            finally:
                store.close()

    def test_ordinary_mode_claims_without_any_preflight_record(self):
        clock = FakeClock(1000)
        with tempfile.TemporaryDirectory(prefix="vst-s2-4e-store-") as directory:
            path = str(Path(directory) / "store.sqlite3")
            store = _store(path, clock)
            try:
                task, epoch = _task_state(store)
                grant = _execution_grant(task, epoch, clock())

                self.assertIsNone(store.claim_runner_execution(
                    grant, active_service_generation="windows-test-generation",
                ))
                with store._read_tx() as conn:
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM supervisor_probes").fetchone()[0], 0,
                    )
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM runner_execution_claims").fetchone()[0], 1,
                    )
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM runner_execution_events").fetchone()[0], 1,
                    )
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM supervisor_runs").fetchone()[0], 1,
                    )
            finally:
                store.close()

    def test_sandbox_mode_still_fails_closed_without_preflight(self):
        clock = FakeClock(1000)
        with tempfile.TemporaryDirectory(prefix="vst-s2-4e-sandbox-") as directory:
            path = str(Path(directory) / "store.sqlite3")
            store = _store(path, clock, sandbox_mode=True)
            try:
                task, epoch = _task_state(store)
                grant = _execution_grant(task, epoch, clock())

                with self.assertRaises(StoreError) as raised:
                    store.claim_runner_execution(
                        grant, active_service_generation="windows-test-generation",
                    )
                self.assertEqual(raised.exception.kind, "probe")
                with store._read_tx() as conn:
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM supervisor_probes").fetchone()[0], 0,
                    )
                    self.assertEqual(
                        conn.execute("SELECT COUNT(*) FROM runner_execution_claims").fetchone()[0], 0,
                    )
            finally:
                store.close()

    def test_v6_empty_execution_ledger_upgrades_explicitly_without_event_loss(self):
        clock = FakeClock(1000)
        with tempfile.TemporaryDirectory(prefix="vst-s2-4e-v6-upgrade-") as directory:
            path = str(Path(directory) / "store.sqlite3")
            initial = _store(path, clock)
            task, _epoch = _task_state(initial)
            initial.close()

            connection = sqlite3.connect(path)
            try:
                connection.execute("PRAGMA foreign_keys=OFF")
                before_events = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                before_chain = connection.execute(
                    "SELECT seq, hash FROM events ORDER BY seq",
                ).fetchall()
                self.assertEqual(connection.execute(
                    "SELECT COUNT(*) FROM runner_execution_claims",
                ).fetchone()[0], 0)
                self.assertEqual(connection.execute(
                    "SELECT COUNT(*) FROM runner_execution_events",
                ).fetchone()[0], 0)

                for trigger in (
                    "runner_execution_claims_no_update", "runner_execution_claims_no_delete",
                    "runner_execution_events_no_update", "runner_execution_events_no_delete",
                    "supervisor_runs_no_update", "supervisor_runs_no_delete",
                ):
                    connection.execute(f"DROP TRIGGER IF EXISTS {trigger}")
                connection.execute("ALTER TABLE runner_execution_events RENAME TO runner_execution_events_v7")
                connection.execute("ALTER TABLE runner_execution_claims RENAME TO runner_execution_claims_v7")
                connection.execute("DROP TABLE runner_execution_events_v7")
                connection.execute("DROP TABLE runner_execution_claims_v7")
                connection.execute("DROP TABLE supervisor_runs")
                connection.executescript("""
                    CREATE TABLE runner_execution_claims (
                        grant_id TEXT PRIMARY KEY,
                        invocation_id TEXT NOT NULL UNIQUE,
                        request_id TEXT NOT NULL UNIQUE,
                        task_id TEXT NOT NULL,
                        slot TEXT NOT NULL,
                        runner_id TEXT NOT NULL,
                        attempt INT NOT NULL CHECK (attempt >= 1),
                        epoch INT NOT NULL CHECK (epoch >= 1),
                        run_id TEXT NOT NULL REFERENCES supervisor_probes(run_id),
                        service_generation TEXT NOT NULL,
                        manifest_sha256 TEXT NOT NULL,
                        payload_sha256 TEXT NOT NULL,
                        grant_body TEXT NOT NULL,
                        claimed_at REAL NOT NULL,
                        UNIQUE (task_id, slot, attempt)
                    );
                    CREATE TABLE runner_execution_events (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT,
                        grant_id TEXT NOT NULL REFERENCES runner_execution_claims(grant_id),
                        state TEXT NOT NULL CHECK (state IN (
                            'PENDING', 'EXECUTION_RESERVED', 'COMPLETE', 'INDETERMINATE', 'RECONCILED'
                        )),
                        payload TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        UNIQUE (grant_id, state)
                    );
                    CREATE TRIGGER runner_execution_claims_no_update BEFORE UPDATE ON runner_execution_claims
                    BEGIN SELECT RAISE(ABORT, 'runner execution claims are append-only'); END;
                    CREATE TRIGGER runner_execution_claims_no_delete BEFORE DELETE ON runner_execution_claims
                    BEGIN SELECT RAISE(ABORT, 'runner execution claims are append-only'); END;
                    CREATE TRIGGER runner_execution_events_no_update BEFORE UPDATE ON runner_execution_events
                    BEGIN SELECT RAISE(ABORT, 'runner execution events are append-only'); END;
                    CREATE TRIGGER runner_execution_events_no_delete BEFORE DELETE ON runner_execution_events
                    BEGIN SELECT RAISE(ABORT, 'runner execution events are append-only'); END;
                """)
                connection.execute("PRAGMA user_version=6")
                connection.commit()
            finally:
                connection.close()

            with self.assertRaises(StoreError) as not_authorized:
                Store(path, clock, event_key=EVENT_KEY)
            self.assertEqual(not_authorized.exception.kind, "schema")

            upgraded = Store(path, clock, event_key=EVENT_KEY, allow_schema_upgrade=True)
            try:
                with upgraded._read_tx() as conn:
                    self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 7)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], before_events)
                    self.assertEqual(
                        [
                            (row[0], row[1])
                            for row in conn.execute("SELECT seq, hash FROM events ORDER BY seq")
                        ],
                        before_chain,
                    )
                    self.assertIn(
                        "supervisor_runs",
                        conn.execute(
                            "SELECT sql FROM sqlite_master WHERE type='table' "
                            "AND name='runner_execution_claims'",
                        ).fetchone()[0],
                    )
                    self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertTrue(upgraded.verify_event_chain())
            finally:
                upgraded.close()


if __name__ == "__main__":
    unittest.main()
