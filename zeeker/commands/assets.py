"""
Asset management commands for UI customizations.
"""

from pathlib import Path

import click
from dotenv import load_dotenv

from ..core.deployer import ZeekerDeployer
from ..core.generator import ZeekerGenerator
from ..core.validator import ZeekerValidator


@click.group()
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
