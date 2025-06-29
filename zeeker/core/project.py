"""
Project management for Zeeker projects.
"""

import importlib.util
import json
import sqlite3
from pathlib import Path

import sqlite_utils

from .types import ValidationResult, ZeekerProject


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

        return result

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

def fetch_data():
    """
    Fetch data for the {resource_name} table.

    Returns:
        List[Dict[str, Any]]: List of records to insert into database

    sqlite-utils will automatically:
    • Create the table from your data structure  
    • Infer column types from your data
    • Handle JSON for complex data structures
    • Add new columns if data structure changes

    Example:
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
        # Example data - replace with your implementation
        # sqlite-utils will infer: id=INTEGER, example_field=TEXT
        {{"id": 1, "example_field": "example_value"}},
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

    def build_database(self) -> ValidationResult:
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

        # Remove existing database
        if db_path.exists():
            db_path.unlink()

        # Create new database using sqlite-utils
        db = sqlite_utils.Database(str(db_path))

        try:
            all_success = True
            for resource_name in project.resources.keys():
                resource_result = self._process_resource(db, resource_name)
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

            # Fetch data
            raw_data = module.fetch_data()

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
