"""
Project management for Zeeker projects.
"""

import importlib.util
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import sqlite_utils

from typing import Dict, Optional

from .types import (
    ValidationResult,
    ZeekerProject,
    ZeekerSchemaConflictError,
    META_TABLE_SCHEMAS,
    META_TABLE_UPDATES,
    calculate_schema_hash,
    extract_table_schema,
)


class ZeekerProjectManager:
    """Manages Zeeker projects and resources."""

    def __init__(self, project_path: Path = None):
        self.project_path = project_path or Path.cwd()
        self.toml_path = self.project_path / "zeeker.toml"
        self.resources_path = self.project_path / "resources"

    def is_project_root(self) -> bool:
        """Check if current directory is a Zeeker project root."""
        return self.toml_path.exists()

    def init_project(self, project_name: str) -> ValidationResult:
        """Initialize a new Zeeker project."""
        result = ValidationResult(is_valid=True)

        # Create project directory if it doesn't exist
        self.project_path.mkdir(exist_ok=True)

        # Check if already a project
        if self.toml_path.exists():
            result.is_valid = False
            result.errors.append("Directory already contains zeeker.toml")
            return result

        # Create basic project structure
        project = ZeekerProject(name=project_name, database=f"{project_name}.db")

        # Save zeeker.toml
        project.save_toml(self.toml_path)

        # Create resources package
        self.resources_path.mkdir(exist_ok=True)
        init_file = self.resources_path / "__init__.py"
        init_file.write_text('"""Resources package for data fetching."""\n')

        # Create .gitignore
        gitignore_content = """# Generated database
*.db

# Python
__pycache__/
*.pyc
*.pyo
.venv/
.env

# Data files (uncomment if you want to ignore data directory)
# data/
# raw/

# OS
.DS_Store
Thumbs.db
"""
        gitignore_path = self.project_path / ".gitignore"
        gitignore_path.write_text(gitignore_content)

        # Create README.md
        readme_content = f"""# {project_name.title()} Database Project

A Zeeker project for managing the {project_name} database.

## Getting Started

1. Add resources:
   ```bash
   zeeker add my_resource --description "Description of the resource"
   ```

2. Implement data fetching in `resources/my_resource.py`

3. Build the database:
   ```bash
   zeeker build
   ```

4. Deploy to S3:
   ```bash
   zeeker deploy
   ```

## Project Structure

- `zeeker.toml` - Project configuration
- `resources/` - Python modules for data fetching
- `{project_name}.db` - Generated SQLite database (gitignored)

## Resources

"""

        readme_path = self.project_path / "README.md"
        readme_path.write_text(readme_content)

        # Create project-specific CLAUDE.md
        claude_content = f"""# CLAUDE.md - {project_name.title()} Project Development Guide

This file provides Claude Code with project-specific context and guidance for developing this project.

## Project Overview

**Project Name:** {project_name}
**Database:** {project_name}.db
**Purpose:** Database project for {project_name} data management

## Development Commands

### Quick Commands
- `uv run zeeker add RESOURCE_NAME` - Add new resource to this project
- `uv run zeeker build` - Build database from all resources in this project
- `uv run zeeker deploy` - Deploy this project's database to S3

### Testing This Project
- `uv run pytest` - Run tests (if added to project)
- Check generated `{project_name}.db` after build
- Verify metadata.json structure

## Resources in This Project

*Resources will be documented here as you add them with `zeeker add`*

## Schema Notes for This Project

### Important Schema Decisions
- Document any project-specific schema choices here
- Note field types that are critical for this project's data
- Record any special data handling requirements

### Common Schema Issues to Watch
- **Dates:** Use ISO format strings like "2024-01-15" 
- **Numbers:** Use float for prices/scores that might have decimals
- **IDs:** Use int for primary keys, str for external system IDs
- **JSON data:** Use dict/list types for complex data structures

## Project-Specific Notes

### Data Sources
- Document where this project's data comes from
- Note any API endpoints, file formats, or data constraints
- Record update frequencies and data refresh patterns

### Business Logic
- Document any special business rules for this project
- Note relationships between resources
- Record any data validation requirements

### Deployment Notes
- Any special S3 configuration for this project
- Environment variables specific to this project
- Deployment schedules or constraints

## Team Notes

*Use this section for team-specific development notes, decisions, or reminders*

---

This file is automatically created by Zeeker and can be customized for your project's needs.
The main Zeeker development guide is in the repository root CLAUDE.md file.
"""

        claude_path = self.project_path / "CLAUDE.md"
        claude_path.write_text(claude_content)

        result.info.append(f"Initialized Zeeker project '{project_name}'")

        # FIXED: Handle relative path safely
        try:
            relative_toml = self.toml_path.relative_to(Path.cwd())
            result.info.append(f"Created: {relative_toml}")
        except ValueError:
            # If not in subpath of cwd, just use filename
            result.info.append(f"Created: {self.toml_path.name}")

        try:
            relative_resources = self.resources_path.relative_to(Path.cwd())
            result.info.append(f"Created: {relative_resources}/")
        except ValueError:
            result.info.append(f"Created: {self.resources_path.name}/")

        try:
            relative_gitignore = gitignore_path.relative_to(Path.cwd())
            result.info.append(f"Created: {relative_gitignore}")
        except ValueError:
            result.info.append(f"Created: {gitignore_path.name}")

        try:
            relative_readme = readme_path.relative_to(Path.cwd())
            result.info.append(f"Created: {relative_readme}")
        except ValueError:
            result.info.append(f"Created: {readme_path.name}")

        try:
            relative_claude = claude_path.relative_to(Path.cwd())
            result.info.append(f"Created: {relative_claude}")
        except ValueError:
            result.info.append(f"Created: {claude_path.name}")

        return result

    def _update_project_claude_md(self, project: ZeekerProject) -> None:
        """Update the project's CLAUDE.md with current resource information."""
        claude_path = self.project_path / "CLAUDE.md"

        if not claude_path.exists():
            return  # No CLAUDE.md to update

        # Read existing CLAUDE.md
        existing_content = claude_path.read_text()

        # Generate resource documentation
        resource_docs = ""
        if project.resources:
            resource_docs = "## Resources in This Project\n\n"
            for resource_name, resource_config in project.resources.items():
                description = resource_config.get(
                    "description", f"{resource_name.replace('_', ' ').title()} data"
                )
                resource_docs += f"### `{resource_name}` Resource\n"
                resource_docs += f"- **Description:** {description}\n"
                resource_docs += f"- **File:** `resources/{resource_name}.py`\n"

                # Add any Datasette configuration
                if "facets" in resource_config:
                    resource_docs += f"- **Facets:** {', '.join(resource_config['facets'])}\n"
                if "sort" in resource_config:
                    resource_docs += f"- **Default Sort:** {resource_config['sort']}\n"
                if "size" in resource_config:
                    resource_docs += f"- **Page Size:** {resource_config['size']}\n"

                resource_docs += f"- **Schema:** Check `resources/{resource_name}.py` fetch_data() for current schema\n"
                resource_docs += "\n"
        else:
            resource_docs = "## Resources in This Project\n\n*No resources added yet. Use `zeeker add RESOURCE_NAME` to add resources.*\n\n"

        # Replace the resources section
        import re

        pattern = r"(## Resources in This Project\n\n).*?(?=\n## |\n---|\Z)"
        if re.search(pattern, existing_content, re.DOTALL):
            updated_content = re.sub(pattern, resource_docs, existing_content, flags=re.DOTALL)
        else:
            # If section doesn't exist, add it before Schema Notes
            schema_pattern = r"(## Schema Notes for This Project)"
            if re.search(schema_pattern, existing_content):
                updated_content = re.sub(schema_pattern, resource_docs + r"\1", existing_content)
            else:
                # Fallback: add before the end
                updated_content = existing_content.replace(
                    "## Team Notes", resource_docs + "## Team Notes"
                )

        claude_path.write_text(updated_content)

    def load_project(self) -> ZeekerProject:
        """Load project configuration."""
        if not self.is_project_root():
            raise ValueError("Not a Zeeker project (no zeeker.toml found)")
        return ZeekerProject.from_toml(self.toml_path)

    def add_resource(
        self, resource_name: str, description: str = None, **kwargs
    ) -> ValidationResult:
        """Add a new resource to the project."""
        result = ValidationResult(is_valid=True)

        if not self.is_project_root():
            result.is_valid = False
            result.errors.append("Not in a Zeeker project directory (no zeeker.toml found)")
            return result

        # Load existing project
        project = self.load_project()

        # Check if resource already exists
        resource_file = self.resources_path / f"{resource_name}.py"
        if resource_file.exists():
            result.is_valid = False
            result.errors.append(f"Resource '{resource_name}' already exists")
            return result

        # Generate resource file
        template = self._generate_resource_template(resource_name)
        resource_file.write_text(template)

        # Update project config with resource metadata
        resource_config = {
            "description": description or f"{resource_name.replace('_', ' ').title()} data"
        }

        # Add any additional Datasette metadata passed via kwargs
        datasette_fields = [
            "facets",
            "sort",
            "size",
            "sortable_columns",
            "hidden",
            "label_column",
            "columns",
            "units",
            "description_html",
        ]
        for field in datasette_fields:
            if field in kwargs:
                resource_config[field] = kwargs[field]

        project.resources[resource_name] = resource_config
        project.save_toml(self.toml_path)

        # Update project CLAUDE.md with new resource information
        self._update_project_claude_md(project)

        try:
            relative_resource = resource_file.relative_to(Path.cwd())
            result.info.append(f"Created resource: {relative_resource}")
        except ValueError:
            result.info.append(f"Created resource: {resource_file.name}")

        try:
            relative_toml = self.toml_path.relative_to(Path.cwd())
            result.info.append(f"Updated: {relative_toml}")
        except ValueError:
            result.info.append(f"Updated: {self.toml_path.name}")

        # Add info about CLAUDE.md update if it exists
        claude_path = self.project_path / "CLAUDE.md"
        if claude_path.exists():
            try:
                relative_claude = claude_path.relative_to(Path.cwd())
                result.info.append(f"Updated: {relative_claude}")
            except ValueError:
                result.info.append(f"Updated: {claude_path.name}")

        return result

    def _generate_resource_template(self, resource_name: str) -> str:
        """Generate a Python template for a resource."""
        return f'''"""
{resource_name.replace('_', ' ').title()} resource for fetching and processing data.

This module should implement a fetch_data() function that returns
a list of dictionaries to be inserted into the '{resource_name}' table.

The database is built using sqlite-utils, which provides:
• Automatic table creation from your data structure
• Type inference (integers → INTEGER, floats → REAL, strings → TEXT)
• JSON support for complex data (lists, dicts stored as JSON)
• Safe data insertion without SQL injection risks
"""

def fetch_data(existing_table):
    """
    Fetch data for the {resource_name} table.

    Args:
        existing_table: sqlite-utils Table object if table exists, None for new table
                       Use this to check for existing data and avoid duplicates

    Returns:
        List[Dict[str, Any]]: List of records to insert into database

    IMPORTANT - Schema Considerations:
    Your FIRST fetch_data() call determines the column types permanently!
    sqlite-utils infers types from the first ~100 records and locks them in.
    Later runs cannot change existing column types, only add new columns.

    Python Type → SQLite Column Type:
    • int          → INTEGER  
    • float        → REAL
    • str          → TEXT
    • bool         → INTEGER (stored as 0/1)
    • dict/list    → TEXT (stored as JSON)
    • None values  → Can cause type inference issues

    Best Practices:
    1. Make sure your first batch has correct Python types
    2. Use consistent data types across all records
    3. Avoid None/null values in key columns on first run
    4. Use float (not int) for numbers that might have decimals later

    Example usage:
        if existing_table:
            # Table exists - check for duplicates and fetch incremental data
            existing_ids = {{row["id"] for row in existing_table.rows}}
            new_data = fetch_from_api()  # Your data source
            return [record for record in new_data if record["id"] not in existing_ids]
        else:
            # Fresh table - CRITICAL: Set schema correctly with first batch!
            return [
                {{"id": 1, "name": "Example", "created": "2024-01-01"}},
                {{"id": 2, "name": "Another", "created": "2024-01-02"}},
            ]
    """
    # TODO: Implement your data fetching logic here
    # This could be:
    # - API calls (requests.get, etc.)
    # - File reading (CSV, JSON, XML, etc.)
    # - Database queries (from other sources)
    # - Web scraping (BeautifulSoup, Scrapy, etc.)
    # - Any other data source

    return [
        # Example data showing proper types for schema inference:
        {{
            "id": 1,                           # int → INTEGER (good for primary keys)
            "title": "Example Title",          # str → TEXT
            "score": 85.5,                     # float → REAL (use float even for whole numbers!)
            "view_count": 100,                 # int → INTEGER 
            "is_published": True,              # bool → INTEGER (0/1)
            "created_date": "2024-01-15",      # str → TEXT (ISO date format recommended)
            "tags": ["news", "technology"],    # list → TEXT (stored as JSON)
            "metadata": {{"priority": "high"}}, # dict → TEXT (stored as JSON)
        }},
        # Add more example records with same structure...
    ]


def transform_data(raw_data):
    """
    Optional: Transform/clean the raw data before database insertion.

    Args:
        raw_data: The data returned from fetch_data()

    Returns:
        List[Dict[str, Any]]: Transformed data

    Examples:
        # Clean strings
        for item in raw_data:
            item['name'] = item['name'].strip().title()

        # Parse dates
        for item in raw_data:
            item['created_date'] = datetime.fromisoformat(item['date_string'])

        # Handle complex data (sqlite-utils stores as JSON)
        for item in raw_data:
            item['metadata'] = {{"tags": ["news", "tech"], "priority": 1}}
    """
    # Optional transformation logic
    return raw_data


# You can add additional helper functions here
'''

    def build_database(self, force_schema_reset: bool = False) -> ValidationResult:
        """Build the SQLite database from all resources using sqlite-utils.

        Uses Simon Willison's sqlite-utils for robust table creation and data insertion:
        - Automatic schema detection from data
        - Proper type inference (INTEGER, TEXT, REAL)
        - Safe table creation and data insertion
        - Better error handling than raw SQL
        """
        result = ValidationResult(is_valid=True)

        if not self.is_project_root():
            result.is_valid = False
            result.errors.append("Not in a Zeeker project directory")
            return result

        project = self.load_project()
        db_path = self.project_path / project.database

        # Open existing database or create new one using sqlite-utils
        # Don't delete existing database - let resources check existing data for duplicates
        #
        # TODO: S3 Database Synchronization Gap
        # Currently this only works with local databases. The incremental update mechanism
        # (existing_table parameter) works perfectly locally but does NOT sync with S3.
        #
        # Issues:
        # - Running 'zeeker build' on different machines starts fresh (ignores S3 database)
        # - Can lead to data duplication when resources don't handle duplicates properly
        # - No way to continue incremental updates after switching machines/environments
        #
        # Potential solutions:
        # 1. Pre-build S3 sync: Download existing database from S3 before building
        # 2. Smart deployment: Check if local DB is newer than S3 version
        # 3. Backup/conflict resolution: Handle cases where both local and S3 have changes
        # 4. Optional flag: --sync-from-s3 to explicitly download before building
        #
        # This would require integration with ZeekerDeployer to download databases
        # and proper conflict resolution strategies.
        db = sqlite_utils.Database(str(db_path))

        try:
            # Initialize meta tables
            self._ensure_meta_tables(db)
            build_id = self._generate_build_id()

            all_success = True
            for resource_name in project.resources.keys():
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
                result.info.append(f"Database built successfully: {project.database}")

                # Generate and save Datasette metadata.json
                metadata = project.to_datasette_metadata()
                metadata_path = self.project_path / "metadata.json"
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                result.info.append("Generated Datasette metadata: metadata.json")

        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Database build failed: {e}")

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

            # Fetch data - pass existing table if it exists for duplicate checking
            existing_table = db[resource_name] if db[resource_name].exists() else None
            raw_data = module.fetch_data(existing_table)

            # Optional transformation
            if hasattr(module, "transform_data"):
                data = module.transform_data(raw_data)
            else:
                data = raw_data

            if not data:
                result.warnings.append(f"Resource '{resource_name}' returned no data")
                return result

            # Validate data structure
            if not isinstance(data, list):
                result.is_valid = False
                result.errors.append(
                    f"Resource '{resource_name}' must return a list of dictionaries, got: {type(data)}"
                )
                return result

            if not all(isinstance(record, dict) for record in data):
                result.is_valid = False
                result.errors.append(
                    f"Resource '{resource_name}' must return a list of dictionaries"
                )
                return result

            # Use sqlite-utils for robust table creation and data insertion
            # alter=True: Automatically add new columns if schema changes
            # replace=True: Replace existing data (fresh rebuild)
            db[resource_name].insert_all(
                data,
                alter=True,  # Auto-add columns if schema changes
                replace=True,  # Replace existing data for clean rebuild
            )

            result.info.append(f"Processed {len(data)} records for table '{resource_name}'")

        except sqlite3.IntegrityError as e:
            result.is_valid = False
            result.errors.append(f"Database integrity error in '{resource_name}': {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Error processing resource '{resource_name}': {e}")

        return result

    def _ensure_meta_tables(self, db: sqlite_utils.Database) -> None:
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

    def _generate_build_id(self) -> str:
        """Generate unique build ID for tracking builds.

        Returns:
            Unique build identifier string
        """
        return f"build_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _get_stored_schema(
        self, db: sqlite_utils.Database, resource_name: str
    ) -> Optional[Dict[str, str]]:
        """Get stored schema information for a resource.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource

        Returns:
            Dictionary of stored schema info or None if not found
        """
        try:
            if not db[META_TABLE_SCHEMAS].exists():
                return None

            row = db[META_TABLE_SCHEMAS].get(resource_name)
            return {
                "schema_hash": row["schema_hash"],
                "schema_version": row["schema_version"],
                "column_definitions": json.loads(row["column_definitions"]),
            }
        except (sqlite_utils.db.NotFoundError, json.JSONDecodeError, Exception):
            return None

    def _update_schema_tracking(
        self, db: sqlite_utils.Database, resource_name: str, column_definitions: Dict[str, str]
    ) -> None:
        """Update schema tracking information for a resource.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource
            column_definitions: Dictionary of column name -> type mappings
        """
        schema_hash = calculate_schema_hash(column_definitions)
        now = datetime.now().isoformat()

        # Check if schema already exists
        existing = self._get_stored_schema(db, resource_name)

        if existing is None:
            # New schema
            db[META_TABLE_SCHEMAS].insert(
                {
                    "resource_name": resource_name,
                    "schema_version": 1,
                    "schema_hash": schema_hash,
                    "column_definitions": json.dumps(column_definitions, sort_keys=True),
                    "created_at": now,
                    "updated_at": now,
                },
                replace=True,
            )
        elif existing["schema_hash"] != schema_hash:
            # Schema changed - increment version
            db[META_TABLE_SCHEMAS].update(
                resource_name,
                {
                    "schema_version": existing["schema_version"] + 1,
                    "schema_hash": schema_hash,
                    "column_definitions": json.dumps(column_definitions, sort_keys=True),
                    "updated_at": now,
                },
            )
        # If schema hash matches, no update needed

    def _update_resource_timestamps(
        self, db: sqlite_utils.Database, resource_name: str, build_id: str, duration_ms: int
    ) -> None:
        """Update resource timestamp tracking.

        Args:
            db: sqlite-utils Database instance
            resource_name: Name of the resource
            build_id: Unique build identifier
            duration_ms: Processing time in milliseconds
        """
        record_count = db[resource_name].count if db[resource_name].exists() else 0

        db[META_TABLE_UPDATES].insert(
            {
                "resource_name": resource_name,
                "last_updated": datetime.now().isoformat(),
                "record_count": record_count,
                "build_id": build_id,
                "duration_ms": duration_ms,
            },
            replace=True,
        )

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

            # Fetch data - pass existing table if it exists for duplicate checking
            existing_table = db[resource_name] if db[resource_name].exists() else None
            raw_data = module.fetch_data(existing_table)

            # Optional transformation
            if hasattr(module, "transform_data"):
                data = module.transform_data(raw_data)
            else:
                data = raw_data

            if not data:
                result.warnings.append(f"Resource '{resource_name}' returned no data")
                return result

            # Validate data structure
            if not isinstance(data, list):
                result.is_valid = False
                result.errors.append(
                    f"Resource '{resource_name}' must return a list of dictionaries, got: {type(data)}"
                )
                return result

            if not all(isinstance(record, dict) for record in data):
                result.is_valid = False
                result.errors.append(
                    f"Resource '{resource_name}' must return a list of dictionaries"
                )
                return result

            # Schema conflict detection and migration handling
            if not force_schema_reset and existing_table is not None:
                # Get the current schema by creating a temporary table with the new data
                temp_table_name = f"_temp_{resource_name}_{int(time.time())}"
                db[temp_table_name].insert_all(data[:1])  # Use first record to detect schema
                new_schema = extract_table_schema(db[temp_table_name])
                db[temp_table_name].drop()  # Clean up temp table

                # Compare with stored schema
                stored_schema = self._get_stored_schema(db, resource_name)
                if stored_schema is not None:
                    new_hash = calculate_schema_hash(new_schema)
                    if stored_schema["schema_hash"] != new_hash:
                        # Schema conflict detected
                        old_schema = stored_schema["column_definitions"]

                        # Check for migration handler
                        if hasattr(module, "migrate_schema"):
                            try:
                                migration_result = module.migrate_schema(existing_table, new_schema)
                                if not migration_result:
                                    raise ZeekerSchemaConflictError(
                                        resource_name, old_schema, new_schema
                                    )
                            except Exception as e:
                                result.is_valid = False
                                result.errors.append(f"Migration failed for '{resource_name}': {e}")
                                return result
                        else:
                            # No migration handler - raise conflict error
                            raise ZeekerSchemaConflictError(resource_name, old_schema, new_schema)

            # Process the data using existing sqlite-utils logic
            db[resource_name].insert_all(
                data,
                alter=True,  # Auto-add columns if schema changes
                replace=True,  # Replace existing data for clean rebuild
            )

            # Update meta tables with schema and timestamp tracking
            final_schema = extract_table_schema(db[resource_name])
            self._update_schema_tracking(db, resource_name, final_schema)

            duration_ms = int((time.time() - start_time) * 1000)
            self._update_resource_timestamps(db, resource_name, build_id, duration_ms)

            result.info.append(f"Processed {len(data)} records for table '{resource_name}'")

        except ZeekerSchemaConflictError:
            # Re-raise schema conflicts without wrapping
            raise
        except sqlite3.IntegrityError as e:
            result.is_valid = False
            result.errors.append(f"Database integrity error in '{resource_name}': {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Error processing resource '{resource_name}': {e}")

        return result
