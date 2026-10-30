"""S2-4.11 contract tests for the pinned non-secret WSL config installer."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools/qa/apply_s2_runtime_configuration.py"
BUNDLE = ROOT / "docs/sdlc/runtime-config"
SOURCE_COMMIT = "cb7e2ed4e786f87d8ea6183d3b943a6f9c915416"
SPEC = importlib.util.spec_from_file_location("s2_config_apply", SCRIPT)
assert SPEC and SPEC.loader
APPLY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APPLY)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inventory() -> dict:
    bundle = json.loads((BUNDLE / "bundle-manifest.json").read_text(encoding="utf-8"))
    layout = json.loads((BUNDLE / "installation-layout.json").read_text(encoding="utf-8"))
    entries = list(bundle["configuration_installation"]) + list(layout["unit_overrides"])
    entries += [item for item in bundle["units"] if item["publication"].startswith("new absent-only")]
    files = {}
    for entry in entries:
        files[entry["destination"]] = {
            "state": "PRESENT",
            "kind": "regular",
            "uid": entry["uid"],
            "gid": entry["gid"],
            "mode": entry["mode"] if isinstance(entry["mode"], str) else format(entry["mode"], "04o"),
            "size": 17,
            "sha256": "a" * 64,
        }
    return {
        "schema": APPLY.INVENTORY_SCHEMA,
        "captured_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "boot_id": "270cd88b-183f-426c-8add-872d9e98bcec",
        "source_head": "80c2b81deac364ed6466600fd46af47aafe805e2",
        "selected_runtime_path": "/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2",
        "runtime_selector": {
            "state": "PRESENT",
            "kind": "symlink",
            "link_target": "/opt/vst-runtime-80c2b81deac364ed6466600fd46af47aafe805e2",
        },
        "configuration_files": files,
    }


def _write_inventory(tmp_path: Path, inventory: dict) -> tuple[Path, str]:
    path = tmp_path / "inventory.json"
    raw = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    path.write_bytes(raw)
    return path, _sha(raw)


def test_payload_contains_exact_non_secret_candidates_and_pins_current_state(tmp_path, monkeypatch):
    path, digest = _write_inventory(tmp_path, _inventory())
    git_blobs = []
    read_blob = APPLY._git_blob

    def record_git_blob(commit, relative_path):
        git_blobs.append((commit, relative_path))
        return read_blob(commit, relative_path)

    monkeypatch.setattr(APPLY, "_git_blob", record_git_blob)

    raw_payload = APPLY.build_payload(path, digest, SOURCE_COMMIT)
    payload = json.loads(raw_payload)

    bundle = json.loads((BUNDLE / "bundle-manifest.json").read_text(encoding="utf-8"))
    layout = json.loads((BUNDLE / "installation-layout.json").read_text(encoding="utf-8"))
    expected = {item["destination"] for item in bundle["configuration_installation"]}
    expected.update(item["destination"] for item in layout["unit_overrides"])
    expected.update(item["destination"] for item in bundle["units"] if item["publication"].startswith("new absent-only"))

    assert payload["schema"] == "VST_S2_RUNTIME_CONFIG_APPLY_V1"
    assert len(payload["files"]) == 26
    assert {item["destination"] for item in payload["files"]} == expected
    assert payload["selected_runtime_path"].endswith(payload["source_head"])
    assert payload["bundle_manifest_sha256"] == APPLY.BUNDLE_MANIFEST_SHA256
    assert payload["installation_layout_sha256"] == APPLY.INSTALLATION_LAYOUT_SHA256
    assert _sha(base64.b64decode(payload["bundle_manifest_b64"])) == APPLY.BUNDLE_MANIFEST_SHA256
    assert _sha(base64.b64decode(payload["installation_layout_b64"])) == APPLY.INSTALLATION_LAYOUT_SHA256
    assert base64.b64decode(payload["inventory_b64"]) == path.read_bytes()
    assert _sha(base64.b64decode(payload["inventory_b64"])) == digest
    assert git_blobs and all(commit == SOURCE_COMMIT for commit, _ in git_blobs)
    assert {name for _, name in git_blobs} == {
        "docs/sdlc/runtime-config/bundle-manifest.json",
        "docs/sdlc/runtime-config/installation-layout.json",
        *("docs/sdlc/runtime-config/" + item["source"] for item in
          list(bundle["configuration_installation"]) + list(layout["unit_overrides"]) + [
              item for item in bundle["units"] if item["publication"].startswith("new absent-only")
          ]),
    }
    for item in payload["files"]:
        candidate = base64.b64decode(item["content_b64"], validate=True)
        assert _sha(candidate) == item["expected_new"]["sha256"]
        assert item["expected_current"]["state"] == "file"
        assert b"PRIVATE KEY" not in candidate
        assert "private" not in item["destination"].lower()


def test_payload_rejects_changed_inventory_digest_before_transfer(tmp_path):
    path, _ = _write_inventory(tmp_path, _inventory())

    with pytest.raises(ValueError, match="exact SHA-256 pin"):
        APPLY.build_payload(path, "0" * 64, SOURCE_COMMIT)


def test_payload_rejects_stale_inventory(tmp_path):
    inventory = _inventory()
    inventory["captured_utc"] = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    path, digest = _write_inventory(tmp_path, inventory)

    with pytest.raises(ValueError, match="five-minute freshness"):
        APPLY.build_payload(path, digest, SOURCE_COMMIT)


@pytest.mark.parametrize("mutation", ["missing", "unknown-kind", "invalid-fingerprint"])
def test_payload_refuses_unknown_target_state_before_transfer(tmp_path, mutation):
    inventory = _inventory()
    destination = next(iter(inventory["configuration_files"]))
    if mutation == "missing":
        del inventory["configuration_files"][destination]
    elif mutation == "unknown-kind":
        inventory["configuration_files"][destination] = {"state": "symlink", "target": "/tmp/other"}
    else:
        inventory["configuration_files"][destination]["sha256"] = "not-a-hash"
    path, digest = _write_inventory(tmp_path, inventory)

    with pytest.raises(ValueError):
        APPLY.build_payload(path, digest, SOURCE_COMMIT)


def test_payload_accepts_exact_absent_state_and_octal_inventory_mode(tmp_path):
    inventory = _inventory()
    destination = next(iter(inventory["configuration_files"]))
    inventory["configuration_files"][destination] = {"state": "ABSENT"}
    path, digest = _write_inventory(tmp_path, inventory)

    payload = json.loads(APPLY.build_payload(path, digest, SOURCE_COMMIT))
    absent = next(item for item in payload["files"] if item["destination"] == destination)
    assert absent["expected_current"] == {"state": "absent"}
    assert absent["expected_new"]["mode"] == int(
        json.loads((BUNDLE / "bundle-manifest.json").read_text(encoding="utf-8"))["configuration_installation"][0]["mode"], 8
    )


@pytest.mark.parametrize("source_commit", ["cb7e2ed", "z" * 40])
def test_payload_rejects_non_full_or_nonexistent_source_commit(tmp_path, source_commit):
    path, digest = _write_inventory(tmp_path, _inventory())

    with pytest.raises(ValueError):
        APPLY.build_payload(path, digest, source_commit)
