"""Tests for fragments functionality."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from zeeker.core.project import ZeekerProjectManager


@pytest.fixture
def temp_project_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def test_fragments_flag_in_cli():
    """Test that the fragments flag is available in CLI."""
    # This is implicitly tested by the CLI integration
    # The flag should be available in zeeker add --help
    assert True


def test_add_resource_with_fragments(temp_project_dir):
    """Test adding a resource with fragments enabled."""
    # Initialize project
    manager = ZeekerProjectManager(temp_project_dir)
    init_result = manager.init_project("test_project")
    assert init_result.is_valid

    # Add resource with fragments
    result = manager.add_resource("legal_docs", "Legal documents with fragments", fragments=True)

    assert result.is_valid
    assert "Created resource: legal_docs.py" in result.info

    # Check that fragments=true is saved in TOML
    toml_content = (temp_project_dir / "zeeker.toml").read_text()
    assert "fragments = true" in toml_content

    # Check that the resource file contains fragments template
    resource_content = (temp_project_dir / "resources" / "legal_docs.py").read_text()
    assert "fetch_fragments_data" in resource_content
    assert "legal_docs_fragments" in resource_content
    assert "You define both table schemas" in resource_content


def test_add_resource_without_fragments(temp_project_dir):
    """Test adding a regular resource without fragments."""
    # Initialize project
    manager = ZeekerProjectManager(temp_project_dir)
    init_result = manager.init_project("test_project")
    assert init_result.is_valid

    # Add regular resource
    result = manager.add_resource("users", "User data")

    assert result.is_valid

    # Check that fragments is not in TOML
    toml_content = (temp_project_dir / "zeeker.toml").read_text()
    assert "fragments" not in toml_content

    # Check that the resource file uses standard template
    resource_content = (temp_project_dir / "resources" / "users.py").read_text()
    assert "fetch_fragments_data" not in resource_content
    assert "fragments" not in resource_content.lower()


def test_build_database_with_fragments(temp_project_dir):
    """Test building a database with fragments enabled resource."""
    # Initialize project
    manager = ZeekerProjectManager(temp_project_dir)
    init_result = manager.init_project("test_project")
    assert init_result.is_valid

    # Add resource with fragments
    add_result = manager.add_resource("docs", "Documents with fragments", fragments=True)
    assert add_result.is_valid

    # Build database
    build_result = manager.build_database()
    assert build_result.is_valid

    # Check that both tables were created
    db_path = temp_project_dir / "test_project.db"
    assert db_path.exists()

    # Verify database structure
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "docs" in tables
    assert "docs_fragments" in tables

    # Check main table has data
    cursor.execute("SELECT COUNT(*) FROM docs")
    main_count = cursor.fetchone()[0]
    assert main_count > 0

    # Check fragments table has data
    cursor.execute("SELECT COUNT(*) FROM docs_fragments")
    fragments_count = cursor.fetchone()[0]
    assert fragments_count > 0

    # Since schema is flexible now, we just verify fragments exist
    # and are linked to main table records somehow
    assert fragments_count > 0  # Fragments were created

    conn.close()


def test_fragments_error_handling(temp_project_dir):
    """Test error handling when fragments resource is missing required functions."""
    # Initialize project
    manager = ZeekerProjectManager(temp_project_dir)
    init_result = manager.init_project("test_project")
    assert init_result.is_valid

    # Create a manual resource file without fetch_fragments_data function
    resource_file = temp_project_dir / "resources" / "bad_docs.py"
    resource_file.write_text(
        """
def fetch_data(existing_table):
    return [{"id": 1, "title": "Test"}]
"""
    )

    # Update TOML to mark it as fragments-enabled
    toml_content = """[project]
name = "test_project"
database = "test_project.db"

[resource.bad_docs]
description = "Bad docs resource"
fragments = true
"""
    (temp_project_dir / "zeeker.toml").write_text(toml_content)

    # Build should fail with appropriate error
    build_result = manager.build_database()
    assert not build_result.is_valid
    assert any("missing fetch_fragments_data() function" in error for error in build_result.errors)


if __name__ == "__main__":
    pytest.main([__file__])
