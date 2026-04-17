"""Tests for transform_data traceback preservation in ResourceProcessor."""

from pathlib import Path
from types import SimpleNamespace

import sqlite_utils

from zeeker.core.database.processor import ResourceProcessor
from zeeker.core.schema import SchemaManager


def _build_module(fetch_return, transform_func=None):
    mod = SimpleNamespace()
    mod.fetch_data = lambda existing_table: fetch_return
    if transform_func is not None:
        mod.transform_data = transform_func
    return mod


def test_transform_raise_is_preserved_in_tracebacks(tmp_path: Path):
    db = sqlite_utils.Database(str(tmp_path / "test.db"))
    processor = ResourceProcessor(tmp_path, SchemaManager())

    def bad_transform(data):
        raise ValueError("boom")

    module = _build_module(fetch_return=[{"id": 1, "name": "a"}], transform_func=bad_transform)
    result = processor.process_resource(db, "users", module)

    assert not result.is_valid
    assert result.errors
    assert "Data transformation failed" in result.errors[0]
    assert result.tracebacks, "expected tracebacks to be populated"
    assert "ValueError: boom" in result.tracebacks[0]


def test_transform_success_has_no_traceback(tmp_path: Path):
    db = sqlite_utils.Database(str(tmp_path / "test.db"))
    processor = ResourceProcessor(tmp_path, SchemaManager())
    processor.schema_manager.ensure_meta_tables(db)

    module = _build_module(
        fetch_return=[{"id": 1, "name": "a"}],
        transform_func=lambda data: [{**d, "extra": True} for d in data],
    )
    result = processor.process_resource(db, "users", module)

    assert result.is_valid
    assert not result.tracebacks


def test_no_transform_function_no_traceback(tmp_path: Path):
    db = sqlite_utils.Database(str(tmp_path / "test.db"))
    processor = ResourceProcessor(tmp_path, SchemaManager())
    processor.schema_manager.ensure_meta_tables(db)

    module = _build_module(fetch_return=[{"id": 1}])
    result = processor.process_resource(db, "widgets", module)

    assert result.is_valid
    assert not result.tracebacks
