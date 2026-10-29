"""Closed schemas for the read-only authenticated assignment-basis contract.

This module deliberately contains no signing, persistence, or assignment writer.
"""

from __future__ import annotations

import copy
import hashlib
import posixpath
import re
from datetime import datetime, timezone
from typing import Any

from .contracts import ContractError, canonical_bytes, manifest_sha256, validate_task_manifest

POLICY_SCHEMA = "VST_S2_ASSIGNMENT_DELEGATION_POLICY_V1"
HANDOFF_SCHEMA = "VST_S2_AUTHENTICATED_ASSIGNMENT_V1"
REQUEST_SCHEMA = "VST_S2_ASSIGNMENT_BASIS_REQUEST_V1"
RESPONSE_SCHEMA = "VST_S2_ASSIGNMENT_BASIS_RESPONSE_V1"
OPERATION = HANDOFF_SCHEMA
POLICY_PATH = "/etc/vst-runner/assignment-delegation-policy.json"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_POLICY_FIELDS = {
    "schema", "policy_id", "repository", "sprint_id", "source_head", "manifest_sha256",
    "owner_principal", "allowed_assignments", "bootstrap_peer", "issuer_peer",
    "allowed_bootstrap_operations", "maximum_handoff_ttl_seconds", "valid_from_utc",
    "expires_at_utc", "revocation_id", "runner_id", "owner_ttl_seconds", "lease_ttl_seconds",
}
_ASSIGNMENT_FIELDS = {
    "story_id", "task_id", "project_id", "phase", "task_manifest_sha256", "test_run_slots",
}
_PEER_FIELDS = {"role", "uid", "gid", "cgroup"}
_HANDOFF_FIELDS = {
    "schema", "assignment_operation_id", "policy_id", "policy_sha256", "repository",
    "sprint_id", "source_head", "manifest_sha256", "bootstrap_peer", "assignment_principal",
    "bootstrap_request", "task_id", "story_id", "project_id", "phase",
    "task_manifest_sha256", "slot", "attempt",
    "epoch", "lease_id", "runner_id", "run_id", "service_generation", "probe_sha256", "issued_at_utc",
    "expires_at_utc", "handoff_sha256",
}
_REQUEST_FIELDS = {"schema", "assignment_operation_id"}
_BOOTSTRAP_REQUEST_FIELDS = {
    "schema", "request_id", "story_id", "task_id", "task_manifest", "slot", "attempt", "run_id",
}
_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_ASSIGNMENT_TTL_SECONDS = 3600
_RESPONSE_FIELDS = {
    "schema", "assignment_operation_id", "handoff_sha256", "policy_id", "policy_sha256",
    "repository", "sprint_id", "source_head", "manifest_sha256", "task_id", "story_id",
    "task_manifest_sha256", "slot", "attempt", "epoch", "lease_id", "runner_id", "principal",
    "run_id", "probe_sha256", "authority_expires_at_utc", "service_generation",
}


def _object(value: Any, fields: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ContractError(f"{name} fields do not match the closed schema")
    return value


def _text(value: Any, name: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ContractError(f"{name} must be a non-empty canonical string")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ContractError(f"{name} has an invalid format")
    return value


def _integer(value: Any, name: str, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ContractError(f"{name} is outside its integer bounds")
    return value


def _utc(value: Any, name: str) -> datetime:
    text = _text(value, name)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ContractError(f"{name} must be canonical UTC") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise ContractError(f"{name} must be canonical UTC")
    return parsed


def _peer(value: Any, role: str) -> dict:
    peer = _object(value, _PEER_FIELDS, f"{role} peer")
    if peer["role"] != role:
        raise ContractError(f"peer role must be {role}")
    _integer(peer["uid"], f"{role}.uid", 1)
    _integer(peer["gid"], f"{role}.gid", 1)
    _text(peer["cgroup"], f"{role}.cgroup")
    if (not peer["cgroup"].startswith("/") or ".." in peer["cgroup"].split("/")
            or posixpath.normpath(peer["cgroup"]) != peer["cgroup"]):
        raise ContractError(f"{role}.cgroup is not an absolute normalized path")
    return copy.deepcopy(peer)


def validate_policy(value: Any) -> tuple[dict, str]:
    policy = _object(value, _POLICY_FIELDS, "assignment policy")
    if policy["schema"] != POLICY_SCHEMA or policy["owner_principal"] != "Codex":
        raise ContractError("assignment policy schema or owner principal is invalid")
    _text(policy["policy_id"], "policy_id", pattern=_ID)
    if policy["repository"] != "Virtual_scrum_team":
        raise ContractError("assignment policy repository is not fixed")
    _text(policy["sprint_id"], "sprint_id", pattern=_ID)
    _text(policy["source_head"], "source_head", pattern=_HEAD)
    _text(policy["manifest_sha256"], "manifest_sha256", pattern=_SHA)
    _text(policy["revocation_id"], "revocation_id", pattern=_ID)
    _text(policy["runner_id"], "runner_id", pattern=_ID)
    for field in ("owner_ttl_seconds", "lease_ttl_seconds"):
        ttl = policy[field]
        if type(ttl) is not int or ttl < 1 or ttl > MAX_ASSIGNMENT_TTL_SECONDS:
            raise ContractError(f"{field} must be an integer in [1, {MAX_ASSIGNMENT_TTL_SECONDS}]")
    if policy["lease_ttl_seconds"] > policy["owner_ttl_seconds"]:
        raise ContractError("lease_ttl_seconds cannot exceed owner_ttl_seconds")
    assignments = policy["allowed_assignments"]
    if not isinstance(assignments, list) or not assignments:
        raise ContractError("assignment policy must contain a non-empty assignment allowlist")
    seen: set[tuple[str, str]] = set()
    seen_story_ids: set[str] = set()
    seen_task_ids: set[str] = set()
    for entry in assignments:
        entry = _object(entry, _ASSIGNMENT_FIELDS, "allowed assignment")
        story = _text(entry["story_id"], "story_id", pattern=_ID)
        task = _text(entry["task_id"], "task_id", pattern=_ID)
        _text(entry["project_id"], "project_id", pattern=_ID)
        _integer(entry["phase"], "phase", 1, 10)
        _text(entry["task_manifest_sha256"], "task_manifest_sha256", pattern=_SHA)
        key = (story, task)
        if key in seen:
            raise ContractError("assignment policy contains a duplicate story/task pair")
        if story in seen_story_ids or task in seen_task_ids:
            raise ContractError("assignment policy reuses a story or task identifier")
        seen.add(key)
        seen_story_ids.add(story)
        seen_task_ids.add(task)
        slots = entry["test_run_slots"]
        if (not isinstance(slots, list) or not slots or any(
                not isinstance(slot, str) or not _ID.fullmatch(slot) for slot in slots)
                or len(slots) != len(set(slots))):
            raise ContractError("assignment slots must be unique non-empty TestRun slot names")
    bootstrap = _peer(policy["bootstrap_peer"], "assignment_bootstrap")
    issuer = _peer(policy["issuer_peer"], "delegated_issuer")
    if (bootstrap["uid"] == issuer["uid"] or bootstrap["gid"] == issuer["gid"]
            or bootstrap["cgroup"] == issuer["cgroup"]):
        raise ContractError("assignment peers must have distinct process identities")
    expected_ops = ["open_story", "register_task", "acquire_epoch", "acquire_lease"]
    if policy["allowed_bootstrap_operations"] != expected_ops:
        raise ContractError("assignment bootstrap operation set is not fixed")
    _integer(policy["maximum_handoff_ttl_seconds"], "maximum_handoff_ttl_seconds", 1, 300)
    valid_from = _utc(policy["valid_from_utc"], "valid_from_utc")
    expires = _utc(policy["expires_at_utc"], "expires_at_utc")
    if expires <= valid_from:
        raise ContractError("assignment policy expiry must follow validity start")
    digest = hashlib.sha256(canonical_bytes(policy)).hexdigest()
    return copy.deepcopy(policy), digest


def validate_request(value: Any) -> str:
    request = _object(value, _REQUEST_FIELDS, "assignment-basis request")
    if request["schema"] != REQUEST_SCHEMA:
        raise ContractError("assignment-basis request schema is invalid")
    return _text(request["assignment_operation_id"], "assignment_operation_id", pattern=_SHA)


def validate_bootstrap_request(value: Any, *, policy: dict) -> dict:
    request = _object(value, _BOOTSTRAP_REQUEST_FIELDS, "authenticated bootstrap request")
    if request["schema"] != "VST_S2_ASSIGNMENT_BOOTSTRAP_REQUEST_V1":
        raise ContractError("authenticated bootstrap request schema is invalid")
    _text(request["request_id"], "request_id", pattern=_REQUEST_ID)
    story_id = _text(request["story_id"], "story_id", pattern=_ID)
    task_id = _text(request["task_id"], "task_id", pattern=_ID)
    slot = _text(request["slot"], "slot", pattern=_ID)
    _integer(request["attempt"], "attempt", 1)
    if request["attempt"] != 1:
        raise ContractError("fresh assignment bootstrap only permits attempt 1")
    run_id = _text(request["run_id"], "run_id", pattern=_ID)
    manifest = validate_task_manifest(request["task_manifest"])
    if (manifest["task_id"] != task_id or manifest["story_id"] != story_id
            or manifest_sha256(manifest) != manifest_sha256(request["task_manifest"])):
        raise ContractError("bootstrap request task manifest identity or canonical digest is invalid")
    allowed = [entry for entry in policy["allowed_assignments"]
               if entry["task_id"] == task_id and entry["story_id"] == story_id]
    if len(allowed) != 1 or allowed[0]["task_manifest_sha256"] != manifest_sha256(manifest):
        raise ContractError("bootstrap request task is outside the root assignment allowlist")
    if manifest["project_id"] != allowed[0]["project_id"] or manifest["phase"] != allowed[0]["phase"]:
        raise ContractError("bootstrap request project or phase differs from root assignment")
    test_run_slots = {
        entry["slot"] for entry in manifest["required_receipts"]
        if entry["receipt_type"] == "TestRun"
    }
    if slot not in test_run_slots or slot not in allowed[0]["test_run_slots"]:
        raise ContractError("bootstrap request slot is outside the root TestRun assignment allowlist")
    return {
        "schema": request["schema"], "request_id": request["request_id"],
        "story_id": story_id, "task_id": task_id, "task_manifest": manifest,
        "slot": slot, "attempt": request["attempt"], "run_id": run_id,
    }


def assignment_operation_id(request: dict, *, policy_sha256: str) -> str:
    identity = {
        "policy_sha256": policy_sha256, "task_id": request["task_id"],
        "story_id": request["story_id"],
        "task_manifest_sha256": manifest_sha256(request["task_manifest"]),
        "request_id": request["request_id"],
    }
    domain = b"VST_S2_AUTHENTICATED_ASSIGNMENT_V1\0"
    return hashlib.sha256(domain + canonical_bytes(identity)).hexdigest()


def assignment_payload_sha256(request: dict, *, policy: dict, policy_sha256: str) -> str:
    payload = {
        "request": request, "bootstrap_peer": policy["bootstrap_peer"],
        "policy_sha256": policy_sha256,
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def validate_handoff(value: Any, *, policy: dict, policy_sha256: str, now: datetime) -> dict:
    handoff = _object(value, _HANDOFF_FIELDS, "assignment handoff")
    if handoff["schema"] != HANDOFF_SCHEMA:
        raise ContractError("assignment handoff schema is invalid")
    for field in ("assignment_operation_id", "policy_sha256", "manifest_sha256",
                  "task_manifest_sha256", "probe_sha256", "handoff_sha256"):
        _text(handoff[field], field, pattern=_SHA)
    if handoff["policy_sha256"] != policy_sha256:
        raise ContractError("assignment handoff policy digest differs from root policy")
    fixed = ("policy_id", "repository", "sprint_id", "source_head", "manifest_sha256")
    if any(handoff[field] != policy[field] for field in fixed):
        raise ContractError("assignment handoff differs from root policy identity")
    if handoff["assignment_principal"] != policy["owner_principal"]:
        raise ContractError("assignment handoff principal differs from root policy")
    bootstrap = _peer(handoff["bootstrap_peer"], "assignment_bootstrap")
    if bootstrap != policy["bootstrap_peer"]:
        raise ContractError("assignment handoff bootstrap peer differs from root policy")
    bootstrap_request = validate_bootstrap_request(handoff["bootstrap_request"], policy=policy)
    _text(handoff["task_id"], "task_id", pattern=_ID)
    _text(handoff["story_id"], "story_id", pattern=_ID)
    _text(handoff["project_id"], "project_id", pattern=_ID)
    _integer(handoff["phase"], "phase", 1, 10)
    _text(handoff["slot"], "slot", pattern=_ID)
    _text(handoff["runner_id"], "runner_id", pattern=_ID)
    _text(handoff["run_id"], "run_id", pattern=_ID)
    _text(handoff["service_generation"], "service_generation", pattern=_ID)
    _integer(handoff["attempt"], "attempt", 1)
    _integer(handoff["epoch"], "epoch", 1)
    _integer(handoff["lease_id"], "lease_id", 1)
    if (bootstrap_request["task_id"] != handoff["task_id"]
            or bootstrap_request["story_id"] != handoff["story_id"]
            or bootstrap_request["task_manifest"]["project_id"] != handoff["project_id"]
            or bootstrap_request["task_manifest"]["phase"] != handoff["phase"]
            or handoff["runner_id"] != policy["runner_id"]
            or manifest_sha256(bootstrap_request["task_manifest"]) != handoff["task_manifest_sha256"]
            or bootstrap_request["slot"] != handoff["slot"]
            or bootstrap_request["attempt"] != handoff["attempt"]
            or bootstrap_request["run_id"] != handoff["run_id"]
            or assignment_operation_id(bootstrap_request, policy_sha256=policy_sha256)
            != handoff["assignment_operation_id"]):
        raise ContractError("assignment handoff differs from its canonical bootstrap request identity")
    allowed = [entry for entry in policy["allowed_assignments"]
               if entry["task_id"] == handoff["task_id"] and entry["story_id"] == handoff["story_id"]]
    if (len(allowed) != 1 or allowed[0]["task_manifest_sha256"] != handoff["task_manifest_sha256"]
            or allowed[0]["project_id"] != handoff["project_id"]
            or allowed[0]["phase"] != handoff["phase"]):
        raise ContractError("assignment handoff is outside the root assignment allowlist")
    if handoff["slot"] not in allowed[0]["test_run_slots"]:
        raise ContractError("assignment handoff slot is outside the root assignment allowlist")
    issued = _utc(handoff["issued_at_utc"], "issued_at_utc")
    expires = _utc(handoff["expires_at_utc"], "expires_at_utc")
    if (expires <= issued or issued > now or expires <= now
            or (expires - issued).total_seconds() > policy["maximum_handoff_ttl_seconds"]
            or issued < _utc(policy["valid_from_utc"], "valid_from_utc")
            or expires > _utc(policy["expires_at_utc"], "expires_at_utc")):
        raise ContractError("assignment handoff is expired or outside policy validity")
    body = {key: item for key, item in handoff.items() if key != "handoff_sha256"}
    if hashlib.sha256(canonical_bytes(body)).hexdigest() != handoff["handoff_sha256"]:
        raise ContractError("assignment handoff digest is invalid")
    return {
        **copy.deepcopy(handoff),
        "bootstrap_request": bootstrap_request,
        "payload_sha256": assignment_payload_sha256(
            bootstrap_request, policy=policy, policy_sha256=policy_sha256,
        ),
    }


def build_response(handoff: dict, *, policy: dict, policy_sha256: str, authority_expires_at: float,
                   service_generation: str) -> dict:
    expires = datetime.fromtimestamp(authority_expires_at, timezone.utc).replace(microsecond=0)
    result = {
        "schema": RESPONSE_SCHEMA,
        "assignment_operation_id": handoff["assignment_operation_id"],
        "handoff_sha256": handoff["handoff_sha256"],
        "policy_id": policy["policy_id"], "policy_sha256": policy_sha256,
        "repository": policy["repository"], "sprint_id": policy["sprint_id"],
        "source_head": policy["source_head"], "manifest_sha256": policy["manifest_sha256"],
        "task_id": handoff["task_id"], "story_id": handoff["story_id"],
        "task_manifest_sha256": handoff["task_manifest_sha256"], "slot": handoff["slot"],
        "attempt": handoff["attempt"], "epoch": handoff["epoch"], "lease_id": handoff["lease_id"],
        "runner_id": handoff["runner_id"], "principal": policy["owner_principal"],
        "run_id": handoff["run_id"], "probe_sha256": handoff["probe_sha256"],
        "authority_expires_at_utc": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "service_generation": _text(service_generation, "service_generation"),
    }
    _object(result, _RESPONSE_FIELDS, "assignment-basis response")
    if expires.strftime("%Y-%m-%dT%H:%M:%SZ") > handoff["expires_at_utc"]:
        raise ContractError("assignment-basis response exceeds handoff expiry")
    return validate_response(result, policy=policy, policy_sha256=policy_sha256, handoff=handoff)


def validate_response(value: Any, *, policy: dict, policy_sha256: str, handoff: dict) -> dict:
    response = _object(value, _RESPONSE_FIELDS, "assignment-basis response")
    if response["schema"] != RESPONSE_SCHEMA:
        raise ContractError("assignment-basis response schema is invalid")
    for field in ("assignment_operation_id", "handoff_sha256", "policy_sha256",
                  "manifest_sha256", "task_manifest_sha256", "probe_sha256"):
        _text(response[field], field, pattern=_SHA)
    expected = {
        "assignment_operation_id": handoff["assignment_operation_id"],
        "handoff_sha256": handoff["handoff_sha256"], "policy_id": policy["policy_id"],
        "policy_sha256": policy_sha256, "repository": policy["repository"],
        "sprint_id": policy["sprint_id"], "source_head": policy["source_head"],
        "manifest_sha256": policy["manifest_sha256"], "task_id": handoff["task_id"],
        "story_id": handoff["story_id"], "task_manifest_sha256": handoff["task_manifest_sha256"],
        "slot": handoff["slot"], "attempt": handoff["attempt"], "epoch": handoff["epoch"],
        "lease_id": handoff["lease_id"], "runner_id": handoff["runner_id"],
        "principal": policy["owner_principal"], "run_id": handoff["run_id"],
        "probe_sha256": handoff["probe_sha256"],
    }
    if any(response[key] != item for key, item in expected.items()):
        raise ContractError("assignment-basis response differs from its verified inputs")
    for field in ("task_id", "story_id", "slot", "runner_id", "principal", "run_id",
                  "service_generation"):
        _text(response[field], field, pattern=_ID if field != "principal" else None)
    for field in ("attempt", "epoch", "lease_id"):
        _integer(response[field], field, 1)
    authority_expiry = _utc(response["authority_expires_at_utc"], "authority_expires_at_utc")
    if authority_expiry > _utc(handoff["expires_at_utc"], "expires_at_utc"):
        raise ContractError("assignment-basis response exceeds handoff expiry")
    return copy.deepcopy(response)
