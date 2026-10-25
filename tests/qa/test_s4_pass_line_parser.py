"""Regression coverage for the trusted pytest PASS-line parser."""

from tools.vst.contracts import _parse_pass_lines


def test_s4_pass_line_parser_accepts_one_quiet_dot_and_rejects_lookalikes():
    valid_plain = "tests/example.py::test_plain"
    valid_quiet = "tests/example.py::test_quiet"
    stdout = "\n".join((
        f"PASS {valid_plain}",
        f".PASS {valid_quiet}",
        "..PASS tests/example.py::test_multiple_progress_dots",
        "xPASS tests/example.py::test_arbitrary_prefix",
        "prefix .PASS tests/example.py::test_embedded_pass",
        ". PASS tests/example.py::test_space_after_progress",
        "PASS  tests/example.py::test_extra_separator_space",
        "PASS ",
        "PASS? tests/example.py::test_lookalike_suffix",
    ))

    executed, skipped, xfailed = _parse_pass_lines(stdout)

    assert executed == [valid_plain, valid_quiet]
    assert skipped == []
    assert xfailed == []
