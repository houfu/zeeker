"""Comprehensive tests for schema management functionality."""

import json
import pytest
import sqlite_utils
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from zeeker.core.schema import SchemaManager
from zeeker.core.types import (
    META_TABLE_SCHEMAS,
    META_TABLE_UPDATES,
    ValidationResult,
    ZeekerSchemaConflictError,
    calculate_schema_hash,
    extract_table_schema,
    infer_schema_from_data,
)


class TestSchemaManager:
    """Direct unit tests for SchemaManager class."""

    @pytest.fixture
    def schema_manager(self):
        """Create SchemaManager instance."""
        return SchemaManager()

    @pytest.fixture
    def temp_db(self):
        """Create temporary SQLite database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db = sqlite_utils.Database(db_path)
        yield db
        db.close()
        Path(db_path).unlink(missing_ok=True)

    def test_ensure_meta_tables_creates_both_tables(self, schema_manager, temp_db):
        """Test that ensure_meta_tables creates both schema and updates tables."""
        # Ensure tables don't exist initially
        assert not temp_db[META_TABLE_SCHEMAS].exists()
        assert not temp_db[META_TABLE_UPDATES].exists()

        schema_manager.ensure_meta_tables(temp_db)

        # Verify both tables were created
        assert temp_db[META_TABLE_SCHEMAS].exists()
        assert temp_db[META_TABLE_UPDATES].exists()

        # Verify schema table structure
        schema_cols = {col.name: col.type for col in temp_db[META_TABLE_SCHEMAS].columns}
        expected_schema_cols = {
            "resource_name": "TEXT",
            "schema_version": "INTEGER",
            "schema_hash": "TEXT",
            "column_definitions": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        assert schema_cols == expected_schema_cols

        # Verify updates table structure
        updates_cols = {col.name: col.type for col in temp_db[META_TABLE_UPDATES].columns}
        expected_updates_cols = {
            "resource_name": "TEXT",
            "last_updated": "TEXT",
            "record_count": "INTEGER",
            "build_id": "TEXT",
            "duration_ms": "INTEGER",
        }
        assert updates_cols == expected_updates_cols

    def test_ensure_meta_tables_idempotent(self, schema_manager, temp_db):
        """Test that calling ensure_meta_tables multiple times is safe."""
        # Create tables first time
        schema_manager.ensure_meta_tables(temp_db)
        initial_schema_count = temp_db[META_TABLE_SCHEMAS].count
        initial_updates_count = temp_db[META_TABLE_UPDATES].count

        # Call again
        schema_manager.ensure_meta_tables(temp_db)

        # Should not create duplicate tables or affect existing data
        assert temp_db[META_TABLE_SCHEMAS].count == initial_schema_count
        assert temp_db[META_TABLE_UPDATES].count == initial_updates_count

    def test_generate_build_id_format(self, schema_manager):
        """Test build ID generation format and uniqueness."""
        build_id1 = schema_manager.generate_build_id()
        build_id2 = schema_manager.generate_build_id()

        # Should start with "build_"
        assert build_id1.startswith("build_")
        assert build_id2.startswith("build_")

        # Should have timestamp format
        import re

        pattern = r"build_\d{8}_\d{6}"
        assert re.match(pattern, build_id1)
        assert re.match(pattern, build_id2)

        # Should be different if called at different times
        # (Note: might be same if called within same second, which is acceptable)

    def test_get_stored_schema_success(self, schema_manager, temp_db):
        """Test successful schema retrieval."""
        schema_manager.ensure_meta_tables(temp_db)

        # Insert test schema
        test_schema = {"id": "INTEGER", "name": "TEXT"}
        temp_db[META_TABLE_SCHEMAS].insert(
            {
                "resource_name": "test_resource",
                "schema_version": 2,
                "schema_hash": "abc123",
                "column_definitions": json.dumps(test_schema),
                "created_at": "2024-01-01T10:00:00",
                "updated_at": "2024-01-02T15:30:00",
            }
        )

        result = schema_manager.get_stored_schema(temp_db, "test_resource")

        assert result is not None
        assert result["schema_hash"] == "abc123"
        assert result["column_definitions"] == test_schema
        assert result["schema_version"] == 2
        assert result["updated_at"] == "2024-01-02T15:30:00"

    def test_get_stored_schema_not_found(self, schema_manager, temp_db):
        """Test schema retrieval when resource doesn't exist."""
        schema_manager.ensure_meta_tables(temp_db)

        result = schema_manager.get_stored_schema(temp_db, "nonexistent_resource")
        assert result is None

    def test_get_stored_schema_malformed_json(self, schema_manager, temp_db):
        """Test schema retrieval with malformed JSON column definitions."""
        schema_manager.ensure_meta_tables(temp_db)

        # Insert schema with malformed JSON
        temp_db[META_TABLE_SCHEMAS].insert(
            {
                "resource_name": "bad_json_resource",
                "schema_version": 1,
                "schema_hash": "bad123",
                "column_definitions": "invalid_json{",  # Malformed JSON
                "created_at": "2024-01-01T10:00:00",
                "updated_at": "2024-01-01T10:00:00",
            }
        )

        # Should handle gracefully and return None
        result = schema_manager.get_stored_schema(temp_db, "bad_json_resource")
        assert result is None

    def test_update_schema_tracking_new_resource(self, schema_manager, temp_db):
        """Test schema tracking for new resource."""
        schema_manager.ensure_meta_tables(temp_db)

        column_definitions = {"id": "INTEGER", "title": "TEXT", "score": "REAL"}
        schema_manager.update_schema_tracking(temp_db, "new_resource", column_definitions)

        # Verify record was inserted
        records = list(
            temp_db[META_TABLE_SCHEMAS].rows_where("resource_name = ?", ["new_resource"])
        )
        assert len(records) == 1

        record = records[0]
        assert record["resource_name"] == "new_resource"
        assert record["schema_version"] == 1
        assert record["schema_hash"] == calculate_schema_hash(column_definitions)
        assert json.loads(record["column_definitions"]) == column_definitions
        assert record["created_at"] is not None
        assert record["updated_at"] is not None

    def test_update_schema_tracking_existing_resource(self, schema_manager, temp_db):
        """Test schema tracking update for existing resource."""
        schema_manager.ensure_meta_tables(temp_db)

        # Insert initial schema
        initial_schema = {"id": "INTEGER", "name": "TEXT"}
        schema_manager.update_schema_tracking(temp_db, "existing_resource", initial_schema)

        # Update with new schema
        updated_schema = {"id": "INTEGER", "name": "TEXT", "email": "TEXT"}
        schema_manager.update_schema_tracking(temp_db, "existing_resource", updated_schema)

        # Verify record was updated, not duplicated
        records = list(
            temp_db[META_TABLE_SCHEMAS].rows_where("resource_name = ?", ["existing_resource"])
        )
        assert len(records) == 1

        record = records[0]
        assert record["resource_name"] == "existing_resource"
        assert record["schema_version"] == 2  # Incremented
        assert record["schema_hash"] == calculate_schema_hash(updated_schema)
        assert json.loads(record["column_definitions"]) == updated_schema

    def test_update_resource_timestamps(self, schema_manager, temp_db):
        """Test resource timestamp and statistics updates."""
        schema_manager.ensure_meta_tables(temp_db)

        # Create a test table with some data
        temp_db["test_resource"].insert_all(
            [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}, {"id": 3, "name": "test3"}]
        )

        build_id = "test_build_123"
        duration_ms = 1500

        schema_manager.update_resource_timestamps(temp_db, "test_resource", build_id, duration_ms)

        # Verify record was inserted/updated
        records = list(
            temp_db[META_TABLE_UPDATES].rows_where("resource_name = ?", ["test_resource"])
        )
        assert len(records) == 1

        record = records[0]
        assert record["resource_name"] == "test_resource"
        assert record["record_count"] == 3  # Should match table count
        assert record["build_id"] == build_id
        assert record["duration_ms"] == duration_ms
        assert record["last_updated"] is not None

        # Test update (replace=True behavior)
        new_build_id = "test_build_456"
        schema_manager.update_resource_timestamps(temp_db, "test_resource", new_build_id, 2000)

        # Should still be only one record
        records = list(
            temp_db[META_TABLE_UPDATES].rows_where("resource_name = ?", ["test_resource"])
        )
        assert len(records) == 1
        assert records[0]["build_id"] == new_build_id

    def test_update_resource_timestamps_nonexistent_table(self, schema_manager, temp_db):
        """Test timestamp updates when resource table doesn't exist."""
        schema_manager.ensure_meta_tables(temp_db)

        # Should handle gracefully with record_count = 0
        schema_manager.update_resource_timestamps(
            temp_db, "nonexistent_resource", "build_123", 1000
        )

        records = list(
            temp_db[META_TABLE_UPDATES].rows_where("resource_name = ?", ["nonexistent_resource"])
        )
        assert len(records) == 1
        assert records[0]["record_count"] == 0

    def test_check_schema_conflicts_no_stored_schema(self, schema_manager, temp_db):
        """Test conflict checking when no stored schema exists."""
        schema_manager.ensure_meta_tables(temp_db)

        sample_data = [{"id": 1, "name": "test"}]
        mock_module = MagicMock()

        result = schema_manager.check_schema_conflicts(
            temp_db, "new_resource", sample_data, mock_module
        )

        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.info) == 0

    def test_check_schema_conflicts_no_conflict(self, schema_manager, temp_db):
        """Test conflict checking when schemas match."""
        schema_manager.ensure_meta_tables(temp_db)

        # Store initial schema
        column_definitions = {"id": "INTEGER", "name": "TEXT"}
        schema_manager.update_schema_tracking(temp_db, "test_resource", column_definitions)

        # Check with same schema
        sample_data = [{"id": 1, "name": "test"}]
        mock_module = MagicMock()

        result = schema_manager.check_schema_conflicts(
            temp_db, "test_resource", sample_data, mock_module
        )

        assert result.is_valid
        assert len(result.errors) == 0

    def test_check_schema_conflicts_with_successful_migration(self, schema_manager, temp_db):
        """Test conflict resolution with successful migration function."""
        schema_manager.ensure_meta_tables(temp_db)

        # Store initial schema
        old_schema = {"id": "INTEGER", "name": "TEXT"}
        schema_manager.update_schema_tracking(temp_db, "test_resource", old_schema)

        # Create actual table to pass to migration
        temp_db["test_resource"].insert({"id": 1, "name": "test"})

        # Create mock module with successful migration
        mock_module = MagicMock()
        mock_migrate = MagicMock(return_value=True)
        mock_module.migrate_schema = mock_migrate

        # New data with additional field
        sample_data = [{"id": 1, "name": "test", "email": "test@example.com"}]

        result = schema_manager.check_schema_conflicts(
            temp_db, "test_resource", sample_data, mock_module
        )

        assert result.is_valid
        assert any("Schema migration successful" in info for info in result.info)

        # Verify migration function was called
        mock_migrate.assert_called_once()
        call_args = mock_migrate.call_args
        # First argument should be a table object
        assert hasattr(call_args[0][0], "name")  # Table object
        # Second argument should be schema info dict
        schema_info = call_args[0][1]
        assert "old_schema" in schema_info
        assert "new_schema" in schema_info

    def test_check_schema_conflicts_migration_returns_false(self, schema_manager, temp_db):
        """Test conflict when migration function returns False."""
        schema_manager.ensure_meta_tables(temp_db)

        # Store initial schema
        old_schema = {"id": "INTEGER", "name": "TEXT"}
        schema_manager.update_schema_tracking(temp_db, "test_resource", old_schema)

        # Create actual table
        temp_db["test_resource"].insert({"id": 1, "name": "test"})

        # Create mock module with failing migration
        mock_module = MagicMock()
        mock_migrate = MagicMock(return_value=False)
        mock_module.migrate_schema = mock_migrate

        # New data with additional field
        sample_data = [{"id": 1, "name": "test", "email": "test@example.com"}]

        with pytest.raises(ZeekerSchemaConflictError):
            schema_manager.check_schema_conflicts(
                temp_db, "test_resource", sample_data, mock_module
            )

    def test_check_schema_conflicts_migration_raises_exception(self, schema_manager, temp_db):
        """Test conflict when migration function raises exception."""
        schema_manager.ensure_meta_tables(temp_db)

        # Store initial schema
        old_schema = {"id": "INTEGER", "name": "TEXT"}
        schema_manager.update_schema_tracking(temp_db, "test_resource", old_schema)

        # Create actual table
        temp_db["test_resource"].insert({"id": 1, "name": "test"})

        # Create mock module with exception-raising migration
        mock_module = MagicMock()
        mock_migrate = MagicMock(side_effect=RuntimeError("Migration failed"))
        mock_module.migrate_schema = mock_migrate

        # New data with additional field
        sample_data = [{"id": 1, "name": "test", "email": "test@example.com"}]

        with pytest.raises(ZeekerSchemaConflictError):
            schema_manager.check_schema_conflicts(
                temp_db, "test_resource", sample_data, mock_module
            )

    def test_check_schema_conflicts_no_migration_function(self, schema_manager, temp_db):
        """Test conflict when no migration function exists."""
        schema_manager.ensure_meta_tables(temp_db)

        # Store initial schema
        old_schema = {"id": "INTEGER", "name": "TEXT"}
        schema_manager.update_schema_tracking(temp_db, "test_resource", old_schema)

        # Create mock module without migration function
        mock_module = MagicMock(spec=[])  # Empty spec = no migrate_schema attribute

        # New data with additional field
        sample_data = [{"id": 1, "name": "test", "email": "test@example.com"}]

        with pytest.raises(ZeekerSchemaConflictError):
            schema_manager.check_schema_conflicts(
                temp_db, "test_resource", sample_data, mock_module
            )

    def test_track_new_table_schema(self, schema_manager, temp_db):
        """Test schema tracking for newly created table."""
        schema_manager.ensure_meta_tables(temp_db)

        data = [
            {"id": 1, "title": "Test 1", "score": 85.5, "active": True},
            {"id": 2, "title": "Test 2", "score": 92.0, "active": False},
        ]

        schema_manager.track_new_table_schema(temp_db, "new_table", data)

        # Verify schema was tracked
        records = list(temp_db[META_TABLE_SCHEMAS].rows_where("resource_name = ?", ["new_table"]))
        assert len(records) == 1

        record = records[0]
        assert record["resource_name"] == "new_table"
        assert record["schema_version"] == 1

        stored_schema = json.loads(record["column_definitions"])
        expected_schema = infer_schema_from_data(data)
        assert stored_schema == expected_schema

    def test_track_new_table_schema_empty_data(self, schema_manager, temp_db):
        """Test schema tracking with empty data."""
        schema_manager.ensure_meta_tables(temp_db)

        schema_manager.track_new_table_schema(temp_db, "empty_table", [])

        # Should not create any schema record for empty data
        records = list(temp_db[META_TABLE_SCHEMAS].rows_where("resource_name = ?", ["empty_table"]))
        assert len(records) == 0


class TestSchemaUtilityFunctions:
    """Test schema utility functions in types.py."""

    def test_calculate_schema_hash_consistency(self):
        """Test that schema hash is consistent for same schema."""
        schema1 = {"id": "INTEGER", "name": "TEXT", "score": "REAL"}
        schema2 = {"id": "INTEGER", "name": "TEXT", "score": "REAL"}

        hash1 = calculate_schema_hash(schema1)
        hash2 = calculate_schema_hash(schema2)

        assert hash1 == hash2
        assert len(hash1) == 16  # Should be truncated to 16 chars

    def test_calculate_schema_hash_order_independence(self):
        """Test that column order doesn't affect hash."""
        schema1 = {"id": "INTEGER", "name": "TEXT", "score": "REAL"}
        schema2 = {"score": "REAL", "name": "TEXT", "id": "INTEGER"}

        hash1 = calculate_schema_hash(schema1)
        hash2 = calculate_schema_hash(schema2)

        assert hash1 == hash2

    def test_calculate_schema_hash_different_schemas(self):
        """Test that different schemas produce different hashes."""
        schema1 = {"id": "INTEGER", "name": "TEXT"}
        schema2 = {"id": "INTEGER", "name": "TEXT", "email": "TEXT"}
        schema3 = {"id": "REAL", "name": "TEXT"}  # Different type

        hash1 = calculate_schema_hash(schema1)
        hash2 = calculate_schema_hash(schema2)
        hash3 = calculate_schema_hash(schema3)

        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_extract_table_schema(self):
        """Test table schema extraction."""

        # Create mock columns with proper attributes
        class MockColumn:
            def __init__(self, name, type_):
                self.name = name
                self.type = type_

        mock_columns = [
            MockColumn("id", "INTEGER"),
            MockColumn("title", "TEXT"),
            MockColumn("score", "REAL"),
            MockColumn("active", "INTEGER"),
        ]

        mock_table = MagicMock()
        mock_table.columns = mock_columns

        result = extract_table_schema(mock_table)

        expected = {"id": "INTEGER", "title": "TEXT", "score": "REAL", "active": "INTEGER"}
        assert result == expected

    def test_infer_schema_from_data_basic_types(self):
        """Test schema inference with basic Python types."""
        data = [
            {"id": 1, "name": "Alice", "score": 85.5, "active": True},
            {"id": 2, "name": "Bob", "score": 92.0, "active": False},
        ]

        result = infer_schema_from_data(data)

        expected = {
            "id": "INTEGER",
            "name": "TEXT",
            "score": "REAL",
            "active": "INTEGER",  # bools become integers
        }
        assert result == expected

    def test_infer_schema_from_data_mixed_numeric_types(self):
        """Test schema inference with mixed int/float values."""
        data = [{"value": 10}, {"value": 15.5}, {"value": 20}]  # int  # float  # int

        result = infer_schema_from_data(data)
        assert result["value"] == "REAL"  # Should infer as REAL for mixed numeric

    def test_infer_schema_from_data_json_types(self):
        """Test schema inference with dict/list values."""
        data = [
            {"metadata": {"key": "value"}, "tags": ["tag1", "tag2"]},
            {"metadata": {"other": "data"}, "tags": ["tag3"]},
        ]

        result = infer_schema_from_data(data)

        assert result["metadata"] == "TEXT"  # JSON stored as TEXT
        assert result["tags"] == "TEXT"  # JSON stored as TEXT

    def test_infer_schema_from_data_missing_columns(self):
        """Test schema inference when not all records have all columns."""
        data = [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob"},  # Missing email
            {"id": 3, "email": "charlie@example.com"},  # Missing name
        ]

        result = infer_schema_from_data(data)

        expected = {"id": "INTEGER", "name": "TEXT", "email": "TEXT"}
        assert result == expected

    def test_infer_schema_from_data_all_null_values(self):
        """Test schema inference with all NULL values in a column."""
        data = [
            {"id": 1, "optional": None},
            {"id": 2, "optional": None},
            {"id": 3, "optional": None},
        ]

        result = infer_schema_from_data(data)

        assert result["id"] == "INTEGER"
        assert result["optional"] == "TEXT"  # Default for all NULL

    def test_infer_schema_from_data_empty_data(self):
        """Test schema inference with empty data."""
        result = infer_schema_from_data([])
        assert result == {}

    def test_infer_schema_from_data_only_bools(self):
        """Test that pure boolean columns are detected correctly."""
        data = [{"flag": True}, {"flag": False}, {"flag": True}]

        result = infer_schema_from_data(data)
        assert result["flag"] == "INTEGER"  # bools stored as integers

    def test_infer_schema_from_data_complex_mixed_types(self):
        """Test schema inference with complex mixed data."""
        data = [
            {
                "id": 1,
                "name": "Product A",
                "price": 19.99,
                "in_stock": True,
                "categories": ["electronics", "gadgets"],
                "metadata": {"brand": "BrandX", "warranty": 2},
                "description": None,
            },
            {
                "id": 2,
                "name": "Product B",
                "price": 25,  # int price
                "in_stock": False,
                "categories": ["books"],
                "metadata": {"author": "Author Y"},
                "description": "A great book",
            },
        ]

        result = infer_schema_from_data(data)

        expected = {
            "id": "INTEGER",
            "name": "TEXT",
            "price": "REAL",  # Mixed int/float = REAL
            "in_stock": "INTEGER",  # bool = INTEGER
            "categories": "TEXT",  # list = TEXT (JSON)
            "metadata": "TEXT",  # dict = TEXT (JSON)
            "description": "TEXT",  # Mixed None/string = TEXT
        }
        assert result == expected


class TestZeekerSchemaConflictError:
    """Test the schema conflict error class."""

    def test_schema_conflict_error_message_format(self):
        """Test that error message contains expected information."""
        old_schema = {"id": "INTEGER", "name": "TEXT"}
        new_schema = {"id": "INTEGER", "name": "TEXT", "email": "TEXT", "age": "INTEGER"}

        error = ZeekerSchemaConflictError("users_table", old_schema, new_schema)
        error_message = str(error)

        # Should contain key information
        assert "users_table" in error_message
        assert "migrate_schema()" in error_message
        assert "--force-schema-reset" in error_message
        assert "schema conflict detected" in error_message.lower()

        # Should show the differences
        assert "email" in error_message  # New column
        assert "age" in error_message  # New column

    def test_schema_conflict_error_basic_message(self):
        """Test basic error message format."""
        old_schema = {"id": "INTEGER"}
        new_schema = {"id": "INTEGER", "name": "TEXT"}

        error = ZeekerSchemaConflictError("test_table", old_schema, new_schema)
        error_message = str(error)

        assert "test_table" in error_message
        assert "migrate_schema()" in error_message
        assert "--force-schema-reset" in error_message
