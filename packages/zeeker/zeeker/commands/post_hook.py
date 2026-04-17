"""Post-build shell hook.

Runs a user-provided shell command after a successful build with zeeker
context injected as environment variables. The CLI wires this up via the
``--post-hook`` flag on ``zeeker build``.
"""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..core.types import BuildReport


@dataclass
class PostHookResult:
    """Outcome of running a post-build hook command."""

    command: str
    exit_code: int
    stdout: str
    stderr: str


def run_post_hook(
    command: str,
    *,
    project_path: Path,
    db_path: Path,
    db_name: str,
    report: BuildReport,
) -> PostHookResult:
    """Run ``command`` as a shell command with zeeker env vars set.

    Writes the current BuildReport to a tempfile and exposes its path via
    ``ZEEKER_BUILD_REPORT`` so the hook can read it (e.g. to skip patching
    on partial failures).

    Env vars exposed to the hook:
        ZEEKER_DB_PATH       absolute path to the .db file
        ZEEKER_DB_NAME       database stem (e.g. my_project)
        ZEEKER_PROJECT_PATH  project root
        ZEEKER_BUILD_STATUS  "success" or "partial_failure"
        ZEEKER_BUILD_REPORT  path to a tempfile with the JSON BuildReport
    """
    # Local import to avoid circular dependency at module load time
    # (helpers imports types; post_hook imports types; cli imports both).
    from .helpers import _build_report_payload

    report_fd = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    try:
        json.dump(_build_report_payload(report), report_fd)
    finally:
        report_fd.close()

    env = {
        **os.environ,
        "ZEEKER_DB_PATH": str(db_path),
        "ZEEKER_DB_NAME": db_name,
        "ZEEKER_PROJECT_PATH": str(project_path),
        "ZEEKER_BUILD_STATUS": "success" if not report.failed else "partial_failure",
        "ZEEKER_BUILD_REPORT": report_fd.name,
    }

    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(project_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return PostHookResult(
        command=command,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
