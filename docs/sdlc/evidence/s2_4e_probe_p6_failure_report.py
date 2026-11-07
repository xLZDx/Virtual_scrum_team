"""P6: windows_service_host._report_service_failure text content (real function, fake advapi32 capturing
the ReportEventW payload) and best-effort behaviour."""
from __future__ import annotations

import ctypes
import sys
from unittest import mock

from s2_4e_probe_common import REPO, record, sub, overall

sys.path.insert(0, str(REPO))
from tools.vst import windows_service_host as sh  # noqa: E402
from tools.vst.contracts import ContractError  # noqa: E402


def make_advapi(captured: list, *, register_raises=None, report_raises=None, register_returns=1234):
    adv = mock.MagicMock()

    def register(machine, name):
        if register_raises:
            raise register_raises
        captured.append(("register", name))
        return register_returns

    def report(source, etype, cat, evid, sid, nstr, ndata, strings, raw):
        if report_raises:
            raise report_raises
        captured.append(("report", strings[0]))
        return True
    adv.RegisterEventSourceW.side_effect = register
    adv.ReportEventW.side_effect = report
    return adv


def raise_chain():
    try:
        try:
            raise ContractError("contract msg")
        except ContractError as ce:
            raise ValueError("secret-value-123") from ce
    except ValueError as ve:
        return ve


def text_of(cap):
    return next(v for k, v in cap if k == "report")


def main() -> None:
    subs = []
    cap: list = []
    exc = raise_chain()
    sh._report_service_failure(make_advapi(cap), "VSTSupervisor", exc)
    text = text_of(cap) if any(k == "report" for k, _ in cap) else ""
    subs.append(sub("event was written once with service-name source", "PASS" if [k for k, _ in cap] == ["register", "report"]
                    and cap[0][1] == "VSTSupervisor" else "FAIL", repr(cap)[:300]))
    subs.append(sub("ValueError message 'secret-value-123' is absent", "PASS" if "secret-value-123" not in text else "FAIL", text))
    subs.append(sub("ContractError message 'contract msg' is present", "PASS" if "contract msg" in text else "FAIL", text))
    subs.append(sub("type names ValueError + ContractError present, ValueError flagged omitted",
                    "PASS" if "ValueError (message omitted)" in text and "ContractError: contract msg" in text else "FAIL", text))
    subs.append(sub("frame lines 'at s2_4e_probe_p6_failure_report.py:<n> in raise_chain' present",
                    "PASS" if "at s2_4e_probe_p6_failure_report.py:" in text and "in raise_chain" in text else "FAIL", text))
    subs.append(sub("'caused by:' separator present", "PASS" if "caused by:" in text else "FAIL", text))
    subs.append(sub("length <= 4000", "PASS" if len(text) <= 4000 else "FAIL", f"len={len(text)}"))

    # the raw secret must also be absent when it is the __context__ (implicit chaining) and from a deep cause chain
    def implicit():
        try:
            raise OSError(5, "os msg")
        except OSError:
            raise RuntimeError("secret-ctx-777")
    try:
        implicit()
    except RuntimeError as e2:
        cap2: list = []
        sh._report_service_failure(make_advapi(cap2), "VSTSigner", e2)
        t2 = text_of(cap2)
        subs.append(sub("implicit __context__ chain: secret absent, OSError message present",
                        "PASS" if "secret-ctx-777" not in t2 and "os msg" in t2 else "FAIL", t2))

    # cap: 10000-char ContractError + 8 chained causes
    big = ContractError("X" * 10000)
    cap3: list = []
    sh._report_service_failure(make_advapi(cap3), "VSTSigner", big)
    t3 = text_of(cap3)
    subs.append(sub("oversized message is truncated to <= 4000", "PASS" if len(t3) <= 4000 else "FAIL", f"len={len(t3)}"))

    def deep():
        e = None
        for i in range(8):
            try:
                try:
                    if e:
                        raise e
                    raise ValueError("secret-deep-0")
                except Exception as inner:
                    raise ContractError(f"level {i}") from inner
            except ContractError as ce:
                e = ce
        return e
    cap4: list = []
    sh._report_service_failure(make_advapi(cap4), "VSTSigner", deep())
    t4 = text_of(cap4)
    levels = [ln for ln in t4.splitlines() if "ContractError: level" in ln]
    subs.append(sub("cause chain limited to 5 entries", "PASS" if len(levels) == 5 and "secret-deep-0" not in t4 else "FAIL",
                    f"entries={len(levels)} len={len(t4)}"))

    # logging failures never propagate
    for label, kw in (("ReportEventW raises", {"report_raises": RuntimeError("log boom")}),
                      ("RegisterEventSourceW raises", {"register_raises": OSError("reg boom")}),
                      ("RegisterEventSourceW returns 0", {"register_returns": 0})):
        try:
            sh._report_service_failure(make_advapi([], **kw), "VSTSigner", exc)
            subs.append(sub(f"logging failure does not propagate ({label})", "PASS", "returned None"))
        except BaseException as e3:  # noqa: BLE001
            subs.append(sub(f"logging failure does not propagate ({label})", "FAIL", repr(e3)))

    # real advapi32 with a service name that has no event source: must not raise either
    try:
        adv = ctypes.WinDLL("advapi32", use_last_error=True)
        sh._report_service_failure(adv, "VSTProbeNoSuchSource", exc)
        subs.append(sub("real advapi32 path does not raise (unregistered source)", "PASS", "returned None"))
    except BaseException as e4:  # noqa: BLE001
        subs.append(sub("real advapi32 path does not raise (unregistered source)", "FAIL", repr(e4)))

    record("P6_report_service_failure", "python docs/sdlc/evidence/s2_4e_probe_p6_failure_report.py",
           overall(subs), subs, text,
           {"patched": "advapi32 replaced by a MagicMock capturing RegisterEventSourceW/ReportEventW; last case uses real advapi32"})


main()
