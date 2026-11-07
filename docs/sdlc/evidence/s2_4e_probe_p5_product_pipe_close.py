"""P5: real product WindowsNamedPipeListener/Client, server writes a response and closes at once
(CloseHandle-only close). Multi-client session, >64 KB response, EOF after full read, and
non-reading clients vs the next accept. Only patch: _verify_service_process (no SCM service exists)."""
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

wp._verify_service_process = lambda *a, **k: None
SVC = "vstprobe5"
BIG = random.Random(99).randbytes(300_000)       # > 64 KB pipe buffer
HUGE = random.Random(98).randbytes(1_500_000)    # far above buffer: needs a reader
SHA = hashlib.sha256(BIG).hexdigest()


def line(conn) -> str:
    buf = b""
    while not buf.endswith(b"\n"):
        c = conn.recv(1)
        if not c:
            break
        buf += c
    return buf.decode().strip()


def server(pipe: str, logpath: str, io_timeout: float) -> None:
    me = own_user_sid()
    lis = wp.WindowsNamedPipeListener(pipe, server_sid=me, server_service=SVC,
                                      allowed_client_services={"S-1-5-32-545": SVC + "c"}, timeout_sec=io_timeout)
    log = open(logpath, "a", encoding="utf-8", buffering=1)
    print("READY", flush=True)
    while True:
        conn = lis.accept(timeout_sec=1.0)
        if conn is None:
            continue
        t0 = time.monotonic()
        req, err = "?", None
        try:
            req = line(conn)
            if req.startswith("ECHO"):
                conn.sendall(("RESP " + req[5:] + "\n").encode())
            elif req == "BIG":
                conn.sendall(b"LEN %d\n" % len(BIG) + BIG)
            elif req == "HUGE":
                conn.sendall(b"LEN %d\n" % len(HUGE) + HUGE)
            elif req == "SMALL":
                conn.sendall(b"OK\n")
        except Exception as exc:  # noqa: BLE001
            err = repr(exc)
        sent_ms = round((time.monotonic() - t0) * 1000)
        c0 = time.monotonic()
        conn.close()
        log.write(json.dumps({"req": req, "err": err, "send_ms": sent_ms,
                              "close_ms": round((time.monotonic() - c0) * 1000)}) + "\n")
        if req == "QUIT":
            break
    lis.close()


def mk(pipe, timeout=10.0):
    return wp.WindowsNamedPipeClient(pipe, expected_server_sid=own_user_sid(),
                                     expected_server_service=SVC, timeout_sec=timeout).connect()


def full_cycle(pipe: str, req: str, timeout=10.0):
    """Returns (payload, eof_value, eof_ms). eof_value must be b'' after the full response."""
    c = mk(pipe, timeout)
    try:
        c.sendall(req.encode() + b"\n")
        buf = b""
        need = None
        while True:
            if need is None and b"\n" in buf:
                head, _, rest = buf.partition(b"\n")
                if head.startswith(b"LEN "):
                    need = len(head) + 1 + int(head[4:])
                else:
                    need = len(head) + 1
            if need is not None and len(buf) >= need:
                break
            d = c.recv(65536)
            if not d:
                return buf, "EOF-BEFORE-COMPLETE", 0
            buf += d
        t0 = time.monotonic()
        try:
            eof = c.recv(65536)
        except Exception as exc:  # noqa: BLE001
            eof = "raised " + repr(exc)
        return buf, eof, round((time.monotonic() - t0) * 1000)
    finally:
        c.close()


def start(pipe, log, io_timeout):
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "server", pipe, log, str(io_timeout)],
                         cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "READY", p.stderr.read()
    return p


def events(log):
    p = Path(log)
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def hold_noread(pipe: str, req: str, hold: float) -> None:
    c = mk(pipe)
    c.sendall(req.encode() + b"\n")
    print("SENT", flush=True)
    time.sleep(hold)
    os._exit(0)


def main() -> None:
    subs = []
    tmp = tempfile.mkdtemp(prefix="s24e-p5-")
    pipe = f"s24e-p5-{os.getpid()}"
    log = str(Path(tmp) / "s.log")
    srv = start(pipe, log, 3.0)
    try:
        # 1. multi-client multi-request: 4 threads x 3 requests, mixed ECHO / BIG
        results, lock = [], threading.Lock()

        def worker(n):
            for i in range(3):
                req = "BIG" if (n + i) % 3 == 0 else f"ECHO c{n}r{i}"
                try:
                    payload, eof, ms = full_cycle(pipe, req)
                    if req == "BIG":
                        head, _, body = payload.partition(b"\n")
                        ok = head == b"LEN %d" % len(BIG) and hashlib.sha256(body).hexdigest() == SHA
                    else:
                        ok = payload == f"RESP c{n}r{i}\n".encode()
                    r = (req, ok, eof == b"", ms)
                except Exception as exc:  # noqa: BLE001
                    r = (req, False, False, repr(exc))
                with lock:
                    results.append(r)
        ths = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        t0 = time.monotonic()
        [t.start() for t in ths]
        [t.join(120) for t in ths]
        subs.append(sub("1a multi-client x multi-request: full payload intact (incl. 300 KB > 64 KB)",
                        "PASS" if len(results) == 12 and all(r[1] for r in results) else "FAIL",
                        f"n={len(results)} results={results} total_ms={round((time.monotonic()-t0)*1000)}"))
        subs.append(sub("1b client sees EOF (b'') after the complete response in every cycle",
                        "PASS" if len(results) == 12 and all(r[2] for r in results) else "FAIL",
                        f"eof flags={[r[2] for r in results]} eof_ms={[r[3] for r in results]}"))
        ev = events(log)
        subs.append(sub("1c server close() never slow (CloseHandle-only): max close_ms < 200",
                        "PASS" if ev and max(e["close_ms"] for e in ev) < 200 else "FAIL",
                        f"max_close_ms={max((e['close_ms'] for e in ev), default=None)} errs={[e for e in ev if e['err']]}"))

        # 2. client that never reads (small response): next accept must not be blocked
        n0 = len(events(log))
        me = Path(__file__).resolve()
        p = subprocess.Popen([sys.executable, str(me), "noread", pipe, "SMALL", "5"], cwd=str(REPO),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert p.stdout.readline().strip() == "SENT", p.stderr.read()
        time.sleep(0.3)
        t0 = time.monotonic()
        out, eof, _ = full_cycle(pipe, "ECHO after-noread-small", timeout=15.0)
        ms = round((time.monotonic() - t0) * 1000)
        p.wait(30)
        subs.append(sub("2 non-reading client (small response) does not delay next client beyond handshake window (2 s)",
                        "PASS" if out == b"RESP after-noread-small\n" and ms < 2500 else "FAIL",
                        f"next_client_ms={ms} out={out!r} events={events(log)[n0:]}"))

        # 3. client that never reads a response far above the pipe buffer: bounded by server IO timeout (3 s)
        n0 = len(events(log))
        p = subprocess.Popen([sys.executable, str(me), "noread", pipe, "HUGE", "9"], cwd=str(REPO),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert p.stdout.readline().strip() == "SENT", p.stderr.read()
        time.sleep(0.3)
        t0 = time.monotonic()
        out, eof, _ = full_cycle(pipe, "ECHO after-noread-huge", timeout=20.0)
        ms = round((time.monotonic() - t0) * 1000)
        p.wait(30)
        e3 = [e for e in events(log)[n0:] if e["req"] == "HUGE"]
        subs.append(sub("3 non-reading client (1.5 MB response) blocks server at most IO timeout (3 s) + handshake (2 s)",
                        "PASS" if out == b"RESP after-noread-huge\n" and ms < 6500 and e3 and e3[0]["err"] else "FAIL",
                        f"next_client_ms={ms} huge_event={e3} (err expected: TimeoutError on sendall)"))
    finally:
        try:
            full_cycle(pipe, "QUIT", timeout=10.0)
        except Exception:  # noqa: BLE001
            pass
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            srv.kill()
        err = srv.stderr.read()
    record("P5_product_pipe_closehandle_multiclient", "python docs/sdlc/evidence/s2_4e_probe_p5_product_pipe_close.py",
           overall(subs), subs, "server stderr: " + err[-1500:] + "\nlog: " + json.dumps(events(log))[-2000:],
           {"patched": "windows_named_pipe._verify_service_process no-op only"})


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        server(sys.argv[2], sys.argv[3], float(sys.argv[4]))
    elif len(sys.argv) > 1 and sys.argv[1] == "noread":
        hold_noread(sys.argv[2], sys.argv[3], float(sys.argv[4]))
    else:
        main()
