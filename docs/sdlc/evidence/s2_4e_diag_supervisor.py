"""Diagnose S2-4E Windows service start-up for all six VST roles (test-only).

Run once from an elevated shell. For each role, in its own subprocess, it runs the
role's real `main()` from the working-tree code (D:\\Repo\\Virtual_scrum_team) against
the installed C:\\ProgramData\\VST runtime. Two things are replaced so an administrator
shell can stand in for the services:
  * assert_current_service_identity: "this process is the live SCM service" is skipped;
  * run_scm_service: instead of the SCM dispatcher, the role's target factory is called
    once, so composition errors surface; serve_forever() is never called.
Results go to s2_4e_diag_supervisor.out next to this script. No key bytes are printed.
"""
import os
import subprocess
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "s2_4e_diag_supervisor.out")
REPO = r"D:\Repo\Virtual_scrum_team"
ROLES = {
    "owner": ("tools.vst.dispatch_owner_service", ["--windows-scm"]),
    "supervisor": ("tools.vst.supervisor_service", ["--windows-scm"]),
    "dispatcher": ("tools.vst.dispatcher_service", ["--windows-scm"]),
    "runner": ("tools.vst.runner_service", ["--windows-scm", "runner"]),
    "signer": ("tools.vst.signer", ["--windows-scm"]),
    "worker": ("tools.vst.runner_service", ["--windows-scm", "worker"]),
}


def child(role: str) -> int:
    sys.dont_write_bytecode = True
    sys.path.insert(0, REPO)
    from importlib import import_module

    from tools.vst import windows_service_host as host

    host.assert_current_service_identity = lambda identity: None
    built = []

    def fake_run(service_name, target_factory):
        target = target_factory()
        built.append(service_name)
        closer = getattr(target, "store", None)
        if closer is not None and hasattr(closer, "close"):
            closer.close()

    host.run_scm_service = fake_run
    module_name, argv = ROLES[role]
    module = import_module(module_name)
    sys.argv = [module_name, *argv]
    try:
        module.main()
    except BaseException:
        print("ROLE %s: FAILED" % role)
        print(traceback.format_exc())
        return 1
    print("ROLE %s: composed OK (%s)" % (role, built))
    return 0


def parent() -> int:
    lines = []
    failed = 0
    for role in ROLES:
        result = subprocess.run(
            [sys.executable, "-I", os.path.abspath(__file__), "--child", role],
            capture_output=True, text=True, timeout=120, cwd=REPO,
        )
        failed += result.returncode != 0
        lines.append(result.stdout.strip() or "ROLE %s: no output" % role)
        if result.stderr.strip():
            lines.append("stderr:\n" + result.stderr.strip())
    lines.append("SUMMARY: %d of %d roles failed" % (failed, len(ROLES)))
    text = "\n\n".join(lines) + "\n"
    with open(OUT, "w", encoding="utf-8") as stream:
        stream.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        raise SystemExit(child(sys.argv[2]))
    raise SystemExit(parent())
