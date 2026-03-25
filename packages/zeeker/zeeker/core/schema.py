"""
Schema management for Zeeker databases.

This module handles schema versioning, conflict detection, meta table management,
and build tracking. Extracted from database.py for clean separation of concerns.
"""

import json
from datetime import datetime

import sqlite_utils

from .types import (
    META_TABLE_SCHEMAS,
    META_TABLE_UPDATES,
    ValidationResult,
    ZeekerSchemaConflictError,
    calculate_schema_hash,
    infer_schema_from_data,
)


class SchemaManager:
    """Manages database schema versioning and meta table operations."""

    def __init__(self):
        """Initialize schema manager."""
        pass

    def ensure_meta_tables(self, db: sqlite_utils.Database) -> None:
        """Create meta tables if they don't exist.

        Args:
            db: sqlite-utils Database instance
        """
        # Create schemas tracking table
        if not db[META_TABLE_SCHEMAS].exists():
            db[META_TABLE_SCHEMAS].create(
                {
                    "resource_name": str,
                    "schema_version": int,
                    "schema_hash": str,
                    "column_definitions": str,  # JSON
                    "created_at": str,
                    "updated_at": str,
                },
                pk="resource_name",
            )

        # Create updates tracking table
        if not db[META_TABLE_UPDATES].exists():
            db[META_TABLE_UPDATES].create(
                {
                    "resource_name": str,
                    "last_updated": str,
                    "record_count": int,
                    "build_id": str,
                    "duration_ms": int,
                },
                pk="resource_name",
            )

    def generate_build_id(self) -> str:
        """Generate unique build ID for tracking builds.

        Returns:
            Unique build identifier string
        """
        return f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def get_stored_schema(
        self, db: sqlite_utils.Database, resource_name: str
    ) -> dict[str, str] | None:
        """Get stored schema information for a resource.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource

        Returns:
            Schema information dictionary or None if not found
        """
        try:
            schema_table = db[META_TABLE_SCHEMAS]
            for row in schema_table.rows_where("resource_name = ?", [resource_name]):
                return {
                    "schema_hash": row["schema_hash"],
                    "column_definitions": json.loads(row["column_definitions"]),
                    "schema_version": row["schema_version"],
                    "updated_at": row["updated_at"],
                }
            return None
        except Exception:
            return None

    def update_schema_tracking(
        self, db: sqlite_utils.Database, resource_name: str, column_definitions: dict[str, str]
    ) -> None:
        """Update schema tracking information for a resource.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource
            column_definitions: Dictionary of column name to type mappings
        """
        schema_hash = calculate_schema_hash(column_definitions)
        now = datetime.now().isoformat()

        schema_table = db[META_TABLE_SCHEMAS]

        # Check if record exists
        existing = list(schema_table.rows_where("resource_name = ?", [resource_name]))

        if existing:
            # Update existing record
            schema_version = existing[0]["schema_version"] + 1
            schema_table.update(
                resource_name,
                {
                    "schema_version": schema_version,
                    "schema_hash": schema_hash,
                    "column_definitions": json.dumps(column_definitions),
                    "updated_at": now,
                },
            )
        else:
            # Insert new record
            schema_table.insert(
                {
                    "resource_name": resource_name,
                    "schema_version": 1,
                    "schema_hash": schema_hash,
                    "column_definitions": json.dumps(column_definitions),
                    "created_at": now,
                    "updated_at": now,
                }
            )

    def update_resource_timestamps(
        self, db: sqlite_utils.Database, resource_name: str, build_id: str, duration_ms: int
    ) -> None:
        """Update resource timestamp and statistics.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource
            build_id: Build identifier
            duration_ms: Build duration in milliseconds
        """
        now = datetime.now().isoformat()

        # Get record count
        try:
            table = db[resource_name]
            record_count = table.count
        except Exception:
            record_count = 0

        updates_table = db[META_TABLE_UPDATES]

        # Upsert the record
        updates_table.insert(
            {
                "resource_name": resource_name,
                "last_updated": now,
                "record_count": record_count,
                "build_id": build_id,
                "duration_ms": duration_ms,
            },
            replace=True,
        )

    def check_schema_conflicts(
        self, db: sqlite_utils.Database, resource_name: str, sample_data: list[dict], module
    ) -> ValidationResult:
        """Check for schema conflicts and handle migration if available.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource
            sample_data: Sample data for schema inference
            module: The resource module (for migration function)

        Returns:
            ValidationResult indicating success or schema conflict
        """
        result = ValidationResult(is_valid=True)

        stored_schema = self.get_stored_schema(db, resource_name)
        if not stored_schema:
            return result  # No stored schema, no conflict

        new_column_definitions = infer_schema_from_data(sample_data)
        new_hash = calculate_schema_hash(new_column_definitions)

        if new_hash != stored_schema["schema_hash"]:
            # Schema conflict detected
            if hasattr(module, "migrate_schema"):
                # Try automatic migration
                migrate_schema = getattr(module, "migrate_schema")
                try:
                    existing_table = db[resource_name]
                    migrate_result = migrate_schema(
                        existing_table,
                        {
                            "old_schema": stored_schema,
                            "new_schema": new_column_definitions,
                        },
                    )
                    if migrate_result:
                        result.info.append(f"Schema migration successful for {resource_name}")
                        self.update_schema_tracking(db, resource_name, new_column_definitions)
                    else:
                        raise ZeekerSchemaConflictError(
                            resource_name,
                            stored_schema["column_definitions"],
                            new_column_definitions,
                        )
                except Exception:
                    # Migration failed, raise conflict error
                    raise ZeekerSchemaConflictError(
                        resource_name, stored_schema["column_definitions"], new_column_definitions
                    )
            else:
                # No migration function, raise conflict error
                raise ZeekerSchemaConflictError(
                    resource_name, stored_schema["column_definitions"], new_column_definitions
                )

        return result

    def track_new_table_schema(
        self, db: sqlite_utils.Database, table_name: str, data: list[dict]
    ) -> None:
        """Track schema for a newly created table.

        Args:
            db: sqlite-utils Database instance
            table_name: Name of the table
            data: Data used to infer the schema
        """
        if data:  # Only track if we have data
            column_definitions = infer_schema_from_data(data)
            self.update_schema_tracking(db, table_name, column_definitions)
