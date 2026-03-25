"""
Zeeker CLI - Database customization tool with project management.

Clean CLI interface that imports functionality from core modules.
"""

import subprocess
from pathlib import Path

import click

from .commands.assets import assets
from .commands.backup import backup
from .commands.helpers import (
    create_deployer,
    echo_errors,
    echo_warnings,
    load_env,
    require_database,
    require_project,
)
from .commands.metadata import metadata
from .core.project import ZeekerProjectManager
from .core.types import ZeekerSchemaConflictError


# Main CLI group
@click.group()
def cli():
    """Zeeker Database Management Tool."""
    pass


# Project management commands
@cli.command()
@click.argument("project_name")
@click.option(
    "--path", type=click.Path(), help="Project directory path (default: ./{project_name})"
)
def init(project_name, path):
    """Initialize a new Zeeker project.

    Creates zeeker.toml, resources/ directory, .gitignore, and README.md.

    Example:
        zeeker init my-project
    """
    project_path = Path(path) if path else Path.cwd() / project_name
    manager = ZeekerProjectManager(project_path)

    result = manager.init_project(project_name)

    if result.errors:
        echo_errors(result)
        return

    for info in result.info:
        click.echo(f"✅ {info}")

    # Run uv sync to create virtual environment and install dependencies
    click.echo("\n🔄 Setting up virtual environment...")
    try:
        sync_result = subprocess.run(
            ["uv", "sync"], cwd=project_path, capture_output=True, text=True, check=False
        )

        if sync_result.returncode == 0:
            click.echo("✅ Virtual environment created and dependencies installed")
        else:
            click.echo(f"⚠️  uv sync failed: {sync_result.stderr.strip()}")
            click.echo("   You can run 'uv sync' manually in the project directory")
    except FileNotFoundError:
        click.echo("⚠️  uv not found - skipping virtual environment setup")
        click.echo(
            "   Install uv (https://docs.astral.sh/uv/) or use pip/poetry for dependency management"
        )

    click.echo("\nNext steps:")
    try:
        relative_path = project_path.relative_to(Path.cwd())
        click.echo(f"  1. cd {relative_path}")
    except ValueError:
        click.echo(f"  1. cd {project_path}")
    click.echo("  2. uv run zeeker add <resource_name>")
    click.echo("  3. uv run zeeker build")
    click.echo("  4. uv run zeeker deploy")


@cli.command()
@click.argument("resource_name")
@click.option("--description", help="Resource description")
@click.option("--facets", multiple=True, help="Datasette facets (can be used multiple times)")
@click.option("--sort", help="Default sort order")
@click.option("--size", type=int, help="Default page size")
@click.option(
    "--fragments", is_flag=True, help="Create a complementary fragments table for large documents"
)
@click.option(
    "--async",
    "is_async",
    is_flag=True,
    help="Generate async templates for concurrent data fetching",
)
@click.option(
    "--fts-fields",
    multiple=True,
    help="Fields to enable full-text search on (can be used multiple times)",
)
@click.option(
    "--fragments-fts-fields",
    multiple=True,
    help="Fields to enable FTS on fragments table (auto-detects text content if not specified)",
)
def add(
    resource_name,
    description,
    facets,
    sort,
    size,
    fragments,
    is_async,
    fts_fields,
    fragments_fts_fields,
):
    """Add a new resource to the project.

    Creates a Python file in resources/ with a template for data fetching.

    Examples:
        zeeker add users --description "User account data" --facets role --size 50
        zeeker add legal_docs --fragments --description "Legal documents"
        zeeker add api_data --async --description "Data from external APIs"
    """
    manager = ZeekerProjectManager()

    kwargs = {}
    if facets:
        kwargs["facets"] = list(facets)
    if sort:
        kwargs["sort"] = sort
    if size:
        kwargs["size"] = size
    if fragments:
        kwargs["fragments"] = True
    if fts_fields:
        kwargs["fts_fields"] = list(fts_fields)
    if fragments_fts_fields:
        kwargs["fragments_fts_fields"] = list(fragments_fts_fields)
    if is_async:
        kwargs["is_async"] = True

    result = manager.add_resource(resource_name, description, **kwargs)

    if result.errors:
        echo_errors(result)
        return

    for info in result.info:
        click.echo(f"✅ {info}")

    click.echo("\nNext steps:")
    click.echo(f"  1. Edit resources/{resource_name}.py")
    click.echo("  2. Implement the fetch_data() function")
    click.echo("  3. zeeker build")


@cli.command()
@click.argument("resources", nargs=-1)
@click.option(
    "--force-schema-reset", is_flag=True, help="Ignore schema conflicts and rebuild tables"
)
@click.option(
    "--sync-from-s3", is_flag=True, help="Download existing database from S3 before building"
)
@click.option(
    "--setup-fts", is_flag=True, help="Set up full-text search (FTS) indexes on configured fields"
)
def build(resources, force_schema_reset, sync_from_s3, setup_fts):
    """Build database from resources using sqlite-utils.

    Runs fetch_data() for specified resources and creates/updates the SQLite database.
    If no resources are specified, builds all resources in the project.

    Examples:
        zeeker build                    # Build all resources
        zeeker build --setup-fts        # Build all resources and set up FTS indexes
        zeeker build users posts        # Build specific resources
    """
    load_env()

    resource_list = list(resources) if resources else None
    if resource_list:
        click.echo(f"Building specific resources: {', '.join(resource_list)}")

    manager = ZeekerProjectManager()

    try:
        result = manager.build_database(
            force_schema_reset=force_schema_reset,
            sync_from_s3=sync_from_s3,
            resources=resource_list,
            setup_fts=setup_fts,
        )
    except ZeekerSchemaConflictError as e:
        click.echo("❌ Schema conflict detected:")
        click.echo(str(e))
        click.echo("\n💡 To resolve this, you can:")
        click.echo("   • Use --force-schema-reset flag to ignore conflicts")
        click.echo("   • Add a migrate_schema() function to handle the change")
        click.echo("   • Delete the database file to rebuild from scratch")
        return

    if result.errors:
        click.echo("❌ Database build failed:")
        echo_errors(result)
        raise click.ClickException("Build failed")

    if result.warnings:
        echo_warnings(result)

    for info in result.info:
        click.echo(f"✅ {info}")

    click.echo("\n🔧 Built with sqlite-utils for robust schema detection")
    click.echo("🚀 Ready for deployment with 'zeeker deploy'")


@cli.command("deploy")
@click.option("--dry-run", is_flag=True, help="Show what would be uploaded without uploading")
def deploy_database(dry_run):
    """Deploy the project database to S3.

    Uploads the generated .db file to S3:
    s3://bucket/latest/{database_name}.db
    """
    manager = ZeekerProjectManager()
    project = require_project(manager)
    if not project:
        return

    deployer = create_deployer()
    if not deployer:
        return

    db_path = require_database(manager, project)
    if not db_path:
        return

    database_name = Path(project.database).stem
    result = deployer.upload_database(db_path, database_name, dry_run)

    if result.errors:
        echo_errors(result)
        return

    for info in result.info:
        click.echo(f"✅ {info}")

    if not dry_run:
        click.echo("\n🚀 Database deployed successfully!")
        click.echo(f"📍 Location: s3://{deployer.bucket_name}/latest/{database_name}.db")
        click.echo("💡 For UI customizations, use: zeeker assets deploy")


# Register command groups
cli.add_command(assets)
cli.add_command(backup)
cli.add_command(metadata)


if __name__ == "__main__":
    cli()
