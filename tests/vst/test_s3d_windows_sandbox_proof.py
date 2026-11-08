"""S3-D functional tests for tools/vst/windows_sandbox_proof.py.

Layers:
- pure checkers / report builder: baseline-good fixtures, mutated one thing at a time, asserting that
  exactly the targeted sub-check fails (so each check fails separately);
- parser: captured icacls text fixtures;
- real host (read-only, no accounts/ACL/firewall changes, provisioning script never run): loopback
  canary, blocked-target connect to 192.0.2.1 (short timeout), job inventory, worker probe, icacls
  inventory of a temp dir, junction walk in a temp dir, account/firewall PowerShell collectors.

Tests named test_DEFECT_* assert the CORRECT (fail-closed) behavior and are expected to FAIL
while the defect exists in the product code; they are not marked xfail on purpose.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys

import pytest

from tools.vst import windows_sandbox_proof as w
from tools.vst.contracts import ContractError

WSID = "S-1-5-21-1111-2222-3333-1001"
RSID = "S-1-5-21-1111-2222-3333-1000"
GRP = "S-1-5-21-1111-2222-3333-1100"
RUN_ID = "run-s3d-1"
SHA = "a" * 40
NOW = 1_000_000.0
MAX_AGE = 300.0

RUN_DIR = "C:\\vst-runs\\r1"
WORKTREE = "C:\\vst-runs\\r1\\wt"
SIGNER, KEY, STORE = "D:\\vst\\signer", "D:\\vst\\keys", "D:\\vst\\store"


@pytest.fixture
def nonwindows(monkeypatch):
    monkeypatch.setattr(w, "_is_windows", lambda: False)

    def boom(*a, **k):
        raise AssertionError("subprocess must not be spawned on a non-Windows host")

    monkeypatch.setattr(subprocess, "run", boom)


# ------------------------------------------------------------------ fixtures

def good_account():
    return {
        "worker": {"name": "vst-worker", "sid": WSID, "enabled": True, "is_local": True,
                   "groups": [{"sid": "S-1-5-32-545", "name": "Users"}], "groups_complete": True},
        "runner": {"name": "HOST\\runner", "sid": RSID},
    }


def worker():
    return good_account()["worker"]


def ace(sid, rights, kind="allow", flags=()):
    return {"sid": sid, "type": kind, "rights": list(rights), "flags": list(flags)}


def acl_item(path, entries=None, complete=True):
    if entries is None:
        entries = [ace("S-1-5-18", ["F"]), ace("S-1-5-32-544", ["F"]), ace(WSID, ["F"], "deny", ["OI", "CI"])]
    return {"path": path, "complete": complete, "entries": entries}


def good_acl():
    return {"paths": [acl_item(SIGNER), acl_item(KEY), acl_item(STORE)]}


def host_item(path="C:\\Windows", entries=None):
    if entries is None:
        entries = [ace("S-1-5-18", ["F"]), ace("S-1-5-32-544", ["F"]), ace("S-1-5-32-545", ["RX"])]
    return acl_item(path, entries)


def good_worktree():
    return {"run_dir": RUN_DIR, "run_dir_real": RUN_DIR, "worktree": WORKTREE, "worktree_real": WORKTREE,
            "walk_complete": True, "reparse_points": [], "host_paths": [host_item()]}


BLOCK_ADDRS = ["0.0.0.0-126.255.255.255", "128.0.0.0-255.255.255.255",
               "::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"]


def block_rule(sddl=None, addrs=None, **kw):
    r = {"name": "blk", "enabled": True, "direction": "Outbound", "action": "Block",
         "local_user_sddl": f"D:(A;;CC;;;{WSID})" if sddl is None else sddl,
         "remote_addresses": list(BLOCK_ADDRS if addrs is None else addrs),
         # unrestricted form of every filter field the checker requires (missing field = restricted)
         "profile": ["Any"], "protocol": ["Any"], "local_port": ["Any"], "remote_port": ["Any"],
         "program": ["Any"], "service": ["Any"], "interface_type": ["Any"], "local_address": ["Any"]}
    r.update(kw)
    return r


def good_fw():
    return {"profiles": [{"name": n, "enabled": True} for n in ("Domain", "Private", "Public")],
            "rules": [block_rule()]}


def good_egress():
    return {"identity_sid": WSID, "loopback_canary_ok": True, "external_connected": False, "external_errno": 10013}


def good_job():
    return {"in_job": True, "windows_build": 22631, "nesting_supported": True,
            "limits": {"kill_on_job_close": True, "breakaway_ok": False, "silent_breakaway_ok": False,
                       "active_process_limit": 8, "process_memory_limit": 1 << 30,
                       "job_memory_limit": 0, "process_time_limit_100ns": 0, "job_time_limit_100ns": 0}}


def good_meta(observed=NOW - 10):
    return {"run_id": RUN_ID, "candidate_sha": SHA, "observed_at_epoch": observed}


def good_probe():
    return {"meta": good_meta(), "egress": good_egress(), "job": good_job()}


def good_inventories():
    return {"account": good_account(), "acl": good_acl(), "worktree": good_worktree(),
            "firewall": good_fw(), "worker_probe": good_probe()}


def failed(verdict):
    return {s["id"] for s in verdict["subchecks"] if not s["ok"]}


def evaluate(inv):
    return w.evaluate_proof(inv, run_id=RUN_ID, candidate_sha=SHA, now=NOW, max_age_sec=MAX_AGE)


# ====================================================== non-Windows refusal

def test_nonwindows_pure_checkers_refuse(nonwindows):
    calls = [
        lambda: w.check_worker_account(good_account()),
        lambda: w.check_secret_isolation(good_acl(), worker()),
        lambda: w.check_worktree_confinement(good_worktree(), worker()),
        lambda: w.check_egress(good_fw(), good_egress(), worker()),
        lambda: w.check_probe_binding(good_meta(), run_id=RUN_ID, candidate_sha=SHA, now=NOW, max_age_sec=MAX_AGE),
        lambda: w.check_job_object(good_job()),
        lambda: w.parse_icacls_output("C:\\x BUILTIN\\Users:(R)\n", "C:\\x"),
        lambda: evaluate(good_inventories()),
    ]
    for i, call in enumerate(calls):
        with pytest.raises(ContractError, match="Windows host"):
            call()
        assert i >= 0


def test_nonwindows_collectors_and_builder_refuse_without_spawning(nonwindows):
    calls = [
        lambda: w.collect_account_inventory("vst-worker"),
        lambda: w.collect_acl_inventory(["C:\\Windows"]),
        lambda: w.collect_firewall_inventory(WSID),
        lambda: w.collect_worktree_inventory("C:\\Windows", "C:\\Windows", ["C:\\Windows"]),
        lambda: w.collect_job_inventory(),
        lambda: w.collect_worker_probe(RUN_ID, SHA),
        lambda: w.build_probe_record(run_id=RUN_ID, candidate_sha=SHA, worker_name="vst-worker", run_dir=RUN_DIR,
                                     worktree=WORKTREE, protected_paths=[SIGNER], host_paths=["C:\\Windows"],
                                     collectors={}),
    ]
    for call in calls:
        with pytest.raises(ContractError, match="Windows host"):
            call()


def test_nonwindows_cli_returns_2(nonwindows, capsys):
    assert w.main(["probe", "--run-id", RUN_ID, "--sha", SHA]) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_baseline_windows_checkers_pass_so_refusal_tests_are_meaningful():
    # Same call set as the non-Windows tests, on the real (Windows) host: must NOT raise.
    assert w.check_worker_account(good_account())["result"] == "PASS"
    assert w.check_secret_isolation(good_acl(), worker())["result"] == "PASS"
    assert w.check_worktree_confinement(good_worktree(), worker())["result"] == "PASS"
    assert w.check_egress(good_fw(), good_egress(), worker())["result"] == "PASS"
    assert w.check_probe_binding(good_meta(), run_id=RUN_ID, candidate_sha=SHA, now=NOW, max_age_sec=MAX_AGE)["result"] == "PASS"
    assert w.check_job_object(good_job())["result"] == "PASS"
    assert evaluate(good_inventories())["result"] == "PASS"


# ====================================================== icacls parser

ICACLS_TEXT = (
    "D:\\vst\\my keys NT AUTHORITY\\SYSTEM:(OI)(CI)(F)\n"
    "                  BUILTIN\\Administrators:(OI)(CI)(F)\n"
    "                  HOST\\vst-worker:(OI)(CI)(DENY)(F)\n"
    "                  HOST\\runner:(I)(RX,W)\n"
    "                  Everyone:(RX)\n"
    "\n"
    "Successfully processed 1 files; Failed processing 0 files\n"
)


def test_parse_icacls_fixture():
    ents = w.parse_icacls_output(ICACLS_TEXT, "D:\\vst\\my keys")
    assert [e["name"] for e in ents] == ["NT AUTHORITY\\SYSTEM", "BUILTIN\\Administrators", "HOST\\vst-worker",
                                         "HOST\\runner", "Everyone"]
    deny = ents[2]
    assert deny["type"] == "deny" and deny["rights"] == ["F"] and deny["flags"] == ["OI", "CI"]
    assert ents[0]["type"] == "allow" and ents[0]["rights"] == ["F"]
    assert ents[3]["rights"] == ["RX", "W"] and ents[3]["flags"] == ["I"]


def test_parse_icacls_case_insensitive_path_echo():
    assert w.parse_icacls_output(ICACLS_TEXT, "d:\\VST\\my keys")[0]["name"] == "NT AUTHORITY\\SYSTEM"


@pytest.mark.parametrize("text,path", [
    (ICACLS_TEXT, "D:\\other"),                                   # echoes a different path
    ("", "D:\\x"),                                                # empty
    ("D:\\x: Access is denied.\nSuccessfully processed 0 files; Failed processing 1 files\n", "D:\\x"),  # no ACE
    ("garbage line\n", "D:\\x"),
])
def test_parse_icacls_refuses_ambiguous_output(text, path):
    with pytest.raises(ContractError):
        w.parse_icacls_output(text, path)


# ====================================================== check_worker_account

def acct_mut(fn):
    a = good_account()
    fn(a)
    return failed(w.check_worker_account(a))


def test_account_good_passes():
    assert w.check_worker_account(good_account())["result"] == "PASS"


def test_account_worker_equals_runner_sid():
    a = good_account()
    a["runner"]["sid"] = WSID
    v = w.check_worker_account(a)
    assert v["result"] == "FAIL" and failed(v) == {"distinct_from_runner"}


def test_account_worker_equals_runner_name_with_different_sid_and_domain_prefix():
    a = good_account()
    a["runner"]["name"] = "OTHERHOST\\VST-Worker"
    assert failed(w.check_worker_account(a)) == {"distinct_from_runner"}


def test_account_admin_group_membership():
    a = good_account()
    a["worker"]["groups"].append({"sid": "S-1-5-32-544", "name": "Administrators"})
    v = w.check_worker_account(a)
    assert v["result"] == "FAIL" and failed(v) == {"not_admin"}


def test_account_rid_500_is_admin():
    a = good_account()
    a["worker"]["sid"] = "S-1-5-21-1111-2222-3333-500"
    assert failed(w.check_worker_account(a)) == {"not_admin"}


def test_account_incomplete_group_enumeration_fails_both_evidence_and_admin():
    a = good_account()
    a["worker"]["groups_complete"] = False
    v = w.check_worker_account(a)
    assert v["result"] == "FAIL" and failed(v) == {"group_evidence_complete", "not_admin", "no_privileged_groups"}


def test_account_disabled_and_nonlocal():
    a = good_account()
    a["worker"]["enabled"] = False
    assert failed(w.check_worker_account(a)) == {"enabled"}
    a = good_account()
    a["worker"]["is_local"] = False
    assert failed(w.check_worker_account(a)) == {"is_local"}


@pytest.mark.parametrize("mutate", [
    lambda a: a.pop("runner"),
    lambda a: a.pop("worker"),
    lambda a: a["worker"].pop("groups_complete"),
    lambda a: a["worker"].pop("groups"),
    lambda a: a["worker"].update(sid="not-a-sid"),
    lambda a: a["runner"].update(sid=None),
    lambda a: a["worker"].update(groups_complete=1),      # bool-typed field must be a real bool
    lambda a: a["worker"].update(enabled="yes"),
    lambda a: a["worker"].update(groups=[{"name": "x"}]),
    lambda a: a["worker"].update(name=5),
])
def test_account_malformed_refused(mutate):
    a = good_account()
    mutate(a)
    with pytest.raises(ContractError):
        w.check_worker_account(a)


def test_account_non_dict_refused():
    with pytest.raises(ContractError):
        w.check_worker_account(None)


# ====================================================== check_secret_isolation

def acl_with(path_idx, entries, complete=True):
    acl = good_acl()
    acl["paths"][path_idx] = acl_item([SIGNER, KEY, STORE][path_idx], entries, complete)
    return acl


@pytest.mark.parametrize("idx,path", [(0, SIGNER), (1, KEY), (2, STORE)])
@pytest.mark.parametrize("rights,label", [(["R"], "read"), (["W"], "write"), (["F"], "read/write"), (["M"], "read/write"),
                                          (["RX"], "read"), (["GR"], "read"), (["WD"], "write")])
def test_secret_direct_access_fails_only_that_path(idx, path, rights, label):
    acl = acl_with(idx, [ace("S-1-5-18", ["F"]), ace(WSID, rights)])
    v = w.check_secret_isolation(acl, worker())
    assert v["result"] == "FAIL"
    assert failed(v) == {f"no_worker_access:{path}"}
    assert label in [s["detail"] for s in v["subchecks"] if not s["ok"]][0]


def test_secret_via_group_membership_read_and_write():
    wk = worker()
    wk["groups"].append({"sid": GRP, "name": "devs"})
    for rights in (["R"], ["W"]):
        acl = acl_with(0, [ace(GRP, rights)])
        assert failed(w.check_secret_isolation(acl, wk)) == {f"no_worker_access:{SIGNER}"}
    # same ACL, worker NOT in that group -> pass (proves the group lookup is what fails the first)
    assert w.check_secret_isolation(acl_with(0, [ace(GRP, ["F"])]), worker())["result"] == "PASS"


@pytest.mark.parametrize("sid", ["S-1-1-0", "S-1-5-11", "S-1-5-32-545"])
def test_secret_via_implicit_everyone_authenticated_users(sid):
    v = w.check_secret_isolation(acl_with(1, [ace(sid, ["R"])]), worker())
    assert failed(v) == {f"no_worker_access:{KEY}"}


def test_secret_via_unresolved_principal_none_sid():
    v = w.check_secret_isolation(acl_with(2, [ace(None, ["F"], "allow")]), worker())
    assert failed(v) == {f"no_worker_access:{STORE}"}
    assert "unresolved" in [s["detail"] for s in v["subchecks"] if not s["ok"]][0]


@pytest.mark.parametrize("token", ["ZZ", "MA", "AS", "XYZZY"])
def test_secret_via_unknown_right_token_fails_closed(token):
    v = w.check_secret_isolation(acl_with(0, [ace(WSID, [token])]), worker())
    assert failed(v) == {f"no_worker_access:{SIGNER}"}


def test_secret_incomplete_acl_evidence_fails():
    v = w.check_secret_isolation(acl_with(1, [ace("S-1-5-18", ["F"])], complete=False), worker())
    assert failed(v) == {f"no_worker_access:{KEY}"}
    assert "incomplete" in [s["detail"] for s in v["subchecks"] if not s["ok"]][0]


def test_secret_explicit_deny_removes_allow_and_unrelated_principal_ignored():
    entries = [ace(WSID, ["R"]), ace(WSID, ["F"], "deny"), ace(RSID, ["F"])]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "PASS"
    # no deny -> same ACL fails: the deny is the thing that makes it pass
    assert w.check_secret_isolation(acl_with(0, [ace(WSID, ["R"]), ace(RSID, ["F"])]), worker())["result"] == "FAIL"


def test_secret_none_right_N_is_not_access():
    assert w.check_secret_isolation(acl_with(0, [ace(WSID, ["N"])]), worker())["result"] == "PASS"


@pytest.mark.parametrize("bad", [
    {},
    {"paths": []},
    {"paths": "x"},
    {"paths": [{"path": SIGNER, "entries": []}]},                                   # no complete
    {"paths": [{"path": SIGNER, "complete": "yes", "entries": []}]},                # complete not bool
    {"paths": [{"path": SIGNER, "complete": True, "entries": [{"sid": WSID, "rights": ["R"]}]}]},   # no type
    {"paths": [{"path": SIGNER, "complete": True, "entries": [{"sid": WSID, "type": "maybe", "rights": ["R"]}]}]},
    {"paths": [{"path": SIGNER, "complete": True, "entries": [{"sid": "junk", "type": "allow", "rights": ["R"]}]}]},
    {"paths": [{"path": SIGNER, "complete": True, "entries": [{"sid": WSID, "type": "allow", "rights": "R"}]}]},
    {"paths": [{"path": SIGNER, "complete": True, "entries": "x"}]},
])
def test_secret_missing_or_malformed_evidence_refused(bad):
    with pytest.raises(ContractError):
        w.check_secret_isolation(bad, worker())


def test_secret_worker_missing_fields_refused():
    with pytest.raises(ContractError):
        w.check_secret_isolation(good_acl(), {"sid": WSID})          # no groups
    with pytest.raises(ContractError):
        w.check_secret_isolation(good_acl(), {"groups": []})         # no sid


# DEFECT: a partial deny nullifies a whole class (src _effective_access: allowed - denied on classes).
@pytest.mark.parametrize("deny_right,allow_right", [("DC", "W"), ("D", "W"), ("RA", "R"), ("REA", "RX")])
def test_DEFECT_partial_deny_must_not_hide_remaining_access(deny_right, allow_right):
    entries = [ace(WSID, [allow_right]), ace(WSID, [deny_right], "deny")]
    v = w.check_secret_isolation(acl_with(0, entries), worker())
    assert v["result"] == "FAIL", f"deny of only {deny_right} wrongly erased all of {allow_right}"


def test_DEFECT_unknown_token_in_deny_must_not_count_as_full_deny():
    entries = [ace(WSID, ["F"]), ace(WSID, ["XYZZY"], "deny")]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"


def test_DEFECT_inherit_only_deny_does_not_protect_the_object_itself():
    entries = [ace(WSID, ["F"]), ace(WSID, ["F"], "deny", ["OI", "CI", "IO"])]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"


# ====================================================== check_worktree_confinement

def wt_mut(**kw):
    inv = good_worktree()
    inv.update(kw)
    return inv


def test_worktree_good_passes():
    assert w.check_worktree_confinement(good_worktree(), worker())["result"] == "PASS"


@pytest.mark.parametrize("target", ["C:\\Windows", "C:\\vst-runs\\r10\\x", "D:\\elsewhere", "C:\\vst-runs"])
def test_worktree_junction_or_symlink_escaping_run_dir_fails(target):
    inv = wt_mut(reparse_points=[{"path": WORKTREE + "\\link", "target": target}])
    v = w.check_worktree_confinement(inv, worker())
    assert v["result"] == "FAIL" and failed(v) == {"no_escaping_reparse"}
    assert WORKTREE + "\\link" in [s["detail"] for s in v["subchecks"] if s["id"] == "no_escaping_reparse"][0]


def test_worktree_unresolved_reparse_target_counts_as_escape():
    inv = wt_mut(reparse_points=[{"path": WORKTREE + "\\bad", "target": None}])
    assert failed(w.check_worktree_confinement(inv, worker())) == {"no_escaping_reparse"}


def test_worktree_internal_reparse_is_allowed_and_case_insensitive():
    inv = wt_mut(reparse_points=[{"path": WORKTREE + "\\a", "target": "c:\\VST-RUNS\\R1\\wt\\b"}])
    assert w.check_worktree_confinement(inv, worker())["result"] == "PASS"


def test_worktree_one_bad_of_many_reparse_points_is_enough():
    inv = wt_mut(reparse_points=[{"path": "C:\\vst-runs\\r1\\wt\\ok", "target": "C:\\vst-runs\\r1\\wt\\y"},
                                 {"path": "C:\\vst-runs\\r1\\bad", "target": "C:\\Users"}])
    assert failed(w.check_worktree_confinement(inv, worker())) == {"no_escaping_reparse"}


@pytest.mark.parametrize("real", ["D:\\other\\wt", "C:\\vst-runs\\r10\\wt", "C:\\vst-runs"])
def test_worktree_not_inside_run_dir(real):
    v = w.check_worktree_confinement(wt_mut(worktree_real=real), worker())
    assert failed(v) == {"worktree_inside_run_dir"}


def test_worktree_inside_case_insensitive_passes():
    assert w.check_worktree_confinement(wt_mut(worktree_real="C:\\VST-RUNS\\R1\\WT"), worker())["result"] == "PASS"


def test_worktree_run_dir_reparse_alias_fails():
    v = w.check_worktree_confinement(wt_mut(run_dir="C:\\alias\\r1"), worker())
    assert failed(v) == {"run_dir_not_aliased"}


def test_worktree_incomplete_walk_fails():
    assert failed(w.check_worktree_confinement(wt_mut(walk_complete=False), worker())) == {"walk_complete"}


@pytest.mark.parametrize("rights", [["W"], ["M"], ["F"], ["AD"], ["WD"], ["GW"], ["D"]])
def test_worktree_writable_host_path_fails(rights):
    entries = [ace("S-1-5-18", ["F"]), ace(WSID, rights)]
    v = w.check_worktree_confinement(wt_mut(host_paths=[host_item("C:\\Windows", entries)]), worker())
    assert failed(v) == {"host_path_not_writable:C:\\Windows"}


def test_worktree_host_path_writable_via_authenticated_users_and_group():
    for sid in ("S-1-5-11", "S-1-1-0"):
        v = w.check_worktree_confinement(wt_mut(host_paths=[host_item("C:\\h", [ace(sid, ["M"])])]), worker())
        assert failed(v) == {"host_path_not_writable:C:\\h"}
    wk = worker()
    wk["groups"].append({"sid": GRP, "name": "g"})
    v = w.check_worktree_confinement(wt_mut(host_paths=[host_item("C:\\h", [ace(GRP, ["W"])])]), wk)
    assert failed(v) == {"host_path_not_writable:C:\\h"}


def test_worktree_host_path_read_only_is_allowed_and_second_path_decides():
    inv = wt_mut(host_paths=[host_item("C:\\a", [ace(WSID, ["RX"])]), host_item("C:\\b", [ace(WSID, ["W"])])])
    assert failed(w.check_worktree_confinement(inv, worker())) == {"host_path_not_writable:C:\\b"}


def test_worktree_host_path_unresolved_or_incomplete_fails():
    inv = wt_mut(host_paths=[host_item("C:\\u", [ace(None, ["F"])])])
    assert failed(w.check_worktree_confinement(inv, worker())) == {"host_path_not_writable:C:\\u"}
    inv = wt_mut(host_paths=[acl_item("C:\\i", [], complete=False)])
    assert failed(w.check_worktree_confinement(inv, worker())) == {"host_path_not_writable:C:\\i"}


def test_worktree_different_drive_is_fail_not_crash():
    v = w.check_worktree_confinement(wt_mut(worktree_real="D:\\r1\\wt"), worker())
    assert failed(v) == {"worktree_inside_run_dir"}


@pytest.mark.parametrize("mutate", [
    lambda i: i.update(host_paths=[]),
    lambda i: i.pop("host_paths"),
    lambda i: i.pop("reparse_points"),
    lambda i: i.pop("walk_complete"),
    lambda i: i.update(walk_complete="true"),
    lambda i: i.pop("worktree_real"),
    lambda i: i.update(worktree_real="relative\\wt"),
    lambda i: i.update(reparse_points=[{"path": "x"}]),
    lambda i: i.update(reparse_points=[{"path": "C:\\vst-runs\\r1\\a", "target": "rel"}]),
])
def test_worktree_missing_or_malformed_refused(mutate):
    inv = good_worktree()
    mutate(inv)
    with pytest.raises(ContractError):
        w.check_worktree_confinement(inv, worker())


# ====================================================== check_egress

def eg(fw=None, probe=None, wk=None):
    return w.check_egress(fw or good_fw(), probe or good_egress(), wk or worker())


def test_egress_good_passes():
    assert eg()["result"] == "PASS"


@pytest.mark.parametrize("rules", [
    [],                                                                         # no rule at all
    [block_rule(enabled=False)],                                                # disabled
    [block_rule(direction="Inbound")],                                          # wrong direction
    [block_rule(action="Allow", remote_addresses=["127.0.0.1"])],               # not Block
    [block_rule(sddl=f"D:(A;;CC;;;{RSID})")],                                   # bound to somebody else
    [block_rule(addrs=BLOCK_ADDRS[:2])],                                        # IPv6 hole
    [block_rule(addrs=BLOCK_ADDRS[1:])],                                        # IPv4 low half missing
    [block_rule(addrs=["0.0.0.0-126.255.255.255", "128.0.0.0-200.0.0.0", BLOCK_ADDRS[2]])],  # gap above 200.0.0.0
    [block_rule(addrs=["LocalSubnet"])],                                        # keyword gives no coverage
    [block_rule(addrs=["127.0.0.1"])],                                          # loopback only
    [block_rule(addrs=[])],
])
def test_egress_no_effective_block_rule_fails(rules):
    fw = good_fw()
    fw["rules"] = rules
    v = eg(fw=fw)
    assert v["result"] == "FAIL" and failed(v) == {"worker_block_rule_covers_non_loopback"}


@pytest.mark.parametrize("rule", [
    block_rule(addrs=["Any"]),
    block_rule(sddl=None, addrs=["Any"]) | {"local_user_sddl": None},           # applies to everyone
    block_rule(addrs=["0.0.0.0/1", "128.0.0.0/1", "::/1", "8000::/1"]),         # CIDR coverage
    block_rule(addrs=["0.0.0.0-126.255.255.255", "128.0.0.0-191.255.255.255", "192.0.0.0-255.255.255.255",
                      "::2-7fff:ffff:ffff:ffff:ffff:ffff:ffff:ffff", "8000::-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"]),
])
def test_egress_alternative_complete_block_encodings_pass(rule):
    fw = good_fw()
    fw["rules"] = [rule]
    assert eg(fw=fw)["result"] == "PASS"


def test_egress_profile_disabled_fails_only_profile_subcheck():
    fw = good_fw()
    fw["profiles"][2]["enabled"] = False
    assert failed(eg(fw=fw)) == {"firewall_profiles_enabled"}


@pytest.mark.parametrize("remote", [["Any"], ["8.8.8.8"], ["10.0.0.0/8"], ["127.0.0.1-200.0.0.1"], ["::1", "2001:db8::1"],
                                    ["127.0.0.1", "LocalSubnet"]])
def test_egress_worker_bound_allow_to_non_loopback_fails(remote):
    fw = good_fw()
    fw["rules"].append({"name": "allow-x", "enabled": True, "direction": "Outbound", "action": "Allow",
                        "local_user_sddl": f"D:(A;;CC;;;{WSID})", "remote_addresses": remote})
    v = eg(fw=fw)
    assert v["result"] == "FAIL" and failed(v) == {"no_worker_allow_rule_non_loopback"}
    assert "allow-x" in [s["detail"] for s in v["subchecks"] if not s["ok"]][0]


@pytest.mark.parametrize("remote", [["127.0.0.1"], ["127.0.0.0/8"], ["::1"], ["localhost"], ["127.0.0.1-127.255.255.255"]])
def test_egress_worker_bound_allow_loopback_only_is_fine(remote):
    fw = good_fw()
    fw["rules"].append({"name": "allow-lo", "enabled": True, "direction": "Outbound", "action": "Allow",
                        "local_user_sddl": f"D:(A;;CC;;;{WSID})", "remote_addresses": remote})
    assert eg(fw=fw)["result"] == "PASS"


def test_egress_allow_for_other_user_or_disabled_or_inbound_is_ignored():
    fw = good_fw()
    base = {"name": "a", "enabled": True, "direction": "Outbound", "action": "Allow",
            "local_user_sddl": f"D:(A;;CC;;;{RSID})", "remote_addresses": ["Any"]}
    fw["rules"] += [base, dict(base, local_user_sddl=f"D:(A;;CC;;;{WSID})", enabled=False),
                    dict(base, local_user_sddl=f"D:(A;;CC;;;{WSID})", direction="Inbound")]
    assert eg(fw=fw)["result"] == "PASS"


def test_egress_probe_identity_not_worker_fails_only_identity():
    p = good_egress()
    p["identity_sid"] = RSID
    assert failed(eg(probe=p)) == {"probe_ran_as_worker"}


def test_egress_external_connect_succeeded_fails_only_external():
    p = good_egress()
    p.update(external_connected=True, external_errno=None)
    assert failed(eg(probe=p)) == {"external_blocked"}


def test_egress_loopback_canary_failed_fails_only_canary():
    p = good_egress()
    p["loopback_canary_ok"] = False
    assert failed(eg(probe=p)) == {"loopback_canary_ok"}


def test_egress_all_failures_reported_independently():
    fw = good_fw()
    fw["rules"] = []
    fw["profiles"][0]["enabled"] = False
    p = {"identity_sid": RSID, "loopback_canary_ok": False, "external_connected": True, "external_errno": None}
    assert failed(eg(fw=fw, probe=p)) == {"firewall_profiles_enabled", "worker_block_rule_covers_non_loopback",
                                          "probe_ran_as_worker", "external_blocked", "loopback_canary_ok"}


@pytest.mark.parametrize("mutate", [
    lambda fw, p: fw.update(profiles=[]),
    lambda fw, p: fw.pop("rules"),
    lambda fw, p: fw.pop("profiles"),
    lambda fw, p: fw["rules"][0].pop("action"),
    lambda fw, p: fw["rules"][0].pop("local_user_sddl"),
    lambda fw, p: fw["rules"][0].update(enabled="yes"),
    lambda fw, p: p.pop("identity_sid"),
    lambda fw, p: p.update(identity_sid="nope"),
    lambda fw, p: p.pop("external_connected"),
    lambda fw, p: p.update(external_connected=0),
    lambda fw, p: p.pop("loopback_canary_ok"),
    lambda fw, p: fw["profiles"][0].pop("enabled"),
])
def test_egress_missing_or_ambiguous_evidence_refused(mutate):
    fw, p = good_fw(), good_egress()
    mutate(fw, p)
    with pytest.raises(ContractError):
        w.check_egress(fw, p, worker())


def test_egress_probe_not_a_dict_refused():
    with pytest.raises(ContractError):
        w.check_egress(good_fw(), None, worker())


# DEFECT: bound-to-worker test is a substring match on the SDDL text (src check_egress: `wsid in sddl.upper()`).
def test_DEFECT_block_rule_for_other_account_with_longer_rid_must_not_count_for_worker():
    wk = worker()
    wk["sid"] = "S-1-5-21-1111-2222-3333-100"
    fw = good_fw()
    fw["rules"] = [block_rule(sddl="D:(A;;CC;;;S-1-5-21-1111-2222-3333-1001)")]
    p = good_egress()
    p["identity_sid"] = wk["sid"]
    assert "worker_block_rule_covers_non_loopback" in failed(w.check_egress(fw, p, wk))


def test_DEFECT_allow_rule_with_empty_remote_list_must_not_be_treated_as_loopback_only():
    fw = good_fw()
    fw["rules"].append({"name": "allow-empty", "enabled": True, "direction": "Outbound", "action": "Allow",
                        "local_user_sddl": f"D:(A;;CC;;;{WSID})", "remote_addresses": []})
    assert "no_worker_allow_rule_non_loopback" in failed(eg(fw=fw))


# ====================================================== check_probe_binding

def bind(meta, **kw):
    args = dict(run_id=RUN_ID, candidate_sha=SHA, now=NOW, max_age_sec=MAX_AGE)
    args.update(kw)
    return w.check_probe_binding(meta, **args)


def test_binding_fresh_passes_at_window_edge():
    assert bind(good_meta(NOW - MAX_AGE))["result"] == "PASS"
    assert bind(good_meta(NOW + 4))["result"] == "PASS"            # within 5 s skew


def test_binding_stale_fails_only_fresh():
    v = bind(good_meta(NOW - MAX_AGE - 1))
    assert v["result"] == "FAIL" and failed(v) == {"fresh"}


def test_binding_future_dated_beyond_skew_fails():
    assert failed(bind(good_meta(NOW + 6))) == {"fresh"}


def test_binding_wrong_run_id_fails_only_run():
    m = good_meta()
    m["run_id"] = "other-run"
    assert failed(bind(m)) == {"run_id_matches"}


def test_binding_wrong_candidate_sha_fails_only_sha():
    m = good_meta()
    m["candidate_sha"] = "b" * 40
    assert failed(bind(m)) == {"candidate_sha_matches"}


@pytest.mark.parametrize("key", ["run_id", "candidate_sha", "observed_at_epoch"])
def test_binding_missing_field_refused(key):
    m = good_meta()
    del m[key]
    with pytest.raises(ContractError):
        bind(m)


def test_binding_wrong_types_refused():
    for key, bad in (("observed_at_epoch", "123"), ("observed_at_epoch", True), ("run_id", 5), ("candidate_sha", None)):
        m = good_meta()
        m[key] = bad
        with pytest.raises(ContractError):
            bind(m)


@pytest.mark.parametrize("kw", [
    {"run_id": ""}, {"run_id": "bad id!"}, {"run_id": "x" * 129}, {"run_id": None},
    {"candidate_sha": "A" * 40}, {"candidate_sha": "a" * 39}, {"candidate_sha": "g" * 40}, {"candidate_sha": ""},
    {"max_age_sec": 0}, {"max_age_sec": -1}, {"max_age_sec": True}, {"max_age_sec": "300"},
])
def test_binding_bad_expectations_refused(kw):
    with pytest.raises(ContractError):
        bind(good_meta(), **kw)


def test_binding_meta_none_refused():
    with pytest.raises(ContractError):
        bind(None)


def test_DEFECT_binding_non_numeric_now_must_be_contract_error():
    with pytest.raises(ContractError):
        bind(good_meta(), now=None)


# ====================================================== check_job_object

def job_mut(fn):
    j = good_job()
    fn(j)
    return failed(w.check_job_object(j))


def test_job_good_passes_with_job_level_memory_only():
    j = good_job()
    j["limits"].update(process_memory_limit=0, job_memory_limit=1 << 30)
    assert w.check_job_object(j)["result"] == "PASS"


def test_job_nesting_unsupported_fails():
    assert job_mut(lambda j: j.update(nesting_supported=False)) == {"nesting_supported"}


def test_job_old_windows_build_fails_even_if_flag_true():
    assert job_mut(lambda j: j.update(windows_build=7601)) == {"nesting_supported"}


def test_job_build_boundary_9200_ok():
    assert job_mut(lambda j: j.update(windows_build=9200)) == set()


def test_job_not_in_job_fails():
    assert job_mut(lambda j: j.update(in_job=False)) == {"in_job"}


def test_job_kill_on_close_missing_fails():
    assert job_mut(lambda j: j["limits"].update(kill_on_job_close=False)) == {"kill_on_job_close"}


def test_job_process_count_limit_missing_fails():
    assert job_mut(lambda j: j["limits"].update(active_process_limit=0)) == {"active_process_limit"}


def test_job_memory_limits_both_missing_fails():
    assert job_mut(lambda j: j["limits"].update(process_memory_limit=0, job_memory_limit=0)) == {"memory_limit"}


def test_job_all_limits_missing_reports_each():
    v = w.check_job_object({"in_job": False, "windows_build": 22631, "nesting_supported": False,
                            "limits": {"kill_on_job_close": False, "breakaway_ok": False, "silent_breakaway_ok": False,
                                       "active_process_limit": 0, "process_memory_limit": 0, "job_memory_limit": 0}})
    assert v["result"] == "FAIL"
    assert failed(v) == {"in_job", "nesting_supported", "kill_on_job_close", "active_process_limit", "memory_limit"}


@pytest.mark.parametrize("mutate", [
    lambda j: j.pop("limits"),
    lambda j: j.pop("in_job"),
    lambda j: j.pop("nesting_supported"),
    lambda j: j.pop("windows_build"),
    lambda j: j["limits"].pop("kill_on_job_close"),
    lambda j: j["limits"].pop("active_process_limit"),
    lambda j: j["limits"].pop("process_memory_limit"),
    lambda j: j["limits"].pop("job_memory_limit"),
    lambda j: j["limits"].update(active_process_limit=True),
    lambda j: j["limits"].update(kill_on_job_close=1),
    lambda j: j.update(windows_build="22631"),
])
def test_job_missing_or_malformed_refused(mutate):
    j = good_job()
    mutate(j)
    with pytest.raises(ContractError):
        w.check_job_object(j)


# ====================================================== evaluate_proof

def test_evaluate_all_good_is_pass_with_six_pass_checks():
    r = evaluate(good_inventories())
    assert r["result"] == "PASS"
    assert set(r["checks"]) == {"worker_account", "secret_isolation", "worktree_confinement", "egress",
                                "probe_binding", "job_object"}
    assert all(c["result"] == "PASS" for c in r["checks"].values())


@pytest.mark.parametrize("key,affected", [
    ("account", {"worker_account", "secret_isolation", "worktree_confinement", "egress"}),
    ("acl", {"secret_isolation"}),
    ("worktree", {"worktree_confinement"}),
    ("firewall", {"egress"}),
    ("worker_probe", {"egress", "probe_binding", "job_object"}),
])
def test_evaluate_unavailable_collector_is_inconclusive_not_pass_or_fail(key, affected):
    inv = good_inventories()
    inv[key] = None
    r = evaluate(inv)
    assert r["result"] == "INCONCLUSIVE"
    assert {n for n, c in r["checks"].items() if c["result"] == "INCONCLUSIVE"} == affected
    assert {n for n, c in r["checks"].items() if c["result"] == "PASS"} == set(r["checks"]) - affected


def test_evaluate_missing_key_equals_none():
    inv = good_inventories()
    del inv["firewall"]
    assert evaluate(inv)["result"] == "INCONCLUSIVE"


def test_evaluate_failed_check_is_fail():
    inv = good_inventories()
    inv["account"]["worker"]["enabled"] = False
    r = evaluate(inv)
    assert r["result"] == "FAIL"
    assert r["checks"]["worker_account"]["result"] == "FAIL"
    assert [n for n, c in r["checks"].items() if c["result"] != "PASS"] == ["worker_account"]


@pytest.mark.parametrize("breaker,check", [
    (lambda i: i["acl"]["paths"][0].update(entries=[ace(WSID, ["R"])]), "secret_isolation"),
    (lambda i: i["worktree"]["reparse_points"].append({"path": "C:\\vst-runs\\r1\\wt\\j", "target": "C:\\Windows"}),
     "worktree_confinement"),
    (lambda i: i["firewall"].update(rules=[]), "egress"),
    (lambda i: i["worker_probe"]["egress"].update(external_connected=True), "egress"),
    (lambda i: i["worker_probe"]["meta"].update(observed_at_epoch=NOW - 10_000), "probe_binding"),
    (lambda i: i["worker_probe"]["meta"].update(run_id="stale-run"), "probe_binding"),
    (lambda i: i["worker_probe"]["job"]["limits"].update(kill_on_job_close=False), "job_object"),
])
def test_evaluate_each_single_breakage_yields_fail_for_that_check_only(breaker, check):
    inv = good_inventories()
    breaker(inv)
    r = evaluate(inv)
    assert r["result"] == "FAIL"
    assert {n for n, c in r["checks"].items() if c["result"] == "FAIL"} == {check}


def test_evaluate_inconclusive_beats_fail():
    inv = good_inventories()
    inv["account"]["worker"]["groups"].append({"sid": "S-1-5-32-544", "name": "Administrators"})   # would FAIL
    inv["acl"] = None                                                                              # unavailable
    r = evaluate(inv)
    assert r["checks"]["worker_account"]["result"] == "FAIL"
    assert r["checks"]["secret_isolation"]["result"] == "INCONCLUSIVE"
    assert r["result"] == "INCONCLUSIVE"


def test_evaluate_malformed_evidence_is_inconclusive_with_reason():
    inv = good_inventories()
    del inv["worker_probe"]["job"]["limits"]
    r = evaluate(inv)
    assert r["checks"]["job_object"]["result"] == "INCONCLUSIVE"
    assert "ambiguous" in r["checks"]["job_object"]["reason"]
    assert r["result"] == "INCONCLUSIVE"


def test_evaluate_probe_missing_egress_section_is_inconclusive():
    inv = good_inventories()
    del inv["worker_probe"]["egress"]
    assert evaluate(inv)["checks"]["egress"]["result"] == "INCONCLUSIVE"


def test_evaluate_bad_run_binding_arguments_refused():
    for kw in ({"run_id": "bad id"}, {"candidate_sha": "x"}):
        args = dict(run_id=RUN_ID, candidate_sha=SHA, now=NOW, max_age_sec=MAX_AGE)
        args.update(kw)
        with pytest.raises(ContractError):
            w.evaluate_proof(good_inventories(), **args)


# ====================================================== build_probe_record

def fake_collectors(log=None, **override):
    log = log if log is not None else []

    def account(name):
        log.append(("account", name))
        return good_account()

    def acl(paths):
        log.append(("acl", tuple(paths)))
        return good_acl()

    def worktree(run_dir, wt, host):
        log.append(("worktree", run_dir, wt, tuple(host)))
        return good_worktree()

    def firewall(sid):
        log.append(("firewall", sid))
        return good_fw()

    def worker_probe(run_id, sha):
        log.append(("worker_probe", run_id, sha))
        return good_probe()

    cols = {"account": account, "acl": acl, "worktree": worktree, "firewall": firewall, "worker_probe": worker_probe}
    cols.update(override)
    return cols


def build(collectors=None, **kw):
    args = dict(run_id=RUN_ID, candidate_sha=SHA, worker_name="vst-worker", run_dir=RUN_DIR, worktree=WORKTREE,
                protected_paths=[SIGNER, KEY, STORE], host_paths=["C:\\Windows"], max_age_sec=MAX_AGE, now=NOW,
                collectors=collectors if collectors is not None else fake_collectors())
    args.update(kw)
    return w.build_probe_record(**args)


def test_record_pass_has_guarantee_limits_schema_and_is_json():
    log = []
    rec = build(fake_collectors(log))
    assert rec["result"] == "PASS"
    assert rec["schema"] == "VST_S3_WINDOWS_SANDBOX_PROOF_V1"
    assert rec["run_id"] == RUN_ID and rec["candidate_sha"] == SHA and rec["worker_account"] == "vst-worker"
    assert rec["collector_errors"] == {}
    assert isinstance(rec["guarantee"], str) and "weaker than the S2 WSL/VM sandbox" in rec["guarantee"]
    assert isinstance(rec["known_limits"], list) and len(rec["known_limits"]) >= 3
    assert all(isinstance(x, str) and x for x in rec["known_limits"])
    assert set(rec["checks"]) == {"worker_account", "secret_isolation", "worktree_confinement", "egress",
                                  "probe_binding", "job_object"}
    assert json.loads(json.dumps(rec)) == rec
    # collectors were wired with the right arguments (worker SID flows to the firewall collector)
    assert ("account", "vst-worker") in log and ("firewall", WSID) in log
    assert ("acl", (SIGNER, KEY, STORE)) in log and ("worker_probe", RUN_ID, SHA) in log
    assert ("worktree", RUN_DIR, WORKTREE, ("C:\\Windows",)) in log


def test_record_guarantee_and_limits_present_for_non_pass_results_too():
    rec = build(fake_collectors(acl=lambda p: (_ for _ in ()).throw(ContractError("boom"))))
    assert rec["result"] == "INCONCLUSIVE"
    assert rec["guarantee"] == w.GUARANTEE and rec["known_limits"] == list(w.KNOWN_LIMITS)


def test_record_collector_failure_is_inconclusive_with_error_recorded_even_if_other_check_fails():
    def bad_acl(paths):
        raise ContractError("icacls exploded")

    def admin_account(name):
        a = good_account()
        a["worker"]["groups"].append({"sid": "S-1-5-32-544", "name": "Administrators"})
        return a

    rec = build(fake_collectors(acl=bad_acl, account=admin_account))
    assert rec["checks"]["worker_account"]["result"] == "FAIL"
    assert rec["result"] == "INCONCLUSIVE"
    assert "ContractError: icacls exploded" in rec["collector_errors"]["acl"]
    assert rec["inventories"]["acl"] is None


@pytest.mark.parametrize("exc", [OSError("io"), KeyError("k"), TypeError("t"), ValueError("v")])
def test_record_collector_exception_types_are_contained(exc):
    def raiser(*a):
        raise exc

    rec = build(fake_collectors(worktree=raiser))
    assert rec["result"] == "INCONCLUSIVE" and "worktree" in rec["collector_errors"]


def test_record_account_unavailable_skips_firewall_and_is_inconclusive():
    log = []

    def no_account(name):
        raise ContractError("no such account")

    rec = build(fake_collectors(log, account=no_account))
    assert rec["result"] == "INCONCLUSIVE"
    assert not any(e[0] == "firewall" for e in log)
    assert "account" in rec["collector_errors"] and rec["collector_errors"]["firewall"] == "worker SID unavailable"


def test_record_supplied_worker_probe_is_used_and_collector_not_called():
    def must_not_run(*a):
        raise AssertionError("worker_probe collector must not run when a probe is supplied")

    rec = build(fake_collectors(worker_probe=must_not_run), worker_probe=good_probe())
    assert rec["result"] == "PASS"


def test_record_supplied_stale_probe_fails():
    rec = build(worker_probe={"meta": good_meta(NOW - 99999), "egress": good_egress(), "job": good_job()})
    assert rec["result"] == "FAIL" and rec["checks"]["probe_binding"]["result"] == "FAIL"


def test_record_supplied_probe_for_other_run_or_sha_fails():
    p = good_probe()
    p["meta"]["candidate_sha"] = "c" * 40
    assert build(worker_probe=p)["checks"]["probe_binding"]["result"] == "FAIL"


def test_record_non_serializable_collector_output_refused():
    with pytest.raises(ContractError, match="JSON"):
        build(fake_collectors(acl=lambda p: {"paths": [object()]}))


@pytest.mark.parametrize("kw", [{"run_id": "bad id"}, {"candidate_sha": "short"}, {"run_id": None}])
def test_record_bad_binding_arguments_refused_before_any_collection(kw):
    log = []
    with pytest.raises(ContractError):
        build(fake_collectors(log), **kw)
    assert log == []


def test_DEFECT_record_malformed_account_inventory_must_not_crash_builder():
    # collector returns a 'worker' dict without 'sid': builder must record INCONCLUSIVE, not raise KeyError.
    rec = build(fake_collectors(account=lambda n: {"worker": {}, "runner": {"name": "x", "sid": RSID}}))
    assert rec["result"] == "INCONCLUSIVE"


def test_DEFECT_record_non_dict_worker_in_account_inventory_must_not_crash_builder():
    rec = build(fake_collectors(account=lambda n: {"worker": "vst-worker"}))
    assert rec["result"] == "INCONCLUSIVE"


# ====================================================== CLI

def test_cli_probe_prints_json_with_stubbed_collector(monkeypatch, capsys):
    monkeypatch.setattr(w, "collect_worker_probe", lambda r, s: {"meta": {"run_id": r, "candidate_sha": s}})
    assert w.main(["probe", "--run-id", RUN_ID, "--sha", SHA]) == 0
    assert json.loads(capsys.readouterr().out)["meta"] == {"run_id": RUN_ID, "candidate_sha": SHA}


def test_cli_probe_refuses_bad_sha_with_exit_2(capsys):
    assert w.main(["probe", "--run-id", RUN_ID, "--sha", "nothex"]) == 2
    assert "REFUSED" in capsys.readouterr().err


# ====================================================== real host, read-only collectors

def test_real_loopback_canary_succeeds():
    assert w._loopback_canary() is True


def test_real_blocked_target_connect_to_documentation_address_does_not_connect():
    import time
    t = time.time()
    connected, err = w._blocked_connect()
    assert connected is False
    assert err is not None
    assert time.time() - t < 5.0          # short timeout honoured


def test_real_job_inventory_shape_and_consistency():
    j = w.collect_job_inventory()
    assert isinstance(j["in_job"], bool)
    assert j["windows_build"] == sys.getwindowsversion().build
    assert j["nesting_supported"] is (j["windows_build"] >= w.MIN_NESTED_JOB_BUILD)
    assert set(j["limits"]) == {"kill_on_job_close", "breakaway_ok", "silent_breakaway_ok", "active_process_limit",
                                "process_memory_limit", "job_memory_limit",
                                "process_time_limit_100ns", "job_time_limit_100ns"}
    assert isinstance(j["limits"]["breakaway_ok"], bool) and isinstance(j["limits"]["silent_breakaway_ok"], bool)
    if not j["in_job"]:
        assert j["limits"]["kill_on_job_close"] is False and j["limits"]["active_process_limit"] == 0
    # whatever the host says must be accepted by the checker without ContractError
    assert w.check_job_object(j)["result"] in ("PASS", "FAIL")


def test_real_worker_probe_binding_and_identity():
    p = w.collect_worker_probe(RUN_ID, SHA, now=123.0)
    assert p["meta"] == {"run_id": RUN_ID, "candidate_sha": SHA, "observed_at_epoch": 123.0}
    name, sid = w._identity()
    assert p["egress"]["identity_sid"] == sid
    assert p["egress"]["loopback_canary_ok"] is True
    assert p["egress"]["external_connected"] is False
    assert p["egress"]["external_target"] == "192.0.2.1:9"
    assert json.loads(json.dumps(p)) == p
    # this process is not the worker account: the egress identity sub-check must FAIL against a different SID
    v = w.check_egress(good_fw(), p["egress"], worker())
    assert "probe_ran_as_worker" in failed(v)


def test_real_worker_probe_refuses_bad_binding():
    with pytest.raises(ContractError):
        w.collect_worker_probe("bad id", SHA)
    with pytest.raises(ContractError):
        w.collect_worker_probe(RUN_ID, "XYZ")


def test_real_acl_inventory_of_temp_dir_parses_and_is_checkable(tmp_path):
    d = str(os.path.realpath(tmp_path))
    inv = w.collect_acl_inventory([d])
    item = inv["paths"][0]
    assert item["path"] == d and item["complete"] is True and item["entries"]
    assert any(e["sid"] and e["sid"].startswith("S-1-") for e in item["entries"])
    assert all(e["type"] in ("allow", "deny") and isinstance(e["rights"], list) for e in item["entries"])
    # a never-existing SID has no access on a real ACL -> checker accepts the real data shape
    ghost = {"sid": "S-1-5-21-9-9-9-4242", "groups": []}
    v = w.check_secret_isolation(inv, ghost)
    assert v["result"] in ("PASS", "FAIL")
    # SYSTEM always has full control of a temp dir -> a worker that IS SYSTEM must FAIL on real data
    system = {"sid": "S-1-5-18", "groups": []}
    assert w.check_secret_isolation(inv, system)["result"] == "FAIL"


def test_real_acl_inventory_refuses_missing_relative_and_empty(tmp_path):
    with pytest.raises(ContractError):
        w.collect_acl_inventory([str(tmp_path / "does-not-exist")])
    with pytest.raises(ContractError):
        w.collect_acl_inventory(["relative\\path"])
    with pytest.raises(ContractError):
        w.collect_acl_inventory([])


def _mk_junction(link, target):
    r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
    assert r.returncode == 0, f"could not create junction (needed for the real walk test): {r.stdout} {r.stderr}"


def test_real_worktree_walk_detects_escaping_junction_and_allows_internal_one(tmp_path):
    run = tmp_path / "run"
    wt = run / "wt"
    (wt / "sub").mkdir(parents=True)
    (wt / "inner").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _mk_junction(wt / "sub" / "escape", outside)
    _mk_junction(wt / "sub" / "inside", wt / "inner")
    inv = w.collect_worktree_inventory(str(run), str(wt), [str(outside)])
    targets = {os.path.basename(p["path"]): p["target"] for p in inv["reparse_points"]}
    assert set(targets) == {"escape", "inside"}
    assert os.path.normcase(targets["escape"]) == os.path.normcase(os.path.realpath(outside))
    assert inv["walk_complete"] is True
    v = w.check_worktree_confinement(inv, {"sid": "S-1-5-21-9-9-9-4242", "groups": []})
    assert "no_escaping_reparse" in failed(v)
    assert "worktree_inside_run_dir" not in failed(v) and "walk_complete" not in failed(v)
    # remove the escaping junction only -> no escape reported
    os.rmdir(wt / "sub" / "escape")
    inv2 = w.collect_worktree_inventory(str(run), str(wt), [str(outside)])
    assert [os.path.basename(p["path"]) for p in inv2["reparse_points"]] == ["inside"]
    assert "no_escaping_reparse" not in failed(
        w.check_worktree_confinement(inv2, {"sid": "S-1-5-21-9-9-9-4242", "groups": []}))


def test_real_worktree_collector_refuses_missing_dirs(tmp_path):
    with pytest.raises(ContractError):
        w.collect_worktree_inventory(str(tmp_path), str(tmp_path / "nope"), [str(tmp_path)])
    with pytest.raises(ContractError):
        w.collect_worktree_inventory("rel", str(tmp_path), [str(tmp_path)])


def test_real_account_collector_absent_account_refused():
    with pytest.raises(ContractError):
        w.collect_account_inventory("vst-s3d-absent-acct")


def test_real_account_collector_rejects_injection_names():
    for bad in ("x'; Remove-LocalUser -Name y; '", "a b", "", "n" * 21, None):
        with pytest.raises(ContractError):
            w.collect_account_inventory(bad)


def test_real_account_inventory_for_current_user_feeds_checker():
    name = os.environ.get("USERNAME", "")
    inv = w.collect_account_inventory(name)       # a failure here (ContractError) is a real finding
    assert inv["worker"]["sid"] == inv["runner"]["sid"]
    assert inv["worker"]["is_local"] is True and isinstance(inv["worker"]["groups"], list)
    v = w.check_worker_account(inv)
    # the current user is the runner: must be rejected as a worker regardless of admin status
    assert v["result"] == "FAIL" and "distinct_from_runner" in failed(v)
    admin = any(g["sid"] == w.ADMIN_GROUP_SID for g in inv["worker"]["groups"])
    assert ("not_admin" in failed(v)) is (admin or not inv["worker"]["groups_complete"])


def test_real_firewall_inventory_is_readable_and_feeds_checker():
    fw = w.collect_firewall_inventory("S-1-5-21-9-9-9-4242")
    assert {p["name"] for p in fw["profiles"]} >= {"Domain", "Private", "Public"}
    assert all(isinstance(p["enabled"], bool) for p in fw["profiles"])
    assert isinstance(fw["rules"], list)
    assert all(isinstance(r["remote_addresses"], list) for r in fw["rules"])
    # a never-provisioned worker SID has no bound Block rule -> egress must FAIL on that sub-check on real data
    ghost = {"sid": "S-1-5-21-9-9-9-4242", "groups": []}
    v = w.check_egress(fw, dict(good_egress(), identity_sid=ghost["sid"]), ghost)
    unbound_global_block = any(r["action"] == "Block" and r["local_user_sddl"] is None
                               and w._rule_is_unrestricted(r, fw["profiles"]) and w._covers_non_loopback(r["remote_addresses"])
                               for r in fw["rules"])
    # every collected rule exposes the scope fields the checker needs (missing = restricted)
    for r in fw["rules"]:
        for f in w._RULE_UNRESTRICTED_FIELDS + ("profile", "remote_addresses"):
            assert f in r and isinstance(r[f], list), (r.get("name"), f)
    assert ("worker_block_rule_covers_non_loopback" not in failed(v)) is unbound_global_block


def test_real_firewall_collector_refuses_bad_sid():
    with pytest.raises(ContractError):
        w.collect_firewall_inventory("S-1-5-21-1'; calc; '")


def test_real_end_to_end_record_for_non_provisioned_worker_is_not_pass(tmp_path):
    # Real collectors, absent worker account: must be INCONCLUSIVE (account unavailable), never PASS.
    run = tmp_path / "run"
    wt = run / "wt"
    wt.mkdir(parents=True)
    rec = w.build_probe_record(run_id=RUN_ID, candidate_sha=SHA, worker_name="vst-s3d-absent-acct",
                               run_dir=str(os.path.realpath(run)), worktree=str(os.path.realpath(wt)),
                               protected_paths=[str(os.path.realpath(tmp_path))], host_paths=[str(os.path.realpath(tmp_path))])
    assert rec["result"] == "INCONCLUSIVE"
    assert "account" in rec["collector_errors"] and "firewall" in rec["collector_errors"]
    assert rec["guarantee"] == w.GUARANTEE and rec["known_limits"]
    assert json.loads(json.dumps(rec)) == rec


# ====================================================== deny whitelist (fix for the partial-deny defect)

@pytest.mark.parametrize("deny", [["RD"], ["WD"], ["AD"], ["REA"], ["WEA"], ["RA"], ["WA"], ["DC"], ["D"], ["DE"],
                                  ["RC"], ["X"], ["XYZZY"], ["N"], ["S"], ["WDAC"], ["WO"], ["MA"]])
@pytest.mark.parametrize("allow", [["F"], ["R"], ["W"]])
def test_deny_of_non_whitelisted_right_removes_nothing(deny, allow):
    entries = [ace(WSID, allow), ace(WSID, deny, "deny")]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"


@pytest.mark.parametrize("allow,deny", [
    (["R"], ["F"]), (["R"], ["M"]), (["R"], ["GA"]), (["W"], ["F"]), (["W"], ["M"]), (["RX"], ["GA"]),
    (["F"], ["F"]), (["M"], ["M"]), (["F"], ["GA"]), (["R", "W"], ["F"]), (["F"], ["R", "F"]),
])
def test_deny_of_full_class_tokens_F_M_GA_removes_everything(allow, deny):
    entries = [ace(WSID, allow), ace(WSID, deny, "deny")]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "PASS"


@pytest.mark.parametrize("allow,deny", [
    (["R"], ["R"]), (["R"], ["GR"]), (["RX"], ["RX"]), (["W"], ["W"]), (["W"], ["GW"]),
    (["R", "W"], ["R", "W"]), (["F"], ["R", "W"]), (["F"], ["RX", "GR", "GW"]),
])
def test_deny_of_R_GR_RX_W_GW_alone_removes_nothing(allow, deny):
    entries = [ace(WSID, allow), ace(WSID, deny, "deny")]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"


def test_deny_read_only_leaves_write():
    entries = [ace(WSID, ["F"]), ace(WSID, ["R"], "deny")]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"
    # host-path writability: the same ACL is a write exposure
    inv = good_worktree()
    inv["host_paths"] = [host_item("C:\\h", entries)]
    assert failed(w.check_worktree_confinement(inv, worker())) == {"host_path_not_writable:C:\\h"}


def test_deny_write_only_no_longer_removes_write_host_path_stays_writable():
    # W/GW alone leave DELETE / WRITE_DAC / WRITE_OWNER, so a deny of W only is not trusted to remove write.
    entries = [ace(WSID, ["F"]), ace(WSID, ["W"], "deny")]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"
    inv = good_worktree()
    inv["host_paths"] = [host_item("C:\\h", entries)]
    assert failed(w.check_worktree_confinement(inv, worker())) == {"host_path_not_writable:C:\\h"}


def test_mixed_deny_tokens_only_F_M_GA_part_counts():
    entries = [ace(WSID, ["F"]), ace(WSID, ["RD", "W"], "deny")]      # nothing whitelisted
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"
    entries = [ace(WSID, ["W"]), ace(WSID, ["RD", "W"], "deny")]      # W alone removes nothing now
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"
    entries = [ace(WSID, ["W"]), ace(WSID, ["RD", "F"], "deny")]      # F in the list removes everything
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "PASS"


def test_inherit_only_deny_flag_case_insensitive_and_non_io_flags_apply():
    assert w.check_secret_isolation(acl_with(0, [ace(WSID, ["F"]), ace(WSID, ["F"], "deny", ["oi", "io"])]), worker())["result"] == "FAIL"
    assert w.check_secret_isolation(acl_with(0, [ace(WSID, ["F"]), ace(WSID, ["F"], "deny", ["OI", "CI"])]), worker())["result"] == "PASS"
    assert w.check_secret_isolation(acl_with(0, [ace(WSID, ["F"]), {"sid": WSID, "type": "deny", "rights": ["F"]}]), worker())["result"] == "PASS"


def test_deny_for_other_principal_never_masks_worker_allow():
    entries = [ace(WSID, ["F"]), ace(RSID, ["F"], "deny")]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"


def test_deny_with_unresolved_principal_still_flags_unresolved():
    entries = [ace(WSID, ["F"], "deny"), ace(None, ["F"], "deny")]
    assert w.check_secret_isolation(acl_with(0, entries), worker())["result"] == "FAIL"


def test_exact_sid_binding_not_prefix_or_substring():
    wk = worker()
    wk["sid"] = "S-1-5-21-1111-2222-3333-100"
    p = dict(good_egress(), identity_sid=wk["sid"])
    for other in ("S-1-5-21-1111-2222-3333-1001", "S-1-5-21-1111-2222-3333-1000", "S-1-5-21-1111-2222-3333-2100"):
        fw = good_fw()
        fw["rules"] = [block_rule(sddl=f"D:(A;;CC;;;{other})")]
        assert "worker_block_rule_covers_non_loopback" in failed(w.check_egress(fw, p, wk))
        fw["rules"].append({"name": "al", "enabled": True, "direction": "Outbound", "action": "Allow",
                            "local_user_sddl": f"D:(A;;CC;;;{other})", "remote_addresses": ["Any"]})
        assert "no_worker_allow_rule_non_loopback" not in failed(w.check_egress(fw, p, wk))
    fw = good_fw()
    fw["rules"] = [block_rule(sddl="D:(A;;CC;;;S-1-5-21-1111-2222-3333-100)")]
    assert w.check_egress(fw, p, wk)["result"] == "PASS"
    fw["rules"] = [block_rule(sddl="D:(A;;CC;;;s-1-5-21-1111-2222-3333-100)")]      # lower-case SID still matches
    assert w.check_egress(fw, p, wk)["result"] == "PASS"


@pytest.mark.parametrize("now", [None, "1000", True, float("nan")])
def test_binding_bad_now_refused_or_not_fresh(now):
    try:
        v = bind(good_meta(), now=now)
    except ContractError:
        return
    assert v["result"] == "FAIL"


@pytest.mark.parametrize("pt", [{"target": "C:\\vst-runs\\r1\\z"}, {"target": "C:\\Windows"}, {"target": None}])
def test_reparse_point_without_path_refused_regardless_of_target(pt):
    inv = good_worktree()
    inv["reparse_points"] = [pt]
    with pytest.raises(ContractError):
        w.check_worktree_confinement(inv, worker())


@pytest.mark.parametrize("acct", [{"worker": {}}, {"worker": "x"}, {"worker": {"sid": None}}, {"worker": {"sid": "bad"}}, "str", []])
def test_record_malformed_account_inventory_variants_inconclusive(acct):
    log = []
    rec = build(fake_collectors(log, account=lambda n: acct))
    assert rec["result"] == "INCONCLUSIVE"
    if acct != {"worker": {"sid": "bad"}}:
        # sid-less inventory: the firewall collector must not be called at all.
        # (a syntactically present but invalid SID is handed on and refused by the real collector's own _sid check)
        assert not any(e[0] == "firewall" for e in log)
    assert rec["checks"]["worker_account"]["result"] == "INCONCLUSIVE"


def test_record_allow_rule_empty_remote_list_fails_egress():
    def fw(sid):
        f = good_fw()
        f["rules"].append({"name": "e", "enabled": True, "direction": "Outbound", "action": "Allow",
                           "local_user_sddl": f"D:(A;;CC;;;{WSID})", "remote_addresses": []})
        return f

    rec = build(fake_collectors(firewall=fw))
    assert rec["checks"]["egress"]["result"] == "FAIL" and rec["result"] == "FAIL"


# ====================================================== icacls (N) = deny-all regression (live ground truth)

KEYS_PATH = "D:\\vst\\keys"
NAME_TO_SID = {
    "Razer\\vst-worker": WSID,
    "NT AUTHORITY\\Authenticated Users": "S-1-5-11",
    "BUILTIN\\Users": "S-1-5-32-545",
    "NT AUTHORITY\\SYSTEM": "S-1-5-18",
    "BUILTIN\\Administrators": "S-1-5-32-544",
}
CAPTURED_ICACLS = (
    "D:\\vst\\keys Razer\\vst-worker:(OI)(CI)(N)\n"
    "             NT AUTHORITY\\SYSTEM:(I)(OI)(CI)(F)\n"
    "             BUILTIN\\Administrators:(I)(OI)(CI)(F)\n"
    "             NT AUTHORITY\\Authenticated Users:(I)(M)\n"
    "             NT AUTHORITY\\Authenticated Users:(I)(OI)(CI)(IO)(M)\n"
    "             BUILTIN\\Users:(I)(RX)\n"
    "             BUILTIN\\Users:(I)(OI)(CI)(IO)(GR,GE)\n"
    "\n"
    "Successfully processed 1 files; Failed processing 0 files\n"
)


def acl_from_icacls(text, path=KEYS_PATH):
    parsed = w.parse_icacls_output(text, path)
    entries = [{"sid": NAME_TO_SID[e["name"]], "name": e["name"], "type": e["type"],
                "rights": e["rights"], "flags": e["flags"]} for e in parsed]
    return {"paths": [{"path": path, "complete": True, "entries": entries}]}


def test_icacls_N_entry_is_parsed_as_deny_all_keeping_flags():
    ents = w.parse_icacls_output(CAPTURED_ICACLS, KEYS_PATH)
    n = ents[0]
    assert n["name"] == "Razer\\vst-worker"
    assert n["type"] == "deny" and n["rights"] == ["F"] and n["flags"] == ["OI", "CI"]
    # other entries untouched
    assert ents[3]["type"] == "allow" and ents[3]["rights"] == ["M"] and ents[3]["flags"] == ["I"]
    assert ents[5]["rights"] == ["RX"] and ents[5]["type"] == "allow"
    assert ents[4]["flags"] == ["I", "OI", "CI", "IO"]


def test_captured_icacls_with_N_entry_gives_worker_no_access():
    v = w.check_secret_isolation(acl_from_icacls(CAPTURED_ICACLS), worker())
    assert v["result"] == "PASS", v


def test_captured_icacls_without_N_entry_exposes_worker_through_group_acls():
    # first line (path echo + N entry) was dropped with the N entry: rebuild an echo line from the SYSTEM entry
    lines = [ln for ln in CAPTURED_ICACLS.splitlines(True) if "(N)" not in ln]
    lines[0] = "D:\\vst\\keys " + lines[0].lstrip()
    text = "".join(lines)
    assert "(N)" not in text
    v = w.check_secret_isolation(acl_from_icacls(text), worker())
    assert v["result"] == "FAIL"
    assert failed(v) == {"no_worker_access:" + KEYS_PATH}


def test_captured_icacls_N_entry_for_another_account_does_not_protect_the_worker():
    # N entry for somebody else (runner) must not protect the worker
    text = CAPTURED_ICACLS.replace("Razer\\vst-worker:(OI)(CI)(N)", "Razer\\runner:(OI)(CI)(N)")
    mapping = dict(NAME_TO_SID, **{"Razer\\runner": RSID})
    parsed = w.parse_icacls_output(text, KEYS_PATH)
    acl = {"paths": [{"path": KEYS_PATH, "complete": True, "entries": [
        {"sid": mapping[e["name"]], "type": e["type"], "rights": e["rights"], "flags": e["flags"]} for e in parsed]}]}
    assert w.check_secret_isolation(acl, worker())["result"] == "FAIL"


def test_N_mixed_with_other_rights_is_not_rewritten():
    ents = w.parse_icacls_output("D:\\k HOST\\a:(OI)(CI)(N,R)\n", "D:\\k")
    assert ents[0]["type"] == "allow" and ents[0]["rights"] == ["N", "R"]
    ents = w.parse_icacls_output("D:\\k HOST\\a:(N)(R)\n", "D:\\k")
    assert ents[0]["type"] == "allow" and ents[0]["rights"] == ["N", "R"]
    # and an allow of R next to an N is still read access for the checker
    acl = {"paths": [{"path": "D:\\k", "complete": True, "entries": [
        {"sid": WSID, "type": e["type"], "rights": e["rights"], "flags": e["flags"]}
        for e in w.parse_icacls_output("D:\\k HOST\\a:(N,R)\n", "D:\\k")]}]}
    assert w.check_secret_isolation(acl, worker())["result"] == "FAIL"


def test_explicit_DENY_N_is_not_rewritten_to_full_deny():
    ents = w.parse_icacls_output("D:\\k HOST\\a:(DENY)(N)\n", "D:\\k")
    assert ents[0]["type"] == "deny" and ents[0]["rights"] == ["N"]


def test_inherit_only_N_entry_does_not_apply_to_object_itself():
    # worker holds M through Authenticated Users on the object; the only deny-all for the worker is inherit-only
    text = ("D:\\k HOST\\vst-worker:(OI)(CI)(IO)(N)\n"
            "     NT AUTHORITY\\Authenticated Users:(M)\n")
    mapping = {"HOST\\vst-worker": WSID, "NT AUTHORITY\\Authenticated Users": "S-1-5-11"}
    parsed = w.parse_icacls_output(text, "D:\\k")
    assert parsed[0]["type"] == "deny" and parsed[0]["flags"] == ["OI", "CI", "IO"]
    acl = {"paths": [{"path": "D:\\k", "complete": True, "entries": [
        {"sid": mapping[e["name"]], "type": e["type"], "rights": e["rights"], "flags": e["flags"]} for e in parsed]}]}
    assert w.check_secret_isolation(acl, worker())["result"] == "FAIL"
    # same text, N entry without IO: protects
    text2 = text.replace("(IO)", "")
    parsed2 = w.parse_icacls_output(text2, "D:\\k")
    acl2 = {"paths": [{"path": "D:\\k", "complete": True, "entries": [
        {"sid": mapping[e["name"]], "type": e["type"], "rights": e["rights"], "flags": e["flags"]} for e in parsed2]}]}
    assert w.check_secret_isolation(acl2, worker())["result"] == "PASS"


# ====================================================== review-fix batch: firewall rule SDDL / scope

BLOCK_SUB = "worker_block_rule_covers_non_loopback"


def egress_failed(rule, **kw):
    fw = good_fw()
    fw["rules"] = [rule]
    return failed(eg(fw=fw, **kw))


@pytest.mark.parametrize("sddl", [
    f"D:(D;;CC;;;{WSID})",                          # deny ACE for the worker is not a binding
    f"D:(A;;CC;;;{WSID})(D;;CC;;;{RSID})",          # any D ACE makes the whole SDDL ambiguous
    f"D:(D;;CC;;;{RSID})(A;;CC;;;{WSID})",
    f"D:(OA;;CC;;;{WSID})",                         # other ACE type
    f"D:(A;;CC;;;{WSID})(XX;;CC;;;{RSID})",
    "garbage", "", "D:", "D:()",                    # unparsable
    f"D:(A;;CC;;;{WSID}0)",                         # trustee must equal the SID exactly (suffix)
    f"D:(A;;CC;;;{RSID})",
    f"D:(A;;CC;;;{WSID[:-1]})",                     # exact-SID token, not a prefix of it
    f"D:(A;;CC)",                                   # too few fields
])
def test_block_rule_sddl_not_exactly_bound_or_ambiguous_does_not_apply(sddl):
    assert egress_failed(block_rule(sddl=sddl)) == {BLOCK_SUB}


@pytest.mark.parametrize("sddl", [f"D:(A;;CC;;;{WSID})", f"d:(a;;cc;;;{WSID.lower()})", "Any", "any", None,
                                  f"D:(A;;CC;;;{RSID})(A;;CC;;;{WSID})"])
def test_block_rule_sddl_exact_worker_trustee_or_unrestricted_applies(sddl):
    rule = block_rule(sddl=sddl)
    rule["local_user_sddl"] = sddl
    assert egress_failed(rule) == set()


@pytest.mark.parametrize("sddl", [f"D:(D;;CC;;;{WSID})", "garbage", f"D:(A;;CC;;;{WSID})(D;;CC;;;{RSID})", f"D:(OA;;CC;;;{WSID})"])
def test_allow_rule_with_ambiguous_sddl_is_treated_as_worker_bound(sddl):
    fw = good_fw()
    fw["rules"].append({"name": "amb-allow", "enabled": True, "direction": "Outbound", "action": "Allow",
                        "local_user_sddl": sddl, "remote_addresses": ["Any"]})
    v = eg(fw=fw)
    assert failed(v) == {"no_worker_allow_rule_non_loopback"}
    assert "amb-allow" in [s["detail"] for s in v["subchecks"] if not s["ok"]][0]


def test_allow_rule_for_everyone_sddl_none_is_ignored_block_wins():
    fw = good_fw()
    fw["rules"].append({"name": "everyone", "enabled": True, "direction": "Outbound", "action": "Allow",
                        "local_user_sddl": None, "remote_addresses": ["Any"]})
    assert eg(fw=fw)["result"] == "PASS"


@pytest.mark.parametrize("field,value", [
    ("protocol", ["TCP"]), ("protocol", ["6"]), ("local_port", ["443"]), ("remote_port", ["443"]),
    ("remote_port", ["80", "443"]), ("program", ["C:\\tools\\x.exe"]), ("service", ["Dnscache"]),
    ("interface_type", ["Wireless"]), ("interface_type", ["RemoteAccess"]), ("local_address", ["10.0.0.1"]),
    ("local_address", ["LocalSubnet"]), ("profile", ["Domain"]), ("profile", ["Domain,Private"]), ("profile", ["Public"]),
    ("package", ["S-1-15-2-1-2-3"]),
])
def test_block_rule_scoped_by_port_program_profile_etc_is_not_a_default_deny(field, value):
    assert egress_failed(block_rule(**{field: value})) == {BLOCK_SUB}


@pytest.mark.parametrize("field", ["protocol", "local_port", "remote_port", "program", "service", "interface_type",
                                   "local_address", "profile"])
def test_block_rule_missing_scope_field_counts_as_restricted(field):
    rule = block_rule()
    del rule[field]
    assert egress_failed(rule) == {BLOCK_SUB}


@pytest.mark.parametrize("value", ["Any", ["Any"], ["*"], [""], None, ["Any", "any"], [None]])
def test_block_rule_unrestricted_spellings_pass(value):
    r = block_rule(protocol=value, local_port=value, remote_port=value, program=value, service=value,
                   interface_type=value, local_address=value)
    assert egress_failed(r) == set()


@pytest.mark.parametrize("profile", ["Any", "All", ["Any"], "Domain,Private,Public", ["Domain", "Private", "Public"],
                                     ["domain,private", "PUBLIC"]])
def test_block_rule_profile_covering_every_enabled_profile_passes(profile):
    assert egress_failed(block_rule(profile=profile)) == set()


def test_block_rule_profile_missing_only_disabled_profile_still_requires_profile_check_to_pass():
    fw = good_fw()
    fw["profiles"][2]["enabled"] = False                   # Public off
    fw["rules"] = [block_rule(profile=["Domain", "Private"])]
    assert failed(eg(fw=fw)) == {"firewall_profiles_enabled"}   # the rule covers every ENABLED profile
    fw["rules"] = [block_rule(profile=["Domain"])]
    assert failed(eg(fw=fw)) == {"firewall_profiles_enabled", BLOCK_SUB}


def test_block_rule_package_field_optional_when_platform_does_not_expose_it():
    assert "package" not in block_rule()
    assert egress_failed(block_rule(package=["Any"])) == set()


def test_one_unrestricted_block_rule_is_enough_next_to_scoped_ones():
    fw = good_fw()
    fw["rules"] = [block_rule(remote_port=["443"]), block_rule(program=["x.exe"]), block_rule()]
    assert eg(fw=fw)["result"] == "PASS"


# ---- errno policy

@pytest.mark.parametrize("errno", [10060, 10061, 10051, 10065, 10035, 0, 13, None, "10013", True, 10013.0])
def test_egress_only_errno_10013_proves_a_block(errno):
    p = good_egress()
    p["external_errno"] = errno
    v = eg(probe=p)
    assert v["result"] == "FAIL" and failed(v) == {"external_blocked"}
    assert "INCONCLUSIVE" in [s["detail"] for s in v["subchecks"] if not s["ok"]][0]


def test_egress_errno_missing_key_is_not_a_block():
    p = good_egress()
    del p["external_errno"]
    assert failed(eg(probe=p)) == {"external_blocked"}


def test_egress_errno_10013_passes_and_connected_true_still_fails_with_10013():
    assert eg(probe=dict(good_egress(), external_errno=10013))["result"] == "PASS"
    assert failed(eg(probe=dict(good_egress(), external_connected=True, external_errno=10013))) == {"external_blocked"}


# ---- loopback CIDR

@pytest.mark.parametrize("addr,expected", [
    ("127.0.0.0/8", True), ("127.0.0.1/32", True), ("127.1.2.3", True), ("::1/128", True), ("::1", True),
    ("localhost", True), ("127.0.0.1-127.0.0.9", True),
    ("127.0.0.0/7", False), ("0.0.0.0/0", False), ("128.0.0.0/1", False), ("::/0", False), ("::/1", False),
    ("10.0.0.0/8", False), ("8.8.8.8", False), ("garbage", False), ("Any", False),
    ("127.0.0.1-128.0.0.0", False), ("LocalSubnet", False),
])
def test_is_loopback_honors_cidr_prefix_length(addr, expected):
    assert w._is_loopback(addr) is expected


@pytest.mark.parametrize("remote", [["127.0.0.0/7"], ["0.0.0.0/0"], ["::/0"], ["127.0.0.0/8", "10.0.0.0/8"]])
def test_egress_allow_rule_with_wide_cidr_that_includes_loopback_fails(remote):
    fw = good_fw()
    fw["rules"].append({"name": "wide", "enabled": True, "direction": "Outbound", "action": "Allow",
                        "local_user_sddl": f"D:(A;;CC;;;{WSID})", "remote_addresses": remote})
    assert failed(eg(fw=fw)) == {"no_worker_allow_rule_non_loopback"}


# ====================================================== review-fix batch: privileged groups

def test_privileged_group_sid_set_is_the_documented_one():
    assert w.PRIVILEGED_GROUP_SIDS == {
        "S-1-5-32-551", "S-1-5-32-549", "S-1-5-32-548", "S-1-5-32-550", "S-1-5-32-552",
        "S-1-5-32-556", "S-1-5-32-547", "S-1-5-32-578"}


@pytest.mark.parametrize("sid", sorted(w.PRIVILEGED_GROUP_SIDS))
def test_worker_in_privileged_builtin_group_fails_only_that_subcheck(sid):
    a = good_account()
    a["worker"]["groups"].append({"sid": sid, "name": "builtin"})
    v = w.check_worker_account(a)
    assert v["result"] == "FAIL" and failed(v) == {"no_privileged_groups"}
    assert sid in [s["detail"] for s in v["subchecks"] if s["id"] == "no_privileged_groups"][0]


@pytest.mark.parametrize("name", ["docker-users", "Docker-Users", "HOST\\docker-users"])
def test_worker_in_docker_users_by_name_fails_only_that_subcheck(name):
    a = good_account()
    a["worker"]["groups"].append({"sid": GRP, "name": name})
    assert failed(w.check_worker_account(a)) == {"no_privileged_groups"}


def test_worker_in_ordinary_groups_passes_privileged_check():
    a = good_account()
    a["worker"]["groups"] += [{"sid": GRP, "name": "devs"}, {"sid": "S-1-5-32-545", "name": "Users"},
                              {"sid": "S-1-5-32-546", "name": "Guests"}]
    assert w.check_worker_account(a)["result"] == "PASS"


def test_privileged_group_via_evaluate_proof_fails_worker_account_only():
    inv = good_inventories()
    inv["account"]["worker"]["groups"].append({"sid": "S-1-5-32-551", "name": "Backup Operators"})
    r = evaluate(inv)
    assert r["result"] == "FAIL" and r["checks"]["worker_account"]["result"] == "FAIL"


@pytest.mark.parametrize("sid", ["S-1-5-113", "S-1-5-4", "S-1-5-3", "S-1-5-2", "S-1-2-0", "S-1-2-1", "S-1-5-15",
                                 "S-1-1-0", "S-1-5-11", "S-1-5-32-545"])
def test_token_principal_set_includes_well_known_logon_sids(sid):
    assert sid in w.IMPLICIT_SIDS
    v = w.check_secret_isolation(acl_with(0, [ace(sid, ["R"])]), worker())
    assert failed(v) == {f"no_worker_access:{SIGNER}"}


# ====================================================== review-fix batch: job breakaway

def test_job_breakaway_ok_fails_only_no_breakaway():
    assert job_mut(lambda j: j["limits"].update(breakaway_ok=True)) == {"no_breakaway"}


def test_job_silent_breakaway_ok_fails_only_no_breakaway():
    assert job_mut(lambda j: j["limits"].update(silent_breakaway_ok=True)) == {"no_breakaway"}


@pytest.mark.parametrize("key", ["breakaway_ok", "silent_breakaway_ok"])
def test_job_breakaway_flags_missing_or_not_bool_refused(key):
    j = good_job()
    del j["limits"][key]
    with pytest.raises(ContractError):
        w.check_job_object(j)
    j = good_job()
    j["limits"][key] = 0
    with pytest.raises(ContractError):
        w.check_job_object(j)


def test_job_missing_breakaway_info_is_inconclusive_through_evaluate():
    inv = good_inventories()
    del inv["worker_probe"]["job"]["limits"]["breakaway_ok"]
    r = evaluate(inv)
    assert r["checks"]["job_object"]["result"] == "INCONCLUSIVE" and r["result"] == "INCONCLUSIVE"


# ====================================================== review-fix batch: worktree depth and link scope

@pytest.mark.parametrize("run_real", ["C:\\", "C:\\runs", "C:\\runs\\", "C:\\a\\..", "\\\\srv\\share", "\\\\srv\\share\\x"])
def test_shallow_run_dir_refused(run_real):
    inv = wt_mut(run_dir=run_real, run_dir_real=run_real, worktree=run_real + "\\wt", worktree_real=run_real + "\\wt")
    with pytest.raises(ContractError, match="two levels"):
        w.check_worktree_confinement(inv, worker())


def test_shallow_run_dir_real_refused_even_when_run_dir_looks_deep():
    with pytest.raises(ContractError):
        w.check_worktree_confinement(wt_mut(run_dir_real="C:\\"), worker())


def test_two_level_run_dir_accepted():
    inv = wt_mut(run_dir="C:\\a\\b", run_dir_real="C:\\a\\b", worktree="C:\\a\\b\\wt", worktree_real="C:\\a\\b\\wt")
    assert w.check_worktree_confinement(inv, worker())["result"] == "PASS"


@pytest.mark.parametrize("target", ["C:\\vst-runs\\r1\\sibling", "C:\\vst-runs\\r1", "C:\\vst-runs\\r1\\wtx",
                                    "C:\\vst-runs\\r1\\wt\\..\\other"])
def test_link_to_sibling_inside_run_dir_but_outside_worktree_is_escaping(target):
    inv = wt_mut(reparse_points=[{"path": WORKTREE + "\\l", "target": target}])
    assert failed(w.check_worktree_confinement(inv, worker())) == {"no_escaping_reparse"}


@pytest.mark.parametrize("target", [WORKTREE, WORKTREE + "\\a\\b", "c:\\VST-RUNS\\R1\\WT\\x", WORKTREE + "\\a\\..\\b"])
def test_link_inside_worktree_root_is_allowed(target):
    inv = wt_mut(reparse_points=[{"path": WORKTREE + "\\l", "target": target}])
    assert w.check_worktree_confinement(inv, worker())["result"] == "PASS"


def test_real_collector_refuses_drive_root_and_one_level_run_dir():
    with pytest.raises(ContractError, match="two levels"):
        w.collect_worktree_inventory("C:\\", "C:\\Windows", ["C:\\Windows"])
    with pytest.raises(ContractError, match="two levels"):
        w.collect_worktree_inventory("C:\\Windows", "C:\\Windows\\System32", ["C:\\Windows"])


def test_real_junction_to_sibling_inside_run_dir_is_reported_as_escaping(tmp_path):
    run = tmp_path / "run"
    wt = run / "wt"
    wt.mkdir(parents=True)
    sibling = run / "sibling"
    sibling.mkdir()
    _mk_junction(wt / "to_sibling", sibling)
    inv = w.collect_worktree_inventory(str(run), str(wt), [str(sibling)])
    assert [os.path.basename(p["path"]) for p in inv["reparse_points"]] == ["to_sibling"]
    v = w.check_worktree_confinement(inv, {"sid": "S-1-5-21-9-9-9-4242", "groups": []})
    assert "no_escaping_reparse" in failed(v) and "worktree_inside_run_dir" not in failed(v)


# ====================================================== review-fix batch: numeric / string hardening

@pytest.mark.parametrize("observed", [float("inf"), float("-inf"), float("nan"), 1e12, -1e12, 1e300, 10 ** 400])
def test_binding_non_finite_or_huge_observed_refused(observed):
    with pytest.raises(ContractError):
        bind(good_meta(observed))


@pytest.mark.parametrize("now", [float("inf"), float("-inf"), float("nan"), 10 ** 400])
def test_binding_non_finite_now_refused(now):
    with pytest.raises(ContractError):
        bind(good_meta(), now=now)


@pytest.mark.parametrize("max_age", [float("inf"), float("nan"), 86400.5, 86401, 1e300, 10 ** 400, 0, -1, 0.0])
def test_binding_max_age_outside_0_86400_refused(max_age):
    with pytest.raises(ContractError):
        bind(good_meta(), max_age_sec=max_age)


def test_binding_max_age_upper_boundary_86400_accepted():
    assert bind(good_meta(NOW - 86400), max_age_sec=86400)["result"] == "PASS"
    assert failed(bind(good_meta(NOW - 86401), max_age_sec=86400)) == {"fresh"}


def test_evaluate_with_infinite_observed_time_is_inconclusive_not_pass():
    inv = good_inventories()
    inv["worker_probe"]["meta"]["observed_at_epoch"] = float("inf")
    r = evaluate(inv)
    assert r["checks"]["probe_binding"]["result"] == "INCONCLUSIVE" and r["result"] == "INCONCLUSIVE"


def test_evaluate_with_huge_int_timestamp_and_bad_max_age_is_inconclusive():
    inv = good_inventories()
    inv["worker_probe"]["meta"]["observed_at_epoch"] = 10 ** 400
    assert evaluate(inv)["checks"]["probe_binding"]["result"] == "INCONCLUSIVE"
    r = w.evaluate_proof(good_inventories(), run_id=RUN_ID, candidate_sha=SHA, now=NOW, max_age_sec=float("nan"))
    assert r["checks"]["probe_binding"]["result"] == "INCONCLUSIVE" and r["result"] == "INCONCLUSIVE"


def test_record_with_non_finite_value_is_refused_not_emitted_as_NaN_json():
    with pytest.raises(ContractError, match="JSON"):
        build(max_age_sec=float("inf"))
    with pytest.raises(ContractError, match="JSON"):
        build(fake_collectors(acl=lambda p: dict(good_acl(), extra=float("nan"))))


def test_record_non_string_worker_sid_is_recorded_and_skips_firewall():
    log = []
    rec = build(fake_collectors(log, account=lambda n: {"worker": {"sid": 5}}))
    assert rec["result"] == "INCONCLUSIVE"
    assert rec["collector_errors"]["account_sid"] == "worker sid is not a string"
    assert not any(e[0] == "firewall" for e in log)


@pytest.mark.parametrize("sha", [SHA + "\n", "\n" + SHA, SHA + " ", SHA.upper(), "\uff41" * 40, "a" * 41])
def test_candidate_sha_must_be_exact_40_lower_hex_no_trailing_newline(sha):
    with pytest.raises(ContractError):
        bind(good_meta(), candidate_sha=sha)
    with pytest.raises(ContractError):
        w.collect_worker_probe(RUN_ID, sha)
    with pytest.raises(ContractError):
        w.evaluate_proof(good_inventories(), run_id=RUN_ID, candidate_sha=sha, now=NOW, max_age_sec=MAX_AGE)
    with pytest.raises(ContractError):
        build(candidate_sha=sha)


@pytest.mark.parametrize("run_id", ["r1\n", "\nr1", ".", "..", "\uff11\uff12", "a b", "", "x" * 129])
def test_run_id_exactness_and_dot_names_refused(run_id):
    with pytest.raises(ContractError):
        bind(good_meta(), run_id=run_id)
    with pytest.raises(ContractError):
        w.collect_worker_probe(run_id, SHA)


@pytest.mark.parametrize("run_id", ["..a", "a.b", "a..b", ".a", "x" * 128])
def test_run_id_legitimate_dotted_names_accepted(run_id):
    m = good_meta()
    m["run_id"] = run_id
    assert bind(m, run_id=run_id)["result"] == "PASS"


def test_meta_sha_with_trailing_newline_does_not_match():
    m = good_meta()
    m["candidate_sha"] = SHA + "\n"
    assert failed(bind(m)) == {"candidate_sha_matches"}


@pytest.mark.parametrize("name", ["vst-worker\n", "\uff41dmin", "a" * 21, "x y"])
def test_account_name_exactness(name):
    with pytest.raises(ContractError):
        w.collect_account_inventory(name)


@pytest.mark.parametrize("sid", [WSID + "\n", "\n" + WSID, WSID + " ", "S-1-\uff15-21"])
def test_sid_fullmatch_ascii_only(sid):
    with pytest.raises(ContractError):
        w.collect_firewall_inventory(sid)
    wk = worker()
    wk["sid"] = sid
    with pytest.raises(ContractError):
        w.check_secret_isolation(good_acl(), wk)


def test_powershell_json_with_utf8_bom_is_decoded(monkeypatch):
    def fake_run(args, **kw):
        return subprocess.CompletedProcess(args, 0, stdout=b"\xef\xbb\xbf{\"a\": 1}\r\n", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert w._run_powershell_json("1") == {"a": 1}


def test_powershell_non_json_or_nonzero_exit_refused(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda a, **k: subprocess.CompletedProcess(a, 0, stdout=b"not json", stderr=b""))
    with pytest.raises(ContractError):
        w._run_powershell_json("1")
    monkeypatch.setattr(subprocess, "run", lambda a, **k: subprocess.CompletedProcess(a, 3, stdout=b"", stderr=b"boom"))
    with pytest.raises(ContractError, match="exited 3"):
        w._run_powershell_json("1")


def test_DEFECT_evaluate_proof_non_dict_inventories_must_be_contract_error():
    for bad in (None, [], "x"):
        with pytest.raises(ContractError):
            w.evaluate_proof(bad, run_id=RUN_ID, candidate_sha=SHA, now=NOW, max_age_sec=MAX_AGE)


# ====================================================== review-fix batch: icacls strictness and completeness

@pytest.mark.parametrize("extra", ["WARNING: something odd", "Successfully processed x files", "Access is denied.",
                                   "some:text without perms", "Successfully processed 1 files; extra"])
def test_icacls_unknown_non_blank_line_raises(extra):
    text = "D:\\k NT AUTHORITY\\SYSTEM:(F)\n" + extra + "\nSuccessfully processed 1 files; Failed processing 0 files\n"
    with pytest.raises(ContractError, match="unrecognized"):
        w.parse_icacls_output(text, "D:\\k")


def test_icacls_unknown_line_between_aces_raises():
    text = "D:\\k BUILTIN\\Users:(R)\n  ??? \n BUILTIN\\Administrators:(F)\n"
    with pytest.raises(ContractError):
        w.parse_icacls_output(text, "D:\\k")


def test_icacls_known_status_lines_and_blank_lines_are_accepted():
    for status in ("Successfully processed 1 files; Failed processing 0 files", "Successfully processed 1 files",
                   "Successfully processed 1 files; Failed processing 1 files", "Failed processing 1 files"):
        text = "D:\\k BUILTIN\\Users:(R)\n\n" + status + "\n\n"
        assert len(w.parse_icacls_output(text, "D:\\k")) == 1


def _acl_with_icacls_text(monkeypatch, tmp_path, tail):
    d = str(os.path.realpath(tmp_path))
    text = d + " S-1-5-18:(F)\n" + tail
    monkeypatch.setattr(w, "_run", lambda args, **k: text)
    return w.collect_acl_inventory([d])["paths"][0]


@pytest.mark.parametrize("tail,complete", [
    ("\nSuccessfully processed 1 files; Failed processing 0 files\n", True),
    ("\nSuccessfully processed 1 files\n", True),
    ("", False),                                                              # no status line seen
    ("\nSuccessfully processed 0 files; Failed processing 1 files\n", False),
    ("\nFailed processing 1 files\n", False),
])
def test_collected_acl_item_complete_only_with_clean_status_line(monkeypatch, tmp_path, tail, complete):
    item = _acl_with_icacls_text(monkeypatch, tmp_path, tail)
    assert item["complete"] is complete
    v = w.check_secret_isolation({"paths": [item]}, worker())
    assert v["result"] == ("PASS" if complete else "FAIL")
    if not complete:
        assert "incomplete" in v["subchecks"][0]["detail"]


def test_collected_acl_with_unknown_line_is_refused(monkeypatch, tmp_path):
    d = str(os.path.realpath(tmp_path))
    monkeypatch.setattr(w, "_run", lambda args, **k: d + " S-1-5-18:(F)\nWARNING weird\n")
    with pytest.raises(ContractError, match="unrecognized"):
        w.collect_acl_inventory([d])


# ====================================================== firewall Package mapping (live rule with no package)

def _capture_firewall_script(monkeypatch, payload):
    seen = {}

    def fake(script, **kw):
        seen["script"] = script
        return payload

    monkeypatch.setattr(w, "_run_powershell_json", fake)
    return seen


def test_firewall_collector_script_maps_empty_package_to_Any_not_unavailable(monkeypatch):
    seen = _capture_firewall_script(monkeypatch, {"profiles": [], "rules": []})
    w.collect_firewall_inventory(WSID)
    script = seen["script"]
    assert "IsNullOrEmpty([string]$ap.Package)" in script
    assert "{,@('Any')}" in script
    # the package assignment must use the Any mapping first; '<unavailable>' stays only the generic unreadable-value fallback
    pkg = script[script.index("$o.package="):]
    assert pkg.index("IsNullOrEmpty") < pkg.index("@('Any')") < pkg.index("&$s $ap.Package")


def test_firewall_collector_package_Any_rule_is_unrestricted_but_unavailable_package_is_restricted(monkeypatch):
    rule = block_rule(package="Any")                               # PowerShell collapses a one-element array to a scalar
    _capture_firewall_script(monkeypatch, {"profiles": [{"name": "Domain", "enabled": True}], "rules": [rule]})
    fw = w.collect_firewall_inventory(WSID)
    assert fw["rules"][0]["package"] == ["Any"]
    assert w._rule_is_unrestricted(fw["rules"][0], fw["profiles"]) is True
    _capture_firewall_script(monkeypatch, {"profiles": [{"name": "Domain", "enabled": True}],
                                           "rules": [block_rule(package="<unavailable>")]})
    fw = w.collect_firewall_inventory(WSID)
    assert fw["rules"][0]["package"] == ["<unavailable>"]
    assert w._rule_is_unrestricted(fw["rules"][0], fw["profiles"]) is False


def test_block_rule_with_package_Any_passes_egress_and_unavailable_package_fails():
    assert egress_failed(block_rule(package=["Any"])) == set()
    assert egress_failed(block_rule(package=["<unavailable>"])) == {BLOCK_SUB}
