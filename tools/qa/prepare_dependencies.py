"""Prepare a new isolated S4 QA target from an already-present locked wheelhouse."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.qa.dependencies import (
    DependencyProvenanceError,
    is_link_or_junction,
    prepare_dependency_target,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--wheelhouse", required=True)
    parser.add_argument("--dependency-target", required=True)
    return parser.parse_args()


def main() -> int:
    args = _args()
    try:
        repo = Path(args.repo_root).resolve(strict=True)
        if not repo.is_dir():
            raise DependencyProvenanceError("repo-root must be an existing directory")
        wheelhouse_input = Path(args.wheelhouse)
        if is_link_or_junction(wheelhouse_input):
            raise DependencyProvenanceError("wheelhouse cannot be a symlink")
        wheelhouse = wheelhouse_input.resolve(strict=True)
        target_input = Path(args.dependency_target)
        target = target_input.resolve(strict=False)
        if is_link_or_junction(target_input) or target.is_relative_to(repo):
            raise DependencyProvenanceError("dependency target must be a new external directory")
        if wheelhouse.is_relative_to(repo):
            raise DependencyProvenanceError("wheelhouse must be outside the candidate repository")
        evidence = prepare_dependency_target(
            repo / "tools" / "qa" / "requirements.lock", wheelhouse, target
        )
    except (OSError, DependencyProvenanceError) as exc:
        print(f"QA_DEPENDENCY_PREPARE BLOCKED: {type(exc).__name__}: {exc}")
        return 2
    print(json.dumps({
        "result": "PREPARED",
        "lock_sha256": evidence["lock_sha256"],
        "dependency_wheels": evidence["wheels"],
        "dependency_target_sha256": evidence["target_sha256"],
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
