"""
S3 deployment for Zeeker databases and assets.
"""

import hashlib
import os
from pathlib import Path

import boto3
from botocore.config import Config

from .types import DeploymentChanges, ValidationResult


class ZeekerDeployer:
    """Handles deployment of databases and assets to S3 with enhanced capabilities."""

    def __init__(self):
        self.bucket_name = os.getenv("S3_BUCKET")
        if not self.bucket_name:
            raise ValueError("S3_BUCKET environment variable is required")

        self.endpoint_url = os.getenv("S3_ENDPOINT_URL")
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not access_key or not secret_key:
            raise ValueError(
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables are required"
            )

        # Configure checksum settings for compatibility with non-AWS S3 endpoints
        s3_config = Config(
            response_checksum_validation="when_required",
            request_checksum_calculation="when_required",
        )

        client_kwargs = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "config": s3_config,
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        self.s3_client = boto3.client("s3", **client_kwargs)

    def upload_database(
        self, db_path: Path, database_name: str, dry_run: bool = False
    ) -> ValidationResult:
        """Upload database file to S3."""
        result = ValidationResult(is_valid=True)

        if not db_path.exists():
            result.is_valid = False
            result.errors.append(f"Database file not found: {db_path}")
            return result

        s3_key = f"latest/{database_name}.db"

        if dry_run:
            result.info.append(f"Would upload: {db_path} -> s3://{self.bucket_name}/{s3_key}")
        else:
            try:
                self.s3_client.upload_file(str(db_path), self.bucket_name, s3_key)
                result.info.append(
                    f"Uploaded database: {db_path} -> s3://{self.bucket_name}/{s3_key}"
                )
            except Exception as e:
                result.is_valid = False
                result.errors.append(f"Failed to upload database: {e}")

        return result

    def get_existing_files(self, database_name: str) -> dict[str, str]:
        """Get existing files on S3 with their ETags for comparison."""
        files = {}
        try:
            s3_prefix = f"assets/databases/{database_name}/"
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_prefix)

            for page in pages:
                for obj in page.get("Contents", []):
                    relative_path = obj["Key"][len(s3_prefix) :]
                    files[relative_path] = obj["ETag"].strip('"')
        except Exception as e:
            # Log error but don't fail - treat as empty S3
            print(f"Warning: Could not list S3 files: {e}")
        return files

    def get_local_files(self, local_path: Path) -> dict[str, str]:
        """Get local files with their MD5 hashes for comparison."""
        files = {}
        for file_path in local_path.rglob("*"):
            if file_path.is_file():
                relative_path = str(file_path.relative_to(local_path)).replace("\\", "/")
                md5_hash = hashlib.md5(file_path.read_bytes()).hexdigest()
                files[relative_path] = md5_hash
        return files

    def calculate_changes(
        self, local_files: dict[str, str], existing_files: dict[str, str], sync: bool, clean: bool
    ) -> DeploymentChanges:
        """Calculate what changes need to be made."""
        changes = DeploymentChanges()

        if clean:
            changes.deletions = list(existing_files.keys())
            changes.uploads = list(local_files.keys())
        else:
            for local_file, local_hash in local_files.items():
                if local_file not in existing_files:
                    changes.uploads.append(local_file)
                elif existing_files[local_file] != local_hash:
                    changes.updates.append(local_file)
                else:
                    changes.unchanged.append(local_file)

            if sync:
                for existing_file in existing_files:
                    if existing_file not in local_files:
                        changes.deletions.append(existing_file)

        return changes

    def show_deployment_summary(
        self,
        changes: DeploymentChanges,
        database_name: str,
        local_files: dict[str, str],
        existing_files: dict[str, str],
    ):
        """Show a summary of what will be deployed."""
        print(f"\n📋 Deployment Summary for '{database_name}':")
        print(f"   Local files: {len(local_files)}")
        print(f"   S3 files: {len(existing_files)}")

        if changes.uploads:
            print(f"   📤 Will upload: {len(changes.uploads)} files")
            for file in changes.uploads[:5]:
                print(f"      • {file}")
            if len(changes.uploads) > 5:
                print(f"      ... and {len(changes.uploads) - 5} more")

        if changes.updates:
            print(f"   🔄 Will update: {len(changes.updates)} files")
            for file in changes.updates[:5]:
                print(f"      • {file}")
            if len(changes.updates) > 5:
                print(f"      ... and {len(changes.updates) - 5} more")

        if changes.deletions:
            print(f"   🗑️  Will delete: {len(changes.deletions)} files")
            for file in changes.deletions:
                print(f"      • {file}")

    def show_detailed_diff(self, changes: DeploymentChanges):
        """Show detailed diff of all changes."""
        print("\n📊 Detailed Changes:")

        if changes.uploads:
            print(f"\n➕ New files ({len(changes.uploads)}):")
            for file in changes.uploads:
                print(f"   + {file}")

        if changes.updates:
            print(f"\n🔄 Modified files ({len(changes.updates)}):")
            for file in changes.updates:
                print(f"   ~ {file}")

        if changes.deletions:
            print(f"\n➖ Files to delete ({len(changes.deletions)}):")
            for file in changes.deletions:
                print(f"   - {file}")

        if changes.unchanged:
            print(f"\n✓ Unchanged files ({len(changes.unchanged)})")
            if len(changes.unchanged) <= 10:
                for file in changes.unchanged:
                    print(f"   = {file}")
            else:
                print(f"   ({len(changes.unchanged)} files)")

    def execute_deployment(
        self, changes: DeploymentChanges, local_path: Path, database_name: str
    ) -> ValidationResult:
        """Execute the deployment based on calculated changes."""
        result = ValidationResult(is_valid=True)
        s3_prefix = f"assets/databases/{database_name}/"

        # Delete files first (in case of clean deployment)
        for file_to_delete in changes.deletions:
            s3_key = s3_prefix + file_to_delete
            try:
                self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
                result.info.append(f"Deleted: {file_to_delete}")
            except Exception as e:
                result.errors.append(f"Failed to delete {file_to_delete}: {e}")
                result.is_valid = False

        # Upload new and updated files
        files_to_upload = changes.uploads + changes.updates
        for file_to_upload in files_to_upload:
            local_file_path = local_path / file_to_upload
            s3_key = s3_prefix + file_to_upload

            try:
                self.s3_client.upload_file(str(local_file_path), self.bucket_name, s3_key)
                action = "Uploaded" if file_to_upload in changes.uploads else "Updated"
                result.info.append(f"{action}: {file_to_upload}")
            except Exception as e:
                result.errors.append(f"Failed to upload {file_to_upload}: {e}")
                result.is_valid = False

        return result

    def upload_assets(
        self, local_path: Path, database_name: str, dry_run: bool = False
    ) -> ValidationResult:
        """Upload assets to S3 (legacy method for backward compatibility)."""
        result = ValidationResult(is_valid=True)

        if not local_path.exists():
            result.is_valid = False
            result.errors.append(f"Local path does not exist: {local_path}")
            return result

        s3_prefix = f"assets/databases/{database_name}/"

        for file_path in local_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_path)
                s3_key = s3_prefix + str(relative_path).replace("\\", "/")

                if dry_run:
                    result.info.append(
                        f"Would upload: {file_path} -> s3://{self.bucket_name}/{s3_key}"
                    )
                else:
                    try:
                        self.s3_client.upload_file(str(file_path), self.bucket_name, s3_key)
                        result.info.append(
                            f"Uploaded: {file_path} -> s3://{self.bucket_name}/{s3_key}"
                        )
                    except Exception as e:
                        result.errors.append(f"Failed to upload {file_path}: {e}")
                        result.is_valid = False

        return result

    def list_assets(self) -> list[str]:
        """List all database assets in S3."""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix="assets/databases/", Delimiter="/"
            )

            databases = []
            for prefix in response.get("CommonPrefixes", []):
                db_name = prefix["Prefix"].split("/")[-2]
                databases.append(db_name)

            return sorted(databases)
        except Exception as e:
            print(f"Error listing assets: {e}")
            return []
