"""S2-1 acceptance coverage for PM review source-fidelity remediation.

Only the functional-test-reviewer owns and executes these focused tests. They
exercise exact attachment/base/HEAD binding and ensure sanitized reports do not
publish source-line values or per-line fingerprints.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
VERIFIER = REPO / "tools" / "verify_s2_review_source_fidelity.py"
BASE = "6117ba24b08a260b42402db6da0bf767864e1c04"
HEAD = "2befed5515455c4dbf022cad68e839a8a2ce799c"
ATTACHMENT = REPO / "docs/sdlc/.pm-review/s2-review-input-833efc361a34266767e331ebf6a2724cecba3e03512e4443ddf6cd661d93311b.txt"
ATTACHMENT_SHA256 = "833efc361a34266767e331ebf6a2724cecba3e03512e4443ddf6cd661d93311b"
SYNTHETIC_VALUE = "synthetic-only-not-a-credential"


def invoke(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class ExactPacketTests(unittest.TestCase):
    def test_all_41_redactions_map_to_exact_blobs_without_line_fingerprints(self) -> None:
        result = invoke([
            "--repo", str(REPO), "--base", BASE, "--head", HEAD,
            "--attachment", str(ATTACHMENT), "--attachment-size", "5766789",
            "--attachment-sha256", ATTACHMENT_SHA256,
            "--expect-markers", "41", "--expect-files", "15",
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["redaction_markers"], 41)
        self.assertEqual(report["redacted_source_files"], 15)
        self.assertEqual(report["line_identity_pass_count"], 41)
        self.assertEqual(report["line_identity_fail_count"], 0)
        self.assertFalse(report["source_lines_or_masked_values_emitted"])
        self.assertEqual(report["security_invariants"], "INCONCLUSIVE_PENDING_INDEPENDENT_REVIEW")
        self.assertTrue(all(record["source_identity"] == "PASS" for record in report["records"]))
        self.assertTrue(all(record.get("head_blob") or record.get("base_blob") for record in report["records"]))
        self.assertNotIn("line_sha256", result.stdout)
        self.assertNotIn("head_line_sha256", result.stdout)
        self.assertNotIn("base_line_sha256", result.stdout)

    def test_attachment_digest_mismatch_fails_closed_without_echoing_source(self) -> None:
        result = invoke([
            "--repo", str(REPO), "--base", BASE, "--head", HEAD,
            "--attachment", str(ATTACHMENT), "--attachment-size", "5766789",
            "--attachment-sha256", "0" * 64,
            "--expect-markers", "41", "--expect-files", "15",
        ])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("attachment SHA-256", result.stderr)
        self.assertNotIn("const token", result.stdout + result.stderr)


class FixtureGit(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="s2-source-fidelity-")
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "user.email", "reviewer@example.invalid")
        self.git("config", "user.name", "S2 Test Fixture")
        self.source = self.repo / "sample.py"
        self.source.write_bytes(
            b"start\r\n```\r\ncredential_token = \"old-value\"\r\nend\r\n"
        )
        self.git("add", "sample.py")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").stdout.decode("ascii").strip()
        self.source.write_bytes(
            f"start\r\n```\r\ncredential_token = \"{SYNTHETIC_VALUE}\"\r\nend\r\n".encode()
        )
        self.git("add", "sample.py")
        self.git("commit", "-qm", "head")
        self.head = self.git("rev-parse", "HEAD").stdout.decode("ascii").strip()
        raw = self.git("diff", "--no-color", "--no-ext-diff", "--unified=3", f"{self.base}...{self.head}", "--", ".").stdout
        self.assertIn(b"```", raw)  # An embedded fence is diff context, not packet termination.
        self.assertEqual(raw.count(SYNTHETIC_VALUE.encode()), 1)
        redacted = raw.replace(SYNTHETIC_VALUE.encode(), b"[REDACTED]")
        self.attachment = self.repo / "packet.txt"
        self.attachment.write_bytes(b"Review input\n```diff\n" + redacted + b"\n```\nend\n")
        self.args = [
            "--repo", str(self.repo), "--base", self.base, "--head", self.head,
            "--attachment", str(self.attachment), "--attachment-size", str(self.attachment.stat().st_size),
            "--attachment-sha256", hashlib.sha256(self.attachment.read_bytes()).hexdigest(),
            "--expect-markers", "1", "--expect-files", "1",
        ]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_crlf_and_embedded_markdown_fence_map_to_head_blob(self) -> None:
        result = invoke(self.args)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["redaction_markers"], 1)
        self.assertEqual(report["records"][0]["file"], "sample.py")
        self.assertEqual(report["records"][0]["diff_side"], "added")
        self.assertGreaterEqual(report["records"][0]["head_line"], 1)
        self.assertRegex(report["records"][0]["head_blob"], r"^[0-9a-f]{40}$")
        self.assertNotIn(SYNTHETIC_VALUE, result.stdout)
        self.assertNotIn("credential_token", result.stdout)
        self.assertNotIn("line_sha256", result.stdout)

    def test_attachment_size_mismatch_fails_closed(self) -> None:
        args = self.args.copy()
        size_index = args.index("--attachment-size") + 1
        args[size_index] = str(int(args[size_index]) + 1)
        result = invoke(args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("attachment byte length", result.stderr)
        self.assertNotIn(SYNTHETIC_VALUE, result.stdout + result.stderr)

    def test_unredacted_mismatch_fails_closed(self) -> None:
        packet = self.attachment.read_bytes().replace(b"\n ```\r\n", b"\n ~~~\r\n", 1)
        self.assertNotEqual(packet, self.attachment.read_bytes())
        self.attachment.write_bytes(packet)
        args = self.args.copy()
        digest_index = args.index("--attachment-sha256") + 1
        args[digest_index] = hashlib.sha256(packet).hexdigest()
        size_index = args.index("--attachment-size") + 1
        args[size_index] = str(len(packet))
        result = invoke(args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diff structure/source mismatch", result.stderr)
        self.assertNotIn(SYNTHETIC_VALUE, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
