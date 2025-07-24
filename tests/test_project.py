"""
Tests for ZeekerProjectManager - project management functionality.
"""

import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from zeeker.core.project import ZeekerProjectManager


class TestZeekerProjectManager:
    """Test project management functionality."""

    @pytest.fixture
    def manager(self, temp_dir):
        """Create a ZeekerProjectManager for testing."""
        return ZeekerProjectManager(temp_dir)

    def test_manager_initialization(self, manager, temp_dir):
        """Test manager initializes with correct paths."""
        assert manager.project_path == temp_dir
        assert manager.toml_path == temp_dir / "zeeker.toml"
        assert manager.resources_path == temp_dir / "resources"

    def test_manager_default_path(self):
        """Test manager defaults to current working directory."""
        manager = ZeekerProjectManager()
        assert manager.project_path == Path.cwd()

    def test_is_project_root_false(self, manager):
        """Test is_project_root returns False when no zeeker.toml."""
        assert not manager.is_project_root()

    def test_is_project_root_true(self, manager):
        """Test is_project_root returns True when zeeker.toml exists."""
        manager.toml_path.write_text("[project]\nname = 'test'")
        assert manager.is_project_root()

    def test_init_project_success(self, manager):
        """Test successful project initialization."""
        result = manager.init_project("test_project")

        assert result.is_valid
        assert len(result.errors) == 0
        assert "Initialized Zeeker project" in result.info[0]

        # Check files created
        assert manager.toml_path.exists()
        assert manager.resources_path.exists()
        assert (manager.resources_path / "__init__.py").exists()
        assert (manager.project_path / ".gitignore").exists()
        assert (manager.project_path / "README.md").exists()

        # Check TOML content
        toml_content = manager.toml_path.read_text()
        assert "test_project" in toml_content
        assert "test_project.db" in toml_content

    def test_init_project_already_exists(self, manager):
        """Test project initialization fails when project already exists."""
        manager.toml_path.write_text("[project]\nname = 'existing'")

        result = manager.init_project("test_project")

        assert not result.is_valid
        assert "already contains zeeker.toml" in result.errors[0]

    def test_load_project_success(self, manager):
        """Test loading an existing project."""
        # Create a test project file
        toml_content = textwrap.dedent(
            """[project]
name = "test_project"
database = "test_project.db"

[resource.users]
description = "User data"
facets = ["role", "department"]
"""
        )
        manager.toml_path.write_text(toml_content)

        project = manager.load_project()

        assert project.name == "test_project"
        assert project.database == "test_project.db"
        assert "users" in project.resources
        assert project.resources["users"]["description"] == "User data"

    def test_load_project_not_found(self, manager):
        """Test loading project fails when not found."""
        with pytest.raises(ValueError, match="Not a Zeeker project"):
            manager.load_project()

    def test_add_resource_success(self, manager):
        """Test adding a resource successfully."""
        # Initialize project first
        manager.init_project("test_project")

        result = manager.add_resource(
            "users", description="User account data", facets=["role", "department"], size=50
        )

        assert result.is_valid
        assert len(result.errors) == 0
        assert "Created resource" in result.info[0]

        # Check resource file created
        resource_file = manager.resources_path / "users.py"
        assert resource_file.exists()

        # Check file content
        content = resource_file.read_text()
        assert "def fetch_data(existing_table):" in content
        assert "users" in content

        # Check project updated
        project = manager.load_project()
        assert "users" in project.resources
        assert project.resources["users"]["description"] == "User account data"
        assert project.resources["users"]["facets"] == ["role", "department"]
        assert project.resources["users"]["size"] == 50

    def test_add_resource_outside_project(self, manager):
        """Test adding resource fails outside project."""
        result = manager.add_resource("users", "User data")

        assert not result.is_valid
        assert "Not in a Zeeker project" in result.errors[0]

    def test_add_resource_already_exists(self, manager):
        """Test adding resource fails when it already exists."""
        manager.init_project("test_project")
        manager.add_resource("users", "User data")

        # Try to add again
        result = manager.add_resource("users", "User data again")

        assert not result.is_valid
        assert "already exists" in result.errors[0]

    def test_generate_resource_template(self, manager):
        """Test resource template generation."""
        template = manager._generate_resource_template("test_resource")

        assert "test_resource" in template
        assert "def fetch_data(existing_table):" in template
        assert "sqlite-utils" in template
        assert "TODO: Implement" in template

    @patch("zeeker.core.project.sqlite_utils.Database")
    def test_build_database_success(self, mock_db_class, manager):
        """Test successful database build."""
        # Setup project
        manager.init_project("test_project")
        manager.add_resource("users", "User data")

        # Create mock resource with fetch_data
        resource_content = """
def fetch_data(existing_table):
    return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
"""
        (manager.resources_path / "users.py").write_text(resource_content)

        # Mock database
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        result = manager.build_database()

        assert result.is_valid
        assert "Database built successfully" in result.info[-2]  # Second to last info message
        assert "Generated Datasette metadata" in result.info[-1]  # Last info message

        # Check database operations
        mock_db.__getitem__.assert_called_with("users")

        # Check metadata file created
        metadata_file = manager.project_path / "metadata.json"
        assert metadata_file.exists()

    def test_build_database_outside_project(self, manager):
        """Test build fails outside project."""
        result = manager.build_database()

        assert not result.is_valid
        assert "Not in a Zeeker project" in result.errors[0]

    @patch("zeeker.core.project.sqlite_utils.Database")
    def test_build_database_missing_resource_file(self, mock_db_class, manager):
        """Test build fails with missing resource file."""
        manager.init_project("test_project")

        # Add resource to config but don't create file
        project = manager.load_project()
        project.resources["missing"] = {"description": "Missing resource"}
        project.save_toml(manager.toml_path)

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        result = manager.build_database()

        assert not result.is_valid
        assert "Resource file not found" in result.errors[0]

    @patch("zeeker.core.project.sqlite_utils.Database")
    def test_build_database_no_fetch_function(self, mock_db_class, manager):
        """Test build fails when resource has no fetch_data function."""
        manager.init_project("test_project")
        manager.add_resource("users", "User data")

        # Create resource without fetch_data function
        (manager.resources_path / "users.py").write_text("# No fetch_data function")

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        result = manager.build_database()

        assert not result.is_valid
        assert "missing fetch_data() function" in result.errors[0]

    @patch("zeeker.core.project.sqlite_utils.Database")
    def test_build_database_invalid_data_type(self, mock_db_class, manager):
        """Test build fails when fetch_data returns wrong type."""
        manager.init_project("test_project")
        manager.add_resource("users", "User data")

        # Create resource that returns wrong type
        resource_content = """
def fetch_data(existing_table):
    return "not a list"
"""
        (manager.resources_path / "users.py").write_text(resource_content)

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        result = manager.build_database()

        assert not result.is_valid
        assert "must return a list of dictionaries" in result.errors[0]

    @patch("zeeker.core.project.sqlite_utils.Database")
    def test_build_database_with_transform(self, mock_db_class, manager):
        """Test build with optional transform_data function."""
        manager.init_project("test_project")
        manager.add_resource("users", "User data")

        # Create resource with both fetch_data and transform_data
        resource_content = """
def fetch_data(existing_table):
    return [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}]

def transform_data(data):
    for item in data:
        item["name"] = item["name"].title()
    return data
"""
        (manager.resources_path / "users.py").write_text(resource_content)

        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.__getitem__.return_value = mock_table
        mock_db_class.return_value = mock_db

        result = manager.build_database()

        assert result.is_valid

        # Check that insert_all was called (transform_data should have been used)
        mock_table.insert_all.assert_called_once()
        call_args = mock_table.insert_all.call_args[0]
        data = call_args[0]

        # The data should be transformed (names capitalized)
        assert any(item["name"] == "Alice" for item in data)
        assert any(item["name"] == "Bob" for item in data)
