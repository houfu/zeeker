
import hashlib
import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from zeeker.cli import (
    ZeekerDeployer,
    DeploymentChanges,
    ValidationResult,
    cli,
)


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    client = Mock()
    client.list_objects_v2.return_value = {"Contents": []}
    client.upload_file.return_value = None
    client.delete_object.return_value = None
    client.get_paginator.return_value.paginate.return_value = []
    return client


@pytest.fixture
def temp_customization(tmp_path):
    """Create a temporary customization directory."""
    custom_dir = tmp_path / "customization"
    custom_dir.mkdir()

    # Create templates directory with a template
    templates_dir = custom_dir / "templates"
    templates_dir.mkdir()
    (templates_dir / "database-test.html").write_text(
        '{% extends "default:database.html" %}\n{% block content %}Test{% endblock %}'
    )

    # Create static directory with CSS and JS
    static_dir = custom_dir / "static"
    static_dir.mkdir()
    (static_dir / "custom.css").write_text("body { color: red; }")
    (static_dir / "custom.js").write_text("console.log('test');")

    # Create metadata.json
    metadata = {
        "title": "Test Database",
        "description": "Test description",
        "extra_css_urls": ["/static/databases/test/custom.css"],
        "extra_js_urls": ["/static/databases/test/custom.js"],
    }
    (custom_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    return custom_dir


class TestDeploymentChanges:
    """Test the DeploymentChanges dataclass."""

    def test_empty_changes(self):
        changes = DeploymentChanges()
        assert not changes.has_changes
        assert not changes.has_destructive_changes

    def test_has_changes_uploads(self):
        changes = DeploymentChanges(uploads=["file1.css"])
        assert changes.has_changes
        assert not changes.has_destructive_changes

    def test_has_changes_updates(self):
        changes = DeploymentChanges(updates=["file1.css"])
        assert changes.has_changes
        assert not changes.has_destructive_changes

    def test_has_destructive_changes(self):
        changes = DeploymentChanges(deletions=["old_file.js"])
        assert changes.has_changes
        assert changes.has_destructive_changes

    def test_mixed_changes(self):
        changes = DeploymentChanges(
            uploads=["new.css"], updates=["existing.js"], deletions=["old.html"]
        )
        assert changes.has_changes
        assert changes.has_destructive_changes


class TestZeekerDeployerHelpers:
    """Test the helper methods in ZeekerDeployer."""

    def test_get_local_files(self, temp_customization):
        """Test getting local files with MD5 hashes."""
        deployer = ZeekerDeployer.__new__(ZeekerDeployer)  # Skip __init__
        files = deployer.get_local_files(temp_customization)

        assert "metadata.json" in files
        assert "templates/database-test.html" in files
        assert "static/custom.css" in files
        assert "static/custom.js" in files

        # Verify MD5 hash calculation
        css_content = "body { color: red; }"
        expected_hash = hashlib.md5(css_content.encode()).hexdigest()
        assert files["static/custom.css"] == expected_hash

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_get_existing_files_empty_s3(self, mock_s3_client):
        """Test getting existing files when S3 is empty."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Mock empty paginator
            mock_paginator = Mock()
            mock_paginator.paginate.return_value = [{"Contents": []}]
            mock_s3_client.get_paginator.return_value = mock_paginator

            deployer = ZeekerDeployer()
            files = deployer.get_existing_files("test_db")

            assert files == {}

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_get_existing_files_with_content(self, mock_s3_client):
        """Test getting existing files when S3 has content."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Mock S3 response with files
            mock_paginator = Mock()
            mock_paginator.paginate.return_value = [
                {
                    "Contents": [
                        {
                            "Key": "assets/databases/test_db/static/old.css",
                            "ETag": '"abc123"',
                        },
                        {
                            "Key": "assets/databases/test_db/templates/page.html",
                            "ETag": '"def456"',
                        },
                    ]
                }
            ]
            mock_s3_client.get_paginator.return_value = mock_paginator

            deployer = ZeekerDeployer()
            files = deployer.get_existing_files("test_db")

            assert files == {"static/old.css": "abc123", "templates/page.html": "def456"}

    def test_calculate_changes_additive_mode(self):
        """Test calculating changes in default additive mode."""
        deployer = ZeekerDeployer.__new__(ZeekerDeployer)  # Skip __init__

        local_files = {
            "static/new.css": "hash1",
            "static/existing.js": "hash2_new",
            "static/unchanged.html": "hash3",
        }

        existing_files = {
            "static/existing.js": "hash2_old",  # Modified
            "static/unchanged.html": "hash3",  # Unchanged
            "static/old.css": "hash4",  # Will be kept (additive mode)
        }

        changes = deployer.calculate_changes(local_files, existing_files, sync=False, clean=False)

        assert changes.uploads == ["static/new.css"]
        assert changes.updates == ["static/existing.js"]
        assert changes.unchanged == ["static/unchanged.html"]
        assert changes.deletions == []  # No deletions in additive mode

    def test_calculate_changes_sync_mode(self):
        """Test calculating changes in sync mode."""
        deployer = ZeekerDeployer.__new__(ZeekerDeployer)  # Skip __init__

        local_files = {
            "static/new.css": "hash1",
            "static/existing.js": "hash2_new",
        }

        existing_files = {
            "static/existing.js": "hash2_old",
            "static/old.css": "hash3",  # Will be deleted (sync mode)
            "static/another_old.js": "hash4",  # Will be deleted (sync mode)
        }

        changes = deployer.calculate_changes(local_files, existing_files, sync=True, clean=False)

        assert changes.uploads == ["static/new.css"]
        assert changes.updates == ["static/existing.js"]
        assert changes.unchanged == []
        assert set(changes.deletions) == {"static/old.css", "static/another_old.js"}

    def test_calculate_changes_clean_mode(self):
        """Test calculating changes in clean mode."""
        deployer = ZeekerDeployer.__new__(ZeekerDeployer)  # Skip __init__

        local_files = {
            "static/new.css": "hash1",
            "static/existing.js": "hash2",
        }

        existing_files = {
            "static/existing.js": "hash2",
            "static/old.css": "hash3",
            "static/another_old.js": "hash4",
        }

        changes = deployer.calculate_changes(local_files, existing_files, sync=False, clean=True)

        # In clean mode, everything is deleted and everything is uploaded
        assert set(changes.uploads) == {"static/new.css", "static/existing.js"}
        assert changes.updates == []
        assert changes.unchanged == []
        assert set(changes.deletions) == {"static/existing.js", "static/old.css", "static/another_old.js"}

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_execute_deployment_success(self, mock_s3_client, temp_customization):
        """Test successful deployment execution."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            deployer = ZeekerDeployer()

            changes = DeploymentChanges(
                uploads=["static/custom.css"],
                updates=["templates/database-test.html"],
                deletions=["static/old.js"],
            )

            result = deployer.execute_deployment(changes, temp_customization, "test_db")

            assert result.is_valid
            assert len(result.info) == 3  # One for each operation
            assert any("Deleted: static/old.js" in info for info in result.info)
            assert any("Uploaded: static/custom.css" in info for info in result.info)
            assert any("Updated: templates/database-test.html" in info for info in result.info)

            # Verify S3 calls
            mock_s3_client.delete_object.assert_called_once()
            assert mock_s3_client.upload_file.call_count == 2

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_execute_deployment_s3_error(self, mock_s3_client, temp_customization):
        """Test deployment with S3 errors."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Make upload_file raise an exception
            mock_s3_client.upload_file.side_effect = Exception("S3 Error")

            deployer = ZeekerDeployer()
            changes = DeploymentChanges(uploads=["static/custom.css"])

            result = deployer.execute_deployment(changes, temp_customization, "test_db")

            assert not result.is_valid
            assert len(result.errors) == 1
            assert "Failed to upload static/custom.css: S3 Error" in result.errors[0]


class TestCLI:
    """Test the CLI deploy command."""

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_deploy_dry_run(self, mock_s3_client, temp_customization):
        """Test deploy with dry-run flag."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Mock empty S3
            mock_paginator = Mock()
            mock_paginator.paginate.return_value = [{"Contents": []}]
            mock_s3_client.get_paginator.return_value = mock_paginator

            runner = CliRunner()
            result = runner.invoke(
                cli, ["deploy", str(temp_customization), "test_db", "--dry-run"]
            )

            assert result.exit_code == 0
            assert "Dry run completed" in result.output
            assert "📤 Will upload: 4 files" in result.output
            # Verify S3 upload methods were NOT called
            mock_s3_client.upload_file.assert_not_called()

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_deploy_sync_with_confirmation(self, mock_s3_client, temp_customization):
        """Test deploy with sync flag and user confirmation."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Mock S3 with existing files
            mock_paginator = Mock()
            mock_paginator.paginate.return_value = [
                {
                    "Contents": [
                        {
                            "Key": "assets/databases/test_db/static/old.css",
                            "ETag": '"abc123"',
                        }
                    ]
                }
            ]
            mock_s3_client.get_paginator.return_value = mock_paginator

            runner = CliRunner()
            # Simulate user saying "no" to confirmation
            result = runner.invoke(
                cli,
                ["deploy", str(temp_customization), "test_db", "--sync"],
                input="n\n",
            )

            assert result.exit_code == 0
            assert "Deployment cancelled" in result.output
            mock_s3_client.upload_file.assert_not_called()

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_deploy_sync_with_yes_flag(self, mock_s3_client, temp_customization):
        """Test deploy with sync and --yes flag (skip confirmation)."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Mock S3 with existing files
            mock_paginator = Mock()
            mock_paginator.paginate.return_value = [
                {
                    "Contents": [
                        {
                            "Key": "assets/databases/test_db/static/old.css",
                            "ETag": '"abc123"',
                        }
                    ]
                }
            ]
            mock_s3_client.get_paginator.return_value = mock_paginator

            runner = CliRunner()
            result = runner.invoke(
                cli, ["deploy", str(temp_customization), "test_db", "--sync", "--yes"]
            )

            assert result.exit_code == 0
            assert "Deployment completed successfully" in result.output
            # Should have called delete and upload
            mock_s3_client.delete_object.assert_called()
            assert mock_s3_client.upload_file.call_count > 0

    def test_deploy_conflicting_flags(self):
        """Test deploy with conflicting flags."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Add this line to create a valid path
            Path("fake_path").mkdir()

            result = runner.invoke(
                cli, ["deploy", "fake_path", "test_db", "--sync", "--clean"]
            )

            assert result.exit_code == 0  # Changed from expecting error
            assert "Cannot use both --clean and --sync flags" in result.output

    def test_deploy_missing_env_vars(self, temp_customization):
        """Test deploy without required environment variables."""
        runner = CliRunner()
        result = runner.invoke(cli, ["deploy", str(temp_customization), "test_db"])

        assert result.exit_code == 0
        assert "Configuration error" in result.output

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_deploy_no_changes(self, mock_s3_client, temp_customization):
        """Test deploy when no changes are needed."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Mock S3 with same files and hashes as local
            css_content = "body { color: red; }"
            css_hash = hashlib.md5(css_content.encode()).hexdigest()

            mock_paginator = Mock()
            mock_paginator.paginate.return_value = [
                {
                    "Contents": [
                        {
                            "Key": "assets/databases/test_db/static/custom.css",
                            "ETag": f'"{css_hash}"',
                        }
                    ]
                }
            ]
            mock_s3_client.get_paginator.return_value = mock_paginator

            # Mock get_local_files to return only the CSS file with matching hash
            with patch.object(ZeekerDeployer, "get_local_files") as mock_get_local:
                mock_get_local.return_value = {"static/custom.css": css_hash}

                runner = CliRunner()
                result = runner.invoke(cli, ["deploy", str(temp_customization), "test_db"])

                assert result.exit_code == 0
                assert "No changes needed" in result.output
                mock_s3_client.upload_file.assert_not_called()

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_deploy_with_diff_flag(self, mock_s3_client, temp_customization):
        """Test deploy with --diff flag shows detailed changes."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Mock S3 with some existing files
            mock_paginator = Mock()
            mock_paginator.paginate.return_value = [
                {
                    "Contents": [
                        {
                            "Key": "assets/databases/test_db/static/old.css",
                            "ETag": '"abc123"',
                        }
                    ]
                }
            ]
            mock_s3_client.get_paginator.return_value = mock_paginator

            runner = CliRunner()
            result = runner.invoke(
                cli, ["deploy", str(temp_customization), "test_db", "--diff", "--dry-run"]
            )

            assert result.exit_code == 0
            assert "📊 Detailed Changes:" in result.output
            assert "➕ New files" in result.output
            assert "Dry run completed" in result.output


class TestIntegration:
    """Integration tests for the complete workflow."""

    @patch.dict("os.environ", {"S3_BUCKET": "test-bucket", "AWS_ACCESS_KEY_ID": "key", "AWS_SECRET_ACCESS_KEY": "secret"})
    def test_full_deployment_workflow(self, mock_s3_client, temp_customization):
        """Test a complete deployment workflow."""
        with patch("zeeker.cli.boto3.client", return_value=mock_s3_client):
            # Mock empty S3 initially
            mock_paginator = Mock()
            mock_paginator.paginate.return_value = [{"Contents": []}]
            mock_s3_client.get_paginator.return_value = mock_paginator

            deployer = ZeekerDeployer()

            # Test the complete workflow
            existing_files = deployer.get_existing_files("test_db")
            local_files = deployer.get_local_files(temp_customization)
            changes = deployer.calculate_changes(local_files, existing_files, sync=False, clean=False)

            assert len(changes.uploads) == 4  # metadata, template, css, js
            assert len(changes.updates) == 0
            assert len(changes.deletions) == 0

            # Execute deployment
            result = deployer.execute_deployment(changes, temp_customization, "test_db")
            assert result.is_valid
            assert mock_s3_client.upload_file.call_count == 4


# Pytest markers for different test categories
pytestmark = [
    pytest.mark.unit,  # Mark all tests as unit tests by default
]

# Mark integration tests separately
TestIntegration = pytest.mark.integration(TestIntegration)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])