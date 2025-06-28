"""
Tests for ZeekerGenerator - asset generation functionality.
"""

import json
from pathlib import Path
import pytest

from zeeker.core.generator import ZeekerGenerator


class TestZeekerGenerator:
    """Test asset generation functionality."""

    @pytest.fixture
    def generator(self, temp_dir):
        """Create a ZeekerGenerator for testing."""
        return ZeekerGenerator("test_database", temp_dir / "output")

    def test_generator_initialization(self, generator):
        """Test generator initializes correctly."""
        assert generator.database_name == "test_database"
        assert generator.sanitized_name == "test_database"  # No special chars to sanitize
        assert generator.output_path.name == "output"

    def test_generator_with_special_chars(self, temp_dir):
        """Test generator handles database names with special characters."""
        generator = ZeekerGenerator("Legal News & Cases!", temp_dir / "output")

        assert generator.database_name == "Legal News & Cases!"
        assert generator.sanitized_name.startswith("Legal-News---Cases-")
        assert len(generator.sanitized_name.split("-")[-1]) == 6  # MD5 hash suffix

    def test_create_base_structure(self, generator):
        """Test creating the base directory structure."""
        generator.create_base_structure()

        assert generator.output_path.exists()
        assert (generator.output_path / "templates").exists()
        assert (generator.output_path / "static").exists()
        assert (generator.output_path / "static" / "images").exists()

    def test_generate_metadata_template(self, generator):
        """Test metadata generation."""
        metadata = generator.generate_metadata_template(
            title="Test Database",
            description="A test database",
            extra_css=["custom.css"],
            extra_js=["custom.js"],
        )

        assert metadata["title"] == "Test Database"
        assert metadata["description"] == "A test database"
        assert "/static/databases/test_database/custom.css" in metadata["extra_css_urls"]
        assert "/static/databases/test_database/custom.js" in metadata["extra_js_urls"]
        assert "test_database" in metadata["databases"]

    def test_generate_css_template(self, generator):
        """Test CSS generation."""
        css_content = generator.generate_css_template("#ff0000", "#00ff00")

        assert "#ff0000" in css_content  # Primary color
        assert "#00ff00" in css_content  # Accent color
        assert "test_database" in css_content  # Database name scoping
        assert "[data-database=" in css_content  # Scoping attribute

    def test_generate_js_template(self, generator):
        """Test JavaScript generation."""
        js_content = generator.generate_js_template()

        assert "test_database" in js_content
        assert "isDatabasePage" in js_content  # Defensive programming function
        assert "DOMContentLoaded" in js_content
        assert "console.log" in js_content

    def test_generate_database_template(self, generator):
        """Test database template generation."""
        template_content = generator.generate_database_template("Custom Title")

        assert "Custom Title" in template_content
        assert "extends" in template_content
        assert "default:database.html" in template_content
        assert "test_database" in template_content

    def test_generate_database_template_default_title(self, generator):
        """Test database template with default title."""
        template_content = generator.generate_database_template()

        assert "Test_Database Database" in template_content

    def test_save_assets(self, generator):
        """Test saving generated assets to files."""
        metadata = {"title": "Test", "description": "Test DB"}
        css_content = "body { color: red; }"
        js_content = "console.log('test');"
        templates = {"database-test_database.html": "<html>Test</html>"}

        generator.save_assets(metadata, css_content, js_content, templates)

        # Check files were created
        assert (generator.output_path / "metadata.json").exists()
        assert (generator.output_path / "static" / "custom.css").exists()
        assert (generator.output_path / "static" / "custom.js").exists()
        assert (generator.output_path / "templates" / "database-test_database.html").exists()

        # Check content
        with open(generator.output_path / "metadata.json") as f:
            saved_metadata = json.load(f)
        assert saved_metadata == metadata

        with open(generator.output_path / "static" / "custom.css") as f:
            saved_css = f.read()
        assert saved_css == css_content

    def test_save_assets_creates_directories(self, generator):
        """Test that save_assets creates necessary directories."""
        # Don't call create_base_structure first
        metadata = {"title": "Test"}

        generator.save_assets(metadata)

        # Should have created the directories
        assert generator.output_path.exists()
        assert (generator.output_path / "templates").exists()
        assert (generator.output_path / "static").exists()
        assert (generator.output_path / "static" / "images").exists()

    def test_metadata_with_source_url(self, generator):
        """Test metadata generation with source URL."""
        metadata = generator.generate_metadata_template(
            title="Test Database",
            description="A test database",
            source_url="https://example.com/data",
        )

        assert metadata["source_url"] == "https://example.com/data"

    def test_metadata_with_custom_license(self, generator):
        """Test metadata generation with custom license."""
        metadata = generator.generate_metadata_template(
            title="Test Database", description="A test database", license_type="MIT"
        )

        assert metadata["license"] == "MIT"

    def test_customization_object(self, generator):
        """Test that generator has customization object."""
        assert hasattr(generator, "customization")
        assert generator.customization.database_name == "test_database"
        assert generator.customization.base_path == generator.output_path
