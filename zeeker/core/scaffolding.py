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

        # Create basic project structure with rich metadata defaults
        formatted_name = project_name.replace("_", " ").replace("-", " ").title()
        project = ZeekerProject(
            name=project_name,
            database=f"{project_name}.db",
            title=f"{formatted_name} Database",
            description=f"Comprehensive data for the {formatted_name} system",
            license="MIT",
            license_url="https://opensource.org/licenses/MIT",
            source=f"{formatted_name} System",
            # source_url left empty for user to add their git repo
        )

        # Save zeeker.toml with enhanced examples
        self._save_enhanced_toml(project)

        # Create all project files
        self._create_resources_package()
        pyproject_path = self._create_pyproject_toml(project_name)
        self._create_gitignore()
        readme_path = self._create_readme(project_name)
        claude_path = self._create_claude_md(project_name)
        github_workflow_path = self._create_github_workflow()

        result.info.append(f"Initialized Zeeker project '{project_name}'")

        # Add file creation info with safe path handling
        self._add_creation_info(result, self.toml_path)
        self._add_creation_info(result, pyproject_path)
        self._add_creation_info(result, self.resources_path, is_directory=True)
        self._add_creation_info(result, self.project_path / ".gitignore")
        self._add_creation_info(result, readme_path)
        self._add_creation_info(result, claude_path)
        self._add_creation_info(result, github_workflow_path)

        return result

    def _save_enhanced_toml(self, project: ZeekerProject) -> None:
        """Save zeeker.toml with enhanced examples and documentation."""
        toml_content = f"""[project]
name = "{project.name}"
database = "{project.database}"
title = "{project.title}"
description = "{project.description}"
license = "{project.license}"
license_url = "{project.license_url}"
source = "{project.source}"
# source_url = "https://github.com/username/repository"  # Add your repo URL

# Example resource configurations with Datasette metadata
# Uncomment and modify these examples, or use: uv run zeeker add <resource_name>

# [resource.users]
# description = "User accounts and profiles"
# sort = "created_at"                                    # Default sort column
# size = 25                                              # Default page size
# facets = ["department", "role"]                        # Faceted browsing
# sortable_columns = ["name", "created_at", "email"]     # Allowed sort columns
# hidden = false                                         # Show/hide table
#
# [resource.users.columns]                               # Column metadata in separate section
# id = "Unique identifier"
# name = "Display name"
# email = "Contact email"
# created_at = "Account creation timestamp"
# department = "User department"
# role = "User role"

# [resource.posts]
# description = "Blog posts and articles"
# sort_desc = "published_at"                            # Default descending sort
# size = 10
# label_column = "title"                                # Primary display column
# units = {{published_at = "YYYY-MM-DD"}}               # Column units/format
#
# [resource.posts.columns]                              # Column metadata in separate section
# title = "Post title"
# content = "Post content"
# published_at = "Publication date"
# author_id = "Author reference ID"

# [resource.documents]
# description = "Legal documents and contracts"
# description_html = "<p>Collection of <strong>legal documents</strong></p>"  # HTML description
# facets = ["document_type", "jurisdiction"]
# size = 50
#
# [resource.documents.columns]                          # Column metadata in separate section
# id = "Document ID"
# title = "Document title"
# content = "Document text"
# document_type = "Type of document"
# jurisdiction = "Legal jurisdiction"
"""

        with open(self.toml_path, "w", encoding="utf-8") as f:
            f.write(toml_content)

    def _create_resources_package(self) -> None:
        """Create the resources package directory and __init__.py file."""
        self.resources_path.mkdir(exist_ok=True)
        init_file = self.resources_path / "__init__.py"
        init_file.write_text('"""Resources package for data fetching."""\n')

    def _create_pyproject_toml(self, project_name: str) -> Path:
        """Create pyproject.toml file with zeeker dependency.

        Args:
            project_name: Name of the project

        Returns:
            Path to the created pyproject.toml file
        """
        pyproject_content = f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "Zeeker database project for {project_name}"
dependencies = ["zeeker"]
requires-python = ">=3.12"

[dependency-groups]
dev = ["black>=25.1.0", "ruff>=0.8.0"]

# Add project-specific dependencies here as needed:
# dependencies = [
#     "zeeker",
#     "requests",        # For HTTP API calls
#     "beautifulsoup4",  # For web scraping and HTML parsing
#     "pandas",          # For data processing and analysis
#     "lxml",            # For XML parsing
#     "pdfplumber",      # For PDF text extraction
#     "openpyxl",        # For Excel file reading
# ]

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]  # Focus on essential errors, warnings, and imports
ignore = ["E501"]  # Line too long (handled by black)
"""
        pyproject_path = self.project_path / "pyproject.toml"
        pyproject_path.write_text(pyproject_content)
        return pyproject_path

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

1. Add dependencies for your data sources:
   ```bash
   uv add requests beautifulsoup4  # Example: web scraping dependencies
   ```

2. Add resources:
   ```bash
   uv run zeeker add my_resource --description "Description of the resource"
   ```

3. Create `.env` file for credentials (optional):
   ```bash
   # Create .env file with API keys and S3 credentials
   echo "MY_API_KEY=your_api_key_here" > .env
   ```

4. Implement data fetching in `resources/my_resource.py`

5. Build the database:
   ```bash
   uv run zeeker build
   ```

6. Deploy to S3:
   ```bash
   uv run zeeker deploy
   ```

## Automated Deployment

This project includes a GitHub Action that automatically builds and deploys to S3:

- **Triggers:** Pushes to main/master branch, or manual dispatch
- **Required Secrets:** Configure in GitHub repository settings:
  - `S3_BUCKET` - Target S3 bucket name
  - `AWS_ACCESS_KEY_ID` - AWS access key
  - `AWS_SECRET_ACCESS_KEY` - AWS secret key
  - `JINA_API_TOKEN` - (optional) For Jina Reader resources
  - `OPENAI_API_KEY` - (optional) For OpenAI resources
- **Workflow:** `.github/workflows/deploy.yml`

To deploy manually: Go to Actions tab → "Deploy Zeeker Project to S3" → Run workflow

## Project Structure

- `pyproject.toml` - Project dependencies and metadata
- `zeeker.toml` - Project configuration
- `resources/` - Python modules for data fetching
- `.env` - Environment variables (gitignored, create manually)
- `{project_name}.db` - Generated SQLite database (gitignored)
- `.venv/` - Virtual environment (gitignored)

## Dependencies

This project uses uv for dependency management. Common dependencies for data projects:

- `requests` - HTTP API calls
- `beautifulsoup4` - Web scraping and HTML parsing
- `pandas` - Data processing and analysis
- `lxml` - XML parsing
- `pdfplumber` - PDF text extraction
- `openpyxl` - Excel file reading

Add dependencies with: `uv add package_name`

## Environment Variables

Zeeker automatically loads `.env` files during build and deployment:

```bash
# S3 deployment (required for deploy)
S3_BUCKET=your-bucket-name
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# API keys for your resources
JINA_API_TOKEN=your-jina-token
OPENAI_API_KEY=your-openai-key
```

## Development

Format and lint code:
- `uv run black .` - Format code with black
- `uv run ruff check .` - Lint code with ruff
- `uv run ruff check --fix .` - Auto-fix ruff issues

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

## Development Environment

This project uses **uv** for dependency management with an isolated virtual environment:

- `pyproject.toml` - Project dependencies and metadata
- `.venv/` - Isolated virtual environment (auto-created)
- All commands should be run with `uv run` prefix

### Dependency Management
- **Add dependencies:** `uv add package_name` (e.g., `uv add requests pandas`)
- **Install dependencies:** `uv sync` (automatically creates .venv if needed)
- **Common packages:** requests, beautifulsoup4, pandas, lxml, pdfplumber, openpyxl

### Environment Variables
Zeeker automatically loads `.env` files when running build, deploy, and asset commands:

- **Create `.env` file:** Store sensitive credentials and configuration
- **Auto-loaded:** Environment variables are available in your resources during `zeeker build`
- **S3 deployment:** Required for `zeeker deploy` and `zeeker assets deploy`

**Example `.env` file:**
```
# S3 deployment credentials
S3_BUCKET=my-datasette-bucket
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_ENDPOINT_URL=https://s3.amazonaws.com

# API keys for data resources
JINA_API_TOKEN=your_jina_token
OPENAI_API_KEY=your_openai_key
```

**Usage in resources:**
```python
import os

def fetch_data(existing_table):
    api_key = os.getenv("MY_API_KEY")  # Loaded from .env automatically
    # ... rest of your code
```

## Development Commands

### Quick Commands
- `uv run zeeker add RESOURCE_NAME` - Add new resource to this project
- `uv run zeeker add RESOURCE_NAME --fragments` - Add resource with document fragments support
- `uv run zeeker build` - Build database from all resources in this project
- `uv run zeeker deploy` - Deploy this project's database to S3

### Code Formatting
- `uv run black .` - Format code with black
- `uv run ruff check .` - Lint code with ruff
- `uv run ruff check --fix .` - Auto-fix ruff issues

### Testing This Project
- `uv run pytest` - Run tests (if added to project)
- Check generated `{project_name}.db` after build
- Verify metadata.json structure

### Working with Dependencies
When implementing resources that need external libraries:
1. **First add the dependency:** `uv add library_name`
2. **Then use in your resource:** `import library_name` in `resources/resource_name.py`
3. **Build works automatically:** `uv run zeeker build` uses the isolated environment

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

    def _create_github_workflow(self) -> Path:
        """Create GitHub Actions workflow for automated deployment.

        Returns:
            Path to the created workflow file
        """
        # Create .github/workflows directory
        github_dir = self.project_path / ".github"
        workflows_dir = github_dir / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        workflow_content = """name: Deploy Zeeker Project to S3

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        default: 'production'
        type: choice
        options:
          - production
          - staging

permissions:
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ github.event.inputs.environment || 'production' }}
    steps:
    - uses: actions/checkout@v4

    - name: Set up Python 3.12
      uses: actions/setup-python@v5
      with:
        python-version: "3.12"

    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        enable-cache: true
        cache-dependency-glob: "pyproject.toml"

    - name: Install dependencies
      run: |
        uv sync

    - name: Build zeeker project
      env:
        JINA_API_TOKEN: ${{ secrets.JINA_API_TOKEN }}
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: |
        uv run zeeker build

    - name: Deploy to S3
      env:
        S3_BUCKET: ${{ secrets.S3_BUCKET }}
        AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
        AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        S3_ENDPOINT_URL: ${{ secrets.S3_ENDPOINT_URL }}
      run: |
        uv run zeeker deploy
"""

        workflow_path = workflows_dir / "deploy.yml"
        workflow_path.write_text(workflow_content)
        return workflow_path

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
