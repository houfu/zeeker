"""
Backup commands for database archival to S3.
"""

from datetime import date
from pathlib import Path

import click

from ..core.project import ZeekerProjectManager
from .helpers import create_deployer, echo_errors, require_database, require_project


@click.command()
@click.option(
    "--date",
    "date_str",
    help="Backup date in YYYY-MM-DD format (default: today)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be backed up without uploading")
def backup(date_str, dry_run):
    """Backup database to S3 archives with date-based organization.

    Creates timestamped backups in S3:
    s3://bucket/archives/YYYY-MM-DD/{database_name}.db

    Examples:
        zeeker backup                    # Backup with today's date
        zeeker backup --date 2025-08-15  # Backup with specific date
        zeeker backup --dry-run          # Show what would be backed up
    """
    manager = ZeekerProjectManager()
    project = require_project(manager)
    if not project:
        return

    deployer = create_deployer()
    if not deployer:
        return

    # Validate and parse date
    if date_str:
        try:
            backup_date = date.fromisoformat(date_str)
            if backup_date > date.today():
                click.echo("❌ Backup date cannot be in the future")
                return
        except ValueError:
            click.echo("❌ Invalid date format. Use YYYY-MM-DD (e.g., 2025-08-15)")
            return
    else:
        backup_date = date.today()

    db_path = require_database(manager, project)
    if not db_path:
        return

    database_name = Path(project.database).stem
    result = deployer.backup_database(db_path, database_name, backup_date.isoformat(), dry_run)

    if result.errors:
        echo_errors(result)
        return

    for info in result.info:
        click.echo(f"✅ {info}")

    if not dry_run:
        click.echo("\n📦 Database backed up successfully!")
        click.echo(
            f"📍 Location: s3://{deployer.bucket_name}/archives/{backup_date.isoformat()}/{database_name}.db"
        )
        click.echo("💡 Use 'zeeker deploy' to update the latest version")
