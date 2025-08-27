"""
Zeeker CLI - Database customization tool with project management.

Clean CLI interface that imports functionality from core modules.
"""

import subprocess
from pathlib import Path

import click
from dotenv import load_dotenv

from .core.deployer import ZeekerDeployer
from .core.generator import ZeekerGenerator
from .core.metadata import MetadataGenerator
from .core.project import ZeekerProjectManager
from .core.types import ZeekerSchemaConflictError
from .core.validator import ZeekerValidator


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
    click.echo("📋 Follow customization guide for deployment to S3")


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

    click.echo("\n📖 See database customization guide for details.")

    return result.is_valid


@assets.command("deploy")
@click.argument("local_path", type=click.Path(exists=True))
@click.argument("database_name")
@click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
@click.option("--sync", is_flag=True, help="Delete S3 files not present locally (full sync)")
@click.option("--clean", is_flag=True, help="Remove all existing assets first, then deploy")
@click.option("--yes", is_flag=True, help="Skip confirmation prompts")
@click.option("--diff", is_flag=True, help="Show detailed differences between local and S3")
def deploy_assets(local_path, database_name, dry_run, sync, clean, yes, diff):
    """Deploy UI assets to S3 following customization guide structure.

    Uploads to: s3://bucket/assets/databases/{database_name}/
    - templates/ → S3 templates/
    - static/ → S3 static/
    - metadata.json → S3 metadata.json

    Database folder name must match .db filename (without .db extension).
    """
    # Load .env file if present for S3 credentials
    load_dotenv(dotenv_path=Path.cwd() / ".env")

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
        click.echo("\n🔍 Dry run completed - no changes made")
        click.echo("Remove --dry-run to perform actual deployment")
    else:
        result = deployer.execute_deployment(changes, local_path_obj, database_name)

        if result.is_valid:
            click.echo("\n✅ Assets deployment completed successfully!")
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
            click.echo("\n❌ Assets deployment failed:")
            for error in result.errors:
                click.echo(f"   {error}")


@assets.command("list")
def list_assets():
    """List all database UI assets in S3."""
    # Load .env file if present for S3 credentials
    load_dotenv(dotenv_path=Path.cwd() / ".env")

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


# Metadata management commands
@cli.group()
def metadata():
    """Metadata management commands."""
    pass


@metadata.command()
@click.argument("resource_name", required=False)
@click.option("--all", is_flag=True, help="Generate for all resources")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without making changes")
@click.option("--force", is_flag=True, help="Overwrite existing column metadata")
@click.option(
    "--project", is_flag=True, help="Generate project-level metadata (title, description, etc.)"
)
@click.option("--resource", "resource_desc", help="Generate description for specific resource")
def generate(resource_name, all, dry_run, force, project, resource_desc):
    """Generate metadata from database schema and project structure.

    Generates intelligent column descriptions, project metadata, and resource descriptions
    based on schema analysis and intelligent heuristics. Updates zeeker.toml accordingly.

    Examples:
        zeeker metadata generate users                    # Column metadata for users table
        zeeker metadata generate --project               # Project-level metadata only
        zeeker metadata generate --resource users        # Resource description for users
        zeeker metadata generate users --project         # Both columns and project metadata
        zeeker metadata generate --all --project         # Everything including project metadata
        zeeker metadata generate users --dry-run         # Preview without changes
    """
    manager = ZeekerProjectManager()

    if not manager.is_project_root():
        click.echo("❌ Not in a Zeeker project directory (no zeeker.toml found)")
        return

    try:
        project = manager.load_project()
    except Exception as e:
        click.echo(f"❌ Error loading project: {e}")
        return

    generator = MetadataGenerator(manager.project_path)

    # Validate arguments
    if resource_desc is not None and not resource_desc.strip():
        click.echo("❌ --resource requires a resource name")
        return

    if not resource_name and not all and not project and not resource_desc:
        click.echo("❌ Specify a resource name, use --all, --project, or --resource")
        return

    # Check if database exists for operations that need it
    db_path = manager.project_path / project.database
    needs_db = resource_name or all or resource_desc

    if needs_db and not db_path.exists():
        click.echo(f"❌ Database not found: {db_path}")
        click.echo("   Run 'zeeker build' first to create the database")
        return

    try:
        project_updated = False

        # Handle project-level metadata generation
        if project:
            missing_project_fields = generator.detect_missing_project_metadata(project)
            if missing_project_fields:
                click.echo(
                    f"🔍 Missing project metadata detected: {', '.join(missing_project_fields)}"
                )

                if dry_run:
                    click.echo("   Would generate:")
                    temp_project = generator.generate_project_metadata(project)
                    for field in missing_project_fields:
                        value = getattr(temp_project, field)
                        if value:
                            click.echo(f"   • {field}: {value}")
                else:
                    project = generator.generate_project_metadata(project)
                    click.echo("✨ Generated project metadata")
                    project_updated = True
            else:
                click.echo("ℹ️  Project metadata already complete")

        # Handle resource description generation
        if resource_desc:
            missing_resource_descs = generator.detect_missing_resource_descriptions(
                project, resource_desc
            )
            if missing_resource_descs:
                click.echo(f"🔍 Generating description for resource '{resource_desc}'...")

                generated_desc = generator.generate_resource_description(db_path, resource_desc)

                if dry_run:
                    click.echo(f"   Would generate description: {generated_desc}")
                else:
                    # Ensure resource exists in project
                    if resource_desc not in project.resources:
                        project.resources[resource_desc] = {}
                    project.resources[resource_desc]["description"] = generated_desc
                    click.echo(f"✨ Generated description for '{resource_desc}': {generated_desc}")
                    project_updated = True
            else:
                click.echo(f"ℹ️  Resource '{resource_desc}' already has description")

        # Handle column metadata generation (existing functionality)
        if all:
            # Generate for all tables
            click.echo("🔍 Analyzing all tables in database...")
            all_metadata = generator.generate_for_all_tables(db_path)

            for table_name, table_metadata in all_metadata.items():
                if "error" in table_metadata:
                    click.echo(f"⚠️  Error analyzing {table_name}: {table_metadata['error']}")
                    continue

                _show_generated_metadata(table_name, table_metadata, dry_run)

                if not dry_run:
                    # Update project configuration
                    project = generator.update_project_metadata(
                        project, table_name, table_metadata, preserve_existing=not force
                    )
                    project_updated = True

        elif resource_name:
            # Generate for specific resource
            if resource_name not in project.resources:
                click.echo(f"❌ Resource '{resource_name}' not found in zeeker.toml")
                return

            click.echo(f"🔍 Analyzing table '{resource_name}'...")
            table_metadata = generator.generate_metadata_for_table(db_path, resource_name)

            _show_generated_metadata(resource_name, table_metadata, dry_run)

            if not dry_run:
                # Update project configuration
                project = generator.update_project_metadata(
                    project, resource_name, table_metadata, preserve_existing=not force
                )
                project_updated = True

        # Save updated project if changes were made
        if project_updated and not dry_run:
            project.save_toml(manager.toml_path)
            click.echo(f"\n✅ Updated zeeker.toml with generated metadata")

    except Exception as e:
        click.echo(f"❌ Error generating metadata: {e}")
        return


@metadata.command()
@click.argument("resource_name", required=False)
def show(resource_name):
    """Show current metadata for resources.

    Examples:
        zeeker metadata show users
        zeeker metadata show
    """
    manager = ZeekerProjectManager()

    if not manager.is_project_root():
        click.echo("❌ Not in a Zeeker project directory (no zeeker.toml found)")
        return

    try:
        project = manager.load_project()
    except Exception as e:
        click.echo(f"❌ Error loading project: {e}")
        return

    if resource_name:
        # Show specific resource
        if resource_name not in project.resources:
            click.echo(f"❌ Resource '{resource_name}' not found")
            return

        _show_resource_metadata(resource_name, project.resources[resource_name])
    else:
        # Show all resources
        if not project.resources:
            click.echo("No resources found in project")
            return

        for name, config in project.resources.items():
            _show_resource_metadata(name, config)
            click.echo()


def _show_generated_metadata(table_name: str, metadata: dict, dry_run: bool = False):
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


def _show_resource_metadata(resource_name: str, resource_config: dict):
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

    # Show other metadata fields
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


if __name__ == "__main__":
    cli()
