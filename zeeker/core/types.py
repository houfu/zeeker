"""
Core data types and structures for Zeeker.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class ValidationResult:
    """Result of validation operations."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: List[str] = field(default_factory=list)


@dataclass
class DatabaseCustomization:
    """Represents a complete database customization."""

    database_name: str
    base_path: Path
    templates: Dict[str, str] = field(default_factory=dict)
    static_files: Dict[str, bytes] = field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class DeploymentChanges:
    """Represents the changes to be made during deployment."""

    uploads: List[str] = field(default_factory=list)
    updates: List[str] = field(default_factory=list)
    deletions: List[str] = field(default_factory=list)
    unchanged: List[str] = field(default_factory=list)

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
    resources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
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
                elif isinstance(value, (int, float, bool)):
                    toml_content += f"{key} = {value}\n"
            toml_content += "\n"

        with open(toml_path, "w", encoding="utf-8") as f:
            f.write(toml_content)

    def to_datasette_metadata(self) -> Dict[str, Any]:
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

            for field in datasette_fields:
                if field in resource_config:
                    table_metadata[field] = resource_config[field]

            # Default description if not provided
            if "description" not in table_metadata:
                table_metadata["description"] = resource_config.get(
                    "description", f"{resource_name.replace('_', ' ').title()} data"
                )

            metadata["databases"][db_name]["tables"][resource_name] = table_metadata

        return metadata
