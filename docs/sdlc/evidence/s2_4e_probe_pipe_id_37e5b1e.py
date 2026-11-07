"""Probe pipe_id_37e5b1e: client identification by SCM pid (no token open) for service listeners,
token-SID path for user-SID listeners, sanitized event-log handler, compile + PS parse.
Real WindowsNamedPipeListener/Client; only _service_process_id (no SCM service) and the client-side
server verification are patched. Evidence only, no product code."""
from __future__ import annotations

import json
import logging
import os
import py_compile
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from unittest import mock

from s2_4e_probe_common import REPO, own_user_sid, record, sub, overall

sys.path.insert(0, str(REPO))
from tools.vst import windows_named_pipe as wp  # noqa: E402
from tools.vst.contracts import ContractError  # noqa: E402

SELF = str(Path(__file__).resolve())
FAKE_SERVER = "S-1-5-32-545"  # Users group: the non-admin user holds it, so later pipe instances can be created
OTHER_SID = "S-1-5-21-9999-8888-7777-1001"


# ---------------------------------------------------------------- child (client) side
def child(pipe: str, tag: str, count: int) -> None:
    wp._verify_service_process = lambda *a, **k: None  # client-side server check has no SCM service
    sys.stdin.readline()  # wait for "go" so the parent can arm the pid patch first
    for i in range(count):
        out = {"tag": tag, "i": i, "pid": os.getpid()}
        try:
            c = wp.WindowsNamedPipeClient(pipe, expected_server_sid=sys.argv[5],
                                          expected_server_service="vstprobeid", timeout_sec=5.0).connect()
            c.sendall(f"ECHO {tag}-{i}\n".encode())
            buf = b""
            while not buf.endswith(b"\n"):
                ch = c.recv(1)
                if not ch:
                    break
                buf += ch
            c.close()
            out.update(resp=buf.decode().strip(), ok=buf.startswith(b"RESP "))
        except Exception as exc:  # noqa: BLE001
            out.update(ok=False, err=repr(exc))
        print(json.dumps(out), flush=True)


def spawn(pipe: str, tag: str, count: int, server_sid: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, SELF, "child", pipe, tag, str(count), server_sid],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def collect(p: subprocess.Popen) -> list:
    out, err = p.communicate(timeout=60)
    rows = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    if not rows:
        rows = [{"ok": False, "err": "no output; stderr=" + err[-300:]}]
    return rows


# ---------------------------------------------------------------- server side
class DropLog(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def serve(lis, want: int, budget=25.0):
    """Accept until `want` events (served + dropped) or budget ends. Returns (served, drops)."""
    h = DropLog()
    wp._LOG.addHandler(h)
    served, t_end = [], time.monotonic() + budget
    try:
        while time.monotonic() < t_end and len(served) + len(h.records) < want:
            conn = lis.accept(timeout_sec=1.0)
            if conn is None:
                continue
            req = b""
            while not req.endswith(b"\n"):
                ch = conn.recv(1)
                if not ch:
                    break
                req += ch
            conn.sendall(b"RESP " + req[5:])
            conn.close()
            served.append(req.decode().strip())
    finally:
        wp._LOG.removeHandler(h)
    return served, h.records


def counting_token_check():
    calls = []
    orig = wp._check_token_user_sid

    def wrapper(token, sid):
        r = orig(token, sid)
        calls.append((sid, r))
        return r
    wp._check_token_user_sid = wrapper
    return calls


def svc_listener(pipe, services):
    return wp.WindowsNamedPipeListener(pipe, server_sid=own_user_sid(), server_service="vstprobeid",
                                       allowed_client_services=services, timeout_sec=5.0)


def run_clients(lis, pipe, specs, server_sid, set_pids, want, sequential=False):
    """specs: [(tag,count)]; set_pids(list_of_pids) arms the patch; returns (rows, served, drops)."""
    procs = [spawn(pipe, t, c, server_sid) for t, c in specs]
    set_pids([p.pid for p in procs])
    for p in procs:
        p.stdin.write("go\n"); p.stdin.flush()
        if sequential:
            pass
    served, drops = serve(lis, want)
    rows = [r for p in procs for r in collect(p)]
    return rows, served, drops, [p.pid for p in procs]


def probe1():
    pipe = "pipeid1-" + str(os.getpid()); subs = []
    calls = counting_token_check(); state = {}
    wp._service_process_id = lambda name: state[name]
    lis = svc_listener(pipe, {"S-1-5-32-545": "vstA", "S-1-5-32-544": "vstB"})
    try:
        def arm(pids): state.update(vstA=pids[0], vstB=pids[1])
        rows, served, drops, pids = run_clients(lis, pipe, [("a", 3), ("b", 3)], own_user_sid(), arm, 6)
    finally:
        lis.close()
    ok = [r for r in rows if r.get("ok")]
    subs.append(sub("2 clients (child pids differ from server) x3 sequential requests all accepted",
                    "PASS" if len(ok) == 6 and len(served) == 6 and not drops and os.getpid() not in pids else "FAIL",
                    f"server_pid={os.getpid()} child_pids={pids} ok={len(ok)}/6 served={sorted(served)} drops={len(drops)} rows={rows[:2]}"))
    subs.append(sub("service path did not open any token (no _check_token_user_sid call)",
                    "PASS" if not calls else "FAIL", f"token_check_calls={calls}"))
    return subs


def probe2():
    pipe = "pipeid2-" + str(os.getpid()); subs = []
    state = {}
    wp._service_process_id = lambda name: state[name]
    lis = svc_listener(pipe, {"S-1-5-32-545": "vstA"})
    try:
        rows, served, drops, pids = run_clients(lis, pipe, [("bad", 1)], own_user_sid(),
                                                lambda p: state.update(vstA=os.getpid()), 1)
        bad_rejected = not rows[0].get("ok") and not served and len(drops) == 1
        subs.append(sub("client pid != SCM pid (server's own pid returned): dropped, client sees EOF/error",
                        "PASS" if bad_rejected else "FAIL",
                        f"client_row={rows[0]} served={served} drops={[(r.getMessage(), str(r.exc_info[1])) for r in drops]}"))
        rows2, served2, drops2, pids2 = run_clients(lis, pipe, [("good", 2)], own_user_sid(),
                                                    lambda p: state.update(vstA=p[0]), 2)
        subs.append(sub("listener keeps serving next valid client after a reject",
                        "PASS" if all(r.get("ok") for r in rows2) and len(served2) == 2 else "FAIL",
                        f"rows={rows2} served={served2} drops={len(drops2)}"))
    finally:
        lis.close()
    return subs


def probe3():
    subs = []
    state = {}

    def fake(name):
        v = state[name]
        if v == "raise":
            raise ContractError("configured Windows service is not running")
        return v
    wp._service_process_id = fake
    for label, mk, expect_ok in (
        ("first service not running (ContractError), second matches -> accepted",
         lambda pid: {"vstA": "raise", "vstB": pid}, True),
        ("all allowed services not running -> rejected",
         lambda pid: {"vstA": "raise", "vstB": "raise"}, False),
        ("first wrong pid, second not running -> rejected",
         lambda pid: {"vstA": os.getpid(), "vstB": "raise"}, False)):
        pipe = "pipeid3-%d-%d" % (os.getpid(), len(subs)); state.clear()
        lis = svc_listener(pipe, {"S-1-5-32-545": "vstA", "S-1-5-32-544": "vstB"})
        try:
            rows, served, drops, pids = run_clients(lis, pipe, [("x", 1)], own_user_sid(),
                                                    lambda p: state.update(mk(p[0])), 1)
        finally:
            lis.close()
        good = (rows[0].get("ok") and len(served) == 1 and not drops) if expect_ok else \
               (not rows[0].get("ok") and not served and len(drops) == 1)
        subs.append(sub(label, "PASS" if good else "FAIL",
                        f"row={rows[0]} served={served} drops={[str(r.exc_info[1]) for r in drops]}"))
    return subs


def probe4():
    subs = []
    wp._service_process_id = lambda n: (_ for _ in ()).throw(AssertionError("must not be called"))
    me = own_user_sid()
    for label, server_sid, user_sid, expect_ok in (
        ("user-SID listener accepts same-user client via token path", FAKE_SERVER, me, True),
        ("user-SID listener rejects when allowed SID is a different SID", me, OTHER_SID, False)):
        calls = counting_token_check()
        pipe = "pipeid4-%d-%d" % (os.getpid(), len(subs))
        lis = wp.WindowsNamedPipeListener(pipe, server_sid=server_sid, server_service="vstprobeid",
                                          allowed_client_services={}, allowed_client_user_sids=(user_sid,),
                                          timeout_sec=5.0)
        try:
            rows, served, drops, _ = run_clients(lis, pipe, [("u", 1)], server_sid, lambda p: None, 1)
        finally:
            lis.close()
        good = (rows[0].get("ok") and served and not drops and calls and calls[0][1] is True) if expect_ok else \
               (not rows[0].get("ok") and not served and len(drops) == 1 and calls and calls[0][1] is False)
        subs.append(sub(label, "PASS" if good else "FAIL",
                        f"row={rows[0]} served={served} token_calls={calls} drops={[str(r.exc_info[1]) for r in drops]}"))
    return subs


def probe5():
    from tools.vst import windows_service_host as sh
    subs = []

    def mk_mock():
        captured = []
        m = mock.MagicMock()
        m.RegisterEventSourceW.return_value = 1234

        def report(src, etype, cat, eid, sid, nstr, dsz, strings, raw):
            captured.append((etype, strings[0]))
            return 1
        m.ReportEventW.side_effect = report
        return m, captured

    def raiser():
        try:
            try:
                raise OSError(5, r"C:\secret\path")
            except OSError as inner:
                raise ValueError("secret-value") from inner
        except ValueError as e:
            return e

    adv, cap = mk_mock()
    lg = logging.getLogger("probe5.pipe"); lg.setLevel(logging.DEBUG); lg.propagate = False
    h = sh._EventLogHandler(adv, "vstprobe"); lg.addHandler(h)
    errs = []
    h.handleError = lambda record: errs.append(record)
    lg.warning("dropped Windows named-pipe client on %s", r"\\.\pipe\secret-path", exc_info=raiser())
    lg.warning("dropped Windows named-pipe client on %s", r"\\.\pipe\secret-path", exc_info=ValueError("secret-value"))
    text = cap[0][1] if cap else ""
    need = ["dropped Windows named-pipe client on %s", "ValueError (message omitted)", "errno=5", "caused by:", "  at ", " in raiser"]
    forbid = ["secret-value", "secret-path", "C:\\secret", r"\\.\pipe"]
    miss = [n for n in need if n not in text]; leak = [f for f in forbid if any(f in c[1] for c in cap)]
    subs.append(sub("WARNING text: template with literal %s, ValueError (message omitted), errno=5, frame lines; no secrets",
                    "PASS" if len(cap) == 2 and not miss and not leak else "FAIL",
                    f"events={len(cap)} missing={miss} leaked={leak} text={text!r} no_tb_text={cap[1][1] if len(cap) > 1 else None!r}"))
    subs.append(sub("event type 2 for WARNING", "PASS" if cap and cap[0][0] == 2 else "FAIL", f"types={[c[0] for c in cap]}"))
    n = len(cap)
    lg.error("service refused %s", "x", exc_info=raiser())
    subs.append(sub("event type 1 for ERROR", "PASS" if len(cap) == n + 1 and cap[-1][0] == 1 else "FAIL",
                    f"types={[c[0] for c in cap]} last={cap[-1][1][:80]!r}"))
    n = len(cap); lg.info("info secret"); lg.debug("debug secret")
    subs.append(sub("INFO/DEBUG records ignored", "PASS" if len(cap) == n else "FAIL", f"added={len(cap) - n}"))
    bad = mock.MagicMock(); bad.RegisterEventSourceW.side_effect = RuntimeError("boom")
    bad2 = mock.MagicMock(); bad2.RegisterEventSourceW.return_value = 7; bad2.ReportEventW.side_effect = RuntimeError("boom2")
    prop = None
    for b in (bad, bad2):
        lg2 = logging.getLogger("probe5.raise%d" % id(b)); lg2.propagate = False; lg2.setLevel(logging.DEBUG)
        hb = sh._EventLogHandler(b, "vstprobe"); lg2.addHandler(hb); herr = []
        hb.handleError = lambda r, herr=herr: herr.append(r)
        try:
            lg2.warning("w %s", "a", exc_info=raiser()); lg2.error("e")
        except BaseException as e:  # noqa: BLE001
            prop = repr(e)
        if herr:
            prop = prop or "handleError called"
    subs.append(sub("raising mock never propagates (Register and Report failures) and handleError not triggered",
                    "PASS" if prop is None and not errs else "FAIL", f"propagated={prop} handler_errors={len(errs)}"))
    adv3, cap3 = mk_mock()
    sh._report_service_failure(adv3, "VstX", raiser())
    t3 = cap3[0][1] if cap3 else ""
    subs.append(sub("_report_service_failure still emits 'VST service X stopped:' (type 1), sanitized",
                    "PASS" if cap3 and cap3[0][0] == 1 and t3.startswith("VST service VstX stopped: ValueError (message omitted)")
                    and "secret" not in t3 else "FAIL", f"{t3!r}"))
    return subs


def probe6():
    subs = []
    files = sorted((REPO / "tools" / "vst").glob("*.py"))
    bad = []
    with tempfile.TemporaryDirectory() as td:
        for i, f in enumerate(files):
            try:
                py_compile.compile(str(f), cfile=os.path.join(td, f"{i}.pyc"), doraise=True)
            except py_compile.PyCompileError as e:
                bad.append((f.name, str(e)[:200]))
    subs.append(sub(f"py_compile all tools/vst/*.py ({len(files)} files)", "PASS" if not bad and files else "FAIL", f"bad={bad}"))
    ps1 = REPO / "tests" / "vst" / "provision_s2_4e_windows.ps1"
    cmd = ("$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('%s',[ref]$t,[ref]$e);"
           "'PSVersion='+$PSVersionTable.PSVersion;'ERRORS='+@($e).Count;$e|%%{$_.Message+' @'+$_.Extent.StartLineNumber}") % ps1
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True, timeout=120)
    ev = ps1.read_text(encoding="utf-8", errors="replace").count("VST_EVENT")
    ok = r.returncode == 0 and "ERRORS=0" in r.stdout and "PSVersion=5.1" in r.stdout
    subs.append(sub("PowerShell 5.1 parse of provision_s2_4e_windows.ps1", "PASS" if ok else "FAIL",
                    f"rc={r.returncode} {r.stdout.strip()!r} stderr={r.stderr.strip()[:200]!r} VST_EVENT_occurrences={ev}"))
    return subs


def main() -> None:
    orig = (wp._service_process_id, wp._verify_service_process)
    subs, log = [], []
    for name, fn in (("probe1", probe1), ("probe2", probe2), ("probe3", probe3), ("probe4", probe4),
                     ("probe5", probe5), ("probe6", probe6)):
        try:
            s = fn()
        except Exception:  # noqa: BLE001
            s = [sub(name + " crashed", "FAIL", traceback.format_exc()[-1500:])]
        for x in s:
            x["name"] = name + ": " + x["name"]
        subs += s
        log.append(f"{name}: " + ", ".join(x["status"] for x in s))
    record("pipe_id_37e5b1e", "python docs/sdlc/evidence/s2_4e_probe_pipe_id_37e5b1e.py", overall(subs), subs,
           "\n".join(log), {"code_delta": "pipe client identified by SCM pid; sanitized EventLog handler"})
    for x in subs:
        print(x["status"], "|", x["name"], "|", x["detail"][:700])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        child(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    else:
        main()
