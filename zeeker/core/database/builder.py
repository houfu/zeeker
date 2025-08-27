"""
Main database builder for Zeeker projects.

This module orchestrates the database building process, coordinating
resource processing, schema management, and S3 synchronization.
"""

import time
from pathlib import Path

import sqlite_utils

from ..schema import SchemaManager
from ..types import ValidationResult, ZeekerProject, ZeekerSchemaConflictError
from .fts_processor import FTSProcessor
from .processor import ResourceProcessor
from .s3_sync import S3Synchronizer


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
        self.processor = ResourceProcessor(self.resources_path, self.schema_manager)
        self.s3_sync = S3Synchronizer()
        self.fts_processor = FTSProcessor(project)

    def build_database(
        self,
        force_schema_reset: bool = False,
        sync_from_s3: bool = False,
        resources: list[str] = None,
        setup_fts: bool = False,
    ) -> ValidationResult:
        """Build the SQLite database from resources using sqlite-utils.

        Uses Simon Willison's sqlite-utils for robust table creation and data insertion:
        - Automatic schema detection from data
        - Proper type inference (INTEGER, TEXT, REAL)
        - Safe table creation and data insertion
        - Better error handling than raw SQL

        Args:
            force_schema_reset: If True, ignore schema conflicts and rebuild
            sync_from_s3: If True, download existing database from S3 before building
            resources: List of specific resource names to build. If None, builds all resources.
            setup_fts: If True, set up full-text search indexes on configured fields

        Returns:
            ValidationResult with build results
        """
        result = ValidationResult(is_valid=True)
        db_path = self.project_path / self.project.database

        # S3 Database Synchronization - Download existing DB if requested
        if sync_from_s3:
            sync_result = self.s3_sync.sync_from_s3(self.project.database, db_path)
            if not sync_result.is_valid:
                result.errors.extend(sync_result.errors)
                # Don't fail build if S3 sync fails - just warn
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

            # Determine which resources to process
            resources_to_build = resources if resources else list(self.project.resources.keys())

            # Process each specified resource
            for resource_name in resources_to_build:
                resource_result = self._process_resource_with_schema_check(
                    db, resource_name, force_schema_reset, build_id
                )

                if not resource_result.is_valid:
                    result.errors.extend(resource_result.errors)
                    result.is_valid = False
                else:
                    result.info.extend(resource_result.info)

                    # Process fragments if enabled
                    resource_config = self.project.resources.get(resource_name, {})
                    is_fragments_enabled = resource_config.get("fragments", False)

                    if is_fragments_enabled:
                        fragments_result = self._process_fragments_for_resource(db, resource_name)
                        if not fragments_result.is_valid:
                            result.errors.extend(fragments_result.errors)
                            result.is_valid = False
                        else:
                            result.info.extend(fragments_result.info)

            # Set up FTS after all resources are processed (only if requested)
            if result.is_valid and setup_fts:
                fts_result = self.fts_processor.setup_fts_for_database(db, force_schema_reset)
                if not fts_result.is_valid:
                    result.errors.extend(fts_result.errors)
                    result.is_valid = False
                else:
                    result.info.extend(fts_result.info)
                    if fts_result.warnings:
                        result.warnings.extend(fts_result.warnings)
            elif result.is_valid and not setup_fts:
                result.info.append("Skipped FTS setup (use --setup-fts flag to enable)")

        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Database build failed: {e}")

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

        # Load resource module
        module_result = self.processor._load_resource_module(resource_name)
        if not module_result.is_valid:
            return module_result

        module = module_result.data

        try:
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
                    sample_data = self.processor.async_executor.call_fetch_data(
                        fetch_data, existing_table, resource_name=resource_name
                    )[
                        :5
                    ]  # Small sample for schema check
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
            resource_result = self.processor.process_resource(db, resource_name)
            if not resource_result.is_valid:
                result.errors.extend(resource_result.errors)
                result.is_valid = False
            else:
                result.info.extend(resource_result.info)

                # Update resource timestamps
                duration_ms = int((time.time() - start_time) * 1000)
                self.schema_manager.update_resource_timestamps(
                    db, resource_name, build_id, duration_ms
                )

        except ZeekerSchemaConflictError as e:
            result.is_valid = False
            result.errors.append(str(e))
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Failed to process resource '{resource_name}': {e}")

        return result

    def _process_fragments_for_resource(
        self, db: sqlite_utils.Database, resource_name: str
    ) -> ValidationResult:
        """Process fragments data for a fragments-enabled resource.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource

        Returns:
            ValidationResult with fragments processing results
        """
        result = ValidationResult(is_valid=True)

        # Load resource module
        module_result = self.processor._load_resource_module(resource_name)
        if not module_result.is_valid:
            return module_result

        module = module_result.data

        # Check if fragments function exists
        if not hasattr(module, "fetch_fragments_data"):
            result.is_valid = False
            result.errors.append(
                f"Resource '{resource_name}' is configured with fragments=true "
                f"but missing fetch_fragments_data() function"
            )
            return result

        # Get raw data from fetch_data for fragments context
        main_data_context = None
        try:
            fetch_data = getattr(module, "fetch_data")
            existing_table = db[resource_name] if db[resource_name].exists() else None
            main_data_context = self.processor.async_executor.call_fetch_data(
                fetch_data, existing_table, resource_name=resource_name
            )
        except Exception:
            # If we can't get context, fragments will work without it
            main_data_context = None

        # Process fragments
        fragments_result = self.processor.process_fragments_data(
            db, resource_name, module, main_data_context
        )
        if not fragments_result.is_valid:
            result.errors.extend(fragments_result.errors)
            result.is_valid = False
        else:
            result.info.extend(fragments_result.info)

        return result
