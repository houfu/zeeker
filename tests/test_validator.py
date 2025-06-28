"""
Tests for ZeekerValidator - focusing on safety-critical template validation.
"""

import pytest

from zeeker.core.validator import ZeekerValidator


class TestTemplateValidation:
    """Test template name validation - critical for site safety."""

    @pytest.fixture
    def validator(self):
        return ZeekerValidator()

    @pytest.mark.parametrize(
        "template_name",
        [
            "database.html",
            "table.html",
            "index.html",
            "query.html",
            "row.html",
            "error.html",
            "base.html",
        ],
    )
    def test_banned_templates_rejected(self, validator, template_name):
        """Banned templates must be rejected to prevent breaking core functionality."""
        result = validator.validate_template_name(template_name, "test_db")

        assert not result.is_valid
        assert len(result.errors) == 1
        assert "BANNED" in result.errors[0]
        assert "database-test_db.html" in result.errors[0]

    @pytest.mark.parametrize(
        "template_name",
        [
            "database-legal_news.html",
            "table-legal_news-headlines.html",
            "custom-legal_news-dashboard.html",
            "_partial-header.html",
            "custom-anything.html",
        ],
    )
    def test_safe_templates_accepted(self, validator, template_name):
        """Safe template names should be accepted."""
        result = validator.validate_template_name(template_name, "legal_news")

        assert result.is_valid
        assert len(result.errors) == 0

    def test_unsafe_template_gets_warning(self, validator):
        """Templates that don't follow recommended patterns get warnings."""
        result = validator.validate_template_name("my-custom-page.html", "test_db")

        assert result.is_valid  # Not banned, just not recommended
        assert len(result.warnings) == 1
        assert "doesn't follow guide's recommended patterns" in result.warnings[0]

    def test_sanitize_database_name(self, validator):
        """Database name sanitization should handle special characters."""
        # Simple name unchanged
        assert validator.sanitize_database_name("simple_name") == "simple_name"

        # Spaces become dashes with hash suffix (using actual computed hash)
        result = validator.sanitize_database_name("legal news")
        assert result.startswith("legal-news-")
        assert len(result.split("-")[-1]) == 6  # MD5 hash suffix

        # Complex name gets hash suffix
        sanitized = validator.sanitize_database_name("Legal News & Cases!")
        assert sanitized.startswith("Legal-News---Cases-")
        assert len(sanitized.split("-")[-1]) == 6  # MD5 hash suffix


class TestMetadataValidation:
    """Test metadata validation for Datasette compliance."""

    @pytest.fixture
    def validator(self):
        return ZeekerValidator()

    def test_valid_metadata_passes(self, validator):
        """Complete, valid metadata should pass validation."""
        metadata = {
            "title": "Test Database",
            "description": "A test database",
            "extra_css_urls": ["/static/databases/test_db/custom.css"],
            "extra_js_urls": ["/static/databases/test_db/custom.js"],
            "databases": {"test_db": {"description": "Test", "title": "Test DB"}},
        }

        result = validator.validate_metadata(metadata)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_databases_section_warns(self, validator):
        """Missing databases section should generate warning."""
        metadata = {"title": "Test", "description": "Test"}

        result = validator.validate_metadata(metadata)
        assert result.is_valid
        assert any("databases" in warning for warning in result.warnings)

    def test_missing_recommended_fields_warns(self, validator):
        """Missing title/description should generate warnings."""
        metadata = {"databases": {"test": {}}}

        result = validator.validate_metadata(metadata)
        assert result.is_valid
        assert any("title" in warning for warning in result.warnings)
        assert any("description" in warning for warning in result.warnings)

    def test_wrong_css_url_pattern_warns(self, validator):
        """CSS URLs not following guide pattern should warn."""
        metadata = {
            "title": "Test",
            "description": "Test",
            "extra_css_urls": ["/wrong/path/style.css"],
        }

        result = validator.validate_metadata(metadata)
        assert result.is_valid
        assert any(
            "CSS URL" in warning and "guide pattern" in warning for warning in result.warnings
        )

    def test_invalid_json_structure_fails(self, validator):
        """Metadata that can't be serialized to JSON should fail."""
        # Create circular reference that can't be JSON serialized
        metadata = {"title": "Test"}
        metadata["self"] = metadata

        result = validator.validate_metadata(metadata)
        assert not result.is_valid
        assert any("JSON structure" in error for error in result.errors)


class TestFileStructureValidation:
    """Test file structure validation."""

    @pytest.fixture
    def validator(self):
        return ZeekerValidator()

    def test_valid_structure_passes(self, validator, sample_assets_dir):
        """Valid assets directory should pass validation."""
        result = validator.validate_file_structure(sample_assets_dir, "test_db")
        assert result.is_valid

    def test_nonexistent_path_fails(self, validator, temp_dir):
        """Non-existent assets path should fail."""
        fake_path = temp_dir / "nonexistent"
        result = validator.validate_file_structure(fake_path, "test_db")

        assert not result.is_valid
        assert "does not exist" in result.errors[0]

    def test_banned_template_in_structure_fails(self, validator, sample_assets_dir):
        """Banned templates in structure should fail validation."""
        templates_dir = sample_assets_dir / "templates"
        (templates_dir / "database.html").write_text("<html>Banned template</html>")

        result = validator.validate_file_structure(sample_assets_dir, "test_db")
        assert not result.is_valid
        assert any("BANNED" in error for error in result.errors)

    def test_invalid_metadata_json_fails(self, validator, sample_assets_dir):
        """Invalid metadata.json should fail validation."""
        (sample_assets_dir / "metadata.json").write_text("invalid json {")

        result = validator.validate_file_structure(sample_assets_dir, "test_db")
        assert not result.is_valid
        assert any("metadata.json" in error for error in result.errors)

    def test_unexpected_directory_warns(self, validator, sample_assets_dir):
        """Unexpected directories should generate warnings."""
        (sample_assets_dir / "weird_directory").mkdir()

        result = validator.validate_file_structure(sample_assets_dir, "test_db")
        assert result.is_valid
        assert any("Unexpected directory" in warning for warning in result.warnings)
