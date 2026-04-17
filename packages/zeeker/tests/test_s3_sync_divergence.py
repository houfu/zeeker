"""Tests for the S3 sync preserve-local guard."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from zeeker.core.database.s3_sync import S3Synchronizer


def test_no_local_db_is_clean(tmp_path: Path):
    sync = S3Synchronizer()
    result = sync.check_local_divergence(tmp_path / "missing.db")
    assert result.is_valid


def test_existing_local_db_is_protected(tmp_path: Path):
    db_path = tmp_path / "my.db"
    db_path.write_bytes(b"anything")  # any existing file triggers the guard

    sync = S3Synchronizer()
    result = sync.check_local_divergence(db_path)
    assert not result.is_valid
    assert any("--force-sync" in e for e in result.errors)
    assert any("Local database already exists" in e for e in result.errors)


def test_sync_from_s3_refuses_when_local_exists(tmp_path: Path):
    db_path = tmp_path / "my.db"
    db_path.write_bytes(b"local data")

    with patch("zeeker.core.deployer.ZeekerDeployer") as deployer_cls:
        sync = S3Synchronizer()
        result = sync.sync_from_s3("my.db", db_path)
        # Divergence check short-circuits before the deployer is constructed.
        deployer_cls.assert_not_called()

    assert not result.is_valid
    assert any("--force-sync" in e for e in result.errors)


def test_sync_from_s3_force_proceeds_and_warns(tmp_path: Path):
    db_path = tmp_path / "my.db"
    db_path.write_bytes(b"local data")

    fake_client = MagicMock()
    fake_client.head_object.return_value = {"ContentLength": 10}

    def _fake_download(Bucket, Key, Filename):
        Path(Filename).write_bytes(b"downloaded-from-s3")

    fake_client.download_file.side_effect = _fake_download

    with patch("zeeker.core.deployer.ZeekerDeployer") as deployer_cls:
        deployer_cls.return_value.s3_client = fake_client
        deployer_cls.return_value.bucket_name = "test-bucket"

        sync = S3Synchronizer()
        result = sync.sync_from_s3("my.db", db_path, force=True)

    assert result.is_valid
    assert fake_client.download_file.called
    assert any("overwriting local database" in w for w in result.warnings)
    assert db_path.read_bytes() == b"downloaded-from-s3"


def test_sync_from_s3_no_local_db_downloads_cleanly(tmp_path: Path):
    db_path = tmp_path / "my.db"  # does not exist

    fake_client = MagicMock()
    fake_client.head_object.return_value = {"ContentLength": 10}

    def _fake_download(Bucket, Key, Filename):
        Path(Filename).write_bytes(b"downloaded")

    fake_client.download_file.side_effect = _fake_download

    with patch("zeeker.core.deployer.ZeekerDeployer") as deployer_cls:
        deployer_cls.return_value.s3_client = fake_client
        deployer_cls.return_value.bucket_name = "test-bucket"

        sync = S3Synchronizer()
        result = sync.sync_from_s3("my.db", db_path)

    assert result.is_valid
    assert fake_client.download_file.called
    # No warnings since there was nothing to overwrite.
    assert not result.warnings
