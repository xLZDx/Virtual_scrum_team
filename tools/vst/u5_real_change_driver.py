"""U5-7 driver: one small real change through the U5 pipeline (reproducible run).

Stages: 1 AEVE proposal (aeve.repair.patch, no model) -> 2 apply_proposals (U5-2 + U5-1 gate)
-> 3 review loop with the real AEVE CLI through tools/uc router + adapter (U5-4)
-> 4 final package (U5-5). Every stage runs only when the previous one allows it; a refusal is
recorded as the outcome and is never worked around. This script never runs a test or a test runner.

Run it once on a clean worktree at the base head (a second run sees the already applied change).
Environment: PYTHONPATH=<target worktree>;<aeve checkout>/src, interpreter C:/Python314/python.exe -s.

  python -s tools/vst/u5_real_change_driver.py --worktree <target> --aeve <aeve checkout> \
      --target-file tests/uc/test_token_baseline.py --out <evidence dir>

Evidence goes to <out>/evidence.json plus the g6.patch.v1 documents. Run the script from a copy
outside the worktree (or pass --allow-dirty-snapshot): an untracked driver inside the worktree
makes the AEVE snapshot dirty and therefore PARTIAL.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PYTHON = "C:/Python314/python.exe"
STORY = "u5-7-real-change"
ROLES = ["repo-recon", "git-worktree-ops"]  # class LOCAL, COVERED_PARTIAL in catalog/role_table.json
REQUIRED_TEST_IDS = [
    "tests/uc/test_token_baseline.py::test_compute_empty_subagent_transcript_is_not_run",
    "tests/uc/test_token_baseline.py::test_compute_unexpected_transcript_after_manifest_created_is_not_run",
]
NOT_RUN_REASON = "operator ban on running tests"


def git(root: str, *args: str) -> str:
    done = subprocess.run(["git", "-C", root, *args], capture_output=True, check=True, timeout=60)
    return done.stdout.decode("utf-8", "replace").strip()


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")


def stage_propose(args, ev: dict) -> tuple[dict, dict]:
    """Stage 1: the AEVE repair lab proposes bounded patches (llm_calls must be 0)."""
    from aeve.intelligence.snapshot import capture_snapshot
    from aeve.repair.patch import propose_patches_report

    t0 = time.perf_counter()
    snapshot = capture_snapshot(Path(args.worktree), allow_dirty=args.allow_dirty_snapshot)
    t1 = time.perf_counter()
    full = propose_patches_report(snapshot)
    t2 = time.perf_counter()
    narrow_snapshot = copy.copy(snapshot)  # same real capture, only the source set is cut to the declared file
    narrow_snapshot.source_bytes = {args.target_file: snapshot.source_bytes[args.target_file]}
    narrow = propose_patches_report(narrow_snapshot)
    out = Path(args.out)
    write_json(out / "g6_patch_v1_full.json", full)
    write_json(out / "g6_patch_v1_narrow.json", narrow)

    def summary(doc: dict) -> dict:
        return {
            "llm_calls": doc["llm_calls"], "executed_project_code": doc["executed_project_code"],
            "proposal_count": doc["proposal_count"], "status": doc.get("status"), "uncovered": doc.get("uncovered"),
            "report_sha256": doc["report_sha256"],
            "recipes": sorted({p["recipe"] for p in doc["proposals"]}),
            "files_with_changed_patch": sorted({p["file"] for p in doc["proposals"] if p["changed"]}),
            "target_proposals": [{k: p[k] for k in ("file", "recipe", "detail", "changed")}
                                 for p in doc["proposals"] if p["file"] == args.target_file],
        }

    ev["propose"] = {
        "snapshot_head": snapshot.head, "snapshot_status": snapshot.status, "snapshot_dirty": snapshot.dirty,
        "snapshot_uncovered": list(snapshot.uncovered), "snapshot_seconds": round(t1 - t0, 3),
        "propose_seconds": round(t2 - t1, 3), "full_document": summary(full), "narrow_document": summary(narrow),
        "narrow_document_note": "same snapshot, source_bytes cut to the declared file; full document kept for comparison",
    }
    if full["llm_calls"] != 0 or narrow["llm_calls"] != 0:
        raise SystemExit("llm_calls is not 0: stop")
    return full, narrow


def stage_apply(args, doc: dict, key: str, ev: dict, base_head: str, proposal_head: str):
    from tools.vst import patch_proposals
    from tools.vst.worker_gate import IsolationContext

    manifest = hashlib.sha256(json.dumps(
        {"task": "U5-7", "allowed_paths": [args.target_file], "base_head": base_head},
        sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
    isolation = IsolationContext(  # real os.lstat / os.path.realpath defaults
        worktree_root=args.worktree, main_checkout_root=args.main_checkout, network_requested=False,
        pinned_base_head=base_head, worktree_head=base_head)
    t0 = time.perf_counter()
    result = patch_proposals.apply_proposals(
        document=doc, manifest_sha256=manifest, base_head=base_head, proposal_base_head=proposal_head,
        allowed_paths=[args.target_file], protected_paths=[], isolation=isolation)
    ev["apply_" + key] = {"seconds": round(time.perf_counter() - t0, 3), "manifest_sha256": manifest,
                          "base_head": base_head, "result": result.to_dict()}
    return result


def executors_of(table: dict, roles: list[str]) -> list[str]:
    found = set()
    for entry in table["entries"]:
        if entry.get("coverage_state") == "COVERED_PARTIAL" and (entry.get("role") in roles or entry.get("canonical_role") in roles
                                                                  or entry.get("name") in roles):
            found.update(entry["executors"])
    return sorted(found)


def stage_review(args, apply_result, base_head: str, ev: dict):
    """Stage 3: review loop; submit = real tools/uc router -> real AEVE CLI."""
    from tools.uc import router
    from tools.vst import review_loop as rl
    from tools.vst.pipeline_migration import migrate_pipeline
    from tools.vst.pipeline_state import PipelineState
    from tools.vst.store import Store

    out = Path(args.out)
    table_path = Path(args.worktree) / "catalog" / "role_table.json"
    table, table_sha = router.load_table_with_digest(table_path)
    declared = executors_of(table, ROLES)
    state_dir = Path(args.state_dir)
    changed = list(apply_result.changed_paths)
    paths_sha = router.contracts.changed_paths_sha256(changed)
    submitted: list[dict] = []

    def run_router(request_id: str, iteration_of: str | None, purpose: str) -> dict:
        role_request = {"schema_version": "uc.role-request.v1", "request_id": request_id, "root": args.worktree,
                        "base_revision": base_head, "changed_paths": changed, "roles": list(ROLES), "purpose": purpose}
        if iteration_of:
            role_request["iteration_of"] = iteration_of
        t0 = time.perf_counter()
        result = router.review(role_request, table=table, aeve_root=Path(args.aeve), state_dir=state_dir,
                               allowed_roots=[args.worktree], table_sha256=table_sha, python=PYTHON, timeout=180.0)
        submitted.append({"purpose": purpose, "request_id": request_id, "seconds": round(time.perf_counter() - t0, 3),
                          "schema_version": result.get("schema_version"), "status": result.get("status"),
                          "reason": result.get("reason"), "detail": result.get("detail"), "result": result})
        return result

    def submit(request):
        return run_router(request.request_id, request.iteration_of, "receipt")

    def verify_report(doc) -> bool:
        # The uc.role-result.v1 contract has no signature and the repository has no report signer for router
        # results (the E2E harness used an invented HMAC convention). Nothing verifies integrity: not verified.
        return False

    class Clock:
        def __call__(self) -> float:
            return time.time()

    db = out / "story.db"
    for suffix in ("", "-wal", "-shm"):
        try:
            os.remove(str(db) + suffix)
        except FileNotFoundError:
            pass
    store = Store(str(db), time.time, event_key=os.urandom(32))  # ephemeral key, never written
    try:
        store.init_slots(1)
        store.open_story(STORY, "u5-7", 4)
        epoch = store.acquire_epoch(STORY, "u5-7-driver", 600.0)
        migrate_pipeline(str(db))
        state = PipelineState(store)
        state.start_worker_attempt(STORY, epoch=epoch, step_id="s-start-1", base_head=base_head)
        t0 = time.perf_counter()
        loop = rl.run_review_loop(
            state, STORY, epoch=epoch, attempt_no=1, initial_head=base_head, declared_coverage=declared,
            iteration_cap=2, changed_paths_sha256=paths_sha, submit=submit, verify_report=verify_report,
            clock=Clock(), manifest_sha256=ev["apply_used"]["manifest_sha256"], allowed_paths=[args.target_file],
            protected_paths=[])
        loop_seconds = time.perf_counter() - t0
    finally:
        store.close()
    ev["review_loop"] = {"declared_coverage": declared, "head_reviewed": base_head, "seconds": round(loop_seconds, 3),
                         "submit_calls": len(submitted), "router_calls": [
                             {k: v for k, v in s.items() if k != "result"} for s in submitted],
                         "result": loop.to_dict()}
    # One extra informational review: advisory purpose on the dirty tree (never a receipt, never fed to CLEAN).
    adv = run_router("u5-7-advisory-1", None, "advisory")
    ev["advisory_review"] = {"note": "informational only; advisory reports can never make the loop CLEAN",
                             "call": {k: v for k, v in submitted[-1].items() if k != "result"},
                             "result": adv}
    return loop


def stage_package(args, apply_result, loop, base_head: str, ev: dict):
    from tools.vst import final_package as fp
    from tools.vst import patch_proposals

    gate_dict = apply_result.to_dict()["gate"] or {}
    proof = gate_dict.get("isolation_proof")
    share = patch_proposals.build_run_record(apply_result, {})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = time.perf_counter()
    pkg = fp.build_final_package(
        story_id=STORY, base_head=base_head, head=apply_result.candidate_head, diff_bytes=apply_result.diff_bytes,
        diff_sha256=apply_result.diff_sha256, changed_paths=list(apply_result.changed_paths),
        test_evidence=[{"test_id": t, "status": "NOT_RUN", "evidence_sha256": None, "head": None,
                        "reason": NOT_RUN_REASON} for t in REQUIRED_TEST_IDS],
        required_test_ids=list(REQUIRED_TEST_IDS), review_results=loop.to_dict(), receipts=[],
        isolation_proof=proof, patch_origin_share=share, now=now,
        allow_not_run={t: NOT_RUN_REASON for t in REQUIRED_TEST_IDS},
        declared_limits=["U5-7 real run: tests NOT_RUN by operator ban", "no receipts exist for this change"])
    ev["final_package"] = {"seconds": round(time.perf_counter() - t0, 3), "now": now, "run_record": share,
                           "verdict": pkg.verdict, "reasons": [list(r) for r in pkg.reasons],
                           "package_sha256": pkg.package_sha256, "package": pkg.package}


def stage_prescreen_replica(args, doc: dict, ev: dict, base_head: str, proposal_head: str) -> None:
    """Informational: repeat the PRESCREEN gate call of apply_proposals (same arguments) to read the isolation proof.

    apply_proposals does not return the prescreen verdict when it stops later, so this replica calls the same
    U5-1 gate on the same claimed diff. It writes nothing and is not part of the apply result.
    """
    import dataclasses

    from tools.vst import patch_proposals
    from tools.vst import worker_gate as wg

    pset = patch_proposals.validate_proposal_document(doc)
    claimed = b"".join(patch_proposals.git_patch_bytes(p) for p in pset.patches)
    synthetic = hashlib.sha1(f"{base_head}:{pset.report_sha256}:prescreen".encode("ascii")).hexdigest()
    isolation = wg.IsolationContext(worktree_root=args.worktree, main_checkout_root=args.main_checkout,
                                    network_requested=False, pinned_base_head=base_head, worktree_head=base_head)
    verdict = wg.gate_worker_change(
        manifest_sha256=ev["apply_used"]["manifest_sha256"], base_head=base_head, candidate_head=synthetic,
        changed_paths=list(pset.patched_paths), allowed_paths=[args.target_file], protected_paths=[],
        diff_bytes=claimed, isolation=dataclasses.replace(isolation, worktree_head=synthetic))
    ev["prescreen_replica"] = {"note": "informational replica of the PRESCREEN call; claimed diff, placeholder candidate head",
                               "claimed_diff_sha256": hashlib.sha256(claimed).hexdigest(), "result": verdict.to_dict()}


def stage_review_path_probe(args, base_head: str, ev: dict) -> None:
    """Informational: can the real router + AEVE CLI answer a receipt request at all? Reviews the UNCHANGED file."""
    from tools.uc import router

    out = Path(args.out)
    table, table_sha = router.load_table_with_digest(Path(args.worktree) / "catalog" / "role_table.json")
    request = {"schema_version": "uc.role-request.v1", "request_id": "u5-7-probe-1", "root": args.worktree,
               "base_revision": base_head, "changed_paths": [args.target_file], "roles": list(ROLES),
               "purpose": "receipt"}
    t0 = time.perf_counter()
    result = router.review(request, table=table, aeve_root=Path(args.aeve), state_dir=Path(args.state_dir),
                           allowed_roots=[args.worktree], table_sha256=table_sha, python=PYTHON, timeout=180.0)
    ev["review_path_probe"] = {"note": "reviews the UNCHANGED target file at HEAD; it is not a review of any change",
                               "seconds": round(time.perf_counter() - t0, 3), "result": result}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--main-checkout", default="D:/Repo/Virtual_scrum_team")
    ap.add_argument("--aeve", required=True)
    ap.add_argument("--target-file", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--state-dir", required=True, help="short absolute path outside the worktree (AEVE ledger paths are long)")
    ap.add_argument("--allow-dirty-snapshot", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ev: dict = {"tests": "NOT_RUN (operator ban on running tests)", "target_file": args.target_file}
    ev_path = out / "evidence.json"
    t_all = time.perf_counter()
    try:
        base_head = git(args.worktree, "rev-parse", "HEAD")
        ev["base_head"] = base_head
        ev["git_status_before"] = git(args.worktree, "status", "--porcelain")
        full, narrow = stage_propose(args, ev)
        proposal_head = ev["propose"]["snapshot_head"]
        result = stage_apply(args, full, "full", ev, base_head, proposal_head)
        ev["apply_used"] = ev["apply_full"]
        if result.verdict != "ACCEPTED":
            ev["apply_used_note"] = "full document not ACCEPTED; retrying once with the narrow document"
            result = stage_apply(args, narrow, "narrow", ev, base_head, proposal_head)
            ev["apply_used"] = ev["apply_narrow"]
        ev["git_status_after_apply"] = git(args.worktree, "status", "--porcelain")
        if result.verdict == "ACCEPTED":
            ev["git_diff_after_apply"] = git(args.worktree, "diff")
            loop = stage_review(args, result, base_head, ev)
            stage_package(args, result, loop, base_head, ev)
        else:
            stage_prescreen_replica(args, narrow, ev, base_head, proposal_head)
            stage_review_path_probe(args, base_head, ev)
            ev["review_loop"] = "NOT_RUN: apply was not ACCEPTED, so there is no candidate change to review"
            ev["final_package"] = "NOT_RUN: apply was not ACCEPTED (no diff, no review result of a candidate)"
    finally:
        ev["total_seconds"] = round(time.perf_counter() - t_all, 3)
        write_json(ev_path, ev)
    print("evidence written to", ev_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
