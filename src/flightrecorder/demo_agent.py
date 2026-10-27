"""A deterministic agent-like workflow using real files and a subprocess test."""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from .recorder import FlightRecorder


SAFE_SOURCE = """class DuplicatePayment(Exception):
    pass


def charge(already_paid):
    if already_paid:
        raise DuplicatePayment("already paid")
    return "charged"
"""

BROKEN_SOURCE = """class DuplicatePayment(Exception):
    pass


def charge(already_paid):
    return "charged"
"""

TEST_SOURCE = """from payment_service import DuplicatePayment, charge

try:
    charge(True)
except DuplicatePayment:
    print("duplicate payment rejected")
else:
    raise AssertionError("payment_service.py accepted a duplicate payment")
"""


def run_demo(recorder: FlightRecorder, workspace: Path) -> str:
    workspace.mkdir(parents=True, exist_ok=True)
    service = workspace / "payment_service.py"
    test = workspace / "test_payment.py"
    service.write_text(SAFE_SOURCE, encoding="utf-8")
    test.write_text(TEST_SOURCE, encoding="utf-8")
    run_id = "run-agent-" + uuid.uuid4().hex[:8]

    def read_file(path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def edit_file(path: str, content: str) -> str:
        Path(path).write_text(content, encoding="utf-8")
        return path

    def run_tests(path: str) -> str:
        result = subprocess.run(
            [sys.executable, str(test)],
            cwd=path,
            text=True,
            capture_output=True,
            timeout=10,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode:
            raise RuntimeError(output)
        return output

    try:
        with recorder.run(
            "Real payment-agent workflow",
            run_id=run_id,
            metadata={"workspace": str(workspace), "demo": True},
        ) as run:
            recorded_read = run.wrap_tool(read_file, name="Read implementation", kind="file_read")
            recorded_edit = run.wrap_tool(
                edit_file,
                name="Apply agent edit",
                kind="file_write",
                watch_paths=[str(workspace)],
            )
            recorded_test = run.wrap_tool(run_tests, name="Run regression test", kind="test")
            recorded_read(str(service))
            recorded_edit(str(service), BROKEN_SOURCE)
            recorded_test(str(workspace))
    except RuntimeError:
        pass
    return run_id

