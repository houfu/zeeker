"""
Project management for Zeeker projects.
"""

from pathlib import Path

from .database import DatabaseBuilder
from .resources import ResourceManager
from .scaffolding import ProjectScaffolder
from .types import ValidationResult, ZeekerProject


class ZeekerProjectManager:
    """Manages Zeeker projects and resources."""

    def __init__(self, project_path: Path = None):
        self.project_path = project_path or Path.cwd()
        self.toml_path = self.project_path / "zeeker.toml"
        self.resources_path = self.project_path / "resources"
        self.scaffolder = ProjectScaffolder(self.project_path)
        self.resource_manager = ResourceManager(self.project_path)

    def is_project_root(self) -> bool:
        """Check if current directory is a Zeeker project root."""
        return self.toml_path.exists()

    def init_project(self, project_name: str) -> ValidationResult:
        """Initialize a new Zeeker project."""
        return self.scaffolder.create_project_structure(project_name)

    def _update_project_claude_md(self, project: ZeekerProject) -> None:
        """Update the project's CLAUDE.md with current resource information."""
        self.scaffolder.update_project_claude_md(project)

    def load_project(self) -> ZeekerProject:
        """Load project configuration."""
        if not self.is_project_root():
            raise ValueError("Not a Zeeker project (no zeeker.toml found)")
        return ZeekerProject.from_toml(self.toml_path)

    def add_resource(
        self, resource_name: str, description: str = None, **kwargs
    ) -> ValidationResult:
        """Add a new resource to the project."""
        if not self.is_project_root():
            result = ValidationResult(is_valid=False)
            result.errors.append("Not in a Zeeker project directory (no zeeker.toml found)")
            return result

        # Load existing project
        project = self.load_project()

        # Use resource manager to add the resource
        result = self.resource_manager.add_resource(project, resource_name, description, **kwargs)

        if result.is_valid:
            # Update project CLAUDE.md with new resource information
            self._update_project_claude_md(project)

            # Add info about CLAUDE.md update if it exists
            claude_path = self.project_path / "CLAUDE.md"
            if claude_path.exists():
                try:
                    relative_claude = claude_path.relative_to(Path.cwd())
                    result.info.append(f"Updated: {relative_claude}")
                except ValueError:
                    result.info.append(f"Updated: {claude_path.name}")

        return result

    def build_database(
        self,
        force_schema_reset: bool = False,
        sync_from_s3: bool = False,
        resources: list[str] = None,
        setup_fts: bool = False,
    ) -> ValidationResult:
        """Build the SQLite database from resources with optional S3 sync.

        Args:
            force_schema_reset: If True, ignore schema conflicts and rebuild
            sync_from_s3: If True, download existing database from S3 before building
            resources: List of specific resource names to build. If None, builds all resources.
            setup_fts: If True, set up full-text search indexes on configured fields

        Returns:
            ValidationResult with build results
        """
        if not self.is_project_root():
            result = ValidationResult(is_valid=False)
            result.errors.append("Not in a Zeeker project directory")
            return result

        project = self.load_project()

        # Validate resource names if specified
        if resources:
            invalid_resources = [r for r in resources if r not in project.resources]
            if invalid_resources:
                result = ValidationResult(is_valid=False)
                result.errors.append(f"Unknown resources: {', '.join(invalid_resources)}")
                result.errors.append(f"Available resources: {', '.join(project.resources.keys())}")
                return result

        builder = DatabaseBuilder(self.project_path, project)

        return builder.build_database(force_schema_reset, sync_from_s3, resources, setup_fts)
