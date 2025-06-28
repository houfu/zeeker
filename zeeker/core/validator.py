"""
Validation logic for Zeeker database assets and configurations.
"""

import re
import json
import hashlib
from pathlib import Path
from typing import Dict, Any

from .types import ValidationResult


class ZeekerValidator:
    """Validates Zeeker database assets for compliance with the customization guide."""

    # Banned template names from the guide - would break core functionality
    BANNED_TEMPLATES = {
        "database.html",  # would break all database pages
        "table.html",  # would break all table pages
        "index.html",  # would break homepage
        "query.html",  # would break SQL interface
        "row.html",  # would break record pages
        "error.html",  # would break error handling
        "base.html",  # would break template inheritance
    }

    REQUIRED_METADATA_FIELDS = {"title", "description"}

    @staticmethod
    def sanitize_database_name(name: str) -> str:
        """Sanitize database name following Datasette conventions from the guide."""
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
        if sanitized != name:
            hash_suffix = hashlib.md5(name.encode()).hexdigest()[:6]
            sanitized = f"{sanitized}-{hash_suffix}"
        return sanitized

    def validate_template_name(self, template_name: str, database_name: str) -> ValidationResult:
        """Validate template names follow the guide's safety rules."""
        result = ValidationResult(is_valid=True)

        # Check if template name is banned (from the guide)
        if template_name in self.BANNED_TEMPLATES:
            result.is_valid = False
            result.errors.append(
                f"Template '{template_name}' is BANNED per customization guide. "
                f"Use 'database-{database_name}.html' instead for database-specific templates."
            )
            return result

        # Check for recommended naming patterns from the guide
        safe_patterns = [
            f"database-{database_name}",  # Database-specific pages
            f"table-{database_name}-",  # Table-specific pages
            "custom-",  # Custom pages
            "_partial-",  # Partial templates
        ]

        is_safe_pattern = any(template_name.startswith(pattern) for pattern in safe_patterns)

        if not is_safe_pattern:
            result.warnings.append(
                f"Template '{template_name}' doesn't follow guide's recommended patterns. "
                f"Consider: database-{database_name}.html, table-{database_name}-TABLENAME.html, "
                f"custom-{database_name}-*.html, or _partial-*.html"
            )

        return result

    def validate_metadata(self, metadata: Dict[str, Any]) -> ValidationResult:
        """Validate metadata follows complete Datasette structure per the guide."""
        result = ValidationResult(is_valid=True)

        # Check for complete Datasette structure (not fragments)
        if "databases" not in metadata:
            result.warnings.append(
                "Per customization guide: metadata should include 'databases' section "
                "for complete Datasette structure"
            )

        # Check recommended fields
        for field in self.REQUIRED_METADATA_FIELDS:
            if field not in metadata:
                result.warnings.append(f"Recommended field '{field}' missing from metadata")

        # Validate JSON structure
        try:
            json.dumps(metadata)
        except (TypeError, ValueError) as e:
            result.is_valid = False
            result.errors.append(f"Invalid JSON structure: {e}")

        # Check CSS/JS URL patterns follow the guide
        if "extra_css_urls" in metadata:
            for url in metadata["extra_css_urls"]:
                if not url.startswith("/static/databases/"):
                    result.warnings.append(
                        f"CSS URL '{url}' should follow guide pattern: '/static/databases/database_name/filename.css'"
                    )

        if "extra_js_urls" in metadata:
            for url in metadata["extra_js_urls"]:
                if not url.startswith("/static/databases/"):
                    result.warnings.append(
                        f"JS URL '{url}' should follow guide pattern: '/static/databases/database_name/filename.js'"
                    )

        return result

    def validate_file_structure(self, assets_path: Path, database_name: str) -> ValidationResult:
        """Validate assets follow the guide's file structure."""
        result = ValidationResult(is_valid=True)

        if not assets_path.exists():
            result.is_valid = False
            result.errors.append(f"Assets path does not exist: {assets_path}")
            return result

        # Check for expected structure from the guide
        expected_dirs = ["templates", "static"]
        existing_dirs = [d.name for d in assets_path.iterdir() if d.is_dir()]

        for dir_name in existing_dirs:
            if dir_name not in expected_dirs:
                result.warnings.append(
                    f"Unexpected directory: {dir_name}. Guide expects: templates/, static/"
                )

        # Validate templates follow naming rules
        templates_dir = assets_path / "templates"
        if templates_dir.exists():
            for template_file in templates_dir.glob("*.html"):
                template_result = self.validate_template_name(template_file.name, database_name)
                result.errors.extend(template_result.errors)
                result.warnings.extend(template_result.warnings)

                # FIXED: If template validation has errors, mark overall result as invalid
                if not template_result.is_valid:
                    result.is_valid = False

        # Validate metadata.json if present
        metadata_file = assets_path / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                metadata_result = self.validate_metadata(metadata)
                result.errors.extend(metadata_result.errors)
                result.warnings.extend(metadata_result.warnings)

                # FIXED: If metadata validation has errors, mark overall result as invalid
                if not metadata_result.is_valid:
                    result.is_valid = False

            except (json.JSONDecodeError, IOError) as e:
                result.is_valid = False
                result.errors.append(f"Error reading metadata.json: {e}")

        return result
