"""Tests for the post-build shell hook runner."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from zeeker.commands.post_hook import PostHookResult, run_post_hook
from zeeker.core.types import BuildReport, ResourceOutcome


@pytest.fixture
def sample_report() -> BuildReport:
    return BuildReport(
        resources=[ResourceOutcome(name="users", status="success", records=3, duration_s=0.1)],
        total_duration_s=0.1,
    )


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_post_hook_success_populates_result(tmp_path: Path, sample_report):
    with patch("subprocess.run", return_value=_FakeCompleted(0, "ok\n", "")) as mock_run:
        result = run_post_hook(
            "echo ok",
            project_path=tmp_path,
            db_path=tmp_path / "mydb.db",
            db_name="mydb",
            report=sample_report,
        )

    assert isinstance(result, PostHookResult)
    assert result.exit_code == 0
    assert result.stdout == "ok\n"
    assert result.command == "echo ok"

    call = mock_run.call_args
    assert call.args[0] == "echo ok"
    assert call.kwargs["shell"] is True
    assert call.kwargs["cwd"] == str(tmp_path)
    assert call.kwargs["capture_output"] is True
    assert call.kwargs["text"] is True
    assert call.kwargs["check"] is False

    env = call.kwargs["env"]
    assert env["ZEEKER_DB_PATH"] == str(tmp_path / "mydb.db")
    assert env["ZEEKER_DB_NAME"] == "mydb"
    assert env["ZEEKER_PROJECT_PATH"] == str(tmp_path)
    assert env["ZEEKER_BUILD_STATUS"] == "success"

    report_path = env["ZEEKER_BUILD_REPORT"]
    assert os.path.exists(report_path)
    payload = json.loads(Path(report_path).read_text())
    assert payload["status"] == "success"
    assert payload["resources"][0]["name"] == "users"


def test_run_post_hook_non_zero_propagates(tmp_path: Path, sample_report):
    with patch("subprocess.run", return_value=_FakeCompleted(5, "", "boom")):
        result = run_post_hook(
            "false",
            project_path=tmp_path,
            db_path=tmp_path / "x.db",
            db_name="x",
            report=sample_report,
        )
    assert result.exit_code == 5
    assert result.stderr == "boom"


def test_run_post_hook_marks_partial_failure_status(tmp_path: Path):
    partial = BuildReport(
        resources=[ResourceOutcome(name="users", status="failed", error_message="x")],
        total_duration_s=0.0,
    )
    with patch("subprocess.run", return_value=_FakeCompleted(0)) as mock_run:
        run_post_hook(
            "echo",
            project_path=tmp_path,
            db_path=tmp_path / "x.db",
            db_name="x",
            report=partial,
        )
    assert mock_run.call_args.kwargs["env"]["ZEEKER_BUILD_STATUS"] == "partial_failure"


def test_run_post_hook_real_subprocess(tmp_path: Path, sample_report):
    """Smoke test that the real subprocess picks up env vars."""
    # Use a portable one-liner: print an env var and exit 0.
    result = run_post_hook(
        'printf "%s" "$ZEEKER_DB_NAME"',
        project_path=tmp_path,
        db_path=tmp_path / "testdb.db",
        db_name="testdb",
        report=sample_report,
    )
    assert result.exit_code == 0
    assert result.stdout == "testdb"
