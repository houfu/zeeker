"""
Zeeker CLI - Database customization tool with project management.

Clean CLI interface that imports functionality from core modules.
"""

import subprocess
from pathlib import Path

import click
from dotenv import load_dotenv

from .commands.assets import assets
from .commands.metadata import metadata
from .core.deployer import ZeekerDeployer
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
        for error in result.errors:
            click.echo(f"❌ {error}")
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

    Use --fragments to create a complementary table for storing document fragments,
    perfect for handling large legal documents that need to be split into searchable chunks.
    Fragments tables are automatically FTS-enabled on text content fields.

    Use --async to generate async/await templates for concurrent data fetching from APIs,
    databases, or other async sources for better performance.

    Examples:
        zeeker add users --description "User account data" --facets role --facets department --size 50
        zeeker add legal_docs --fragments --description "Legal documents with auto-searchable fragments"
        zeeker add api_data --async --description "Data from external APIs with concurrent fetching"
        zeeker add large_docs --fragments --async --description "Async document processing with fragments"
        zeeker add documents --fts-fields title --fts-fields content --description "Searchable documents"
        zeeker add posts --fragments --fts-fields title --description "Blog posts with searchable fragments"
    """
    manager = ZeekerProjectManager()

    # Build kwargs for Datasette metadata
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
        for error in result.errors:
            click.echo(f"❌ {error}")
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
        zeeker build                    # Build all resources (no FTS setup)
        zeeker build --setup-fts        # Build all resources and set up FTS indexes
        zeeker build users              # Build only 'users' resource
        zeeker build users posts        # Build 'users' and 'posts' resources

    FTS (Full-Text Search) Setup:
    • Use --setup-fts flag on first build to create FTS indexes
    • Omit --setup-fts on subsequent builds to avoid FTS conflicts
    • Perfect for CI/CD environments where you want reliable, repeatable builds

    Uses Simon Willison's sqlite-utils for robust database operations:

    • Automatic table creation with proper schema detection
    • Type inference from data (INTEGER, TEXT, REAL, JSON)
    • Safe data insertion without SQL injection risks
    • JSON support for complex data structures
    • Better error handling than raw SQL
    • Automatic schema conflict detection with migration support

    Generates complete Datasette metadata.json following customization guide format.
    Creates meta tables for schema versioning and update tracking.

    Must be run from a Zeeker project directory (contains zeeker.toml).
    """
    # Load .env file if present for resource environment variables
    load_dotenv(dotenv_path=Path.cwd() / ".env")

    # Convert tuple of resources to list, or None if empty
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
        for error in result.errors:
            click.echo(f"   {error}")
        raise click.ClickException("Build failed")

    if result.warnings:
        for warning in result.warnings:
            click.echo(f"⚠️ {warning}")

    for info in result.info:
        click.echo(f"✅ {info}")

    click.echo("\n🔧 Built with sqlite-utils for robust schema detection")
    click.echo("📖 Generated metadata follows customization guide format")
    click.echo("🚀 Ready for deployment with 'zeeker deploy'")


@cli.command("deploy")
@click.option("--dry-run", is_flag=True, help="Show what would be uploaded without uploading")
def deploy_database(dry_run):
    """Deploy the project database to S3.

    Uploads the generated .db file to S3 following customization guide structure:
    - Database: s3://bucket/latest/{database_name}.db
    - Assets: s3://bucket/assets/databases/{database_name}/

    Must be run from a Zeeker project directory (contains zeeker.toml).
    Use 'zeeker assets deploy' for UI customizations.
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

    db_path = manager.project_path / project.database
    if not db_path.exists():
        click.echo(f"❌ Database not found: {project.database}")
        click.echo("Run 'zeeker build' first to build the database")
        return

    # Extract database name without .db extension for S3 path (per guide)
    database_name = Path(project.database).stem

    result = deployer.upload_database(db_path, database_name, dry_run)

    if result.errors:
        for error in result.errors:
            click.echo(f"❌ {error}")
        return

    for info in result.info:
        click.echo(f"✅ {info}")

    if not dry_run:
        click.echo("\n🚀 Database deployed successfully!")
        click.echo(f"📍 Location: s3://{deployer.bucket_name}/latest/{database_name}.db")
        click.echo("💡 For UI customizations, use: zeeker assets deploy")


# Legacy commands for backward compatibility (with deprecation warnings)
@cli.command("generate", hidden=True)
@click.argument("database_name")
@click.argument("output_path", type=click.Path())
@click.option("--title", help="Database title")
@click.option("--description", help="Database description")
@click.option("--primary-color", default="#3498db", help="Primary color")
@click.option("--accent-color", default="#e74c3c", help="Accent color")
def generate_legacy(database_name, output_path, title, description, primary_color, accent_color):
    """[DEPRECATED] Use 'zeeker assets generate' instead."""
    click.echo("⚠️  DEPRECATED: Use 'zeeker assets generate' instead")

    ctx = click.get_current_context()
    ctx.invoke(
        assets.commands["generate"],
        database_name=database_name,
        output_path=output_path,
        title=title,
        description=description,
        primary_color=primary_color,
        accent_color=accent_color,
    )


# Register command groups
cli.add_command(assets)
cli.add_command(metadata)


if __name__ == "__main__":
    cli()
