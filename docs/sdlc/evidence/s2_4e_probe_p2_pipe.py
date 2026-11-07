"""P2: named-pipe lifecycle over tools/vst/windows_named_pipe.py in separate processes.

Patched (only): windows_named_pipe._verify_service_process -> no-op (SCM pid check), in BOTH the server
process and every client process. Server SID is set to the current user SID; clients are admitted through
allowed_client_services {Users S-1-5-32-545: name} because the module rejects server SID == client SID.
Modes: (default) orchestrator/client, "server", "noread <pipe> <hold_sec>".
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from s2_4e_probe_common import REPO, own_user_sid, record, sub, overall

sys.path.insert(0, str(REPO))
from tools.vst import windows_named_pipe as wp  # noqa: E402

wp._verify_service_process = lambda *a, **k: None  # the ONLY monkeypatch
SVC = "vstprobe"
BIG = random.Random(1234).randbytes(1 << 20)
BIG_SHA = hashlib.sha256(BIG).hexdigest()


def read_line(conn, limit=128) -> bytes:
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = conn.recv(1)
        if not chunk:
            break
        buf += chunk
        if len(buf) > limit:
            raise ValueError("line too long")
    return buf


def server(pipe: str, logpath: str) -> None:
    import logging
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format="%(levelname)s %(message)s")
    me = own_user_sid()
    listener = wp.WindowsNamedPipeListener(
        pipe, server_sid=me, server_service=SVC,
        allowed_client_services={"S-1-5-32-545": SVC + "-client"}, timeout_sec=15.0)
    log = open(logpath, "a", encoding="utf-8", buffering=1)

    def emit(**kw):
        kw["t"] = time.time()
        log.write(json.dumps(kw) + "\n")

    print("READY", flush=True)
    while True:
        t0 = time.monotonic()
        conn = listener.accept(timeout_sec=1.0)
        if conn is None:
            waited = (time.monotonic() - t0) * 1000
            if waited > 1500:  # longer than the 1 s accept timeout => spent in handshake wait
                emit(ev="dropped_after_handshake_wait", ms=round(waited))
            continue
        accepted = time.monotonic()
        req = "?"
        try:
            req = read_line(conn).decode().strip()
            emit(ev="request", req=req)
            quit_ = req == "QUIT"
            if req.startswith("ECHO"):
                conn.sendall(("RESP " + req[5:] + "\n").encode())
            elif req == "BIG":
                conn.sendall(b"LEN %d\n" % len(BIG) + BIG)
            elif req == "SMALL":
                conn.sendall(b"OK\n")
            elif quit_:
                conn.sendall(b"BYE\n")
            sent = time.monotonic()
            emit(ev="sent", req=req, send_ms=round((sent - accepted) * 1000))
        except Exception as exc:  # noqa: BLE001
            emit(ev="handler_error", error=repr(exc))
            quit_ = False
        c0 = time.monotonic()
        conn.close()  # FlushFileBuffers + DisconnectNamedPipe + CloseHandle
        emit(ev="closed", req=req,close_ms=round((time.monotonic() - c0) * 1000))
        if quit_:
            break
    listener.close()


def client(pipe: str, timeout=15.0):
    return wp.WindowsNamedPipeClient(pipe, expected_server_sid=own_user_sid(),
                                     expected_server_service=SVC, timeout_sec=timeout).connect()


def request(pipe: str, line: str, timeout=15.0) -> bytes:
    c = client(pipe, timeout)
    try:
        c.sendall(line.encode() + b"\n")
        buf = b""
        while True:
            chunk = c.recv(65536)
            if not chunk:
                return buf
            buf += chunk
            if line == "BIG":
                if buf.startswith(b"LEN ") and b"\n" in buf:
                    head, _, body = buf.partition(b"\n")
                    if len(body) >= int(head[4:]):
                        return buf
            elif buf.endswith(b"\n"):
                return buf
    finally:
        c.close()


def noread(pipe: str, hold: float) -> None:
    c = client(pipe)
    c.sendall(b"SMALL\n")
    print("SENT", flush=True)
    time.sleep(hold)
    os._exit(0)  # exit without reading the response


def events(logpath: str):
    p = Path(logpath)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def main() -> None:
    pipe = f"s24e-probe-{os.getpid()}"
    tmp = tempfile.mkdtemp(prefix="s24e-p2-")
    logpath = str(Path(tmp) / "server.log")
    me = Path(__file__).resolve()
    srv = subprocess.Popen([sys.executable, str(me), "server", pipe, logpath], cwd=str(REPO),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subs, notes = [], []
    try:
        assert srv.stdout.readline().strip() == "READY"
        # (a) 5 sequential cycles
        res = []
        for i in range(5):
            t0 = time.monotonic()
            try:
                out = request(pipe, f"ECHO {i}")
                res.append((out == f"RESP {i}\n".encode(), round((time.monotonic() - t0) * 1000)))
            except Exception as exc:  # noqa: BLE001
                res.append((False, repr(exc)))
        subs.append(sub("(a) 5 sequential request/response cycles", "PASS" if all(r[0] for r in res) else "FAIL",
                        f"(ok, ms) per cycle: {res}"))
        # (b1) client sends then exits without reading
        n0 = len(events(logpath))
        p = subprocess.Popen([sys.executable, str(me), "noread", pipe, "0.15"], cwd=str(REPO),
                             stderr=subprocess.PIPE, text=True)
        p.wait(timeout=30)
        time.sleep(0.5)
        ev = events(logpath)[n0:]
        closed = [e for e in ev if e["ev"] == "closed" and e.get("req") == "SMALL"]
        handled = any(e["ev"] == "request" and e.get("req") == "SMALL" for e in ev)
        t0 = time.monotonic()
        nxt = request(pipe, "ECHO after-b1")
        nxt_ms = round((time.monotonic() - t0) * 1000)
        ok = bool(closed) and closed[0]["close_ms"] < 1000 and nxt == b"RESP after-b1\n"
        subs.append(sub("(b1) client exits without reading: server close does not block; next client served",
                        "PASS" if ok else "FAIL",
                        f"handled_by_server={handled} close_ms={closed[0]['close_ms'] if closed else None} "
                        f"next_client_ok={nxt == b'RESP after-b1' + chr(10).encode()} next_ms={nxt_ms} events={ev}"))
        # (b2) extra observation: client stays connected, never reads, for 4 s
        n0 = len(events(logpath))
        p = subprocess.Popen([sys.executable, str(me), "noread", pipe, "4"], cwd=str(REPO),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        sent_line = p.stdout.readline().strip()
        if sent_line != "SENT":
            p.kill()
            raise RuntimeError("b2 noread client did not send: stderr=" + p.stderr.read()[-1500:]
                               + " server_events=" + json.dumps(events(logpath))[-1500:])
        time.sleep(0.3)
        t0 = time.monotonic()
        nxt = request(pipe, "ECHO during-hold", timeout=20.0)
        wait_ms = round((time.monotonic() - t0) * 1000)
        p.wait(timeout=30)
        ev = events(logpath)[n0:]
        closed = [e for e in ev if e["ev"] == "closed" and e.get("req") == "SMALL"]
        notes.append({"b2_observation": {
            "scenario": "peer connected, request sent, response NOT read, peer held open 4 s",
            "server_close_ms": closed[0]["close_ms"] if closed else None,
            "second_client_latency_ms": wait_ms, "second_client_ok": nxt == b"RESP during-hold\n",
            "meaning": "close() (FlushFileBuffers) blocks until the peer reads or exits; with a "
                       "single-threaded accept loop one stalled same-trust peer delays all others"}})
        subs.append(sub("(b2) INFORMATIONAL stalled non-reading peer (not a pass/fail criterion)", "PASS",
                        json.dumps(notes[-1]["b2_observation"])))
        # (c) connect, send nothing: server must drop in ~5 s and keep serving
        n0 = len(events(logpath))
        holder = client(pipe)
        t0 = time.monotonic()
        side = {}

        def other():
            time.sleep(0.5)
            s0 = time.monotonic()
            side["ok"] = request(pipe, "ECHO during-silent", timeout=20.0) == b"RESP during-silent\n"
            side["ms"] = round((time.monotonic() - s0) * 1000)
        th = threading.Thread(target=other)
        th.start()
        data, err = None, None
        try:
            data = holder.recv(16)  # b"" once the server drops the instance
        except Exception as exc:  # noqa: BLE001
            err = repr(exc)
        drop_ms = round((time.monotonic() - t0) * 1000)
        th.join(30)
        holder.close()
        again = request(pipe, "ECHO after-silent") == b"RESP after-silent\n"
        dropped_evt = [e for e in events(logpath)[n0:] if e["ev"] == "dropped_after_handshake_wait"]
        ok = (bool(dropped_evt) and 4500 <= dropped_evt[0]["ms"] <= 7000 and 4000 <= drop_ms <= 7000
              and side.get("ok") and again)
        subs.append(sub("(c) silent client dropped by server at ~5 s handshake; listener keeps serving",
                        "PASS" if ok else "FAIL",
                        f"recv={data!r} err={err} drop_ms={drop_ms} concurrent_client={side} "
                        f"served_after_drop={again} server_events={events(logpath)[n0:]}"))
        eof_ok = data == b""
        subs.append(sub("(c2) client recv() reports EOF (b'') once the server dropped the instance",
                        "PASS" if eof_ok else "FAIL",
                        f"recv returned {data!r}, raised {err} (233 = ERROR_PIPE_NOT_CONNECTED is not mapped to EOF; "
                        "recv maps only 109/232)"))
        # (d) ~1 MiB response intact
        t0 = time.monotonic()
        try:
            out = request(pipe, "BIG", timeout=30.0)
            head, _, body = out.partition(b"\n")
            good = head == b"LEN %d" % len(BIG) and hashlib.sha256(body).hexdigest() == BIG_SHA
            detail = f"header={head!r} body_len={len(body)} sha_match={hashlib.sha256(body).hexdigest() == BIG_SHA}"
        except Exception as exc:  # noqa: BLE001
            good, detail = False, repr(exc)
        subs.append(sub("(d) 1 MiB response received intact", "PASS" if good else "FAIL",
                        detail + f" ms={round((time.monotonic() - t0) * 1000)}"))
        try:
            request(pipe, "QUIT")
        except Exception as exc:  # noqa: BLE001
            notes.append({"quit_error": repr(exc)})
    finally:
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            srv.kill()
        err = srv.stderr.read()
    record("P2", "python docs/sdlc/evidence/s2_4e_probe_p2_pipe.py", overall(subs), subs,
           "server stderr: " + err[-1500:] + "\nserver log: " + json.dumps(events(logpath))[-2000:],
           {"patched": "windows_named_pipe._verify_service_process replaced by a no-op in server and client "
                       "processes; nothing else patched. server_sid=current user SID; client policy "
                       "allowed_client_services={S-1-5-32-545 (Users)}",
            "notes": notes})


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        server(sys.argv[2], sys.argv[3])
    elif len(sys.argv) > 1 and sys.argv[1] == "noread":
        noread(sys.argv[2], float(sys.argv[3]))
    else:
        main()
