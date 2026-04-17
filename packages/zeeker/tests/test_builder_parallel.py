"""Tests for cross-resource parallel fetch phase in DatabaseBuilder."""

import asyncio
import time
from pathlib import Path

import pytest

from zeeker.core.database.builder import DatabaseBuilder
from zeeker.core.types import ZeekerProject


def _write_resource(resources_dir: Path, name: str, body: str) -> None:
    resources_dir.mkdir(parents=True, exist_ok=True)
    (resources_dir / f"{name}.py").write_text(body)


def _async_sleep_resource(name: str, sleep_s: float = 0.3) -> str:
    """Module body that sleeps asynchronously then returns a tiny record."""
    return f"""
import asyncio

async def fetch_data(existing_table):
    await asyncio.sleep({sleep_s})
    return [{{"id": 1, "name": "{name}"}}]
"""


def _sync_sleep_resource(name: str, sleep_s: float = 0.3) -> str:
    return f"""
import time

def fetch_data(existing_table):
    time.sleep({sleep_s})
    return [{{"id": 1, "name": "{name}"}}]
"""


def _build_project(tmp_path: Path, resource_names: list[str]) -> DatabaseBuilder:
    project = ZeekerProject(
        name="parallel_test",
        database="parallel_test.db",
        resources={name: {} for name in resource_names},
        root_path=tmp_path,
    )
    return DatabaseBuilder(tmp_path, project)


def test_parallel_fetch_is_faster_than_sequential(tmp_path: Path):
    names = ["a", "b", "c", "d"]
    resources_dir = tmp_path / "resources"
    for n in names:
        _write_resource(resources_dir, n, _async_sleep_resource(n, sleep_s=0.3))

    builder = _build_project(tmp_path, names)

    started = time.perf_counter()
    result = builder.build_database(max_parallel=4)
    elapsed = time.perf_counter() - started

    assert result.is_valid, f"Build failed: {result.errors}"
    assert len(result.report.succeeded) == 4
    # 4 × 0.3s serial = 1.2s+ of pure sleep; parallel should finish well
    # under that. Give a generous bound to avoid CI flake.
    assert elapsed < 1.0, f"Parallel build took {elapsed:.2f}s — not parallel?"


def test_parallel_fetch_handles_mixed_sync_and_async(tmp_path: Path):
    resources_dir = tmp_path / "resources"
    _write_resource(resources_dir, "a_async", _async_sleep_resource("a_async", 0.3))
    _write_resource(resources_dir, "b_sync", _sync_sleep_resource("b_sync", 0.3))

    builder = _build_project(tmp_path, ["a_async", "b_sync"])

    started = time.perf_counter()
    result = builder.build_database(max_parallel=4)
    elapsed = time.perf_counter() - started

    assert result.is_valid, result.errors
    assert len(result.report.succeeded) == 2
    # Two 0.3s fetches in parallel should be ~0.3s, definitely under 0.6s.
    assert elapsed < 0.6


def test_parallel_one_failure_doesnt_block_others(tmp_path: Path):
    resources_dir = tmp_path / "resources"
    _write_resource(
        resources_dir,
        "ok",
        """
def fetch_data(existing_table):
    return [{"id": 1}]
""",
    )
    _write_resource(
        resources_dir,
        "boom",
        """
def fetch_data(existing_table):
    raise RuntimeError("boom")
""",
    )

    builder = _build_project(tmp_path, ["ok", "boom"])
    result = builder.build_database(max_parallel=2)

    # Build itself reports not-valid (one failed), but the succeeded resource
    # must still appear in the report.
    names = {r.name: r.status for r in result.report.resources}
    assert names == {"ok": "success", "boom": "failed"}
    failed = next(r for r in result.report.resources if r.name == "boom")
    assert failed.error_message and "boom" in failed.error_message
    assert failed.traceback and "RuntimeError" in failed.traceback


def test_sequential_default_still_works(tmp_path: Path):
    """max_parallel=1 (the default) must preserve existing behaviour."""
    resources_dir = tmp_path / "resources"
    _write_resource(
        resources_dir,
        "a",
        """
def fetch_data(existing_table):
    return [{"id": 1, "name": "alpha"}]
""",
    )

    builder = _build_project(tmp_path, ["a"])
    result = builder.build_database()  # default max_parallel=1

    assert result.is_valid
    assert len(result.report.succeeded) == 1
