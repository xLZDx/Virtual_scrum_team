"""Prepare an unsigned, non-secret source plan; never install or approve a bundle."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

CANONICAL_ROOT = Path("D:/Repo/Virtual_scrum_team")
ARCHIVE_PATHS = (
    "tools/vst", "tools/qa/install_wsl_runner_runtime.sh",
    "tools/qa/install_wsl_worker_helper.sh", "tools/qa/verify_wsl_source_bundle.py",
    "tools/qa/verify_wsl_runtime_stage.py",
    "tools/qa/worker_exec.c",
    "docs/SANDBOX_SPEC.md",
)
UNITS = (
    "vst-supervisor.service", "vst-signer.service", "vst-runner.service",
    "vst-dispatcher.service", "vst-dispatch-owner.service", "vst-dispatch-owner.socket",
)
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024


def _git(root: Path, *arguments: str) -> bytes:
    # Archive paths and revision are fixed or validated; no shell evaluation.
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
         "-C", str(root), "--no-replace-objects", *arguments],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=60, check=False,
    )
    if result.returncode:
        raise ValueError("git source inspection failed: " + result.stderr.decode("utf-8", "replace")[:2048])
    if len(result.stdout) > MAX_ARCHIVE_BYTES:
        raise ValueError("source output exceeds the 64 MiB limit")
    return result.stdout


def prepare_source_plan(root: Path, expected_head: str) -> dict:
    """Describe committed source; returned candidate is not staging authorization.

    Dirty working files are not inputs. The Windows handoff independently requires
    its working script to equal the committed version before executing anything.
    Target inventory and compiler provenance must be attached and reviewed later.
    """
    root = root.resolve(strict=True)
    if root != CANONICAL_ROOT.resolve(strict=True):
        raise ValueError("source plan requires the canonical project checkout")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise ValueError("expected HEAD must be 40 lowercase hex characters")
    actual = _git(root, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if actual != expected_head:
        raise ValueError("checkout HEAD differs from requested source revision")
    archive = _git(root, "archive", "--format=tar", expected_head, "--", *ARCHIVE_PATHS)
    if not archive:
        raise ValueError("empty source archive")
    files: dict[str, str] = {}
    archive_members: dict[str, dict[str, object]] = {}
    entries: set[str] = set()
    total = 0
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as stream:
        for member in stream:
            name = member.name.rstrip("/")
            if (not name or name.startswith("/") or "\\" in name
                    or any(part in ("", ".", "..") for part in name.split("/"))
                    or name in entries or not (member.isdir() or member.isreg())):
                raise ValueError("unsafe or duplicate source archive member")
            entries.add(name)
            if len(entries) > 50000:
                raise ValueError("too many archive entries")
            if member.isdir():
                archive_members[name] = {"kind": "dir"}
            if member.isreg():
                total += member.size
                if member.size < 0 or total > MAX_ARCHIVE_BYTES:
                    raise ValueError("expanded source archive exceeds limit")
                content = stream.extractfile(member)
                if content is None:
                    raise ValueError("unreadable archive member")
                data = content.read()
                if len(data) != member.size:
                    raise ValueError("archive member size differs from its declared size")
                digest = hashlib.sha256(data).hexdigest()
                files[name] = digest
                archive_members[name] = {"kind": "file", "sha256": digest, "size": len(data)}
    required = {"docs/SANDBOX_SPEC.md", "tools/qa/worker_exec.c",
                "tools/qa/install_wsl_worker_helper.sh", "tools/qa/install_wsl_runner_runtime.sh",
                "tools/qa/verify_wsl_source_bundle.py",
                "tools/qa/verify_wsl_runtime_stage.py"}
    required.update("tools/vst/systemd/" + name for name in UNITS)
    if not required <= files.keys():
        raise ValueError("source archive lacks a required runtime artifact")
    return {
        "schema": "VST_S2_RUNTIME_SOURCE_PLAN_V2",
        "status": "UNSIGNED_REVIEW_CANDIDATE",
        "source_head": expected_head,
        "archive_sha256": hashlib.sha256(archive).hexdigest(),
        "archive_members": archive_members,
        "sandbox_spec_sha256": files["docs/SANDBOX_SPEC.md"],
        "archive_files": files,
        "unit_sha256": {name: files["tools/vst/systemd/" + name] for name in UNITS},
        "runtime_path": "/opt/vst-runtime-" + expected_head,
        "helper": {
            "path": "/usr/local/libexec/vst-s4-worker-exec-" + expected_head,
            "source_sha256": files["tools/qa/worker_exec.c"],
            "build_recipe_sha256": files["tools/qa/install_wsl_worker_helper.sh"],
            "compiler_path": "/usr/bin/cc",
            "compiler_provenance": "NOT_VERIFIED",
            "binary_sha256": None,
            "uid": 0, "gid": 988, "mode": "4750",
        },
        "target_inventory": "NOT_VERIFIED",
        "store_disposition": "UNKNOWN",
        "permitted_operation": "stage-only-after-source-tests-and-exact-plan-review",
        "selection": "separate-post-staging-manifest-review-required",
        "activation": "NOT_AUTHORIZED_BY_THIS_PLAN",
        "unresolved": ["current target/identity collision inventory", "compiler provenance",
                       "source/test approval and exact staging-plan review"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    try:
        plan = prepare_source_plan(Path(__file__).resolve().parents[2], args.expected_head)
    except (ValueError, OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        parser.exit(1, "source plan refused: " + str(exc) + "\n")
    print(json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


if __name__ == "__main__":
    main()
