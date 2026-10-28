"""Fail-closed Store-backed pub/sub adapter for exact VST dispatch intents."""

from __future__ import annotations

import os
import signal
import sys
import threading
from dataclasses import dataclass
from typing import Any

from .contracts import ContractError
from .runner_service import (
    MAX_DISPATCH_TIMEOUT_SEC, _read_root_controlled_json, dispatch_manifest_run,
)
from .supervisor_service import SupervisorClient

DEFAULT_CONFIG_PATH = "/etc/vst-runner/dispatcher-service.json"
@dataclass(frozen=True)
class DispatcherServiceConfig:
    supervisor_socket: str
    runner_socket: str
    idle_poll_sec: float = 0.25
    rpc_timeout_sec: float = 5.0


def load_dispatcher_service_config(
    path: str = DEFAULT_CONFIG_PATH,
) -> DispatcherServiceConfig:
    value = _read_root_controlled_json(path, max_bytes=65536)
    required = {"supervisor_socket", "runner_socket"}
    optional = {"idle_poll_sec", "rpc_timeout_sec"}
    if set(value) - required - optional or not required <= set(value):
        raise ContractError("dispatcher service configuration fields do not match its schema")
    for field in ("supervisor_socket", "runner_socket"):
        if not isinstance(value[field], str) or not os.path.isabs(value[field]):
            raise ContractError(f"dispatcher service {field} must be an absolute path")
    for field, default, maximum in (
        ("idle_poll_sec", 0.25, 5.0), ("rpc_timeout_sec", 5.0, 30.0),
    ):
        number = value.get(field, default)
        if (isinstance(number, bool) or not isinstance(number, (int, float))
                or not 0.01 <= number <= maximum):
            raise ContractError(f"dispatcher service {field} is outside its allowed range")
    return DispatcherServiceConfig(
        supervisor_socket=value["supervisor_socket"],
        runner_socket=value["runner_socket"],
        idle_poll_sec=float(value.get("idle_poll_sec", 0.25)),
        rpc_timeout_sec=float(value.get("rpc_timeout_sec", 5.0)),
    )


class StoreBackedDispatcher:
    """Consume only Supervisor-filtered intents; never enumerate or select tasks."""

    def __init__(self, config: DispatcherServiceConfig):
        self.config = config
        self.supervisor = SupervisorClient(
            config.supervisor_socket, timeout_sec=config.rpc_timeout_sec,
        )
        self._shutdown = threading.Event()
        self._cursor: dict[str, Any] | None = None

    def shutdown(self) -> None:
        self._shutdown.set()

    def serve_forever(self) -> None:
        while not self._shutdown.is_set():
            delivery = self.supervisor.next_dispatch_intent(self._cursor)
            intent = delivery["intent"]
            if intent is None:
                self._cursor = delivery["cursor_idle"]
                self._shutdown.wait(self.config.idle_poll_sec)
                continue
            request_id = intent.get("request_id")
            if not isinstance(request_id, str):
                raise ContractError("Supervisor delivered an intent without a request id")
            grant = self.supervisor.issue_dispatch_grant(request_id)
            deadline = grant.get("execution_deadline_sec")
            if type(deadline) is not int or deadline < 1:
                raise ContractError("Supervisor returned a grant with an invalid execution deadline")
            timeout = min(MAX_DISPATCH_TIMEOUT_SEC, float(deadline + 120))
            # Cursor advances only after a complete receipt. Any ambiguous RPC or runner outcome
            # stops this service; restart replays the same event and the one-use grant fences it.
            dispatch_manifest_run(
                self.config.runner_socket, grant, timeout_sec=timeout,
            )
            self._cursor = delivery["cursor_after"]


def main() -> None:
    if os.name != "posix" or not hasattr(signal, "SIGTERM"):
        raise ContractError("VST dispatcher requires POSIX signal and Unix-socket support")
    config_path = DEFAULT_CONFIG_PATH
    if len(sys.argv) == 2:
        config_path = sys.argv[1]
    elif len(sys.argv) > 2:
        raise ContractError("dispatcher service accepts only one fixed config path")
    config = load_dispatcher_service_config(config_path)
    service = StoreBackedDispatcher(config)
    signal.signal(signal.SIGTERM, lambda _signum, _frame: service.shutdown())
    signal.signal(signal.SIGINT, lambda _signum, _frame: service.shutdown())
    service.serve_forever()


if __name__ == "__main__":
    main()
