"""
Asset generation for Zeeker database customizations.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any

from .types import DatabaseCustomization
from .validator import ZeekerValidator


class ZeekerGenerator:
    """Generates Zeeker assets following the customization guide."""

    def __init__(self, database_name: str, output_path: Path):
        self.database_name = database_name
        self.sanitized_name = ZeekerValidator.sanitize_database_name(database_name)
        self.output_path = output_path
        self.customization = DatabaseCustomization(database_name, output_path)

    def create_base_structure(self) -> None:
        """Create structure following the guide: templates/, static/, static/images/"""
        dirs = [
            self.output_path,
            self.output_path / "templates",
            self.output_path / "static",
            self.output_path / "static" / "images",
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def generate_metadata_template(self, title: str, description: str, **kwargs) -> Dict[str, Any]:
        """Generate complete Datasette metadata following the guide format."""
        # Use sanitized name for URL paths (matches S3 structure)
        url_name = self.sanitized_name

        metadata = {
            "title": title,
            "description": description,
            "license": kwargs.get("license_type", "CC-BY-4.0"),
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
        }

        if kwargs.get("source_url"):
            metadata["source_url"] = kwargs["source_url"]

        # Follow guide URL pattern: /static/databases/database_name/filename
        if kwargs.get("extra_css"):
            metadata["extra_css_urls"] = [
                f"/static/databases/{url_name}/{css}" for css in kwargs["extra_css"]
            ]

        if kwargs.get("extra_js"):
            metadata["extra_js_urls"] = [
                f"/static/databases/{url_name}/{js}" for js in kwargs["extra_js"]
            ]

        # Complete Datasette structure (not fragments) per guide
        metadata["databases"] = {self.database_name: {"description": description, "title": title}}

        return metadata

    def generate_css_template(
        self, primary_color: str = "#3498db", accent_color: str = "#e74c3c"
    ) -> str:
        """Generate CSS following the guide's scoping best practices."""
        return f"""/* Custom styles for {self.database_name} database */
/* Following Zeeker customization guide patterns */

/* CSS Custom Properties for theming */
:root {{
    --color-accent-primary: {primary_color};
    --color-accent-secondary: {accent_color};
}}

/* Scope to your database to avoid conflicts (per guide) */
[data-database="{self.sanitized_name}"] {{
    /* Database-specific styles here */
}}

/* Database-specific header styling */
.page-database[data-database="{self.sanitized_name}"] .database-title {{
    color: var(--color-accent-primary);
    text-shadow: 0 2px 4px rgba(52, 152, 219, 0.3);
}}

/* Custom table styling */
.page-database[data-database="{self.sanitized_name}"] .card {{
    border-left: 4px solid var(--color-accent-primary);
    transition: transform 0.2s ease;
}}

.page-database[data-database="{self.sanitized_name}"] .card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}}

/* Responsive design */
@media (max-width: 768px) {{
    .page-database[data-database="{self.sanitized_name}"] .database-title {{
        font-size: 1.5rem;
    }}
}}
"""

    def generate_js_template(self) -> str:
        """Generate JavaScript following the guide's defensive programming practices."""
        return f"""// Custom JavaScript for {self.database_name} database
// Following Zeeker customization guide best practices

// Defensive programming - ensure we're on the right database (per guide)
function isDatabasePage() {{
    return window.location.pathname.includes('/{self.database_name}') ||
           document.body.dataset.database === '{self.sanitized_name}';
}}

document.addEventListener('DOMContentLoaded', function() {{
    if (!isDatabasePage()) {{
        return; // Exit if not our database (safety per guide)
    }}
    
    console.log('Custom JS loaded for {self.database_name} database');
    
    // Initialize custom features safely
    initCustomFeatures();
}});

function initCustomFeatures() {{
    // Add custom search suggestions (safe implementation)
    const searchInput = document.querySelector('.hero-search-input');
    if (searchInput) {{
        searchInput.placeholder = 'Search {self.database_name}...';
    }}
    
    // Custom table enhancements
    enhanceTables();
}}

function enhanceTables() {{
    // Safe element selection per guide
    const tables = document.querySelectorAll('.table-wrapper table');
    tables.forEach(table => {{
        // Add your custom table functionality here
        table.classList.add('enhanced-table');
    }});
}}
"""

    def generate_database_template(self, custom_title: Optional[str] = None) -> str:
        """Generate safe database template following guide naming conventions."""
        title = custom_title or f"{self.database_name.title()} Database"

        # Follow guide pattern: database-DBNAME.html (safe naming)
        return f"""{{%% extends "default:database.html" %%}}

{{%% block extra_head %%}}
{{{{ super() }}}}
<meta name="description" content="Custom database: {self.database_name}">
{{%% endblock %%}}

{{%% block content %%}}
<div class="custom-database-header">
    <h1>📊 {title}</h1>
    <p>Welcome to the {self.database_name} database</p>
</div>

{{{{ super() }}}}
{{%% endblock %%}}
"""

    def save_assets(self, metadata=None, css_content=None, js_content=None, templates=None):
        """Save assets following the guide's file structure."""
        self.create_base_structure()

        if metadata:
            with open(self.output_path / "metadata.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

        if css_content:
            with open(self.output_path / "static" / "custom.css", "w", encoding="utf-8") as f:
                f.write(css_content)

        if js_content:
            with open(self.output_path / "static" / "custom.js", "w", encoding="utf-8") as f:
                f.write(js_content)

        if templates:
            for template_name, template_content in templates.items():
                with open(
                    self.output_path / "templates" / template_name, "w", encoding="utf-8"
                ) as f:
                    f.write(template_content)
