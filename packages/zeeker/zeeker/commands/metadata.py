"""
Metadata management commands.
"""

import click

from ..core.metadata import MetadataGenerator
from ..core.project import ZeekerProjectManager
from .helpers import (
    require_database,
    require_project,
    show_generated_metadata,
    show_resource_metadata,
)


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

    Examples:
        zeeker metadata generate users                    # Column metadata for users table
        zeeker metadata generate --project               # Project-level metadata only
        zeeker metadata generate --all --project         # Everything
        zeeker metadata generate users --dry-run         # Preview without changes
    """
    manager = ZeekerProjectManager()
    project_obj = require_project(manager)
    if not project_obj:
        return

    generator = MetadataGenerator(manager.project_path)

    if resource_desc is not None and not resource_desc.strip():
        click.echo("❌ --resource requires a resource name")
        return

    if not resource_name and not all and not project and not resource_desc:
        click.echo("❌ Specify a resource name, use --all, --project, or --resource")
        return

    # Check if database exists for operations that need it
    needs_db = resource_name or all or resource_desc
    db_path = None
    if needs_db:
        db_path = require_database(manager, project_obj)
        if not db_path:
            return

    try:
        project_updated = False

        # Handle project-level metadata generation
        if project:
            missing_project_fields = generator.detect_missing_project_metadata(project_obj)
            if missing_project_fields:
                click.echo(
                    f"🔍 Missing project metadata detected: {', '.join(missing_project_fields)}"
                )

                if dry_run:
                    click.echo("   Would generate:")
                    temp_project = generator.generate_project_metadata(project_obj)
                    for field in missing_project_fields:
                        value = getattr(temp_project, field)
                        if value:
                            click.echo(f"   • {field}: {value}")
                else:
                    project_obj = generator.generate_project_metadata(project_obj)
                    click.echo("✨ Generated project metadata")
                    project_updated = True
            else:
                click.echo("ℹ️  Project metadata already complete")

        # Handle resource description generation
        if resource_desc:
            missing_resource_descs = generator.detect_missing_resource_descriptions(
                project_obj, resource_desc
            )
            if missing_resource_descs:
                click.echo(f"🔍 Generating description for resource '{resource_desc}'...")

                generated_desc = generator.generate_resource_description(db_path, resource_desc)

                if dry_run:
                    click.echo(f"   Would generate description: {generated_desc}")
                else:
                    if resource_desc not in project_obj.resources:
                        project_obj.resources[resource_desc] = {}
                    project_obj.resources[resource_desc]["description"] = generated_desc
                    click.echo(f"✨ Generated description for '{resource_desc}': {generated_desc}")
                    project_updated = True
            else:
                click.echo(f"ℹ️  Resource '{resource_desc}' already has description")

        # Handle column metadata generation
        if all:
            click.echo("🔍 Analyzing all tables in database...")
            all_metadata = generator.generate_for_all_tables(db_path)

            for table_name, table_metadata in all_metadata.items():
                if "error" in table_metadata:
                    click.echo(f"⚠️  Error analyzing {table_name}: {table_metadata['error']}")
                    continue

                show_generated_metadata(table_name, table_metadata, dry_run)

                if not dry_run:
                    project_obj = generator.update_project_metadata(
                        project_obj, table_name, table_metadata, preserve_existing=not force
                    )
                    project_updated = True

        elif resource_name:
            if resource_name not in project_obj.resources:
                click.echo(f"❌ Resource '{resource_name}' not found in zeeker.toml")
                return

            click.echo(f"🔍 Analyzing table '{resource_name}'...")
            table_metadata = generator.generate_metadata_for_table(db_path, resource_name)

            show_generated_metadata(resource_name, table_metadata, dry_run)

            if not dry_run:
                project_obj = generator.update_project_metadata(
                    project_obj, resource_name, table_metadata, preserve_existing=not force
                )
                project_updated = True

        if project_updated and not dry_run:
            project_obj.save_toml(manager.toml_path)
            click.echo("\n✅ Updated zeeker.toml with generated metadata")

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
    project = require_project(manager)
    if not project:
        return

    if resource_name:
        if resource_name not in project.resources:
            click.echo(f"❌ Resource '{resource_name}' not found")
            return
        show_resource_metadata(resource_name, project.resources[resource_name])
    else:
        if not project.resources:
            click.echo("No resources found in project")
            return

        for name, config in project.resources.items():
            show_resource_metadata(name, config)
            click.echo()
