"""
Database building operations for Zeeker projects.

This module handles building SQLite databases from resources, including
S3 synchronization capabilities for multi-machine workflows.
"""

import importlib.util
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import sqlite_utils

from .schema import SchemaManager
from .types import (
    META_TABLE_SCHEMAS,
    META_TABLE_UPDATES,
    ValidationResult,
    ZeekerProject,
    ZeekerSchemaConflictError,
    calculate_schema_hash,
    infer_schema_from_data,
)


class DatabaseBuilder:
    """Builds SQLite databases from Zeeker resources with S3 sync support."""

    def __init__(self, project_path: Path, project: ZeekerProject):
        """Initialize database builder.

        Args:
            project_path: Path to the Zeeker project
            project: ZeekerProject configuration
        """
        self.project_path = project_path
        self.project = project
        self.resources_path = project_path / "resources"
        self.schema_manager = SchemaManager()

    def build_database(
        self, force_schema_reset: bool = False, sync_from_s3: bool = False
    ) -> ValidationResult:
        """Build the SQLite database from all resources using sqlite-utils.

        Uses Simon Willison's sqlite-utils for robust table creation and data insertion:
        - Automatic schema detection from data
        - Proper type inference (INTEGER, TEXT, REAL)
        - Safe table creation and data insertion
        - Better error handling than raw SQL

        Args:
            force_schema_reset: If True, ignore schema conflicts and rebuild
            sync_from_s3: If True, download existing database from S3 before building

        Returns:
            ValidationResult with build results
        """
        result = ValidationResult(is_valid=True)
        db_path = self.project_path / self.project.database

        # S3 Database Synchronization - Download existing DB if requested
        if sync_from_s3:
            sync_result = self._sync_from_s3(db_path)
            if not sync_result.is_valid:
                result.errors.extend(sync_result.errors)
                # Don't fail build if S3 sync fails - just warn
                result.warnings = getattr(result, "warnings", [])
                result.warnings.append("S3 sync failed but continuing with local build")
            else:
                result.info.extend(sync_result.info)

        # Open existing database or create new one using sqlite-utils
        # Don't delete existing database - let resources check existing data for duplicates
        db = sqlite_utils.Database(str(db_path))

        try:
            # Initialize meta tables
            self.schema_manager.ensure_meta_tables(db)
            build_id = self.schema_manager.generate_build_id()

            all_success = True
            for resource_name in self.project.resources.keys():
                resource_result = self._process_resource_with_schema_check(
                    db, resource_name, force_schema_reset, build_id
                )
                if not resource_result.is_valid:
                    result.errors.extend(resource_result.errors)
                    result.is_valid = False
                    all_success = False
                else:
                    result.info.extend(resource_result.info)

            if result.is_valid and all_success:
                result.info.append(f"Database built successfully: {self.project.database}")

                # Generate and save Datasette metadata.json
                metadata = self.project.to_datasette_metadata()
                metadata_path = self.project_path / "metadata.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                result.info.append("Generated Datasette metadata: metadata.json")

        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Database build failed: {e}")

        return result

    def _sync_from_s3(self, local_db_path: Path) -> ValidationResult:
        """Download existing database from S3 if available.

        Args:
            local_db_path: Local path where database should be saved

        Returns:
            ValidationResult with sync results
        """
        result = ValidationResult(is_valid=True)

        try:
            # Import deployer here to avoid circular imports
            from .deployer import ZeekerDeployer

            deployer = ZeekerDeployer()
            database_name = local_db_path.stem  # Remove .db extension

            # Check if database exists on S3
            s3_key = f"latest/{database_name}.db"

            try:
                # Check if the object exists
                deployer.s3_client.head_object(Bucket=deployer.bucket_name, Key=s3_key)

                # Database exists on S3, download it
                deployer.s3_client.download_file(deployer.bucket_name, s3_key, str(local_db_path))
                result.info.append(f"Downloaded existing database from S3: {s3_key}")

            except deployer.s3_client.exceptions.NoSuchKey:
                # Database doesn't exist on S3 - this is fine for new projects
                result.info.append(f"No existing database found on S3 at {s3_key}")

        except ImportError:
            result.is_valid = False
            result.errors.append("S3 sync requires AWS credentials and boto3")
        except ValueError as e:
            result.is_valid = False
            result.errors.append(f"S3 configuration error: {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"S3 sync failed: {e}")

        return result

    def _process_resource_with_schema_check(
        self, db: sqlite_utils.Database, resource_name: str, force_schema_reset: bool, build_id: str
    ) -> ValidationResult:
        """Process a single resource with schema conflict detection and migration support.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource to process
            force_schema_reset: If True, ignore schema conflicts and rebuild
            build_id: Unique build identifier for tracking

        Returns:
            ValidationResult with processing results
        """
        result = ValidationResult(is_valid=True)
        start_time = time.time()

        resource_file = self.resources_path / f"{resource_name}.py"
        if not resource_file.exists():
            result.is_valid = False
            result.errors.append(f"Resource file not found: {resource_file}")
            return result

        try:
            # Dynamically import the resource module
            spec = importlib.util.spec_from_file_location(resource_name, resource_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the fetch_data function
            if not hasattr(module, "fetch_data"):
                result.is_valid = False
                result.errors.append(f"Resource '{resource_name}' missing fetch_data() function")
                return result

            fetch_data = getattr(module, "fetch_data")

            # Check for existing table and schema conflicts
            existing_table = db[resource_name] if db[resource_name].exists() else None

            if existing_table and not force_schema_reset:
                # Check for schema conflicts
                try:
                    sample_data = fetch_data(existing_table)[:5]  # Small sample for schema check
                    if sample_data:
                        schema_result = self.schema_manager.check_schema_conflicts(
                            db, resource_name, sample_data, module
                        )
                        result.info.extend(schema_result.info)
                except Exception as e:
                    if isinstance(e, ZeekerSchemaConflictError):
                        raise
                    # If we can't get sample data, proceed with build
                    pass

            # Process the resource
            resource_result = self._process_resource(db, resource_name)
            if not resource_result.is_valid:
                result.errors.extend(resource_result.errors)
                result.is_valid = False
            else:
                result.info.extend(resource_result.info)

                # Check if this is a fragments resource and process fragments
                resource_config = self.project.resources.get(resource_name, {})
                is_fragments_enabled = resource_config.get("fragments", False)

                if is_fragments_enabled:
                    if not hasattr(module, "fetch_fragments_data"):
                        result.is_valid = False
                        result.errors.append(
                            f"Resource '{resource_name}' is configured with fragments=true "
                            f"but missing fetch_fragments_data() function"
                        )
                    else:
                        fragments_result = self._process_fragments_data(db, resource_name, module)
                        if not fragments_result.is_valid:
                            result.errors.extend(fragments_result.errors)
                            result.is_valid = False
                        else:
                            result.info.extend(fragments_result.info)
                elif hasattr(module, "fetch_fragments_data"):
                    # Resource has fragments function but not configured as fragments-enabled
                    # This is okay - just process the fragments silently
                    fragments_result = self._process_fragments_data(db, resource_name, module)
                    if not fragments_result.is_valid:
                        result.errors.extend(fragments_result.errors)
                        result.is_valid = False
                    else:
                        result.info.extend(fragments_result.info)

                # Update timestamps
                duration_ms = int((time.time() - start_time) * 1000)
                self.schema_manager.update_resource_timestamps(db, resource_name, build_id, duration_ms)

        except ZeekerSchemaConflictError as e:
            result.is_valid = False
            result.errors.append(str(e))
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to process resource '{resource_name}': {e}")

        return result

    def _process_resource(self, db: sqlite_utils.Database, resource_name: str) -> ValidationResult:
        """Process a single resource using sqlite-utils for robust data insertion.

        Benefits of sqlite-utils over raw SQL:
        - Automatic table creation with correct schema
        - Type inference from data (no manual column type guessing)
        - JSON support for complex data structures
        - Proper error handling and validation
        - No SQL injection risks
        """
        result = ValidationResult(is_valid=True)

        resource_file = self.resources_path / f"{resource_name}.py"
        if not resource_file.exists():
            result.is_valid = False
            result.errors.append(f"Resource file not found: {resource_file}")
            return result

        try:
            # Dynamically import the resource module
            spec = importlib.util.spec_from_file_location(resource_name, resource_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the fetch_data function
            if not hasattr(module, "fetch_data"):
                result.is_valid = False
                result.errors.append(f"Resource '{resource_name}' missing fetch_data() function")
                return result

            fetch_data = getattr(module, "fetch_data")

            # Check if table already exists to pass to fetch_data
            existing_table = db[resource_name] if db[resource_name].exists() else None

            # Fetch the data
            raw_data = fetch_data(existing_table)

            if not isinstance(raw_data, list):
                result.is_valid = False
                result.errors.append(f"fetch_data() in '{resource_name}' must return a list")
                return result

            if not raw_data:
                result.info.append(f"No data returned for resource '{resource_name}' - skipping")
                return result

            # Apply transformation if available
            if hasattr(module, "transform_data"):
                transform_data = getattr(module, "transform_data")
                transformed_data = transform_data(raw_data)
            else:
                transformed_data = raw_data

            # Validate transformed data structure
            if not isinstance(transformed_data, list):
                result.is_valid = False
                result.errors.append(f"transform_data() in '{resource_name}' must return a list")
                return result

            if not all(isinstance(item, dict) for item in transformed_data):
                result.is_valid = False
                result.errors.append(f"All items in '{resource_name}' data must be dictionaries")
                return result

            # Insert data using sqlite-utils (handles table creation automatically)
            table = db[resource_name]

            # Track schema for conflict detection
            if not existing_table:  # New table
                self.schema_manager.track_new_table_schema(db, resource_name, transformed_data)

            # Insert all records at once for better performance
            table.insert_all(transformed_data, replace=False)

            result.info.append(
                f"Processed {len(transformed_data)} records for resource '{resource_name}'"
            )

        except sqlite3.IntegrityError as e:
            result.is_valid = False
            result.errors.append(f"Database integrity error in '{resource_name}': {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to process resource '{resource_name}': {e}")

        return result

    def _process_fragments_data(
        self, db: sqlite_utils.Database, resource_name: str, module
    ) -> ValidationResult:
        """Process fragments data for a resource that supports document fragmentation.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the main resource
            module: The imported resource module

        Returns:
            ValidationResult with processing results
        """
        result = ValidationResult(is_valid=True)
        fragments_table_name = f"{resource_name}_fragments"

        try:
            if not hasattr(module, "fetch_fragments_data"):
                result.is_valid = False
                result.errors.append(
                    f"Resource '{resource_name}' missing fetch_fragments_data() function"
                )
                return result

            fetch_fragments_data = getattr(module, "fetch_fragments_data")

            # Check if fragments table already exists
            existing_fragments_table = (
                db[fragments_table_name] if db[fragments_table_name].exists() else None
            )

            # Fetch fragments data
            raw_fragments = fetch_fragments_data(existing_fragments_table)

            if not isinstance(raw_fragments, list):
                result.is_valid = False
                result.errors.append(
                    f"fetch_fragments_data() in '{resource_name}' must return a list"
                )
                return result

            if not raw_fragments:
                result.info.append(f"No fragments data for '{resource_name}' - skipping")
                return result

            # Apply transformation if available
            if hasattr(module, "transform_fragments_data"):
                transform_fragments_data = getattr(module, "transform_fragments_data")
                transformed_fragments = transform_fragments_data(raw_fragments)
            else:
                transformed_fragments = raw_fragments

            # Validate fragments data structure
            if not isinstance(transformed_fragments, list):
                result.is_valid = False
                result.errors.append(
                    f"transform_fragments_data() in '{resource_name}' must return a list"
                )
                return result

            if not all(isinstance(item, dict) for item in transformed_fragments):
                result.is_valid = False
                result.errors.append(
                    f"All items in '{resource_name}' fragments data must be dictionaries"
                )
                return result

            # Insert fragments data using sqlite-utils
            fragments_table = db[fragments_table_name]

            # Track schema for conflict detection
            if not existing_fragments_table:  # New table
                self.schema_manager.track_new_table_schema(db, fragments_table_name, transformed_fragments)

            # Insert all fragments at once for better performance
            fragments_table.insert_all(transformed_fragments, replace=False)

            result.info.append(
                f"Processed {len(transformed_fragments)} fragments for resource '{resource_name}'"
            )

        except sqlite3.IntegrityError as e:
            result.is_valid = False
            result.errors.append(f"Database integrity error in '{resource_name}' fragments: {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to process fragments for '{resource_name}': {e}")

        return result

