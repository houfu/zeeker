"""
Shared helper functions for CLI commands.
"""

import click


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
