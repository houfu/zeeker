"""
Zeeker CLI - Database customization tool with project management.

Clean CLI interface that imports functionality from core modules.
"""

import click
from pathlib import Path

from .core.project import ZeekerProjectManager
from .core.validator import ZeekerValidator
from .core.generator import ZeekerGenerator
from .core.deployer import ZeekerDeployer


# Main CLI group
@click.group()
def cli():
    """Zeeker Database Management Tool."""
    pass


# Project management commands
@cli.command()
@click.argument("project_name")
@click.option(
    "--path", type=click.Path(), help="Project directory path (default: current directory)"
)
def init(project_name, path):
    """Initialize a new Zeeker project.

    Creates zeeker.toml, resources/ directory, .gitignore, and README.md.

    Example:
        zeeker init my-project
    """
    project_path = Path(path) if path else Path.cwd()
    manager = ZeekerProjectManager(project_path)

    result = manager.init_project(project_name)

    if result.errors:
        for error in result.errors:
            click.echo(f"❌ {error}")
        return

    for info in result.info:
        click.echo(f"✅ {info}")

    click.echo(f"\nNext steps:")
    click.echo(f"  1. cd {project_path.relative_to(Path.cwd()) if path else '.'}")
    click.echo(f"  2. zeeker add <resource_name>")
    click.echo(f"  3. zeeker build")
    click.echo(f"  4. zeeker deploy")


@cli.command()
@click.argument("resource_name")
@click.option("--description", help="Resource description")
@click.option("--facets", multiple=True, help="Datasette facets (can be used multiple times)")
@click.option("--sort", help="Default sort order")
@click.option("--size", type=int, help="Default page size")
def add(resource_name, description, facets, sort, size):
    """Add a new resource to the project.

    Creates a Python file in resources/ with a template for data fetching.

    Example:
        zeeker add users --description "User account data" --facets role --facets department --size 50
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

    result = manager.add_resource(resource_name, description, **kwargs)

    if result.errors:
        for error in result.errors:
            click.echo(f"❌ {error}")
        return

    for info in result.info:
        click.echo(f"✅ {info}")

    click.echo(f"\nNext steps:")
    click.echo(f"  1. Edit resources/{resource_name}.py")
    click.echo(f"  2. Implement the fetch_data() function")
    click.echo(f"  3. zeeker build")


@cli.command()
def build():
    """Build database from all resources using sqlite-utils.

    Runs fetch_data() for each resource and creates/updates the SQLite database.
    Uses Simon Willison's sqlite-utils for robust database operations:

    • Automatic table creation with proper schema detection
    • Type inference from data (INTEGER, TEXT, REAL, JSON)
    • Safe data insertion without SQL injection risks
    • JSON support for complex data structures
    • Better error handling than raw SQL

    Generates complete Datasette metadata.json following customization guide format.

    Must be run from a Zeeker project directory (contains zeeker.toml).
    """
    manager = ZeekerProjectManager()

    result = manager.build_database()

    if result.errors:
        click.echo("❌ Database build failed:")
        for error in result.errors:
            click.echo(f"   {error}")
        return

    if result.warnings:
        for warning in result.warnings:
            click.echo(f"⚠️ {warning}")

    for info in result.info:
        click.echo(f"✅ {info}")

    click.echo(f"\n🔧 Built with sqlite-utils for robust schema detection")
    click.echo(f"📖 Generated metadata follows customization guide format")
    click.echo(f"🚀 Ready for deployment with 'zeeker deploy'")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be uploaded without uploading")
def deploy(dry_run):
    """Deploy the project database to S3.

    Uploads the generated .db file to S3 following customization guide structure:
    - Database: s3://bucket/latest/{database_name}.db
    - Assets: s3://bucket/assets/databases/{database_name}/

    Must be run from a Zeeker project directory (contains zeeker.toml).
    Use 'zeeker assets deploy' for UI customizations.
    """
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
        click.echo(f"\n🚀 Database deployed successfully!")
        click.echo(f"📍 Location: s3://{deployer.bucket_name}/latest/{database_name}.db")
        click.echo(f"💡 For UI customizations, use: zeeker assets deploy")


# Asset management commands (existing functionality with new names)
@cli.group()
def assets():
    """Asset management commands for UI customizations."""
    pass


@assets.command()
@click.argument("database_name")
@click.argument("output_path", type=click.Path())
@click.option("--title", help="Database title")
@click.option("--description", help="Database description")
@click.option("--primary-color", default="#3498db", help="Primary color")
@click.option("--accent-color", default="#e74c3c", help="Accent color")
def generate(database_name, output_path, title, description, primary_color, accent_color):
    """Generate new database UI assets following the customization guide.

    Creates templates/, static/, and metadata.json following guide patterns.
    Template names use safe database-specific naming (database-DBNAME.html).
    """
    output_dir = Path(output_path)
    generator = ZeekerGenerator(database_name, output_dir)

    # Generate complete metadata following guide format
    metadata = generator.generate_metadata_template(
        title=title or f"{database_name.title()} Database",
        description=description or f"Custom database for {database_name}",
        extra_css=["custom.css"],
        extra_js=["custom.js"],
    )

    css_content = generator.generate_css_template(primary_color, accent_color)
    js_content = generator.generate_js_template()
    db_template = generator.generate_database_template()

    # Use safe template naming per guide: database-DBNAME.html
    safe_template_name = f"database-{generator.sanitized_name}.html"
    templates = {safe_template_name: db_template}

    generator.save_assets(metadata, css_content, js_content, templates)
    click.echo(f"Generated assets for '{database_name}' in {output_dir}")
    click.echo(f"✅ Safe template created: {safe_template_name}")
    click.echo(f"📋 Follow customization guide for deployment to S3")


@assets.command()
@click.argument("assets_path", type=click.Path(exists=True))
@click.argument("database_name")
def validate(assets_path, database_name):
    """Validate database UI assets against customization guide rules.

    Checks for:
    - Banned template names (database.html, table.html, etc.)
    - Proper file structure (templates/, static/)
    - Complete metadata.json format
    - CSS/JS URL patterns
    """
    validator = ZeekerValidator()
    result = validator.validate_file_structure(Path(assets_path), database_name)

    if result.errors:
        click.echo("❌ Validation failed:")
        for error in result.errors:
            click.echo(f"  ERROR: {error}")

    if result.warnings:
        click.echo("⚠️ Warnings:")
        for warning in result.warnings:
            click.echo(f"  WARNING: {warning}")

    if result.info:
        for info in result.info:
            click.echo(f"  INFO: {info}")

    if result.is_valid and not result.warnings:
        click.echo("✅ Validation passed! Assets follow customization guide.")
    elif result.is_valid:
        click.echo("✅ Validation passed with warnings.")

    click.echo(f"\n📖 See database customization guide for details.")

    return result.is_valid


@assets.command()
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("database_name")
@click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
@click.option("--sync", is_flag=True, help="Delete S3 files not present locally (full sync)")
@click.option("--clean", is_flag=True, help="Remove all existing assets first, then deploy")
@click.option("--yes", is_flag=True, help="Skip confirmation prompts")
@click.option("--diff", is_flag=True, help="Show detailed differences between local and S3")
def deploy(local_path, database_name, dry_run, sync, clean, yes, diff):
    """Deploy UI assets to S3 following customization guide structure.

    Uploads to: s3://bucket/assets/databases/{database_name}/
    - templates/ → S3 templates/
    - static/ → S3 static/
    - metadata.json → S3 metadata.json

    Database folder name must match .db filename (without .db extension).
    """
    if clean and sync:
        click.echo("❌ Cannot use both --clean and --sync flags")
        return

    try:
        deployer = ZeekerDeployer()
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}")
        return

    local_path_obj = Path(local_path)
    existing_files = deployer.get_existing_files(database_name)
    local_files = deployer.get_local_files(local_path_obj)
    changes = deployer.calculate_changes(local_files, existing_files, sync, clean)

    if diff:
        deployer.show_detailed_diff(changes)
    else:
        deployer.show_deployment_summary(changes, database_name, local_files, existing_files)

    if not changes.has_changes:
        click.echo("   ✅ No changes needed")
        return

    if changes.has_destructive_changes and not yes and not dry_run:
        if clean:
            msg = f"This will delete ALL {len(existing_files)} existing files and upload {len(local_files)} new files."
        else:
            msg = f"This will delete {len(changes.deletions)} files not present locally."

        click.echo(f"\n⚠️  {msg}")
        click.echo("Deleted files cannot be recovered.")

        if not click.confirm("Continue?"):
            click.echo("Deployment cancelled.")
            return

    if dry_run:
        click.echo(f"\n🔍 Dry run completed - no changes made")
        click.echo("Remove --dry-run to perform actual deployment")
    else:
        result = deployer.execute_deployment(changes, local_path_obj, database_name)

        if result.is_valid:
            click.echo(f"\n✅ Assets deployment completed successfully!")
            click.echo(
                f"📍 Location: s3://{deployer.bucket_name}/assets/databases/{database_name}/"
            )
            if changes.deletions:
                click.echo(f"   Deleted: {len(changes.deletions)} files")
            if changes.uploads:
                click.echo(f"   Uploaded: {len(changes.uploads)} files")
            if changes.updates:
                click.echo(f"   Updated: {len(changes.updates)} files")
        else:
            click.echo(f"\n❌ Assets deployment failed:")
            for error in result.errors:
                click.echo(f"   {error}")


@assets.command()
def list():
    """List all database UI assets in S3."""
    try:
        deployer = ZeekerDeployer()
    except ValueError as e:
        click.echo(f"❌ Configuration error: {e}")
        return

    databases = deployer.list_assets()

    if databases:
        click.echo(f"Database assets found in {deployer.bucket_name}:")
        for db in databases:
            click.echo(f"  - {db}")
    else:
        click.echo(f"No database assets found in {deployer.bucket_name}.")


# Legacy commands for backward compatibility (with deprecation warnings)
@cli.command(hidden=True)
@click.argument("database_name")
@click.argument("output_path", type=click.Path())
@click.option("--title", help="Database title")
@click.option("--description", help="Database description")
@click.option("--primary-color", default="#3498db", help="Primary color")
@click.option("--accent-color", default="#e74c3c", help="Accent color")
def generate(database_name, output_path, title, description, primary_color, accent_color):
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


if __name__ == "__main__":
    cli()
