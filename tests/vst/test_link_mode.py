"""Link mode switch (`tools/vst/link_mode.py`, catalog `catalog/link_mode.json`).

Written from the acceptance criteria, NOT_RUN (operator ban on running tests in this task):

1. the default catalog loads and resolves to mode `gates`, available true;
2. `router` is declared but unavailable and pinned in code: `set_mode(path, "router")` raises MODE_UNAVAILABLE
   (before the file is even read) and the file bytes do not change; an unknown mode raises UNKNOWN_MODE;
3. `set_mode` to the mode that is already current does not rewrite the file;
4. `load` rejects a bad file with CATALOG_INVALID (content problems) or CATALOG_UNREADABLE (cannot be read),
   including a catalog that marks `router` available, an altered pinned router entry, an unavailable `gates`,
   lone surrogates and a UTF-8 BOM;
5. CLI `main`: exit 0 ok, 1 refusal, 2 usage, 3 internal error; the output is exactly one ASCII JSON line;
6. the write is atomic (`_write_atomic`, `_replace_with_retry`): a brief PermissionError (winerror 5 or 32) is
   retried, a permanent failure keeps the old bytes and leaves no temp file.

The shipped catalog can never reach the write path through the public API (router is pinned unavailable and gates
is already current), so criterion 6 calls the private writers directly. `WriteFailedMappingTest` is the only place
that reaches `set_mode`'s write branch: it flips the code constant `ROUTER_CAPABILITY_READY` with `mock.patch`
(the documented future switch), to prove that a failed write becomes WRITE_FAILED. Drop that class if patching the
constant is not wanted.

Fixtures are copies of the real catalog in a temp directory. The repo catalog file is only ever read.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.vst import link_mode as lm

REAL_CATALOG = Path(__file__).resolve().parents[2] / "catalog" / "link_mode.json"
NAME = "link_mode.json"
BOM = b"\xef\xbb\xbf"


def base_doc() -> dict:
    """A fresh parsed copy of the real catalog (the independent source of the fixture shape)."""
    return json.loads(REAL_CATALOG.read_bytes().decode("utf-8"))


def router_available_doc() -> dict:
    doc = base_doc()
    doc["modes"]["router"] = {"available": True, "description": "hypothetical available router"}
    return doc


def make_permission_error(winerror: int) -> PermissionError:
    class _Perm(PermissionError):
        pass

    _Perm.winerror = winerror  # class attribute: works on every platform
    return _Perm(13, "denied")


class TempDirCase(unittest.TestCase):
    def setUp(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.dir = Path(holder.name)

    def put(self, data, name: str = NAME) -> Path:
        path = self.dir / name
        if isinstance(data, dict):
            data = json.dumps(data, indent=2).encode("utf-8")
        elif isinstance(data, str):
            data = data.encode("utf-8")
        path.write_bytes(data)
        return path

    def fresh_dir(self) -> Path:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        return Path(holder.name)

    def assert_code(self, code: str, func, *args):
        with self.assertRaises(lm.LinkModeError) as caught:
            func(*args)
        self.assertEqual(caught.exception.code, code)
        return caught.exception


class DefaultCatalogTest(unittest.TestCase):
    def test_real_catalog_file_exists(self):
        self.assertTrue(REAL_CATALOG.is_file())

    def test_load_default_catalog_mode_is_gates(self):
        config = lm.load(REAL_CATALOG)
        self.assertEqual(config.mode, "gates")
        self.assertTrue(config.entry("gates").available)
        self.assertFalse(config.entry("router").available)

    def test_resolve_default_catalog_is_gates_available(self):
        resolved = lm.resolve(REAL_CATALOG)
        self.assertEqual(resolved.mode, "gates")
        self.assertIs(resolved.available, True)
        self.assertIsNone(resolved.reason)
        self.assertEqual(resolved.to_dict(), {"mode": "gates", "available": True, "reason": None})

    def test_resolve_without_argument_uses_the_shipped_catalog(self):
        self.assertEqual(lm.resolve().mode, "gates")
        self.assertIs(lm.resolve().available, True)

    def test_copy_of_real_catalog_loads_the_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / NAME
            shutil.copyfile(REAL_CATALOG, copy)
            self.assertEqual(lm.resolve(copy), lm.resolve(REAL_CATALOG))


class SetModeRefusalTest(TempDirCase):
    def test_router_is_unavailable_and_file_is_unchanged(self):
        path = self.put(base_doc())
        before = path.read_bytes()
        err = self.assert_code(lm.MODE_UNAVAILABLE, lm.set_mode, path, "router")
        self.assertEqual(err.code, "MODE_UNAVAILABLE")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(os.listdir(self.dir), [NAME])

    def test_router_refusal_on_byte_exact_copy_of_real_catalog(self):
        path = self.dir / NAME
        shutil.copyfile(REAL_CATALOG, path)
        before = path.read_bytes()
        self.assert_code(lm.MODE_UNAVAILABLE, lm.set_mode, path, "router")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(lm.resolve(path).mode, "gates")

    def test_router_refusal_does_not_depend_on_the_file(self):
        cases = (
            ("missing", None),
            ("empty", b""),
            ("not json", b"{ not json"),
            ("router marked available", router_available_doc()),
        )
        for label, data in cases:
            with self.subTest(file=label):
                directory = self.fresh_dir()
                path = directory / NAME
                before = None
                if data is not None:
                    payload = json.dumps(data).encode("utf-8") if isinstance(data, dict) else data
                    path.write_bytes(payload)
                    before = path.read_bytes()
                self.assert_code(lm.MODE_UNAVAILABLE, lm.set_mode, path, "router")
                if before is None:
                    self.assertEqual(os.listdir(directory), [])
                else:
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(os.listdir(directory), [NAME])

    def test_unknown_mode_is_refused_and_file_is_unchanged(self):
        for bad in ("bogus", "", "GATES", "Router", " gates", "gates ", None, 5, ["gates"]):
            with self.subTest(mode=bad):
                path = self.put(base_doc())
                before = path.read_bytes()
                self.assert_code(lm.UNKNOWN_MODE, lm.set_mode, path, bad)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(os.listdir(self.dir), [NAME])

    def test_set_gates_on_invalid_file_is_refused_and_untouched(self):
        path = self.put(b"{ not json")
        before = path.read_bytes()
        self.assert_code(lm.CATALOG_INVALID, lm.set_mode, path, "gates")
        self.assertEqual(path.read_bytes(), before)

    def test_set_gates_on_missing_file_is_unreadable(self):
        self.assert_code(lm.CATALOG_UNREADABLE, lm.set_mode, self.dir / "absent.json", "gates")
        self.assertEqual(os.listdir(self.dir), [])


class SetModeNoOpTest(TempDirCase):
    def test_set_gates_when_gates_does_not_rewrite(self):
        path = self.put(base_doc())
        # a layout the writer would never produce, so any rewrite changes the bytes
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        before_bytes = path.read_bytes()
        os.utime(path, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
        before_mtime = path.stat().st_mtime_ns
        resolved = lm.set_mode(path, "gates")
        self.assertEqual(resolved, lm.ResolvedMode("gates", True, None))
        self.assertEqual(path.read_bytes(), before_bytes)
        self.assertEqual(path.stat().st_mtime_ns, before_mtime)
        self.assertEqual(os.listdir(self.dir), [NAME])


class LoadRejectsTest(TempDirCase):
    def assert_invalid_doc(self, doc, label=""):
        path = self.put(doc)
        with self.subTest(case=label):
            self.assert_code(lm.CATALOG_INVALID, lm.load, path)
            self.assert_code(lm.CATALOG_INVALID, lm.resolve, path)

    def test_wrong_schema(self):
        for value in ("vst.link_mode.v2", "", "VST.LINK_MODE.V1", 5, None):
            doc = base_doc()
            doc["schema"] = value
            self.assert_invalid_doc(doc, f"schema={value!r}")

    def test_extra_top_level_key(self):
        doc = base_doc()
        doc["extra"] = 1
        self.assert_invalid_doc(doc)

    def test_missing_top_level_key(self):
        for key in ("schema", "mode", "modes"):
            doc = base_doc()
            del doc[key]
            self.assert_invalid_doc(doc, f"missing {key}")

    def test_top_level_not_an_object(self):
        for text in ("[]", '"x"', "null", "5", "true"):
            self.assert_invalid_doc(text, text)

    def test_duplicate_json_key(self):
        modes = json.dumps(base_doc()["modes"])
        top = '{"schema": "vst.link_mode.v1", "mode": "gates", "mode": "gates", "modes": ' + modes + "}"
        self.assert_invalid_doc(top, "duplicate top-level key")
        gates = json.dumps(base_doc()["modes"]["gates"])
        router = json.dumps(base_doc()["modes"]["router"])
        nested = ('{"schema": "vst.link_mode.v1", "mode": "gates", "modes": {"gates": ' + gates
                  + ', "router": ' + router + ', "router": ' + router + "}}")
        self.assert_invalid_doc(nested, "duplicate mode name")
        self.assertEqual(lm.load(self.put(json.dumps(base_doc()))).mode, "gates")  # same text without the dup loads

    def test_nan_and_infinity(self):
        text = json.dumps(base_doc())
        for constant in ("NaN", "Infinity", "-Infinity"):
            self.assert_invalid_doc(text.replace('"mode": "gates"', '"mode": ' + constant), f"mode={constant}")
            self.assert_invalid_doc(text.replace('"available": true', '"available": ' + constant, 1),
                                    f"available={constant}")

    def test_non_utf8_bytes(self):
        good = json.dumps(base_doc()).encode("utf-8")
        for label, data in (
            ("lone continuation byte", b"\xff\xfe\x00{"),
            ("latin-1 inside a string", good.replace(b"VST owns", b"VST \xe9owns")),
            ("utf-16 text", json.dumps(base_doc()).encode("utf-16")),
        ):
            path = self.put(data)
            with self.subTest(case=label):
                self.assert_code(lm.CATALOG_INVALID, lm.load, path)

    def test_utf8_bom_is_rejected_with_the_bom_detail(self):
        good = json.dumps(base_doc()).encode("utf-8")
        path = self.put(BOM + good)
        err = self.assert_code(lm.CATALOG_INVALID, lm.load, path)
        self.assertIn("BOM", err.detail)
        self.assert_code(lm.CATALOG_INVALID, lm.resolve, path)
        self.assert_code(lm.CATALOG_INVALID, lm.set_mode, path, "gates")
        self.assertEqual(path.read_bytes(), BOM + good)
        # the same bytes without the BOM load, so the BOM is the only reason
        self.assertEqual(lm.load(self.put(good)).mode, "gates")

    def test_invalid_json_and_empty_file(self):
        for label, data in (
            ("empty", b""),
            ("spaces only", b"   \n"),
            ("truncated", b"{"),
            ("not json", b"not json"),
            ("single quotes", b"{'schema': 1}"),
            ("trailing garbage", json.dumps(base_doc()).encode("utf-8") + b" x"),
            ("two documents", json.dumps(base_doc()).encode("utf-8") * 2),
            ("too deeply nested", b"[" * 200000),
        ):
            path = self.put(data)
            with self.subTest(case=label):
                self.assert_code(lm.CATALOG_INVALID, lm.load, path)

    def test_directory_instead_of_file(self):
        folder = self.dir / "folder.json"
        folder.mkdir()
        self.assert_code(lm.CATALOG_UNREADABLE, lm.load, folder)
        self.assert_code(lm.CATALOG_UNREADABLE, lm.load, self.dir)

    def test_missing_file(self):
        self.assert_code(lm.CATALOG_UNREADABLE, lm.load, self.dir / "absent.json")
        self.assert_code(lm.CATALOG_UNREADABLE, lm.resolve, self.dir / "absent.json")

    def test_modes_table_with_missing_mode(self):
        for name in ("gates", "router"):
            doc = base_doc()
            del doc["modes"][name]
            self.assert_invalid_doc(doc, f"missing {name}")
        doc = base_doc()
        doc["modes"] = {}
        self.assert_invalid_doc(doc, "empty modes table")

    def test_modes_table_with_extra_mode(self):
        doc = base_doc()
        doc["modes"]["extra"] = {"available": True, "description": "x"}
        self.assert_invalid_doc(doc)

    def test_modes_table_with_wrong_case_name(self):
        doc = base_doc()
        doc["modes"]["Router"] = doc["modes"].pop("router")
        self.assert_invalid_doc(doc)

    def test_wrong_types_and_entry_shapes(self):
        def edit(label, func):
            doc = base_doc()
            func(doc)
            self.assert_invalid_doc(doc, label)

        edit("mode is int", lambda d: d.__setitem__("mode", 5))
        edit("mode is null", lambda d: d.__setitem__("mode", None))
        edit("mode is list", lambda d: d.__setitem__("mode", ["gates"]))
        edit("modes is list", lambda d: d.__setitem__("modes", []))
        edit("modes is string", lambda d: d.__setitem__("modes", "gates"))
        edit("gates entry is string", lambda d: d["modes"].__setitem__("gates", "x"))
        edit("router entry is null", lambda d: d["modes"].__setitem__("router", None))
        edit("gates available is string", lambda d: d["modes"]["gates"].__setitem__("available", "true"))
        edit("gates available is int 1", lambda d: d["modes"]["gates"].__setitem__("available", 1))
        edit("gates available is null", lambda d: d["modes"]["gates"].__setitem__("available", None))
        edit("gates description is int", lambda d: d["modes"]["gates"].__setitem__("description", 5))
        edit("gates description is empty", lambda d: d["modes"]["gates"].__setitem__("description", ""))
        edit("gates description is blank", lambda d: d["modes"]["gates"].__setitem__("description", "   "))
        edit("gates has extra key", lambda d: d["modes"]["gates"].__setitem__("x", 1))
        edit("gates missing description", lambda d: d["modes"]["gates"].pop("description"))
        edit("router available is string", lambda d: d["modes"]["router"].__setitem__("available", "false"))
        edit("router available is int 0", lambda d: d["modes"]["router"].__setitem__("available", 0))
        edit("router blocked_reason is int", lambda d: d["modes"]["router"].__setitem__("blocked_reason", 5))
        edit("router blocked_reason empty", lambda d: d["modes"]["router"].__setitem__("blocked_reason", ""))
        edit("router blocked_reason missing", lambda d: d["modes"]["router"].pop("blocked_reason"))
        edit("router requires missing", lambda d: d["modes"]["router"].pop("requires"))
        edit("router requires is string", lambda d: d["modes"]["router"].__setitem__("requires", "AEVE S20-T07"))
        edit("router requires empty", lambda d: d["modes"]["router"].__setitem__("requires", []))
        edit("router requires has int", lambda d: d["modes"]["router"].__setitem__("requires", [1]))
        edit("router requires has blank", lambda d: d["modes"]["router"].__setitem__("requires", ["a", " "]))
        edit("router requires has duplicate", lambda d: d["modes"]["router"].__setitem__("requires", ["a", "a"]))
        edit("router has extra key", lambda d: d["modes"]["router"].__setitem__("x", 1))

    def test_router_marked_available_is_rejected(self):
        path = self.put(router_available_doc())
        self.assert_code(lm.CATALOG_INVALID, lm.load, path)
        self.assert_code(lm.CATALOG_INVALID, lm.resolve, path)
        self.assert_code(lm.CATALOG_INVALID, lm.set_mode, path, "gates")
        # a hand edit that also makes router the current mode is rejected too
        doc = router_available_doc()
        doc["mode"] = "router"
        self.assert_invalid_doc(doc, "router available and current")

    def test_router_with_altered_pinned_values_is_rejected(self):
        def edit(label, func):
            doc = base_doc()
            func(doc["modes"]["router"])
            self.assert_invalid_doc(doc, label)

        edit("blocked_reason changed", lambda r: r.__setitem__("blocked_reason", "SOMETHING_ELSE"))
        edit("blocked_reason lower case", lambda r: r.__setitem__("blocked_reason", r["blocked_reason"].lower()))
        edit("blocked_reason with suffix", lambda r: r.__setitem__("blocked_reason", r["blocked_reason"] + "_"))
        edit("requires one item", lambda r: r.__setitem__("requires", ["AEVE S20-T07"]))
        edit("requires reversed", lambda r: r.__setitem__("requires", ["AEVE S20-T08", "AEVE S20-T07"]))
        edit("requires extra item", lambda r: r.__setitem__("requires", r["requires"] + ["AEVE S20-T09"]))
        edit("requires item changed", lambda r: r.__setitem__("requires", ["AEVE S20-T07", "AEVE S20-T99"]))

    def test_gates_unavailable_is_rejected(self):
        doc = base_doc()
        doc["modes"]["gates"] = {
            "available": False,
            "description": "gates switched off",
            "blocked_reason": "SOME_REASON",
            "requires": ["something"],
        }
        self.assert_invalid_doc(doc, "gates unavailable, gates current")
        doc["mode"] = "router"
        self.assert_invalid_doc(doc, "gates unavailable, router current")

    def test_current_mode_router_while_router_unavailable(self):
        doc = base_doc()
        doc["mode"] = "router"
        self.assert_invalid_doc(doc)

    def test_current_mode_unknown(self):
        for value in ("bogus", "", "GATES"):
            doc = base_doc()
            doc["mode"] = value
            self.assert_invalid_doc(doc, f"mode={value!r}")

    def test_lone_surrogate_is_rejected(self):
        lone = "bad \ud800 text"

        def edit(label, func):
            doc = base_doc()
            func(doc)
            path = self.put(doc)  # json.dumps escapes the surrogate, so the file itself is valid ASCII JSON
            with self.subTest(case=label):
                self.assertIn(b"\\ud800", path.read_bytes())
                self.assert_code(lm.CATALOG_INVALID, lm.load, path)
                self.assert_code(lm.CATALOG_INVALID, lm.set_mode, path, "gates")

        edit("gates description", lambda d: d["modes"]["gates"].__setitem__("description", lone))
        edit("router description", lambda d: d["modes"]["router"].__setitem__("description", lone))
        edit("router blocked_reason", lambda d: d["modes"]["router"].__setitem__("blocked_reason", lone))
        edit("router requires item", lambda d: d["modes"]["router"].__setitem__("requires", ["AEVE S20-T07", lone]))
        edit("current mode", lambda d: d.__setitem__("mode", "\ud800"))

    def test_error_detail_does_not_echo_file_content(self):
        secret = "SECRET-MARKER-9f3a"
        doc = base_doc()
        doc["schema"] = secret
        err = self.assert_code(lm.CATALOG_INVALID, lm.load, self.put(doc))
        self.assertNotIn(secret, str(err))
        self.assertNotIn(secret, err.detail)

    def test_valid_catalog_still_loads_with_pinned_router(self):
        # guards against a loader that rejects everything
        path = self.put(base_doc())
        self.assertEqual(lm.load(path).mode, "gates")
        self.assertEqual(lm.load(path).entry("router").requires, ("AEVE S20-T07", "AEVE S20-T08"))
        self.assertEqual(lm.load(path).entry("router").blocked_reason,
                         "ROUTER_REQUIRES_AEVE_TASK_PACKET_AND_HANDOFF_VERIFIER")


class CliTest(TempDirCase):
    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = lm.main(argv)
        self.assertEqual(err.getvalue(), "")
        text = out.getvalue()
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(text.count("\n"), 1, "output must be exactly one line")
        self.assertTrue(text.isascii(), "output must be ASCII only")
        return code, json.loads(text)

    def test_get_exit_0_and_one_json_line(self):
        before = REAL_CATALOG.read_bytes()
        code, payload = self.run_main(["get"])
        self.assertEqual(code, 0)
        self.assertEqual(payload, {"ok": True, "mode": "gates", "available": True, "reason": None})
        self.assertEqual(REAL_CATALOG.read_bytes(), before)

    def test_get_failure_exit_1(self):
        with mock.patch.object(lm, "resolve", side_effect=lm.LinkModeError(lm.CATALOG_INVALID, "boom")):
            code, payload = self.run_main(["get"])
        self.assertEqual(code, 1)
        self.assertEqual(payload, {"ok": False, "code": "CATALOG_INVALID", "detail": "boom"})

    def test_get_honours_a_patched_default_path(self):
        broken = self.put(b"{ not json")
        with mock.patch.object(lm, "DEFAULT_PATH", broken):
            code, payload = self.run_main(["get"])
        self.assertEqual(code, 1)
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["code"], "CATALOG_INVALID")
        with mock.patch.object(lm, "DEFAULT_PATH", self.dir / "absent.json"):
            code, payload = self.run_main(["get"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["code"], "CATALOG_UNREADABLE")
        good = self.put(base_doc(), "good.json")
        with mock.patch.object(lm, "DEFAULT_PATH", good):
            code, payload = self.run_main(["get"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["mode"], "gates")

    def test_set_honours_a_patched_default_path(self):
        with mock.patch.object(lm, "DEFAULT_PATH", self.dir / "absent.json"):
            code, payload = self.run_main(["set", "gates"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["code"], "CATALOG_UNREADABLE")

    def test_set_router_exit_1_and_file_unchanged(self):
        path = self.put(base_doc())
        before = path.read_bytes()
        with mock.patch.object(lm, "DEFAULT_PATH", path):
            code, payload = self.run_main(["set", "router"])
        self.assertEqual(code, 1)
        self.assertIs(payload["ok"], False)
        self.assertEqual(payload["code"], "MODE_UNAVAILABLE")
        self.assertEqual(path.read_bytes(), before)

    def test_set_router_exit_1_even_when_the_file_is_broken(self):
        with mock.patch.object(lm, "DEFAULT_PATH", self.dir / "absent.json"):
            code, payload = self.run_main(["set", "router"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["code"], "MODE_UNAVAILABLE")

    def test_set_unknown_mode_exit_1(self):
        path = self.put(base_doc())
        with mock.patch.object(lm, "DEFAULT_PATH", path):
            code, payload = self.run_main(["set", "bogus"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["code"], "UNKNOWN_MODE")
        self.assertIs(payload["ok"], False)

    def test_set_gates_exit_0(self):
        path = self.put(base_doc())
        before = path.read_bytes()
        with mock.patch.object(lm, "DEFAULT_PATH", path):
            code, payload = self.run_main(["set", "gates"])
        self.assertEqual(code, 0)
        self.assertEqual(payload, {"ok": True, "mode": "gates", "available": True, "reason": None})
        self.assertEqual(path.read_bytes(), before)

    def test_set_on_broken_file_exit_1(self):
        path = self.put(b"")
        with mock.patch.object(lm, "DEFAULT_PATH", path):
            code, payload = self.run_main(["set", "gates"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["code"], "CATALOG_INVALID")
        self.assertEqual(path.read_bytes(), b"")

    def test_unexpected_exception_exit_3_internal(self):
        secret = "SECRET-INTERNAL-77"
        with mock.patch.object(lm, "resolve", side_effect=RuntimeError(secret)):
            code, payload = self.run_main(["get"])
        self.assertEqual(code, 3)
        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["code"], "INTERNAL")
        self.assertNotIn(secret, json.dumps(payload))
        with mock.patch.object(lm, "set_mode", side_effect=RuntimeError(secret)):
            code, payload = self.run_main(["set", "gates"])
        self.assertEqual(code, 3)
        self.assertEqual(payload["code"], "INTERNAL")
        self.assertNotIn(secret, json.dumps(payload))

    def test_output_is_ascii_even_for_non_ascii_detail(self):
        detail = "café ☃ Ж"
        out = io.StringIO()
        with mock.patch.object(lm, "resolve", side_effect=lm.LinkModeError(lm.CATALOG_INVALID, detail)):
            with contextlib.redirect_stdout(out):
                code = lm.main(["get"])
        raw = out.getvalue()
        self.assertEqual(code, 1)
        self.assertTrue(raw.isascii())
        self.assertEqual(raw.count("\n"), 1)
        self.assertEqual(json.loads(raw)["detail"], detail)

    def test_usage_errors_exit_2(self):
        for argv in ([], ["get", "x"], ["set"], ["set", "a", "b"], ["bogus"], ["GET"], ["set", "router", "x"]):
            with self.subTest(argv=argv):
                code, payload = self.run_main(argv)
                self.assertEqual(code, 2)
                self.assertIs(payload["ok"], False)
                self.assertEqual(payload["code"], "USAGE")
                self.assertTrue(payload["detail"])


class AtomicWriteTest(TempDirCase):
    """`_write_atomic(path, data)` and `_replace_with_retry(source, target)` called directly."""

    def target(self, old: bytes | None = b"old content\n") -> Path:
        directory = self.fresh_dir()
        path = directory / NAME
        if old is not None:
            path.write_bytes(old)
        return path

    def test_new_content_replaces_old_exactly_and_leaves_no_temp(self):
        path = self.target()
        data = b'{\n  "a": 1\n}\n'
        lm._write_atomic(path, data)
        self.assertEqual(path.read_bytes(), data)
        self.assertEqual(os.listdir(path.parent), [NAME])

    def test_line_endings_stay_lf_and_bytes_are_not_translated(self):
        path = self.target()
        data = "line1\nline2 é\n".encode("utf-8")
        lm._write_atomic(path, data)
        written = path.read_bytes()
        self.assertEqual(written, data)
        self.assertNotIn(b"\r", written)

    def test_creates_the_file_when_it_does_not_exist(self):
        path = self.target(old=None)
        lm._write_atomic(path, b"fresh\n")
        self.assertEqual(path.read_bytes(), b"fresh\n")
        self.assertEqual(os.listdir(path.parent), [NAME])

    def test_empty_data_is_written_as_an_empty_file(self):
        path = self.target()
        lm._write_atomic(path, b"")
        self.assertEqual(path.read_bytes(), b"")

    def test_brief_permission_error_is_retried_then_new_content_lands(self):
        for winerror in (5, 32):
            with self.subTest(winerror=winerror):
                path = self.target()
                real_replace = os.replace
                calls = []

                def flaky(source, target):
                    calls.append(1)
                    if len(calls) <= 2:
                        raise make_permission_error(winerror)
                    return real_replace(source, target)

                with mock.patch.object(lm.os, "replace", side_effect=flaky), mock.patch.object(lm.time, "sleep"):
                    lm._write_atomic(path, b"new content\n")
                self.assertEqual(len(calls), 3)
                self.assertEqual(path.read_bytes(), b"new content\n")
                self.assertEqual(os.listdir(path.parent), [NAME])

    def test_replace_with_retry_moves_the_source_after_brief_errors(self):
        for winerror in (5, 32):
            with self.subTest(winerror=winerror):
                directory = self.fresh_dir()
                source = directory / "source.tmp"
                target = directory / NAME
                source.write_bytes(b"payload")
                target.write_bytes(b"old")
                real_replace = os.replace
                calls = []

                def flaky(src, dst):
                    calls.append(1)
                    if len(calls) <= 2:
                        raise make_permission_error(winerror)
                    return real_replace(src, dst)

                with mock.patch.object(lm.os, "replace", side_effect=flaky), mock.patch.object(lm.time, "sleep"):
                    lm._replace_with_retry(str(source), target)
                self.assertEqual(target.read_bytes(), b"payload")
                self.assertFalse(source.exists())

    def test_permanent_permission_error_keeps_old_file_and_leaves_no_temp(self):
        for winerror in (5, 32):
            with self.subTest(winerror=winerror):
                path = self.target()
                before = path.read_bytes()
                with mock.patch.object(lm.os, "replace", side_effect=make_permission_error(winerror)) as fake, \
                        mock.patch.object(lm.time, "sleep"):
                    with self.assertRaises(PermissionError):
                        lm._write_atomic(path, b"new content\n")
                self.assertGreaterEqual(fake.call_count, 2, "a brief error must be retried at least once")
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(os.listdir(path.parent), [NAME], "no temp file may stay behind")

    def test_other_os_error_is_not_retried_and_leaves_no_temp(self):
        for error in (make_permission_error(1), OSError(28, "no space left")):
            with self.subTest(error=repr(error)):
                path = self.target()
                before = path.read_bytes()
                with mock.patch.object(lm.os, "replace", side_effect=error) as fake, \
                        mock.patch.object(lm.time, "sleep"):
                    with self.assertRaises(OSError):
                        lm._write_atomic(path, b"new content\n")
                self.assertEqual(fake.call_count, 1)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(os.listdir(path.parent), [NAME])

    def test_failure_while_writing_temp_file_leaves_no_temp(self):
        path = self.target()
        before = path.read_bytes()
        with mock.patch.object(lm.os, "fsync", side_effect=OSError(5, "io error")):
            with self.assertRaises(OSError):
                lm._write_atomic(path, b"new content\n")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(os.listdir(path.parent), [NAME])

    def test_non_bytes_data_is_refused_and_leaves_no_temp(self):
        path = self.target()
        before = path.read_bytes()
        with self.assertRaises(TypeError):
            lm._write_atomic(path, "text, not bytes")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(os.listdir(path.parent), [NAME])


class WriteFailedMappingTest(TempDirCase):
    """`set_mode` turns a failed write into WRITE_FAILED.

    That branch is unreachable with the shipped code, so the code constant ROUTER_CAPABILITY_READY (the documented
    future switch) is flipped with `mock.patch` and a catalog that declares router available is used.
    """

    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.object(lm, "ROUTER_CAPABILITY_READY", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def switch_fixture(self) -> Path:
        directory = self.fresh_dir()
        path = directory / NAME
        path.write_bytes(json.dumps(router_available_doc(), indent=2).encode("utf-8"))
        return path

    def test_switch_writes_the_new_document(self):
        path = self.switch_fixture()
        resolved = lm.set_mode(path, "router")
        self.assertEqual(resolved, lm.ResolvedMode("router", True, None))
        data = path.read_bytes()
        expected = router_available_doc()
        expected["mode"] = "router"
        self.assertEqual(json.loads(data.decode("utf-8")), expected)
        self.assertTrue(data.endswith(b"\n"))
        self.assertNotIn(b"\r", data)
        self.assertEqual(os.listdir(path.parent), [NAME])

    def test_permanent_replace_failure_is_write_failed_and_keeps_old_file(self):
        path = self.switch_fixture()
        before = path.read_bytes()
        with mock.patch.object(lm.os, "replace", side_effect=make_permission_error(5)), \
                mock.patch.object(lm.time, "sleep"):
            self.assert_code(lm.WRITE_FAILED, lm.set_mode, path, "router")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(os.listdir(path.parent), [NAME])
        self.assertEqual(lm.load(path).mode, "gates")

    def test_brief_replace_failure_still_ends_with_the_new_content(self):
        path = self.switch_fixture()
        real_replace = os.replace
        calls = []

        def flaky(source, target):
            calls.append(1)
            if len(calls) <= 2:
                raise make_permission_error(5)
            return real_replace(source, target)

        with mock.patch.object(lm.os, "replace", side_effect=flaky), mock.patch.object(lm.time, "sleep"):
            resolved = lm.set_mode(path, "router")
        self.assertEqual(resolved.mode, "router")
        self.assertEqual(lm.load(path).mode, "router")
        self.assertEqual(os.listdir(path.parent), [NAME])

    def test_value_error_from_the_writer_is_write_failed(self):
        path = self.switch_fixture()
        before = path.read_bytes()
        with mock.patch.object(lm, "_write_atomic", side_effect=ValueError("embedded null")):
            self.assert_code(lm.WRITE_FAILED, lm.set_mode, path, "router")
        self.assertEqual(path.read_bytes(), before)

    def test_os_error_from_the_writer_is_write_failed(self):
        path = self.switch_fixture()
        before = path.read_bytes()
        with mock.patch.object(lm, "_write_atomic", side_effect=OSError(28, "no space left")):
            err = self.assert_code(lm.WRITE_FAILED, lm.set_mode, path, "router")
        self.assertNotIn("no space left", err.detail)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
