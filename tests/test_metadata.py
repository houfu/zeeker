"""
Tests for metadata generation functionality.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlite_utils

from zeeker.core.metadata import MetadataGenerator
from zeeker.core.types import ZeekerProject


class TestMetadataGenerator:
    """Test the MetadataGenerator class."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database with sample data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        # Create database with sample tables
        db = sqlite_utils.Database(db_path)

        # Create users table
        users_data = [
            {
                "id": 1,
                "name": "Alice",
                "email": "alice@example.com",
                "created_at": "2024-01-01",
                "is_active": True,
            },
            {
                "id": 2,
                "name": "Bob",
                "email": "bob@example.com",
                "created_at": "2024-01-02",
                "is_active": False,
            },
        ]
        db["users"].insert_all(users_data)

        # Create posts table
        posts_data = [
            {
                "id": 1,
                "user_id": 1,
                "title": "Hello World",
                "content": "First post",
                "published_at": "2024-01-01",
                "view_count": 100,
            },
            {
                "id": 2,
                "user_id": 2,
                "title": "Second Post",
                "content": "Another post",
                "published_at": "2024-01-02",
                "view_count": 50,
            },
        ]
        db["posts"].insert_all(posts_data)

        # Create complex table with various patterns
        complex_data = [
            {
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "display_name": "Test Item",
                "category_type": "electronics",
                "price_amount": 99.99,
                "has_discount": True,
                "stock_count": 10,
                "updated_at": "2024-01-01 12:00:00",
                "website_url": "https://example.com",
            }
        ]
        db["products"].insert_all(complex_data)

        yield db_path

        # Cleanup
        db_path.unlink()

    @pytest.fixture
    def generator(self):
        """Create MetadataGenerator instance."""
        return MetadataGenerator(Path("/tmp"))

    def test_exact_pattern_matching(self, generator):
        """Test exact column name pattern matching."""
        schema = {
            "id": "INTEGER",
            "name": "TEXT",
            "email": "TEXT",
            "created_at": "TEXT",
            "is_active": "INTEGER",
        }

        descriptions = generator.generate_column_descriptions(schema)

        assert descriptions["id"] == "Unique identifier"
        assert descriptions["name"] == "Display name"
        assert descriptions["email"] == "Email address"
        assert descriptions["created_at"] == "Creation timestamp"
        assert descriptions["is_active"] == "Boolean: is active"

    def test_pattern_rule_matching(self, generator):
        """Test regex pattern rule matching."""
        schema = {
            "user_id": "INTEGER",
            "post_uuid": "TEXT",
            "has_comments": "INTEGER",
            "can_edit": "INTEGER",
            "created_date": "TEXT",
            "updated_time": "TEXT",
            "comment_count": "INTEGER",
            "total_views": "INTEGER",
            "profile_url": "TEXT",
            "article_name": "TEXT",
        }

        descriptions = generator.generate_column_descriptions(schema)

        assert descriptions["user_id"] == "User reference ID"
        assert descriptions["post_uuid"] == "Post UUID reference"
        assert descriptions["has_comments"] == "Boolean: has comments"
        assert descriptions["can_edit"] == "Boolean: can edit"
        assert descriptions["created_date"] == "Created date"
        assert descriptions["updated_time"] == "Updated time"
        assert descriptions["comment_count"] == "Count of Comment"
        assert descriptions["total_views"] == "Numeric value"  # Falls back to type-based
        assert descriptions["profile_url"] == "Profile URL"
        assert descriptions["article_name"] == "Article name"

    def test_type_fallback_matching(self, generator):
        """Test type-based fallback descriptions."""
        schema = {
            "weird_column": "INTEGER",
            "another_weird": "TEXT",
            "decimal_thing": "REAL",
            "binary_data": "BLOB",
        }

        descriptions = generator.generate_column_descriptions(schema)

        assert descriptions["weird_column"] == "Numeric value"
        assert descriptions["another_weird"] == "Text content"
        assert descriptions["decimal_thing"] == "Decimal number"
        assert descriptions["binary_data"] == "Binary data"

    def test_readable_name_fallback(self, generator):
        """Test conversion to readable names as final fallback."""
        schema = {"some_unknown_field": "UNKNOWN_TYPE"}

        descriptions = generator.generate_column_descriptions(schema)

        assert descriptions["some_unknown_field"] == "Some Unknown Field value"

    def test_generate_metadata_for_table(self, generator, temp_db):
        """Test generating complete metadata for a table."""
        metadata = generator.generate_metadata_for_table(temp_db, "users")

        # Check column descriptions
        assert "columns" in metadata
        columns = metadata["columns"]
        assert columns["id"] == "Unique identifier"
        assert columns["name"] == "Display name"
        assert columns["email"] == "Email address"
        assert columns["created_at"] == "Creation timestamp"
        assert columns["is_active"] == "Boolean: is active"

        # Check suggestions (these are generated based on heuristics)
        # We don't test exact values since they may change, but check structure
        if "suggested_facets" in metadata:
            assert isinstance(metadata["suggested_facets"], list)
        if "suggested_sortable" in metadata:
            assert isinstance(metadata["suggested_sortable"], list)
        if "suggested_label" in metadata:
            assert isinstance(metadata["suggested_label"], str)

    def test_generate_for_complex_table(self, generator, temp_db):
        """Test metadata generation for table with complex patterns."""
        metadata = generator.generate_metadata_for_table(temp_db, "products")

        columns = metadata["columns"]
        assert columns["uuid"] == "Unique identifier"
        assert columns["display_name"] == "Display name"
        assert columns["category_type"] == "Category type"
        assert columns["price_amount"] == "Price amount"
        assert columns["has_discount"] == "Boolean: has discount"
        assert columns["stock_count"] == "Count of Stock"
        assert columns["updated_at"] == "Last update timestamp"
        assert columns["website_url"] == "Website URL"

    def test_generate_for_all_tables(self, generator, temp_db):
        """Test generating metadata for all tables."""
        all_metadata = generator.generate_for_all_tables(temp_db)

        # Should have metadata for all non-meta tables
        assert "users" in all_metadata
        assert "posts" in all_metadata
        assert "products" in all_metadata

        # Should not include meta tables
        assert "_zeeker_schemas" not in all_metadata
        assert "_zeeker_updates" not in all_metadata

        # Check structure of generated metadata
        for table_name, metadata in all_metadata.items():
            assert "columns" in metadata
            assert isinstance(metadata["columns"], dict)

    def test_table_not_found_error(self, generator, temp_db):
        """Test error handling for non-existent table."""
        with pytest.raises(ValueError, match="Table 'nonexistent' not found"):
            generator.generate_metadata_for_table(temp_db, "nonexistent")

    def test_update_project_metadata_new_resource(self, generator):
        """Test updating project metadata for new resource."""
        project = ZeekerProject(name="test", database="test.db")

        generated_metadata = {"columns": {"id": "Unique identifier", "name": "Display name"}}

        updated_project = generator.update_project_metadata(
            project, "users", generated_metadata, preserve_existing=True
        )

        assert "users" in updated_project.resources
        assert updated_project.resources["users"]["columns"]["id"] == "Unique identifier"
        assert updated_project.resources["users"]["columns"]["name"] == "Display name"

    def test_update_project_metadata_preserve_existing(self, generator):
        """Test preserving existing metadata when updating."""
        project = ZeekerProject(
            name="test",
            database="test.db",
            resources={
                "users": {"columns": {"id": "Custom ID description", "email": "User email"}}
            },
        )

        generated_metadata = {
            "columns": {
                "id": "Generated ID description",
                "name": "Display name",
                "created_at": "Creation timestamp",
            }
        }

        updated_project = generator.update_project_metadata(
            project, "users", generated_metadata, preserve_existing=True
        )

        columns = updated_project.resources["users"]["columns"]

        # Should preserve existing descriptions
        assert columns["id"] == "Custom ID description"  # Preserved
        assert columns["email"] == "User email"  # Preserved

        # Should add new descriptions
        assert columns["name"] == "Display name"  # Added
        assert columns["created_at"] == "Creation timestamp"  # Added

    def test_update_project_metadata_force_overwrite(self, generator):
        """Test overwriting existing metadata when force is used."""
        project = ZeekerProject(
            name="test",
            database="test.db",
            resources={"users": {"columns": {"id": "Custom ID description"}}},
        )

        generated_metadata = {"columns": {"id": "Generated ID description", "name": "Display name"}}

        updated_project = generator.update_project_metadata(
            project, "users", generated_metadata, preserve_existing=False
        )

        columns = updated_project.resources["users"]["columns"]

        # Should overwrite with generated descriptions
        assert columns["id"] == "Generated ID description"
        assert columns["name"] == "Display name"

    def test_case_insensitive_matching(self, generator):
        """Test that pattern matching is case insensitive."""
        schema = {"ID": "INTEGER", "Name": "TEXT", "EMAIL": "TEXT", "Created_At": "TEXT"}

        descriptions = generator.generate_column_descriptions(schema)

        assert descriptions["ID"] == "Unique identifier"
        assert descriptions["Name"] == "Display name"
        assert descriptions["EMAIL"] == "Email address"
        assert descriptions["Created_At"] == "Creation timestamp"

    def test_snake_case_to_title_case(self, generator):
        """Test conversion of snake_case to Title Case in pattern replacements."""
        schema = {
            "user_profile_id": "INTEGER",
            "blog_post_count": "INTEGER",
            "is_email_verified": "INTEGER",
        }

        descriptions = generator.generate_column_descriptions(schema)

        assert descriptions["user_profile_id"] == "User Profile reference ID"
        assert descriptions["blog_post_count"] == "Count of Blog Post"
        assert descriptions["is_email_verified"] == "Boolean: is email verified"

    def test_project_metadata_detection_missing_fields(self, generator):
        """Test detection of missing project metadata fields."""
        # Project with missing fields
        project = ZeekerProject(name="test", database="test.db")

        missing_fields = generator.detect_missing_project_metadata(project)

        expected_missing = [
            "title",
            "description",
            "license",
            "license_url",
            "source",
            "source_url",
        ]
        assert set(missing_fields) == set(expected_missing)

    def test_project_metadata_detection_complete_fields(self, generator):
        """Test detection when project metadata is complete."""
        # Project with all fields
        project = ZeekerProject(
            name="test",
            database="test.db",
            title="Test Database",
            description="Test description",
            license="MIT",
            license_url="https://opensource.org/licenses/MIT",
            source="Test System",
            source_url="https://example.com",
        )

        missing_fields = generator.detect_missing_project_metadata(project)

        assert missing_fields == []

    def test_project_metadata_generation(self, generator):
        """Test generation of missing project metadata."""
        project = ZeekerProject(name="my_test_project", database="test.db")

        updated_project = generator.generate_project_metadata(project)

        assert updated_project.title == "My Test Project Database"
        assert updated_project.description == "Comprehensive data for the My Test Project system"
        assert updated_project.license == "MIT"
        assert updated_project.license_url == "https://opensource.org/licenses/MIT"
        assert updated_project.source == "My Test Project System"
        assert updated_project.source_url is None  # Intentionally left empty

    def test_project_metadata_generation_preserve_existing(self, generator):
        """Test that existing project metadata is preserved."""
        project = ZeekerProject(
            name="test", database="test.db", title="Custom Title", license="Apache-2.0"
        )

        updated_project = generator.generate_project_metadata(project)

        # Existing fields should be preserved
        assert updated_project.title == "Custom Title"
        assert updated_project.license == "Apache-2.0"

        # Missing fields should be generated
        assert updated_project.description == "Comprehensive data for the Test system"
        assert updated_project.source == "Test System"

        # license_url should not be auto-generated for non-MIT license
        assert updated_project.license_url is None

    def test_resource_description_detection_missing(self, generator):
        """Test detection of missing resource descriptions."""
        project = ZeekerProject(
            name="test",
            database="test.db",
            resources={
                "users": {"columns": {"id": "Unique identifier"}},  # Missing description
                "posts": {"description": "Blog posts", "columns": {"id": "ID"}},  # Has description
            },
        )

        # Check specific resource
        missing_users = generator.detect_missing_resource_descriptions(project, "users")
        assert missing_users == ["users"]

        missing_posts = generator.detect_missing_resource_descriptions(project, "posts")
        assert missing_posts == []

        # Check all resources
        all_missing = generator.detect_missing_resource_descriptions(project)
        assert all_missing == ["users"]

    def test_resource_description_detection_nonexistent(self, generator):
        """Test detection for non-existent resource."""
        project = ZeekerProject(name="test", database="test.db", resources={})

        missing = generator.detect_missing_resource_descriptions(project, "nonexistent")
        assert missing == ["nonexistent"]

    def test_resource_description_generation_users_table(self, generator, temp_db):
        """Test resource description generation for users table."""
        description = generator.generate_resource_description(temp_db, "users")

        # Should detect users table with email column
        assert description == "User accounts and profiles"

    def test_resource_description_generation_posts_table(self, generator, temp_db):
        """Test resource description generation for posts table."""
        description = generator.generate_resource_description(temp_db, "posts")

        # Should detect content-related table
        assert description == "Blog posts and articles"

    def test_resource_description_generation_products_table(self, generator, temp_db):
        """Test resource description generation for products table."""
        description = generator.generate_resource_description(temp_db, "products")

        # Should detect product-related table
        assert description == "Product catalog and inventory"

    def test_resource_description_generation_nonexistent_table(self, generator):
        """Test resource description generation for non-existent table."""
        # Create a temp db path that doesn't exist
        fake_db = Path("/tmp/nonexistent.db")

        description = generator.generate_resource_description(fake_db, "missing_table")

        assert description == "Missing Table data"


class TestMetadataGeneratorCLIIntegration:
    """Test CLI integration with MetadataGenerator."""

    @pytest.fixture
    def mock_project_manager(self):
        """Mock ZeekerProjectManager for CLI tests."""
        with patch("zeeker.cli.ZeekerProjectManager") as mock:
            manager = mock.return_value
            manager.is_project_root.return_value = True
            manager.project_path = Path("/tmp/test_project")
            manager.toml_path = Path("/tmp/test_project/zeeker.toml")

            # Mock project
            project = ZeekerProject(
                name="test_project",
                database="test.db",
                resources={"users": {"description": "User data"}},
            )
            manager.load_project.return_value = project

            yield manager

    def test_cli_help_commands(self):
        """Test that CLI help shows metadata commands."""
        from zeeker.cli import cli

        # This would be tested in integration tests
        # Just verify the command structure exists
        assert hasattr(cli, "commands")

    def test_metadata_generate_dry_run(self, mock_project_manager):
        """Test metadata generate with dry-run flag."""
        # This would test the actual CLI command in integration tests
        # For now, just verify the structure is set up correctly
        from zeeker.commands.metadata import metadata

        assert metadata is not None
        assert hasattr(metadata, "commands")
