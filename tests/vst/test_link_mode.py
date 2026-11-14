"""Link mode switch (`tools/vst/link_mode.py`, catalog `catalog/link_mode.json`).

Written from the acceptance criteria of docs/sdlc/LINK2_ROUTER_DESIGN.md (AC-33 to AC-36) and of LINK_MODE.md.
State after sprint LINK-2 task T6: the code constant `ROUTER_CAPABILITY_READY` is True, the shipped catalog marks
`router` available and keeps `mode` at `gates`.

1. the default catalog loads and resolves to mode `gates`, available true; `router` is available (AC-36);
2. `set_mode(path, "router")` succeeds on a catalog copy, rewrites the file with `mode` router and `get` then reports
   router available (AC-33); `set_mode(path, "gates")` switches back; an unknown mode raises UNKNOWN_MODE;
3. while the code constant is False (patched here) `set_mode(..., "router")` raises MODE_UNAVAILABLE with detail
   ROUTER_CAPABILITY_NOT_READY before the file is read, and the file bytes do not change;
4. `load` rejects a bad file with CATALOG_INVALID (content problems) or CATALOG_UNREADABLE (cannot be read),
   including: READY True with a blocked router entry (AC-34, a half-reverted flip), READY False with an available
   router (AC-35), an unavailable `gates`, lone surrogates and a UTF-8 BOM;
5. CLI `main`: exit 0 ok, 1 refusal, 2 usage, 3 internal error; the output is exactly one ASCII JSON line;
6. the write is atomic (`_write_atomic`, `_replace_with_retry`): a brief PermissionError (winerror 5 or 32) is
   retried, a permanent failure keeps the old bytes and leaves no temp file;
7. `set_mode` turns a failed write into WRITE_FAILED and keeps the old file.

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


# The router entry of the catalog before LINK2-T6 (written out here, not read from the code under test).
OLD_BLOCKED_ROUTER = {
    "available": False,
    "description": "router mode is declared but blocked",
    "blocked_reason": "ROUTER_REQUIRES_AEVE_TASK_PACKET_AND_HANDOFF_VERIFIER",
    "requires": ["AEVE S20-T07", "AEVE S20-T08"],
}


def router_blocked_doc() -> dict:
    """A catalog whose router entry is still blocked (the state before the flip, or a half-reverted flip)."""
    doc = base_doc()
    doc["modes"]["router"] = dict(OLD_BLOCKED_ROUTER, requires=list(OLD_BLOCKED_ROUTER["requires"]))
    return doc


def router_available_doc() -> dict:
    doc = base_doc()
    doc["modes"]["router"] = {"available": True, "description": "an available router"}
    return doc


def not_ready():
    """Patch the code constant to False (the state before LINK2-T6 and the state of a reverted flip)."""
    return mock.patch.object(lm, "ROUTER_CAPABILITY_READY", False)


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
        self.assertTrue(config.entry("router").available)

    def test_code_constant_is_flipped_and_the_old_blocked_constants_are_gone(self):
        self.assertIs(lm.ROUTER_CAPABILITY_READY, True)
        self.assertFalse(hasattr(lm, "ROUTER_BLOCKED_REASON"))
        self.assertFalse(hasattr(lm, "ROUTER_REQUIRES"))

    def test_default_mode_stays_gates_although_router_is_available(self):  # AC-36
        raw = json.loads(REAL_CATALOG.read_bytes().decode("utf-8"))
        self.assertEqual(raw["mode"], "gates")
        self.assertIs(raw["modes"]["router"]["available"], True)
        self.assertEqual(set(raw["modes"]["router"]), {"available", "description"})
        self.assertEqual(lm.resolve(REAL_CATALOG).mode, "gates")

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
    def test_router_refused_while_the_capability_is_not_ready_and_file_is_unchanged(self):
        path = self.put(base_doc())
        before = path.read_bytes()
        with not_ready():
            err = self.assert_code(lm.MODE_UNAVAILABLE, lm.set_mode, path, "router")
        self.assertEqual(err.detail, "ROUTER_CAPABILITY_NOT_READY")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(os.listdir(self.dir), [NAME])

    def test_not_ready_refusal_does_not_depend_on_the_file(self):
        cases = (
            ("missing", None),
            ("empty", b""),
            ("not json", b"{ not json"),
            ("router marked available", router_available_doc()),
            ("router blocked", router_blocked_doc()),
        )
        for label, data in cases:
            with self.subTest(file=label), not_ready():
                directory = self.fresh_dir()
                path = directory / NAME
                before = None
                if data is not None:
                    payload = json.dumps(data).encode("utf-8") if isinstance(data, dict) else data
                    path.write_bytes(payload)
                    before = path.read_bytes()
                err = self.assert_code(lm.MODE_UNAVAILABLE, lm.set_mode, path, "router")
                self.assertEqual(err.detail, "ROUTER_CAPABILITY_NOT_READY")
                if before is None:
                    self.assertEqual(os.listdir(directory), [])
                else:
                    self.assertEqual(path.read_bytes(), before)
                    self.assertEqual(os.listdir(directory), [NAME])

    def test_set_router_succeeds_on_the_real_catalog_copy(self):  # AC-33
        path = self.dir / NAME
        shutil.copyfile(REAL_CATALOG, path)
        resolved = lm.set_mode(path, "router")
        self.assertEqual(resolved, lm.ResolvedMode("router", True, None))
        self.assertEqual(lm.resolve(path), lm.ResolvedMode("router", True, None))
        written = json.loads(path.read_bytes().decode("utf-8"))
        expected = json.loads(REAL_CATALOG.read_bytes().decode("utf-8"))
        expected["mode"] = "router"  # only the current mode differs from the shipped catalog
        self.assertEqual(written, expected)
        self.assertEqual(os.listdir(self.dir), [NAME])

    def test_set_router_then_gates_round_trips_to_the_shipped_content(self):
        path = self.dir / NAME
        shutil.copyfile(REAL_CATALOG, path)
        lm.set_mode(path, "router")
        self.assertEqual(lm.set_mode(path, "gates"), lm.ResolvedMode("gates", True, None))
        self.assertEqual(json.loads(path.read_bytes().decode("utf-8")),
                         json.loads(REAL_CATALOG.read_bytes().decode("utf-8")))

    def test_set_router_when_router_is_already_current_does_not_rewrite(self):
        doc = base_doc()
        doc["mode"] = "router"
        path = self.put(doc)
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))  # a layout the writer would never produce
        before = path.read_bytes()
        self.assertEqual(lm.set_mode(path, "router"), lm.ResolvedMode("router", True, None))
        self.assertEqual(path.read_bytes(), before)

    def test_set_router_on_a_blocked_router_entry_is_refused_as_invalid_and_unchanged(self):
        path = self.put(router_blocked_doc())  # READY True + blocked entry: a half-reverted flip fails closed
        before = path.read_bytes()
        self.assert_code(lm.CATALOG_INVALID, lm.set_mode, path, "router")
        self.assertEqual(path.read_bytes(), before)

    def test_set_router_on_missing_or_broken_file_is_refused_by_the_file_rules(self):
        self.assert_code(lm.CATALOG_UNREADABLE, lm.set_mode, self.dir / "absent.json", "router")
        broken = self.put(b"{ not json")
        self.assert_code(lm.CATALOG_INVALID, lm.set_mode, broken, "router")
        self.assertEqual(broken.read_bytes(), b"{ not json")

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
        edit("router available is string", lambda d: d["modes"]["router"].__setitem__("available", "true"))
        edit("router available is int 1", lambda d: d["modes"]["router"].__setitem__("available", 1))
        edit("router available is null", lambda d: d["modes"]["router"].__setitem__("available", None))
        edit("router description is int", lambda d: d["modes"]["router"].__setitem__("description", 5))
        edit("router description is empty", lambda d: d["modes"]["router"].__setitem__("description", ""))
        edit("router description is blank", lambda d: d["modes"]["router"].__setitem__("description", "  "))
        edit("router description missing", lambda d: d["modes"]["router"].pop("description"))
        edit("router has extra key", lambda d: d["modes"]["router"].__setitem__("x", 1))
        edit("available router keeps blocked_reason", lambda d: d["modes"]["router"].__setitem__("blocked_reason", "X"))
        edit("available router keeps requires", lambda d: d["modes"]["router"].__setitem__("requires", ["a"]))

    def test_blocked_entry_shape_rules_still_apply_when_the_capability_is_not_ready(self):
        def edit(label, func):
            doc = router_blocked_doc()
            func(doc["modes"]["router"])
            path = self.put(doc)
            with self.subTest(case=label), not_ready():
                self.assert_code(lm.CATALOG_INVALID, lm.load, path)

        with not_ready():  # the unedited blocked entry is the valid pre-flip state
            self.assertFalse(lm.load(self.put(router_blocked_doc())).entry("router").available)
        edit("blocked_reason is int", lambda r: r.__setitem__("blocked_reason", 5))
        edit("blocked_reason empty", lambda r: r.__setitem__("blocked_reason", ""))
        edit("blocked_reason missing", lambda r: r.pop("blocked_reason"))
        edit("requires missing", lambda r: r.pop("requires"))
        edit("requires is string", lambda r: r.__setitem__("requires", "AEVE S20-T07"))
        edit("requires empty", lambda r: r.__setitem__("requires", []))
        edit("requires has int", lambda r: r.__setitem__("requires", [1]))
        edit("requires has blank", lambda r: r.__setitem__("requires", ["a", " "]))
        edit("requires has duplicate", lambda r: r.__setitem__("requires", ["a", "a"]))
        edit("extra key", lambda r: r.__setitem__("x", 1))

    def test_router_available_while_the_capability_is_not_ready_is_rejected(self):  # AC-35
        path = self.put(router_available_doc())
        with not_ready():
            self.assert_code(lm.CATALOG_INVALID, lm.load, path)
            self.assert_code(lm.CATALOG_INVALID, lm.resolve, path)
            self.assert_code(lm.CATALOG_INVALID, lm.set_mode, path, "gates")
            # a hand edit that also makes router the current mode is rejected too
            doc = router_available_doc()
            doc["mode"] = "router"
            self.assert_code(lm.CATALOG_INVALID, lm.load, self.put(doc, "current_router.json"))
        # the same bytes load once the capability is ready
        self.assertEqual(lm.load(path).mode, "gates")

    def test_blocked_router_while_the_capability_is_ready_is_rejected(self):  # AC-34
        path = self.put(router_blocked_doc())
        self.assert_code(lm.CATALOG_INVALID, lm.load, path)
        self.assert_code(lm.CATALOG_INVALID, lm.resolve, path)
        self.assert_code(lm.CATALOG_INVALID, lm.set_mode, path, "gates")
        err = self.assert_code(lm.CATALOG_INVALID, lm.load, path)
        self.assertIn("router", err.detail)
        # a blocked router with other values is rejected too: the flip is all or nothing
        for label, change in (
            ("other reason", {"blocked_reason": "SOMETHING_ELSE"}),
            ("other requires", {"requires": ["AEVE S20-T99"]}),
        ):
            doc = router_blocked_doc()
            doc["modes"]["router"].update(change)
            self.assert_invalid_doc(doc, label)
        # and while router is the current mode
        doc = router_blocked_doc()
        doc["mode"] = "router"
        self.assert_invalid_doc(doc, "router blocked and current")

    def test_blocked_router_with_any_valid_values_loads_while_the_capability_is_not_ready(self):
        # D3: the pinned-values rule is dropped; only the entry shape and the READY rule decide
        doc = router_blocked_doc()
        doc["modes"]["router"].update(blocked_reason="ANY_REASON", requires=["x", "y", "z"])
        path = self.put(doc)
        with not_ready():
            entry = lm.load(path).entry("router")
        self.assertFalse(entry.available)
        self.assertEqual((entry.blocked_reason, entry.requires), ("ANY_REASON", ("x", "y", "z")))

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
        doc = router_blocked_doc()
        doc["mode"] = "router"
        with not_ready():  # the only state in which a blocked router entry is a valid entry
            self.assert_code(lm.CATALOG_INVALID, lm.load, self.put(doc))

    def test_current_mode_router_is_valid_now_that_router_is_available(self):
        doc = base_doc()
        doc["mode"] = "router"
        resolved = lm.resolve(self.put(doc))
        self.assertEqual(resolved, lm.ResolvedMode("router", True, None))

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
        edit("current mode", lambda d: d.__setitem__("mode", "\ud800"))

    def test_error_detail_does_not_echo_file_content(self):
        secret = "SECRET-MARKER-9f3a"
        doc = base_doc()
        doc["schema"] = secret
        err = self.assert_code(lm.CATALOG_INVALID, lm.load, self.put(doc))
        self.assertNotIn(secret, str(err))
        self.assertNotIn(secret, err.detail)

    def test_valid_catalog_still_loads_with_available_router(self):
        # guards against a loader that rejects everything
        path = self.put(base_doc())
        self.assertEqual(lm.load(path).mode, "gates")
        entry = lm.load(path).entry("router")
        self.assertTrue(entry.available)
        self.assertIsNone(entry.blocked_reason)
        self.assertEqual(entry.requires, ())


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

    def test_set_router_exit_0_and_get_reports_router(self):  # AC-33
        path = self.put(base_doc())
        with mock.patch.object(lm, "DEFAULT_PATH", path):
            code, payload = self.run_main(["set", "router"])
            self.assertEqual(code, 0)
            self.assertEqual(payload, {"ok": True, "mode": "router", "available": True, "reason": None})
            code, payload = self.run_main(["get"])
        self.assertEqual(code, 0)
        self.assertEqual(payload, {"ok": True, "mode": "router", "available": True, "reason": None})
        self.assertEqual(json.loads(path.read_bytes().decode("utf-8"))["mode"], "router")

    def test_set_router_exit_1_and_file_unchanged_while_not_ready(self):
        path = self.put(base_doc())
        before = path.read_bytes()
        with mock.patch.object(lm, "DEFAULT_PATH", path), not_ready():
            code, payload = self.run_main(["set", "router"])
        self.assertEqual(code, 1)
        self.assertEqual(payload, {"ok": False, "code": "MODE_UNAVAILABLE", "detail": "ROUTER_CAPABILITY_NOT_READY"})
        self.assertEqual(path.read_bytes(), before)

    def test_set_router_exit_1_even_when_the_file_is_broken_while_not_ready(self):
        with mock.patch.object(lm, "DEFAULT_PATH", self.dir / "absent.json"), not_ready():
            code, payload = self.run_main(["set", "router"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["code"], "MODE_UNAVAILABLE")

    def test_set_router_on_missing_file_is_catalog_unreadable_when_ready(self):
        with mock.patch.object(lm, "DEFAULT_PATH", self.dir / "absent.json"):
            code, payload = self.run_main(["set", "router"])
        self.assertEqual(code, 1)
        self.assertEqual(payload["code"], "CATALOG_UNREADABLE")

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

    def test_public_replace_with_retry_moves_a_file_and_retries_brief_errors(self):
        directory = self.fresh_dir()
        source, target = directory / "s.tmp", directory / NAME
        source.write_bytes(b"payload")
        real_replace = os.replace
        calls = []

        def flaky(src, dst):
            calls.append(1)
            if len(calls) == 1:
                raise make_permission_error(32)
            return real_replace(src, dst)

        with mock.patch.object(lm.os, "replace", side_effect=flaky), mock.patch.object(lm.time, "sleep"):
            lm.replace_with_retry(str(source), target)
        self.assertEqual((target.read_bytes(), len(calls)), (b"payload", 2))

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
    """`set_mode` turns a failed write into WRITE_FAILED; the write branch is reached by `set router` (the shipped
    catalog is on `gates`, so switching to router is a real write)."""

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
