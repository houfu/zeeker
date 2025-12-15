"""
Tests for ZeekerDeployer S3 deployment functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from zeeker.core.deployer import ZeekerDeployer
from zeeker.core.types import DeploymentChanges


class TestZeekerDeployer:
    """Test S3 deployment functionality."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        mock_client = MagicMock()
        mock_client.upload_file.return_value = None
        mock_client.delete_object.return_value = None
        mock_client.list_objects_v2.return_value = {"Contents": []}

        # Mock paginator
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Contents": []}]
        mock_client.get_paginator.return_value = mock_paginator

        return mock_client

    @pytest.fixture
    def deployer(self, s3_env_vars, mock_s3_client):
        """Create a ZeekerDeployer with mocked S3 client."""
        with patch("boto3.client", return_value=mock_s3_client):
            deployer = ZeekerDeployer()
            deployer.s3_client = mock_s3_client
            return deployer

    def test_init_with_missing_bucket(self):
        """Test initialization fails without S3_BUCKET."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="S3_BUCKET environment variable is required"):
                ZeekerDeployer()

    def test_init_with_missing_credentials(self):
        """Test initialization fails without AWS credentials."""
        with patch.dict("os.environ", {"S3_BUCKET": "test-bucket"}, clear=True):
            with pytest.raises(ValueError, match="AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY"):
                ZeekerDeployer()

    def test_upload_database_success(self, deployer, temp_dir):
        """Test successful database upload."""
        db_path = temp_dir / "test.db"
        db_path.write_text("test database content")

        result = deployer.upload_database(db_path, "test_database")

        assert result.is_valid
        assert len(result.errors) == 0
        assert "Uploaded database" in result.info[0]

        deployer.s3_client.upload_file.assert_called_once_with(
            str(db_path), "test-bucket", "latest/test_database.db"
        )

    def test_upload_database_missing_file(self, deployer, temp_dir):
        """Test upload fails with missing database file."""
        missing_path = temp_dir / "missing.db"

        result = deployer.upload_database(missing_path, "test_database")

        assert not result.is_valid
        assert "Database file not found" in result.errors[0]
        deployer.s3_client.upload_file.assert_not_called()

    def test_upload_database_dry_run(self, deployer, temp_dir):
        """Test dry run doesn't actually upload."""
        db_path = temp_dir / "test.db"
        db_path.write_text("test database content")

        result = deployer.upload_database(db_path, "test_database", dry_run=True)

        assert result.is_valid
        assert "Would upload" in result.info[0]
        deployer.s3_client.upload_file.assert_not_called()

    def test_get_existing_files(self, deployer):
        """Test getting existing files from S3."""
        # Mock S3 response
        mock_contents = [
            {"Key": "assets/databases/test_db/metadata.json", "ETag": '"abc123"'},
            {"Key": "assets/databases/test_db/static/custom.css", "ETag": '"def456"'},
        ]

        mock_page = {"Contents": mock_contents}
        deployer.s3_client.get_paginator.return_value.paginate.return_value = [mock_page]

        result = deployer.get_existing_files("test_db")

        expected = {
            "metadata.json": "abc123",
            "static/custom.css": "def456",
        }
        assert result == expected

    def test_get_local_files(self, deployer, temp_dir):
        """Test getting local files with hashes."""
        # Create test files
        (temp_dir / "metadata.json").write_text('{"title": "test"}')
        (temp_dir / "static").mkdir()
        (temp_dir / "static" / "custom.css").write_text("body { color: red; }")

        result = deployer.get_local_files(temp_dir)

        assert "metadata.json" in result
        assert "static/custom.css" in result
        assert len(result["metadata.json"]) == 32  # MD5 hash length
        assert len(result["static/custom.css"]) == 32

    def test_calculate_changes_uploads(self, deployer):
        """Test change calculation for new files."""
        local_files = {"metadata.json": "hash1", "static/custom.css": "hash2"}
        existing_files = {}

        changes = deployer.calculate_changes(local_files, existing_files, sync=False, clean=False)

        assert changes.uploads == ["metadata.json", "static/custom.css"]
        assert changes.updates == []
        assert changes.deletions == []
        assert changes.has_changes

    def test_calculate_changes_updates(self, deployer):
        """Test change calculation for modified files."""
        local_files = {"metadata.json": "newhash", "static/custom.css": "hash2"}
        existing_files = {"metadata.json": "oldhash", "static/custom.css": "hash2"}

        changes = deployer.calculate_changes(local_files, existing_files, sync=False, clean=False)

        assert changes.uploads == []
        assert changes.updates == ["metadata.json"]
        assert changes.unchanged == ["static/custom.css"]
        assert changes.deletions == []
        assert changes.has_changes

    def test_calculate_changes_sync_deletions(self, deployer):
        """Test change calculation with sync deleting remote files."""
        local_files = {"metadata.json": "hash1"}
        existing_files = {"metadata.json": "hash1", "old_file.txt": "hash2"}

        changes = deployer.calculate_changes(local_files, existing_files, sync=True, clean=False)

        assert changes.uploads == []
        assert changes.updates == []
        assert changes.unchanged == ["metadata.json"]
        assert changes.deletions == ["old_file.txt"]
        assert changes.has_changes
        assert changes.has_destructive_changes

    def test_calculate_changes_clean(self, deployer):
        """Test change calculation with clean deployment."""
        local_files = {"metadata.json": "hash1"}
        existing_files = {"old_metadata.json": "hash2", "old_file.txt": "hash3"}

        changes = deployer.calculate_changes(local_files, existing_files, sync=False, clean=True)

        assert changes.uploads == ["metadata.json"]
        assert changes.updates == []
        assert changes.deletions == ["old_metadata.json", "old_file.txt"]
        assert changes.has_changes
        assert changes.has_destructive_changes

    def test_execute_deployment_uploads(self, deployer, temp_dir):
        """Test executing deployment with uploads."""
        # Create test files
        (temp_dir / "metadata.json").write_text('{"title": "test"}')

        changes = DeploymentChanges()
        changes.uploads = ["metadata.json"]

        result = deployer.execute_deployment(changes, temp_dir, "test_db")

        assert result.is_valid
        assert "Uploaded: metadata.json" in result.info

        deployer.s3_client.upload_file.assert_called_once_with(
            str(temp_dir / "metadata.json"), "test-bucket", "assets/databases/test_db/metadata.json"
        )

    def test_execute_deployment_deletions(self, deployer, temp_dir):
        """Test executing deployment with deletions."""
        changes = DeploymentChanges()
        changes.deletions = ["old_file.txt"]

        result = deployer.execute_deployment(changes, temp_dir, "test_db")

        assert result.is_valid
        assert "Deleted: old_file.txt" in result.info

        deployer.s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="assets/databases/test_db/old_file.txt"
        )

    def test_execute_deployment_s3_error(self, deployer, temp_dir):
        """Test deployment handles S3 errors gracefully."""
        (temp_dir / "metadata.json").write_text('{"title": "test"}')

        # Mock S3 upload failure
        deployer.s3_client.upload_file.side_effect = Exception("S3 error")

        changes = DeploymentChanges()
        changes.uploads = ["metadata.json"]

        result = deployer.execute_deployment(changes, temp_dir, "test_db")

        assert not result.is_valid
        assert "Failed to upload metadata.json: S3 error" in result.errors

    def test_list_assets(self, deployer):
        """Test listing database assets."""
        # Mock S3 response
        mock_response = {
            "CommonPrefixes": [
                {"Prefix": "assets/databases/legal_news/"},
                {"Prefix": "assets/databases/court_cases/"},
            ]
        }
        deployer.s3_client.list_objects_v2.return_value = mock_response

        result = deployer.list_assets()

        assert result == ["court_cases", "legal_news"]  # Sorted
        deployer.s3_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket", Prefix="assets/databases/", Delimiter="/"
        )

    def test_list_assets_empty(self, deployer):
        """Test listing assets when none exist."""
        deployer.s3_client.list_objects_v2.return_value = {}

        result = deployer.list_assets()

        assert result == []

    def test_list_assets_with_error(self, deployer):
        """Test listing assets handles errors gracefully."""
        deployer.s3_client.list_objects_v2.side_effect = Exception("S3 error")

        result = deployer.list_assets()

        assert result == []

    def test_legacy_upload_assets(self, deployer, temp_dir):
        """Test legacy upload_assets method for backward compatibility."""
        # Create test files
        (temp_dir / "metadata.json").write_text('{"title": "test"}')
        (temp_dir / "static").mkdir()
        (temp_dir / "static" / "custom.css").write_text("body { color: red; }")

        result = deployer.upload_assets(temp_dir, "test_db")

        assert result.is_valid
        assert len(result.info) == 2  # Two files uploaded
        assert deployer.s3_client.upload_file.call_count == 2

        # Check the calls
        calls = deployer.s3_client.upload_file.call_args_list
        assert any("metadata.json" in str(call) for call in calls)
        assert any("custom.css" in str(call) for call in calls)

    def test_upload_assets_dry_run(self, deployer, temp_dir):
        """Test legacy upload_assets dry run."""
        (temp_dir / "metadata.json").write_text('{"title": "test"}')

        result = deployer.upload_assets(temp_dir, "test_db", dry_run=True)

        assert result.is_valid
        assert "Would upload" in result.info[0]
        deployer.s3_client.upload_file.assert_not_called()

    def test_upload_assets_missing_path(self, deployer, temp_dir):
        """Test upload_assets with missing path."""
        missing_path = temp_dir / "missing"

        result = deployer.upload_assets(missing_path, "test_db")

        assert not result.is_valid
        assert "does not exist" in result.errors[0]
