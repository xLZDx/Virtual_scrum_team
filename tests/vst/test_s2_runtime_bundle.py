"""TP-19/22: strict exact-source and post-staging runtime manifest schemas."""
from __future__ import annotations

import copy
import hashlib

import pytest

from tools.vst import runtime_bundle as bundle
from tools.vst.contracts import ContractError


def file_entry(payload: bytes, *, mode: int = 0o644, gid: int = 0) -> dict:
    return {"kind": "file", "sha256": hashlib.sha256(payload).hexdigest(), "uid": 0,
            "gid": gid, "mode": mode, "size": len(payload), "nlink": 1}


def valid_manifest() -> dict:
    source_head = "a" * 40
    old_head = "b" * 40
    return {
        "schema": 3,
        "repository": "Virtual_scrum_team",
        "archive_sha256": "1" * 64,
        "source_plan_sha256": "7" * 64,
        "target_inventory_sha256": "8" * 64,
        "compiler_path": "/usr/bin/cc",
        "compiler_resolved_path": "/usr/bin/x86_64-linux-gnu-gcc-13",
        "compiler_symlink_target": "/etc/alternatives/cc",
        "compiler_sha256": "9" * 64,
        "source_head": source_head,
        "spec_sha256": "2" * 64,
        "old_runtime_tree_sha256": "3" * 64,
        "runtime_path": "/opt/vst-runtime-" + source_head,
        "runtime_tree_sha256": "4" * 64,
        "helper_path": "/usr/local/libexec/vst-s4-worker-exec-" + source_head,
        "helper_head": source_head,
        "helper_source_sha256": "5" * 64,
        "helper_binary_sha256": "6" * 64,
        "helper_gid": 988,
        "helper_mode": 0o4750,
        "helper_nlink": 1,
        "old_selector": {"kind": "symlink", "target": "/opt/vst-runtime-" + old_head,
                         "uid": 0, "gid": 0, "mode": 0o777},
        "units": {
            name: {"old": {"kind": "absent"},
                   "new": file_entry(("unit:" + name).encode())}
            for name in bundle.UNITS
        },
        "parents": {
            path: {"uid": uid, "gid": gid, "mode": mode}
            for path, (uid, gid, mode) in bundle.PARENTS.items()
        },
    }


def test_valid_manifest_has_stable_digest_and_binds_each_unit() -> None:
    value = valid_manifest()

    assert bundle.validate_manifest(value) == value
    first = bundle.manifest_sha256(value)
    second = bundle.manifest_sha256(copy.deepcopy(value))
    assert first == second

    changed = copy.deepcopy(value)
    changed["units"][bundle.UNITS[0]]["new"]["sha256"] = "f" * 64
    assert bundle.manifest_sha256(changed) != first


@pytest.mark.parametrize("mutation", [
    "missing", "unknown", "bad_digest", "bad_head", "bad_path",
    "bad_inventory_digest", "bad_compiler_path",
])
def test_manifest_rejects_unbound_or_unknown_fields(mutation: str) -> None:
    value = valid_manifest()
    if mutation == "missing":
        del value["spec_sha256"]
    elif mutation == "unknown":
        value["extra"] = True
    elif mutation == "bad_digest":
        value["archive_sha256"] = "not-a-sha"
    elif mutation == "bad_head":
        value["helper_head"] = "A" * 40
    elif mutation == "bad_path":
        value["runtime_path"] = "/opt/vst-runtime/../other"
    elif mutation == "bad_inventory_digest":
        value["target_inventory_sha256"] = "invalid"
    else:
        value["compiler_resolved_path"] = "/tmp/unreviewed-compiler"

    with pytest.raises(ContractError):
        bundle.validate_manifest(value)


@pytest.mark.parametrize("mutation", ["schema_bool", "helper_gid_bool", "nlink_bool", "mode_bool"])
def test_manifest_rejects_booleans_where_integer_metadata_is_required(mutation: str) -> None:
    value = valid_manifest()
    if mutation == "schema_bool":
        value["schema"] = True
    elif mutation == "helper_gid_bool":
        value["helper_gid"] = True
    elif mutation == "nlink_bool":
        value["helper_nlink"] = True
    else:
        value["units"][bundle.UNITS[0]]["new"]["mode"] = True

    with pytest.raises(ContractError):
        bundle.validate_manifest(value)


def test_manifest_rejects_extra_unit_and_wrong_fixed_helper_identity() -> None:
    extra = valid_manifest()
    extra["units"]["other.service"] = {"old": {"kind": "absent"}, "new": {"kind": "absent"}}
    with pytest.raises(ContractError, match="exactly the six"):
        bundle.validate_manifest(extra)

    changed = valid_manifest()
    changed["helper_path"] = "/tmp/worker"
    with pytest.raises(ContractError, match="fixed versioned destinations"):
        bundle.validate_manifest(changed)


def test_manifest_rejects_hardlinked_new_unit_and_nonroot_parent() -> None:
    linked = valid_manifest()
    linked["units"][bundle.UNITS[0]]["new"]["nlink"] = 2
    with pytest.raises(ContractError, match="one hard link"):
        bundle.validate_manifest(linked)

    unsafe = valid_manifest()
    unsafe["parents"]["/opt"]["mode"] = 0o775
    with pytest.raises(ContractError, match="parent metadata"):
        bundle.validate_manifest(unsafe)
