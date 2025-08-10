"""
Core data types and structures for Zeeker.
"""

import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Meta table constants
META_TABLE_SCHEMAS = "_zeeker_schemas"
META_TABLE_UPDATES = "_zeeker_updates"
META_TABLE_NAMES = [META_TABLE_SCHEMAS, META_TABLE_UPDATES]


class ZeekerSchemaConflictError(Exception):
    """Raised when schema changes detected without migration handler."""

    def __init__(self, resource_name: str, old_schema: dict[str, str], new_schema: dict[str, str]):
        self.resource_name = resource_name
        self.old_schema = old_schema
        self.new_schema = new_schema

        # Find schema differences for helpful error message
        old_cols = set(old_schema.keys())
        new_cols = set(new_schema.keys())
        added_cols = new_cols - old_cols
        removed_cols = old_cols - new_cols
        changed_types = {
            col: (old_schema[col], new_schema[col])
            for col in old_cols & new_cols
            if old_schema[col] != new_schema[col]
        }

        msg_parts = [f"Schema conflict detected for resource '{resource_name}'."]

        if added_cols:
            msg_parts.append(f"Added columns: {', '.join(sorted(added_cols))}")
        if removed_cols:
            msg_parts.append(f"Removed columns: {', '.join(sorted(removed_cols))}")
        if changed_types:
            for col, (old_type, new_type) in changed_types.items():
                msg_parts.append(f"Changed '{col}': {old_type} → {new_type}")

        msg_parts.extend(
            [
                "",
                "To resolve this conflict:",
                f"1. Add migrate_schema() function to resources/{resource_name}.py",
                "2. Or delete the database file to rebuild from scratch",
                "3. Or use --force-schema-reset flag",
            ]
        )

        super().__init__("\n".join(msg_parts))


@dataclass
class ValidationResult:
    """Result of validation operations."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)


@dataclass
class DatabaseCustomization:
    """Represents a complete database customization."""

    database_name: str
    base_path: Path
    templates: dict[str, str] = field(default_factory=dict)
    static_files: dict[str, bytes] = field(default_factory=dict)
    metadata: dict[str, Any] | None = None


@dataclass
class DeploymentChanges:
    """Represents the changes to be made during deployment."""

    uploads: list[str] = field(default_factory=list)
    updates: list[str] = field(default_factory=list)
    deletions: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.uploads or self.updates or self.deletions)

    @property
    def has_destructive_changes(self) -> bool:
        return bool(self.deletions)


@dataclass
class ZeekerProject:
    """Represents a Zeeker project configuration."""

    name: str
    database: str
    resources: dict[str, dict[str, Any]] = field(default_factory=dict)
    root_path: Path = field(default_factory=Path)

    @classmethod
    def from_toml(cls, toml_path: Path) -> "ZeekerProject":
        """Load project from zeeker.toml file."""

        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        project_data = data.get("project", {})

        # Extract resource sections (resource.*)
        resources = data.get("resource", {})

        return cls(
            name=project_data.get("name", ""),
            database=project_data.get("database", ""),
            resources=resources,
            root_path=toml_path.parent,
        )

    def save_toml(self, toml_path: Path) -> None:
        """Save project to zeeker.toml file."""
        toml_content = f"""[project]
name = "{self.name}"
database = "{self.database}"

"""
        for resource_name, resource_config in self.resources.items():
            toml_content += f"[resource.{resource_name}]\n"
            for key, value in resource_config.items():
                if isinstance(value, str):
                    toml_content += f'{key} = "{value}"\n'
                elif isinstance(value, list):
                    # Format arrays nicely
                    formatted_list = "[" + ", ".join(f'"{item}"' for item in value) + "]"
                    toml_content += f"{key} = {formatted_list}\n"
                elif isinstance(value, bool):
                    toml_content += f"{key} = {str(value).lower()}\n"
                elif isinstance(value, (int, float)):
                    toml_content += f"{key} = {value}\n"
            toml_content += "\n"

        with open(toml_path, "w", encoding="utf-8") as f:
            f.write(toml_content)

    def to_datasette_metadata(self) -> dict[str, Any]:
        """Convert project configuration to complete Datasette metadata.json format.

        Follows the guide: must provide complete Datasette metadata structure,
        not fragments. Includes proper CSS/JS URL patterns.
        """
        # Database name for S3 path (matches .db filename without extension)
        db_name = Path(self.database).stem

        metadata = {
            "title": f"{self.name.replace('_', ' ').replace('-', ' ').title()} Database",
            "description": f"Database for {self.name} project",
            "license": "MIT",
            "license_url": "https://opensource.org/licenses/MIT",
            "source": f"{self.name} project",
            "extra_css_urls": [f"/static/databases/{db_name}/custom.css"],
            "extra_js_urls": [f"/static/databases/{db_name}/custom.js"],
            "databases": {
                db_name: {
                    "description": f"Database for {self.name} project",
                    "title": f"{self.name.replace('_', ' ').replace('-', ' ').title()}",
                    "tables": {},
                }
            },
        }

        # Add table metadata from resource configurations
        for resource_name, resource_config in self.resources.items():
            table_metadata = {}

            # Copy Datasette-specific fields
            datasette_fields = [
                "description",
                "description_html",
                "facets",
                "sort",
                "size",
                "sortable_columns",
                "hidden",
                "label_column",
                "columns",
                "units",
            ]

            for field_name in datasette_fields:
                if field_name in resource_config:
                    table_metadata[field_name] = resource_config[field_name]

            # Default description if not provided
            if "description" not in table_metadata:
                table_metadata["description"] = resource_config.get(
                    "description", f"{resource_name.replace('_', ' ').title()} data"
                )

            metadata["databases"][db_name]["tables"][resource_name] = table_metadata

        return metadata


def calculate_schema_hash(column_definitions: dict[str, str]) -> str:
    """Calculate a hash of table schema for change detection.

    Args:
        column_definitions: Dictionary of column_name -> column_type

    Returns:
        Hex string hash of the schema
    """
    # Sort columns for consistent hashing
    sorted_schema = json.dumps(column_definitions, sort_keys=True)
    return hashlib.sha256(sorted_schema.encode()).hexdigest()[:16]


def extract_table_schema(table) -> dict[str, str]:
    """Extract column definitions from a sqlite-utils Table.

    Args:
        table: sqlite-utils Table object

    Returns:
        Dictionary mapping column names to their types
    """
    return {col.name: col.type for col in table.columns}


def infer_schema_from_data(data: list[dict[str, Any]]) -> dict[str, str]:
    """Infer schema from a list of data records.

    Args:
        data: List of dictionary records

    Returns:
        Dictionary mapping column names to their inferred SQLite types
    """
    if not data:
        return {}

    # Get all columns from all records
    all_columns = set()
    for record in data:
        all_columns.update(record.keys())

    schema = {}
    for column in all_columns:
        # Look at values in this column to infer type
        values = [record.get(column) for record in data if column in record]
        non_null_values = [v for v in values if v is not None]

        if not non_null_values:
            schema[column] = "TEXT"  # Default for all NULL
            continue

        # Check types in order of specificity
        if all(isinstance(v, bool) for v in non_null_values):
            schema[column] = "INTEGER"  # bools stored as integers
        elif all(isinstance(v, int) for v in non_null_values):
            schema[column] = "INTEGER"
        elif all(isinstance(v, (int, float)) for v in non_null_values):
            schema[column] = "REAL"
        elif all(isinstance(v, (dict, list)) for v in non_null_values):
            schema[column] = "TEXT"  # JSON stored as text
        else:
            schema[column] = "TEXT"  # Default fallback

    return schema
