"""Retired detached capture entrypoint refuses all external probe handoffs."""
from __future__ import annotations

import pytest

from tools.vst import preflight_host_capture


def test_detached_capture_runner_refuses_request_attestation_and_file_arguments():
    with pytest.raises(RuntimeError, match="detached probe capture is retired"):
        preflight_host_capture.run_probe(
            request_path="/etc/vst-runner/probe-request.json",
            attestation_path="/run/vst-preflight/attestation.json",
            output_path="/run/vst-preflight/record.json",
            operator_key=b"caller-supplied-key",
        )


def test_detached_capture_cli_returns_refusal_without_consuming_arguments(capsys):
    assert preflight_host_capture.main([
        "--request", "/etc/vst-runner/probe-request.json",
        "--attestation", "/run/vst-preflight/attestation.json",
    ]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "detached probe capture is retired"
