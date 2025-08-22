"""
Resource management for Zeeker projects.

This module handles adding resources to projects, managing resource configurations,
and updating project files. Extracted from project.py for clean separation of concerns.
"""

from pathlib import Path

from .templates import ResourceTemplateGenerator
from .types import ValidationResult, ZeekerProject


class ResourceManager:
    """Manages resource creation and configuration for Zeeker projects."""

    def __init__(self, project_path: Path):
        """Initialize resource manager.

        Args:
            project_path: Path to the Zeeker project
        """
        self.project_path = project_path
        self.toml_path = self.project_path / "zeeker.toml"
        self.resources_path = self.project_path / "resources"
        self.template_generator = ResourceTemplateGenerator()

    def add_resource(
        self, project: ZeekerProject, resource_name: str, description: str = None, **kwargs
    ) -> ValidationResult:
        """Add a new resource to the project.

        Args:
            project: ZeekerProject configuration
            resource_name: Name of the resource to add
            description: Description of the resource
            **kwargs: Additional resource configuration options

        Returns:
            ValidationResult with add results
        """
        result = ValidationResult(is_valid=True)

        # Check if resource already exists
        resource_file = self.resources_path / f"{resource_name}.py"
        if resource_file.exists():
            result.is_valid = False
            result.errors.append(f"Resource '{resource_name}' already exists")
            return result

        # Generate and write resource file
        template = self.template_generator.generate_resource_template(
            resource_name,
            fragments=kwargs.get("fragments", False),
            is_async=kwargs.get("is_async", False),
        )
        resource_file.write_text(template)

        # Create resource configuration
        resource_config = self._build_resource_config(resource_name, description, kwargs)

        # Update project configuration
        project.resources[resource_name] = resource_config
        project.save_toml(self.toml_path)

        # Add creation info to result
        self._add_file_info(result, resource_file, "Created resource")
        self._add_file_info(result, self.toml_path, "Updated")

        return result

    def _build_resource_config(self, resource_name: str, description: str, kwargs: dict) -> dict:
        """Build resource configuration from parameters.

        Args:
            resource_name: Name of the resource
            description: Resource description
            kwargs: Additional configuration options

        Returns:
            Resource configuration dictionary
        """
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
            "fragments",
            "fts_fields",
            "fragments_fts_fields",
        ]

        for field in datasette_fields:
            if field in kwargs:
                resource_config[field] = kwargs[field]

        return resource_config

    def _add_file_info(self, result: ValidationResult, file_path: Path, action: str) -> None:
        """Add file operation info to result with safe path handling.

        Args:
            result: ValidationResult to update
            file_path: Path of the file
            action: Action performed (e.g., "Created", "Updated")
        """
        try:
            relative_path = file_path.relative_to(Path.cwd())
            result.info.append(f"{action}: {relative_path}")
        except ValueError:
            # If not in subpath of cwd, just use filename
            result.info.append(f"{action}: {file_path.name}")
