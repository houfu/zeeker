"""
Metadata management commands.
"""

import click

from ..core.metadata import MetadataGenerator
from ..core.project import ZeekerProjectManager
from .helpers import show_generated_metadata, show_resource_metadata


@click.group()
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

                show_generated_metadata(table_name, table_metadata, dry_run)

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

            show_generated_metadata(resource_name, table_metadata, dry_run)

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

        show_resource_metadata(resource_name, project.resources[resource_name])
    else:
        # Show all resources
        if not project.resources:
            click.echo("No resources found in project")
            return

        for name, config in project.resources.items():
            show_resource_metadata(name, config)
            click.echo()
