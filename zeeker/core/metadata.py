"""
Metadata generation for Zeeker projects.

This module handles automatic generation of column metadata by analyzing
database schemas and applying smart pattern matching to infer meaningful
column descriptions.
"""

import re
from pathlib import Path
from typing import Any, Dict

import sqlite_utils

from .types import ValidationResult, ZeekerProject, extract_table_schema


class MetadataGenerator:
    """Generates intelligent metadata for database columns and tables."""

    def __init__(self, project_path: Path):
        """Initialize metadata generator.

        Args:
            project_path: Path to the Zeeker project
        """
        self.project_path = project_path

        # Column name patterns for smart description generation
        self.EXACT_PATTERNS = {
            # Common identifiers
            "id": "Unique identifier",
            "uuid": "Unique identifier",
            "guid": "Unique identifier",
            # Names and titles
            "name": "Display name",
            "title": "Title or heading",
            "label": "Display label",
            "slug": "URL-friendly identifier",
            # Contact information
            "email": "Email address",
            "phone": "Phone number",
            "url": "Web URL",
            "website": "Website URL",
            # Content fields
            "description": "Description text",
            "summary": "Brief summary",
            "content": "Main content",
            "text": "Text content",
            "body": "Body text",
            "notes": "Additional notes",
            # Dates and times
            "created_at": "Creation timestamp",
            "updated_at": "Last update timestamp",
            "deleted_at": "Deletion timestamp",
            "published_at": "Publication timestamp",
            "date": "Date value",
            "time": "Time value",
            "timestamp": "Timestamp value",
            # Status and flags
            "status": "Status indicator",
            "state": "State value",
            "active": "Active status flag",
            "enabled": "Enabled status flag",
            "visible": "Visibility flag",
            "deleted": "Deletion flag",
            "archived": "Archive status flag",
            # Common business fields
            "price": "Price amount",
            "price_amount": "Price amount",
            "cost": "Cost amount",
            "amount": "Amount value",
            "quantity": "Quantity count",
            "count": "Total count",
            "total": "Total value",
            "score": "Numeric score",
            "rating": "Rating value",
            "rank": "Ranking position",
            "order": "Sort order",
            "position": "Position value",
            "priority": "Priority level",
            # Location fields
            "address": "Street address",
            "city": "City name",
            "state": "State or province",
            "country": "Country name",
            "zip": "ZIP/postal code",
            "postal_code": "Postal code",
            "latitude": "Latitude coordinate",
            "longitude": "Longitude coordinate",
        }

        # Regex patterns for flexible matching
        self.PATTERN_RULES = [
            # Foreign keys
            (r"^(.+)_id$", r"\1 reference ID"),
            (r"^(.+)_uuid$", r"\1 UUID reference"),
            # Boolean flags (keep original casing for simple words)
            (r"^is_(.+)$", r"Boolean: is \1"),
            (r"^has_(.+)$", r"Boolean: has \1"),
            (r"^can_(.+)$", r"Boolean: can \1"),
            (r"^should_(.+)$", r"Boolean: should \1"),
            # Date/time patterns
            (r"^(.+)_date$", r"\1 date"),
            (r"^(.+)_time$", r"\1 time"),
            (r"^(.+)_at$", r"\1 timestamp"),
            (r"^(.+)_on$", r"\1 date"),
            # Count/number patterns
            (r"^(.+)_count$", r"Count of \1"),
            (r"^(.+)_total$", r"Total \1"),
            (r"^(.+)_sum$", r"Sum of \1"),
            (r"^num_(.+)$", r"Number of \1"),
            # URL/link patterns
            (r"^(.+)_url$", r"\1 URL"),
            (r"^(.+)_link$", r"\1 link"),
            # Name variants
            (r"^(.+)_name$", r"\1 name"),
            (r"^(.+)_title$", r"\1 title"),
            # Type/kind patterns
            (r"^(.+)_type$", r"\1 type"),
            (r"^(.+)_kind$", r"\1 kind"),
            (r"^(.+)_category$", r"\1 category"),
        ]

        # Type-based fallback descriptions
        self.TYPE_FALLBACKS = {
            "INTEGER": "Numeric value",
            "TEXT": "Text content",
            "REAL": "Decimal number",
            "NUMERIC": "Numeric value",
            "BLOB": "Binary data",
            "JSON": "JSON data",
        }

    def generate_column_descriptions(self, table_schema: Dict[str, str]) -> Dict[str, str]:
        """Generate intelligent column descriptions based on schema.

        Args:
            table_schema: Dictionary of column_name -> column_type

        Returns:
            Dictionary of column_name -> description
        """
        descriptions = {}

        for column_name, column_type in table_schema.items():
            description = self._generate_single_description(column_name, column_type)
            descriptions[column_name] = description

        return descriptions

    def _generate_single_description(self, column_name: str, column_type: str) -> str:
        """Generate description for a single column.

        Args:
            column_name: Name of the column
            column_type: SQLite type of the column

        Returns:
            Generated description string
        """
        # Check exact matches first (case insensitive)
        lower_name = column_name.lower()
        if lower_name in self.EXACT_PATTERNS:
            return self.EXACT_PATTERNS[lower_name]

        # Check pattern rules
        for pattern, replacement in self.PATTERN_RULES:
            match = re.match(pattern, lower_name)
            if match:
                # Replace matched groups in the replacement string
                desc = replacement
                for i, group in enumerate(match.groups(), 1):
                    # Handle different formatting based on context
                    if "Boolean:" in replacement:
                        # For boolean flags, keep simple lowercase
                        formatted_group = group.replace("_", " ")
                    else:
                        # For other patterns, convert to title case
                        formatted_group = group.replace("_", " ").title()
                    desc = desc.replace(f"\\{i}", formatted_group)
                return desc

        # Fall back to type-based description
        if column_type.upper() in self.TYPE_FALLBACKS:
            return self.TYPE_FALLBACKS[column_type.upper()]

        # Final fallback: convert column name to readable format
        readable_name = column_name.replace("_", " ").replace("-", " ").title()
        return f"{readable_name} value"

    def generate_metadata_for_table(self, db_path: Path, table_name: str) -> Dict[str, Any]:
        """Generate complete metadata for a specific table.

        Args:
            db_path: Path to the SQLite database
            table_name: Name of the table to analyze

        Returns:
            Dictionary containing generated metadata
        """
        # Open database and extract schema
        db = sqlite_utils.Database(db_path)

        if table_name not in db.table_names():
            raise ValueError(f"Table '{table_name}' not found in database")

        table = db[table_name]
        schema = extract_table_schema(table)

        # Generate column descriptions
        column_descriptions = self.generate_column_descriptions(schema)

        # Basic table metadata
        metadata = {"columns": column_descriptions}

        # Add suggested facets for categorical-looking columns
        facet_candidates = []
        for col_name, col_type in schema.items():
            lower_name = col_name.lower()
            # Suggest facets for likely categorical fields
            if col_type == "TEXT" and any(
                pattern in lower_name
                for pattern in [
                    "type",
                    "category",
                    "status",
                    "kind",
                    "group",
                    "class",
                    "department",
                    "role",
                ]
            ):
                facet_candidates.append(col_name)

        if facet_candidates:
            metadata["suggested_facets"] = facet_candidates

        # Suggest sort columns (dates, numbers, names)
        sort_candidates = []
        for col_name, col_type in schema.items():
            lower_name = col_name.lower()
            if (
                col_type in ["INTEGER", "REAL"]
                or "date" in lower_name
                or "time" in lower_name
                or lower_name in ["name", "title", "created_at", "updated_at"]
            ):
                sort_candidates.append(col_name)

        if sort_candidates:
            metadata["suggested_sortable"] = sort_candidates

        # Suggest label column (name, title, etc.)
        label_candidates = ["name", "title", "label", "display_name"]
        for candidate in label_candidates:
            if candidate in schema:
                metadata["suggested_label"] = candidate
                break

        return metadata

    def update_project_metadata(
        self,
        project: ZeekerProject,
        resource_name: str,
        generated_metadata: Dict[str, Any],
        preserve_existing: bool = True,
    ) -> ZeekerProject:
        """Update project configuration with generated metadata.

        Args:
            project: ZeekerProject to update
            resource_name: Name of the resource to update
            generated_metadata: Generated metadata dictionary
            preserve_existing: If True, don't overwrite existing metadata

        Returns:
            Updated ZeekerProject
        """
        if resource_name not in project.resources:
            project.resources[resource_name] = {}

        resource_config = project.resources[resource_name]

        # Add column descriptions (preserve existing if requested)
        if "columns" in generated_metadata:
            if preserve_existing and "columns" in resource_config:
                # Merge: keep existing, add new ones
                existing_columns = resource_config["columns"]
                new_columns = generated_metadata["columns"]

                merged_columns = existing_columns.copy()
                for col_name, description in new_columns.items():
                    if col_name not in merged_columns:
                        merged_columns[col_name] = description

                resource_config["columns"] = merged_columns
            else:
                resource_config["columns"] = generated_metadata["columns"]

        # Add suggestions as comments (not actual metadata)
        # These would be shown to user but not saved to TOML

        return project

    def generate_for_all_tables(self, db_path: Path) -> Dict[str, Dict[str, Any]]:
        """Generate metadata for all tables in a database.

        Args:
            db_path: Path to the SQLite database

        Returns:
            Dictionary mapping table_name -> generated_metadata
        """
        db = sqlite_utils.Database(db_path)
        results = {}

        # Skip meta tables
        skip_tables = {"_zeeker_schemas", "_zeeker_updates"}

        for table_name in db.table_names():
            if table_name not in skip_tables:
                try:
                    metadata = self.generate_metadata_for_table(db_path, table_name)
                    results[table_name] = metadata
                except Exception as e:
                    # Continue with other tables if one fails
                    results[table_name] = {"error": str(e)}

        return results

    def detect_missing_project_metadata(self, project: ZeekerProject) -> list[str]:
        """Detect missing project-level metadata fields.

        Args:
            project: ZeekerProject to analyze

        Returns:
            List of missing field names
        """
        missing_fields = []

        # Check for missing or empty project-level fields
        if not project.title:
            missing_fields.append("title")
        if not project.description:
            missing_fields.append("description")
        if not project.license:
            missing_fields.append("license")
        if not project.license_url:
            missing_fields.append("license_url")
        if not project.source:
            missing_fields.append("source")
        if not project.source_url:
            missing_fields.append("source_url")

        return missing_fields

    def generate_project_metadata(self, project: ZeekerProject) -> ZeekerProject:
        """Generate missing project-level metadata.

        Args:
            project: ZeekerProject to update

        Returns:
            Updated ZeekerProject with generated metadata
        """
        # Only generate fields that are missing/empty
        if not project.title:
            project.title = f"{project.name.replace('_', ' ').replace('-', ' ').title()} Database"

        if not project.description:
            project.description = f"Comprehensive data for the {project.name.replace('_', ' ').replace('-', ' ').title()} system"

        if not project.license:
            project.license = "MIT"

        if not project.license_url and project.license == "MIT":
            project.license_url = "https://opensource.org/licenses/MIT"

        if not project.source:
            project.source = f"{project.name.replace('_', ' ').replace('-', ' ').title()} System"

        # Note: source_url is intentionally left empty as it requires user input

        return project

    def detect_missing_resource_descriptions(
        self, project: ZeekerProject, resource_name: str = None
    ) -> list[str]:
        """Detect resources missing description fields.

        Args:
            project: ZeekerProject to analyze
            resource_name: Specific resource to check, or None for all resources

        Returns:
            List of resource names missing descriptions
        """
        missing_descriptions = []

        resources_to_check = [resource_name] if resource_name else project.resources.keys()

        for res_name in resources_to_check:
            if res_name in project.resources:
                resource_config = project.resources[res_name]
                if not resource_config.get("description"):
                    missing_descriptions.append(res_name)
            else:
                # Resource doesn't exist in config yet
                if resource_name:  # Only add if specifically requested
                    missing_descriptions.append(resource_name)

        return missing_descriptions

    def generate_resource_description(self, db_path: Path, resource_name: str) -> str:
        """Generate intelligent description for a resource based on its table schema.

        Args:
            db_path: Path to the SQLite database
            resource_name: Name of the resource/table

        Returns:
            Generated description string
        """
        try:
            db = sqlite_utils.Database(db_path)

            if resource_name not in db.table_names():
                # Fallback description for resources without tables yet
                return f"{resource_name.replace('_', ' ').title()} data"

            table = db[resource_name]
            schema = extract_table_schema(table)
            column_names = list(schema.keys())

            # Use heuristics based on table name and columns
            resource_lower = resource_name.lower()

            # User/account related tables
            if any(
                pattern in resource_lower for pattern in ["user", "account", "profile", "member"]
            ):
                if any(col in column_names for col in ["email", "password", "login"]):
                    return "User accounts and profiles"
                else:
                    return "User data and information"

            # Content related tables
            elif any(
                pattern in resource_lower
                for pattern in ["post", "article", "blog", "content", "page"]
            ):
                return "Blog posts and articles"

            # Product/inventory related
            elif any(
                pattern in resource_lower for pattern in ["product", "item", "inventory", "catalog"]
            ):
                return "Product catalog and inventory"

            # Transaction/order related
            elif any(
                pattern in resource_lower
                for pattern in ["order", "transaction", "payment", "purchase"]
            ):
                return "Orders and transactions"

            # Event/activity related
            elif any(
                pattern in resource_lower for pattern in ["event", "activity", "log", "audit"]
            ):
                return "Events and activity logs"

            # Message/communication related
            elif any(
                pattern in resource_lower
                for pattern in ["message", "comment", "review", "feedback"]
            ):
                return "Messages and communications"

            # Location related
            elif any(
                pattern in resource_lower for pattern in ["location", "place", "address", "store"]
            ):
                return "Location and address data"

            # Category/classification related
            elif any(
                pattern in resource_lower for pattern in ["category", "tag", "label", "group"]
            ):
                return "Categories and classifications"

            # Analyze column patterns for more specific descriptions
            else:
                # Look for common column patterns
                has_timestamps = any(
                    "created_at" in col or "updated_at" in col or "timestamp" in col
                    for col in column_names
                )
                has_user_ref = any("user_id" in col or "user" in col for col in column_names)
                has_content = any(
                    "content" in col or "text" in col or "body" in col for col in column_names
                )
                has_name_title = any("name" in col or "title" in col for col in column_names)

                if has_content and has_user_ref:
                    return f"User-generated {resource_name.replace('_', ' ')}"
                elif has_name_title and has_timestamps:
                    return f"{resource_name.replace('_', ' ').title()} records and metadata"
                elif has_user_ref:
                    return f"User-related {resource_name.replace('_', ' ')}"
                else:
                    return f"{resource_name.replace('_', ' ').title()} data and records"

        except Exception:
            # Fallback if analysis fails
            return f"{resource_name.replace('_', ' ').title()} data"
