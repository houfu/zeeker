"""
S3 synchronization for Zeeker databases.

This module handles downloading existing databases from S3 before building
to enable multi-machine workflows and incremental updates.
"""

from pathlib import Path

from ..types import ValidationResult


class S3Synchronizer:
    """Handles S3 database synchronization operations."""

    def sync_from_s3(self, database_name: str, local_db_path: Path) -> ValidationResult:
        """Download existing database from S3 if available.

        Args:
            database_name: Name of the database file
            local_db_path: Local path where database should be saved

        Returns:
            ValidationResult with sync results
        """
        result = ValidationResult(is_valid=True)

        try:
            # Import here to avoid making boto3 a hard dependency
            from ..deployer import ZeekerDeployer

            deployer = ZeekerDeployer()
            s3_key = f"latest/{database_name}"

            # Check if database exists on S3 and download if found
            try:
                # Check if the object exists
                deployer.s3_client.head_object(Bucket=deployer.bucket_name, Key=s3_key)

                # Database exists on S3, download it
                deployer.s3_client.download_file(deployer.bucket_name, s3_key, str(local_db_path))
                result.info.append(f"Downloaded existing database from S3: {s3_key}")

            except deployer.s3_client.exceptions.NoSuchKey:
                # Database doesn't exist on S3 - this is fine for new projects
                result.info.append(f"No existing database found on S3 at {s3_key}")

        except ImportError:
            result.is_valid = False
            result.errors.append("S3 sync requires AWS credentials and boto3")
        except ValueError as e:
            result.is_valid = False
            result.errors.append(f"S3 configuration error: {e}")
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"S3 sync failed: {e}")

        return result
