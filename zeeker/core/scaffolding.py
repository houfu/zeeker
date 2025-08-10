"""
Project scaffolding operations for Zeeker projects.

This module handles project initialization, file creation, and directory structure
setup. Extracted from project.py for clean separation of concerns.
"""

import re
from pathlib import Path

from .types import ValidationResult, ZeekerProject


class ProjectScaffolder:
    """Handles project scaffolding and file generation."""

    def __init__(self, project_path: Path):
        """Initialize scaffolder with project path.

        Args:
            project_path: Path to the project directory
        """
        self.project_path = project_path
        self.toml_path = self.project_path / "zeeker.toml"
        self.resources_path = self.project_path / "resources"

    def create_project_structure(self, project_name: str) -> ValidationResult:
        """Create the complete project directory structure and files.

        Args:
            project_name: Name of the project

        Returns:
            ValidationResult with creation results
        """
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

        # Create all project files
        self._create_resources_package()
        self._create_gitignore()
        readme_path = self._create_readme(project_name)
        claude_path = self._create_claude_md(project_name)

        result.info.append(f"Initialized Zeeker project '{project_name}'")

        # Add file creation info with safe path handling
        self._add_creation_info(result, self.toml_path)
        self._add_creation_info(result, self.resources_path, is_directory=True)
        self._add_creation_info(result, self.project_path / ".gitignore")
        self._add_creation_info(result, readme_path)
        self._add_creation_info(result, claude_path)

        return result

    def _create_resources_package(self) -> None:
        """Create the resources package directory and __init__.py file."""
        self.resources_path.mkdir(exist_ok=True)
        init_file = self.resources_path / "__init__.py"
        init_file.write_text('"""Resources package for data fetching."""\n')

    def _create_gitignore(self) -> None:
        """Create .gitignore file with standard exclusions."""
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

    def _create_readme(self, project_name: str) -> Path:
        """Create README.md file with project documentation.

        Args:
            project_name: Name of the project

        Returns:
            Path to the created README.md file
        """
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
        return readme_path

    def _create_claude_md(self, project_name: str) -> Path:
        """Create project-specific CLAUDE.md file.

        Args:
            project_name: Name of the project

        Returns:
            Path to the created CLAUDE.md file
        """
        claude_content = f"""# CLAUDE.md - {project_name.title()} Project Development Guide

This file provides Claude Code with project-specific context and guidance for developing this project.

## Project Overview

**Project Name:** {project_name}
**Database:** {project_name}.db
**Purpose:** Database project for {project_name} data management

## Development Commands

### Quick Commands
- `uv run zeeker add RESOURCE_NAME` - Add new resource to this project
- `uv run zeeker add RESOURCE_NAME --fragments` - Add resource with document fragments support
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

### Fragment Resources
If using fragment-enabled resources (created with `--fragments`):
- **Two Tables:** Each fragment resource creates a main table and a `_fragments` table
- **Schema Freedom:** You design both table schemas through your `fetch_data()` and `fetch_fragments_data()` functions
- **Linking:** Include some way to link fragments back to main records (your choice of field names)
- **Use Cases:** Large documents, legal texts, research papers, or any content that benefits from searchable chunks

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
        return claude_path

    def update_project_claude_md(self, project: ZeekerProject) -> None:
        """Update the project's CLAUDE.md with current resource information.

        Args:
            project: ZeekerProject configuration with resource information
        """
        claude_path = self.project_path / "CLAUDE.md"

        if not claude_path.exists():
            return  # No CLAUDE.md to update

        # Read existing CLAUDE.md
        existing_content = claude_path.read_text()

        # Generate resource documentation
        resource_docs = self._generate_resource_documentation(project)

        # Replace the resources section using regex
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

    def _generate_resource_documentation(self, project: ZeekerProject) -> str:
        """Generate documentation section for project resources.

        Args:
            project: ZeekerProject configuration

        Returns:
            Resource documentation as markdown string
        """
        if not project.resources:
            return "## Resources in This Project\n\n*No resources added yet. Use `zeeker add RESOURCE_NAME` to add resources.*\n\n"

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

            if resource_config.get("fragments", False):
                resource_docs += f"- **Type:** Fragment-enabled (creates two tables: `{resource_name}` and `{resource_name}_fragments`)\n"
                resource_docs += f"- **Schema:** Check `resources/{resource_name}.py` both fetch_data() and fetch_fragments_data() functions\n"
            else:
                resource_docs += f"- **Schema:** Check `resources/{resource_name}.py` fetch_data() for current schema\n"
            resource_docs += "\n"

        return resource_docs

    def _add_creation_info(
        self, result: ValidationResult, file_path: Path, is_directory: bool = False
    ) -> None:
        """Add file/directory creation info to result with safe path handling.

        Args:
            result: ValidationResult to update
            file_path: Path of the created file/directory
            is_directory: Whether the path is a directory
        """
        try:
            relative_path = file_path.relative_to(Path.cwd())
            display_path = str(relative_path) + ("/" if is_directory else "")
        except ValueError:
            # If not in subpath of cwd, just use filename/dirname
            display_path = file_path.name + ("/" if is_directory else "")

        result.info.append(f"Created: {display_path}")
