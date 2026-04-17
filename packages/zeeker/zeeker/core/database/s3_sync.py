"""
S3 synchronization for Zeeker databases.

This module handles downloading existing databases from S3 before building
to enable multi-machine workflows and incremental updates. It refuses to
overwrite an existing local DB by default (the user must opt in with
``force=True``) because any local patches/fixes would otherwise be silently
discarded.
"""

from pathlib import Path

from ..types import ValidationResult


class S3Synchronizer:
    """Handles S3 database synchronization operations."""

    def check_local_divergence(self, local_db_path) -> ValidationResult:
        """Return ``is_valid=False`` when a local DB already exists.

        Deliberately conservative: we don't try to auto-detect whether the
        local file is "safe to overwrite" (every build writes to meta tables
        anyway, so a byte-level hash comparison is unreliable). Instead we
        treat any existing local DB as potentially containing work the user
        doesn't want to lose and require an explicit ``--force-sync``.
        """
        result = ValidationResult(is_valid=True)
        path = Path(local_db_path)
        if not path.exists():
            return result

        result.is_valid = False
        result.errors.append(
            f"Local database already exists at {path}. Syncing from "
            "S3 would overwrite any local changes."
        )
        result.errors.append(
            "Use --force-sync to overwrite, or deploy first to push your " "local changes to S3."
        )
        return result

    def sync_from_s3(
        self,
        database_name: str,
        local_db_path: Path,
        *,
        force: bool = False,
    ) -> ValidationResult:
        """Download existing database from S3 if available.

        Args:
            database_name: Name of the database file
            local_db_path: Local path where database should be saved
            force: If True, overwrite an existing local DB without complaint.

        Returns:
            ValidationResult with sync results
        """
        result = ValidationResult(is_valid=True)

        path = Path(local_db_path)
        try:
            # Import here to avoid making boto3 a hard dependency
            from ..deployer import ZeekerDeployer

            # Guard against wiping out local changes unless explicitly opted in.
            if not force:
                divergence = self.check_local_divergence(path)
                if not divergence.is_valid:
                    return divergence
            elif path.exists():
                result.warnings.append(
                    "--force-sync: overwriting local database (any unsynced "
                    "changes will be lost)."
                )

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
