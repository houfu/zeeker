"""
Backup commands for database archival to S3.
"""

from datetime import date
from pathlib import Path

import click
from dotenv import load_dotenv

from ..core.deployer import ZeekerDeployer
from ..core.project import ZeekerProjectManager


@click.command()
@click.option(
    "--date",
    "date_str",
    help="Backup date in YYYY-MM-DD format (default: today)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be backed up without uploading")
def backup(date_str, dry_run):
    """Backup database to S3 archives with date-based organization.

    Creates timestamped backups in S3 following the structure:
    s3://bucket/archives/YYYY-MM-DD/{database_name}.db

    Examples:
        zeeker backup                    # Backup with today's date
        zeeker backup --date 2025-08-15  # Backup with specific date
        zeeker backup --dry-run          # Show what would be backed up
    """
    # Load .env file if present for S3 credentials
    load_dotenv(dotenv_path=Path.cwd() / ".env")

    manager = ZeekerProjectManager()

    if not manager.is_project_root():
        click.echo("❌ Not in a Zeeker project directory (no zeeker.toml found)")
        return

    try:
        project = manager.load_project()
        deployer = ZeekerDeployer()
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}")
        click.echo("Please set the required environment variables:")
        click.echo("  - S3_BUCKET")
        click.echo("  - AWS_ACCESS_KEY_ID")
        click.echo("  - AWS_SECRET_ACCESS_KEY")
        click.echo("  - S3_ENDPOINT_URL (optional)")
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

    # Check if database exists
    db_path = manager.project_path / project.database
    if not db_path.exists():
        click.echo(f"❌ Database not found: {project.database}")
        click.echo("Run 'zeeker build' first to build the database")
        return

    # Extract database name without .db extension for S3 path
    database_name = Path(project.database).stem

    # Perform backup
    result = deployer.backup_database(db_path, database_name, backup_date.isoformat(), dry_run)

    if result.errors:
        for error in result.errors:
            click.echo(f"❌ {error}")
        return

    for info in result.info:
        click.echo(f"✅ {info}")

    if not dry_run:
        click.echo("\n📦 Database backed up successfully!")
        click.echo(
            f"📍 Location: s3://{deployer.bucket_name}/archives/{backup_date.isoformat()}/{database_name}.db"
        )
        click.echo("💡 Use 'zeeker deploy' to update the latest version")
