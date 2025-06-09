"""
Test suite for Zeeker CLI functionality.

Tests directory structure validation, template naming, metadata validation,
and CLI command functionality.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from zeeker.cli import (
    DatabaseCustomization,
    ValidationResult,
    ZeekerDeployer,
    ZeekerGenerator,
    ZeekerValidator,
    cli,
)


class TestZeekerValidator:
    """Test the ZeekerValidator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ZeekerValidator()

    def test_sanitize_database_name(self):
        """Test database name sanitization."""
        # Normal names should pass through
        assert self.validator.sanitize_database_name("test_db") == "test_db"
        assert self.validator.sanitize_database_name("test-db") == "test-db"
        assert self.validator.sanitize_database_name("testdb123") == "testdb123"

        # Special characters should be replaced
        result = self.validator.sanitize_database_name("test@db#name")
        assert "@" not in result
        assert "#" not in result
        assert result.startswith("test-db-name")

        # Should add hash suffix for complex names
        result = self.validator.sanitize_database_name("test@db#name!")
        assert len(result.split("-")) >= 4  # Original parts + hash

    def test_validate_template_name_banned_templates(self):
        """Test validation of banned template names."""
        banned_templates = [
            "database.html",
            "table.html",
            "index.html",
            "query.html",
            "row.html",
            "error.html",
            "base.html",
        ]

        for template in banned_templates:
            result = self.validator.validate_template_name(template, "testdb")
            assert not result.is_valid
            assert len(result.errors) > 0
            assert "banned" in result.errors[0].lower()

    def test_validate_template_name_safe_patterns(self):
        """Test validation of safe template naming patterns."""
        safe_templates = [
            ("database-testdb.html", "testdb"),
            ("table-testdb-users.html", "testdb"),
            ("custom-header.html", "testdb"),
            ("_partial-footer.html", "testdb"),
        ]

        for template, db_name in safe_templates:
            result = self.validator.validate_template_name(template, db_name)
            assert result.is_valid
            # May have warnings but should not have errors

    def test_validate_template_name_warnings(self):
        """Test that improper naming generates warnings."""
        # Should warn about not including database name
        result = self.validator.validate_template_name("database-wrongname.html", "testdb")
        assert result.is_valid
        assert len(result.warnings) > 0
        assert "database name" in result.warnings[0].lower()

        # Should warn about not following patterns
        result = self.validator.validate_template_name("random.html", "testdb")
        assert result.is_valid
        assert len(result.warnings) > 0
        assert "recommended naming patterns" in result.warnings[0].lower()

    def test_validate_metadata_structure(self):
        """Test metadata validation."""
        # Valid metadata
        valid_metadata = {
            "title": "Test Database",
            "description": "A test database",
            "license": "CC-BY-4.0",
            "extra_css_urls": ["/static/databases/testdb/custom.css"],
            "extra_js_urls": ["/static/databases/testdb/custom.js"],
        }

        result = self.validator.validate_metadata(valid_metadata)
        assert result.is_valid

        # Missing recommended fields
        minimal_metadata = {"license": "CC-BY-4.0"}
        result = self.validator.validate_metadata(minimal_metadata)
        assert result.is_valid  # Valid but should have warnings
        assert len(result.warnings) >= 2  # Missing title and description

        # Invalid JSON structure (circular reference)
        invalid_metadata = {"key": None}
        invalid_metadata["circular"] = invalid_metadata
        result = self.validator.validate_metadata(invalid_metadata)
        assert not result.is_valid

    def test_validate_metadata_url_patterns(self):
        """Test validation of CSS/JS URL patterns."""
        metadata_with_bad_urls = {
            "title": "Test",
            "description": "Test",
            "extra_css_urls": ["http://example.com/style.css"],
            "extra_js_urls": ["/wrong/path/script.js"],
        }

        result = self.validator.validate_metadata(metadata_with_bad_urls)
        assert result.is_valid  # Valid but should warn
        assert len(result.warnings) >= 2  # Both URLs should warn

    def test_validate_file_structure_missing_path(self):
        """Test validation with missing customization path."""
        result = self.validator.validate_file_structure(Path("/nonexistent"), "testdb")
        assert not result.is_valid
        assert "does not exist" in result.errors[0].lower()

    def test_validate_file_structure_complete(self):
        """Test validation of complete file structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create expected structure
            (base_path / "templates").mkdir()
            (base_path / "static").mkdir()
            (base_path / "static" / "images").mkdir()

            # Create valid files
            (base_path / "templates" / "database-testdb.html").write_text("<h1>Test Template</h1>")
            (base_path / "static" / "custom.css").write_text("body { color: red; }")

            # Create valid metadata
            metadata = {
                "title": "Test Database",
                "description": "A test database",
                "license": "CC-BY-4.0",
            }
            (base_path / "metadata.json").write_text(json.dumps(metadata))

            result = self.validator.validate_file_structure(base_path, "testdb")
            assert result.is_valid

    def test_validate_file_structure_with_issues(self):
        """Test validation with various file structure issues."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create structure with issues
            (base_path / "templates").mkdir()
            (base_path / "static").mkdir()
            (base_path / "unexpected_dir").mkdir()  # Should warn

            # Create banned template
            (base_path / "templates" / "database.html").write_text("<h1>Banned</h1>")

            # Create invalid metadata
            (base_path / "metadata.json").write_text("invalid json {")

            result = self.validator.validate_file_structure(base_path, "testdb")
            assert not result.is_valid  # Invalid due to bad metadata
            assert len(result.errors) > 0  # Banned template and bad JSON
            assert len(result.warnings) > 0  # Unexpected directory


class TestZeekerGenerator:
    """Test the ZeekerGenerator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_path = Path(self.temp_dir)
        self.generator = ZeekerGenerator("test_database", self.output_path)

    def test_initialization(self):
        """Test generator initialization."""
        assert self.generator.database_name == "test_database"
        assert self.generator.sanitized_name == "test_database"
        assert self.generator.output_path == self.output_path

    def test_create_base_structure(self):
        """Test creation of base directory structure."""
        self.generator.create_base_structure()

        expected_dirs = [
            self.output_path,
            self.output_path / "templates",
            self.output_path / "static",
            self.output_path / "static" / "images",
        ]

        for dir_path in expected_dirs:
            assert dir_path.exists()
            assert dir_path.is_dir()

    def test_generate_metadata_template(self):
        """Test metadata template generation."""
        metadata = self.generator.generate_metadata_template(
            title="Test DB",
            description="A test database",
            extra_css=["custom.css"],
            extra_js=["app.js"],
        )

        assert metadata["title"] == "Test DB"
        assert metadata["description"] == "A test database"
        assert metadata["license"] == "CC-BY-4.0"
        assert "/static/databases/test_database/custom.css" in metadata["extra_css_urls"]
        assert "/static/databases/test_database/app.js" in metadata["extra_js_urls"]
        assert "test_database" in metadata["databases"]

    def test_generate_css_template(self):
        """Test CSS template generation."""
        css = self.generator.generate_css_template(
            primary_color="#123456", accent_color="#654321", include_examples=True
        )

        assert "#123456" in css
        assert "#654321" in css
        assert "test_database" in css
        assert ":root" in css  # CSS custom properties
        assert "data-database" in css  # Scoped styles

    def test_generate_js_template(self):
        """Test JavaScript template generation."""
        js = self.generator.generate_js_template(include_examples=True)

        assert "test_database" in js
        assert "isDatabasePage" in js
        assert "DOMContentLoaded" in js
        assert "console.log" in js

    def test_generate_database_template(self):
        """Test database template generation."""
        template = self.generator.generate_database_template("Custom Title")

        assert "Custom Title" in template
        assert "test_database" in template
        assert "extends" in template
        assert "block content" in template

    def test_save_customization(self):
        """Test saving complete customization to disk."""
        metadata = {"title": "Test", "description": "Test DB"}
        css_content = "body { color: red; }"
        js_content = "console.log('test');"
        templates = {"database-test.html": "<h1>Test</h1>"}

        self.generator.save_customization(metadata, css_content, js_content, templates)

        # Check that all files were created
        assert (self.output_path / "metadata.json").exists()
        assert (self.output_path / "static" / "custom.css").exists()
        assert (self.output_path / "static" / "custom.js").exists()
        assert (self.output_path / "templates" / "database-test.html").exists()

        # Verify content
        saved_metadata = json.loads((self.output_path / "metadata.json").read_text())
        assert saved_metadata["title"] == "Test"

        saved_css = (self.output_path / "static" / "custom.css").read_text()
        assert "color: red" in saved_css


class TestZeekerDeployer:
    """Test the ZeekerDeployer class."""

    @patch("os.getenv")
    @patch("boto3.client")
    def test_initialization_success(self, mock_boto_client, mock_getenv):
        """Test successful deployer initialization with environment variables."""
        # Mock environment variables
        env_vars = {
            "S3_BUCKET": "test-bucket",
            "S3_ENDPOINT_URL": "https://sin1.contabostorage.com",
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        deployer = ZeekerDeployer()

        assert deployer.bucket_name == "test-bucket"
        assert deployer.endpoint_url == "https://sin1.contabostorage.com"

        # Verify boto3.client was called with correct parameters
        mock_boto_client.assert_called_once_with(
            "s3",
            aws_access_key_id="test_access_key",
            aws_secret_access_key="test_secret_key",
            endpoint_url="https://sin1.contabostorage.com",
        )

    @patch("os.getenv")
    def test_initialization_missing_bucket(self, mock_getenv):
        """Test initialization failure when S3_BUCKET is missing."""
        # Mock missing S3_BUCKET
        env_vars = {
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        with pytest.raises(ValueError, match="S3_BUCKET environment variable is required"):
            ZeekerDeployer()

    @patch("os.getenv")
    def test_initialization_missing_credentials(self, mock_getenv):
        """Test initialization failure when AWS credentials are missing."""
        # Mock missing credentials
        env_vars = {
            "S3_BUCKET": "test-bucket",
            "AWS_ACCESS_KEY_ID": "test_access_key",
            # Missing AWS_SECRET_ACCESS_KEY
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        with pytest.raises(ValueError, match="AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"):
            ZeekerDeployer()

    @patch("os.getenv")
    @patch("boto3.client")
    def test_initialization_without_endpoint_url(self, mock_boto_client, mock_getenv):
        """Test initialization without custom endpoint URL (default AWS)."""
        # Mock environment variables without endpoint URL
        env_vars = {
            "S3_BUCKET": "test-bucket",
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        deployer = ZeekerDeployer()

        assert deployer.bucket_name == "test-bucket"
        assert deployer.endpoint_url is None

        # Verify boto3.client was called without endpoint_url
        mock_boto_client.assert_called_once_with(
            "s3",
            aws_access_key_id="test_access_key",
            aws_secret_access_key="test_secret_key",
        )

    @patch("os.getenv")
    @patch("boto3.client")
    def test_upload_customization_dry_run(self, mock_boto_client, mock_getenv):
        """Test dry run upload functionality."""
        # Mock environment variables
        env_vars = {
            "S3_BUCKET": "test-bucket",
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        deployer = ZeekerDeployer()

        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)
            (test_path / "test.txt").write_text("test content")

            result = deployer.upload_customization(test_path, "testdb", dry_run=True)

            assert result.is_valid
            assert len(result.info) > 0
            assert "Would upload" in result.info[0]
            # Should not have called upload_file in dry run
            mock_client.upload_file.assert_not_called()

    @patch("os.getenv")
    @patch("boto3.client")
    def test_upload_customization_missing_path(self, mock_boto_client, mock_getenv):
        """Test upload with missing local path."""
        # Mock environment variables
        env_vars = {
            "S3_BUCKET": "test-bucket",
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        deployer = ZeekerDeployer()
        result = deployer.upload_customization(Path("/nonexistent"), "testdb")

        assert not result.is_valid
        assert "does not exist" in result.errors[0].lower()

    @patch("os.getenv")
    @patch("boto3.client")
    def test_list_customizations(self, mock_boto_client, mock_getenv):
        """Test listing customizations from S3."""
        # Mock environment variables
        env_vars = {
            "S3_BUCKET": "test-bucket",
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        # Mock S3 response
        mock_client.list_objects_v2.return_value = {
            "CommonPrefixes": [
                {"Prefix": "assets/databases/db1/"},
                {"Prefix": "assets/databases/db2/"},
            ]
        }

        deployer = ZeekerDeployer()
        databases = deployer.list_customizations()

        assert "db1" in databases
        assert "db2" in databases
        assert len(databases) == 2


class TestCLICommands:
    """Test the CLI command interface."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_generate_command(self):
        """Test the generate CLI command."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(
                cli,
                [
                    "generate",
                    "test_db",
                    "output",
                    "--title",
                    "Test Database",
                    "--description",
                    "A test database",
                ],
            )

            assert result.exit_code == 0
            assert "Generated customization" in result.output

            # Check that files were created
            output_path = Path("output")
            assert (output_path / "metadata.json").exists()
            assert (output_path / "static" / "custom.css").exists()
            assert (output_path / "static" / "custom.js").exists()
            assert (output_path / "templates").exists()

    def test_validate_command_success(self):
        """Test the validate CLI command with valid structure."""
        with self.runner.isolated_filesystem():
            # First generate a customization
            self.runner.invoke(
                cli, ["generate", "test_db", "output", "--title", "Test", "--description", "Test"]
            )

            # Then validate it
            result = self.runner.invoke(cli, ["validate", "output", "test_db"])

            assert result.exit_code == 0
            assert "✅" in result.output or "Validation passed" in result.output

    def test_validate_command_failure(self):
        """Test the validate CLI command with invalid structure."""
        with self.runner.isolated_filesystem():
            # Create invalid structure
            Path("invalid").mkdir()
            (Path("invalid") / "templates").mkdir()
            (Path("invalid") / "templates" / "database.html").write_text("banned template")

            result = self.runner.invoke(cli, ["validate", "invalid", "test_db"])

            assert result.exit_code == 0  # Command runs but validation fails
            assert "❌" in result.output or "ERROR" in result.output

    @patch("zeeker.cli.ZeekerDeployer")
    @patch("os.getenv")
    def test_deploy_command_dry_run(self, mock_getenv, mock_deployer_class):
        """Test the deploy CLI command in dry run mode."""
        # Mock environment variables
        env_vars = {
            "S3_BUCKET": "test-bucket",
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        mock_deployer = MagicMock()
        mock_deployer_class.return_value = mock_deployer
        mock_deployer.upload_customization.return_value = ValidationResult(
            is_valid=True, info=["Would upload: test.txt"]
        )
        mock_deployer.bucket_name = "test-bucket"

        with self.runner.isolated_filesystem():
            Path("test_customization").mkdir()
            (Path("test_customization") / "test.txt").write_text("test")

            result = self.runner.invoke(
                cli,
                [
                    "deploy",
                    "test_customization",
                    "test_db",
                    "--dry-run",
                ],
            )

            assert result.exit_code == 0
            assert "Dry run completed" in result.output
            mock_deployer.upload_customization.assert_called_once()

    @patch("os.getenv")
    def test_deploy_command_missing_env_vars(self, mock_getenv):
        """Test deploy command with missing environment variables."""
        # Mock missing environment variables
        mock_getenv.return_value = None

        with self.runner.isolated_filesystem():
            Path("test_customization").mkdir()
            (Path("test_customization") / "test.txt").write_text("test")

            result = self.runner.invoke(
                cli,
                [
                    "deploy",
                    "test_customization",
                    "test_db",
                ],
            )

            assert result.exit_code == 0  # Command doesn't fail, just shows error
            assert "Configuration error" in result.output
            assert "S3_BUCKET" in result.output

    @patch("zeeker.cli.ZeekerDeployer")
    @patch("os.getenv")
    def test_list_databases_command(self, mock_getenv, mock_deployer_class):
        """Test the list-databases CLI command."""
        # Mock environment variables
        env_vars = {
            "S3_BUCKET": "test-bucket",
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
        }
        mock_getenv.side_effect = lambda key, default=None: env_vars.get(key, default)

        mock_deployer = MagicMock()
        mock_deployer_class.return_value = mock_deployer
        mock_deployer.list_customizations.return_value = ["db1", "db2", "db3"]
        mock_deployer.bucket_name = "test-bucket"

        result = self.runner.invoke(cli, ["list-databases"])

        assert result.exit_code == 0
        assert "db1" in result.output
        assert "db2" in result.output
        assert "db3" in result.output
        assert "test-bucket" in result.output

    @patch("os.getenv")
    def test_list_databases_command_missing_env_vars(self, mock_getenv):
        """Test list-databases command with missing environment variables."""
        # Mock missing environment variables
        mock_getenv.return_value = None

        result = self.runner.invoke(cli, ["list-databases"])

        assert result.exit_code == 0  # Command doesn't fail, just shows error
        assert "Configuration error" in result.output
        assert "S3_BUCKET" in result.output

    def test_cli_help(self):
        """Test that CLI help works."""
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Zeeker Database Customization Tool" in result.output


class TestDatabaseCustomization:
    """Test the DatabaseCustomization dataclass."""

    def test_initialization(self):
        """Test DatabaseCustomization initialization."""
        customization = DatabaseCustomization(database_name="test_db", base_path=Path("/test"))

        assert customization.database_name == "test_db"
        assert customization.base_path == Path("/test")
        assert customization.templates == {}
        assert customization.static_files == {}
        assert customization.metadata is None


class TestValidationResult:
    """Test the ValidationResult dataclass."""

    def test_initialization(self):
        """Test ValidationResult initialization."""
        result = ValidationResult(is_valid=True)

        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.info == []

    def test_with_messages(self):
        """Test ValidationResult with various message types."""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
            info=["Info 1"],
        )

        assert not result.is_valid
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert len(result.info) == 1


if __name__ == "__main__":
    pytest.main([__file__])
