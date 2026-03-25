"""
Shared helper functions for CLI commands.
"""

from pathlib import Path

import click
from dotenv import load_dotenv

from ..core.types import ValidationResult


def echo_errors(result: ValidationResult) -> None:
    """Display errors from a ValidationResult."""
    for error in result.errors:
        click.echo(f"❌ {error}")


def echo_warnings(result: ValidationResult) -> None:
    """Display warnings from a ValidationResult."""
    for warning in result.warnings:
        click.echo(f"⚠️ {warning}")


def load_env() -> None:
    """Load .env file from current directory if present."""
    load_dotenv(dotenv_path=Path.cwd() / ".env")


def require_project(manager) -> object | None:
    """Validate project root and load project, or print error and return None."""
    if not manager.is_project_root():
        click.echo("❌ Not in a Zeeker project directory (no zeeker.toml found)")
        return None
    try:
        return manager.load_project()
    except Exception as e:
        click.echo(f"❌ Error loading project: {e}")
        return None


def require_database(manager, project) -> Path | None:
    """Validate database file exists, or print error and return None."""
    db_path = manager.project_path / project.database
    if not db_path.exists():
        click.echo(f"❌ Database not found: {project.database}")
        click.echo("Run 'zeeker build' first to build the database")
        return None
    return db_path


def create_deployer():
    """Create a ZeekerDeployer, loading .env first. Returns None on config error."""
    from ..core.deployer import ZeekerDeployer

    load_env()
    try:
        return ZeekerDeployer()
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}")
        click.echo("Please set the required environment variables:")
        click.echo("  - S3_BUCKET")
        click.echo("  - AWS_ACCESS_KEY_ID")
        click.echo("  - AWS_SECRET_ACCESS_KEY")
        click.echo("  - S3_ENDPOINT_URL (optional)")
        return None


def show_generated_metadata(table_name: str, metadata: dict, dry_run: bool = False):
    """Helper to display generated metadata in a nice format."""
    prefix = "📋" if dry_run else "✨"
    action = "Would generate" if dry_run else "Generated"

    click.echo(f"\n{prefix} {action} metadata for '{table_name}':")

    if "columns" in metadata:
        click.echo("   Column descriptions:")
        for col_name, description in metadata["columns"].items():
            click.echo(f"     • {col_name}: {description}")

    if "suggested_facets" in metadata:
        facets = ", ".join(metadata["suggested_facets"])
        click.echo(f"   💡 Suggested facets: {facets}")

    if "suggested_sortable" in metadata:
        sortable = ", ".join(metadata["suggested_sortable"])
        click.echo(f"   💡 Suggested sortable columns: {sortable}")

    if "suggested_label" in metadata:
        click.echo(f"   💡 Suggested label column: {metadata['suggested_label']}")


def show_resource_metadata(resource_name: str, resource_config: dict):
    """Helper to display current resource metadata."""
    click.echo(f"📊 Resource: {resource_name}")

    if "description" in resource_config:
        click.echo(f"   Description: {resource_config['description']}")

    if "columns" in resource_config:
        click.echo("   Column descriptions:")
        for col_name, description in resource_config["columns"].items():
            click.echo(f"     • {col_name}: {description}")
    else:
        click.echo("   No column descriptions")

    metadata_fields = [
        "facets",
        "sort",
        "size",
        "sortable_columns",
        "label_column",
        "units",
        "hidden",
    ]
    for field in metadata_fields:
        if field in resource_config:
            click.echo(f"   {field.replace('_', ' ').title()}: {resource_config[field]}")
