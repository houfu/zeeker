# Zeeker Database Management Tool

[![PyPI version](https://badge.fury.io/py/zeeker.svg)](https://badge.fury.io/py/zeeker)
[![Test Status](https://github.com/houfu/zeeker/workflows/Test/badge.svg)](https://github.com/houfu/zeeker/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A Python library and CLI tool for creating, managing, and deploying databases and customizations for Zeeker's Datasette-based system. Zeeker uses a **three-pass asset system** that allows you to manage complete database projects and customize individual databases without breaking overall site functionality.

## 🚀 Features

- **Complete Database Projects**: Create, build, and deploy entire databases with data resources
- **Intelligent Metadata Generation**: Auto-generate column descriptions, project metadata, and resource descriptions from schema analysis
- **Document Fragments**: Built-in support for splitting large documents into searchable chunks with automatic full-text search
- **Automated Meta Tables**: Schema versioning and update tracking with zero configuration
- **Schema Conflict Detection**: Safe migration system prevents data corruption from schema changes
- **Safe UI Customizations**: Template validation prevents breaking core Datasette functionality  
- **Database-Specific Styling**: CSS and JavaScript scoped to individual databases
- **S3 Deployment & Sync**: Direct deployment to S3-compatible storage with multi-machine sync capabilities
- **sqlite-utils Integration**: Robust database operations with automatic schema detection
- **Isolated Environments**: Automatic pyproject.toml generation and virtual environment setup per project
- **Dependency Management**: Built-in support for project-specific dependencies with uv integration
- **Validation & Testing**: Comprehensive validation before deployment
- **Best Practices**: Generates code following Datasette and web development standards

## ✨ What's New in v0.5.0

- **🧠 Intelligent Metadata Generation**: Auto-generate column descriptions, project metadata, and resource descriptions from schema analysis
- **📋 Metadata Management**: New `zeeker metadata generate|show` commands with dry-run, force, and selective generation
- **🎛️ Conditional FTS Setup**: `--setup-fts` flag for optional full-text search configuration  
- **🔧 Modular CLI**: Refactored command structure with separated modules for better maintainability
- **📊 Datasette Integration**: Complete metadata.json support with facets, sorting, and display options

## 🛠 Two Workflows

Zeeker supports two complementary workflows:

### 📊 **Database Projects** (Primary Workflow)
Create and manage complete databases with data resources:
- Initialize projects with `zeeker init`
- Add data resources with `zeeker add`
- Build SQLite databases with `zeeker build`
- Deploy databases with `zeeker deploy`
- Generate metadata with `zeeker metadata generate`

### 🎨 **UI Customizations** (Secondary Workflow)  
Customize the appearance of individual databases:
- Generate UI assets with `zeeker assets generate`
- Validate customizations with `zeeker assets validate`
- Deploy UI assets with `zeeker assets deploy`

## 🔄 Multi-Machine Workflows with S3 Sync

Zeeker's S3 sync feature enables seamless collaboration across different development environments:

### When to Use S3 Sync

**Perfect for:**
- Multiple developers working on the same database project
- Switching between development machines (laptop, desktop, cloud)
- Incremental data updates without duplicating records
- Production data updates from different scheduled jobs

### How S3 Sync Works

1. **First Build**: `zeeker build` creates database locally
2. **Deploy**: `zeeker deploy` uploads to S3 `latest/{database}.db`
3. **Other Machine**: `zeeker build --sync-from-s3` downloads existing database first
4. **Incremental Update**: Your `fetch_data(existing_table)` can check for existing records

### Example Workflow

```bash
# Machine A: Initial build and deploy
zeeker build
zeeker deploy

# Machine B: Sync existing data, then add new records
zeeker build --sync-from-s3  # Downloads existing DB first
zeeker deploy                # Uploads updated DB

# Machine A: Get latest updates
zeeker build --sync-from-s3  # Gets Machine B's updates
```

**Key Benefits:**
- ✅ No duplicate data when switching machines
- ✅ Incremental updates instead of full rebuilds  
- ✅ Automatic handling of missing S3 databases
- ✅ Same AWS credentials used for both sync and deploy

## 📦 Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/houfu/zeeker.git
cd zeeker

# Install dependencies with uv
uv sync

# Install in development mode
uv pip install -e .
```

### Using pip

```bash
# Note: Package publication to PyPI is in progress
pip install zeeker
```

## 🛠 Quick Start

### Database Project Workflow

#### 1. Create a New Database Project

```bash
# Initialize a new project (creates pyproject.toml, zeeker.toml, resources/, and sets up virtual environment)
uv run zeeker init legal_news_project

# Navigate to project directory
cd legal_news_project

# Add project-specific dependencies (example)
uv add requests beautifulsoup4 pandas
```

#### 2. Add Data Resources

```bash
# Add a resource for legal articles
uv run zeeker add articles \
  --description "Legal news articles" \
  --facets category --facets jurisdiction \
  --sort "published_date desc" \
  --size 25

# Add a resource for court cases  
uv run zeeker add court_cases \
  --description "Court case summaries" \
  --facets court_level --facets case_type

# Add a resource for large legal documents with fragments support
uv run zeeker add legal_docs --fragments \
  --description "Legal documents with searchable fragments"
```

**Fragment Support**: The `--fragments` flag creates resources optimized for large documents (legal documents, contracts, research papers). This automatically creates two tables: one for document metadata and another for searchable text fragments with **built-in full-text search** on text content.

#### 3. Implement Data Fetching

Edit `resources/articles.py`:
```python
from sqlite_utils.db import Table
from typing import Optional, List, Dict, Any

def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """Fetch legal news articles."""
    # Your data fetching logic here
    # Could be API calls, file reading, web scraping, etc.
    # Use existing_table to check for existing records and avoid duplicates
    return [
        {
            "id": 1,
            "title": "New Privacy Legislation Passed",
            "content": "The legislature has passed...",
            "category": "privacy",
            "jurisdiction": "singapore",
            "published_date": "2024-01-15"
        },
        # ... more articles
    ]
```

#### 4. Build and Deploy Database

```bash
# Build SQLite database from all resources
# Automatically creates meta tables for schema tracking
uv run zeeker build

# Or sync from S3 first for incremental updates across machines
uv run zeeker build --sync-from-s3

# Deploy database to S3
uv run zeeker deploy
```

### UI Customization Workflow

#### 1. Generate UI Assets for a Database

```bash
# Generate customization for the legal_news_project database
uv run zeeker assets generate legal_news_project ./ui-customization \
  --title "Legal News Database" \
  --description "Singapore legal news and commentary" \
  --primary-color "#e74c3c" \
  --accent-color "#c0392b"
```

This creates:
```
ui-customization/
├── metadata.json              # Datasette metadata configuration
├── static/
│   ├── custom.css            # Database-specific CSS
│   ├── custom.js             # Database-specific JavaScript
│   └── images/               # Directory for custom images
└── templates/
    └── database-legal_news_project.html  # Database-specific template
```

#### 2. Validate UI Customization

```bash
# Validate the customization for compliance
uv run zeeker assets validate ./ui-customization legal_news_project
```

The validator checks for:
- ✅ Safe template names (prevents breaking core functionality)
- ✅ Proper metadata structure
- ✅ Best practice recommendations
- ❌ Banned template names that would break the site

#### 3. Deploy UI Assets

```bash
# Set up environment variables
export S3_BUCKET="your-bucket-name"
export S3_ENDPOINT_URL="https://s3.amazonaws.com"  # Optional: use your S3-compatible provider
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# Deploy (dry run first)
uv run zeeker assets deploy ./ui-customization legal_news_project --dry-run

# Deploy for real
uv run zeeker assets deploy ./ui-customization legal_news_project
```

#### 4. List Deployed Customizations

```bash
# See all database UI customizations in S3
uv run zeeker assets list
```

## 📚 How It Works

### Three-Pass Asset System

Zeeker processes assets in three passes:

1. **Pass 1**: Download database files (`.db` files)
2. **Pass 2**: Set up base assets (shared templates, CSS, etc.)
3. **Pass 3**: Apply your database-specific customizations

Your customizations **overlay** the base assets, so you only need to provide files you want to change.

### S3 Structure

```
s3://your-bucket/
├── latest/                          # Your .db files
│   └── legal_news_project.db
└── assets/
    ├── default/                     # Base assets (auto-managed)
    │   ├── templates/
    │   ├── static/
    │   └── metadata.json
    └── databases/                   # Your UI customizations
        └── legal_news_project/      # Matches your .db filename
            ├── templates/
            ├── static/
            └── metadata.json
```

## 📊 Database Project Guide

### Project Structure

A Zeeker project consists of:

```
my-project/
├── pyproject.toml           # Project dependencies and metadata (PEP 621 compliant)
├── zeeker.toml              # Project configuration
├── resources/               # Python modules for data fetching
│   ├── __init__.py
│   ├── articles.py          # Resource: articles table
│   └── court_cases.py       # Resource: court_cases table
├── .venv/                   # Isolated virtual environment (gitignored)
├── my-project.db            # Generated SQLite database (gitignored)
├── metadata.json            # Generated Datasette metadata
├── .gitignore               # Git ignore rules
├── CLAUDE.md                # Development guide for Claude Code
└── README.md                # Project documentation
```

### Resource Development

Each resource is a Python module that implements `fetch_data()`:

```python
"""
Articles resource for legal news data.
"""
from sqlite_utils.db import Table
from typing import Optional, List, Dict, Any

def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """
    Fetch data for the articles table.
    
    Args:
        existing_table: sqlite-utils Table object if table exists, None if new table
    
    Returns:
        List[Dict[str, Any]]: List of records to insert into database
    """
    # Your data fetching logic here
    # This could be:
    # - API calls (requests.get, etc.)
    # - File reading (CSV, JSON, XML, etc.) 
    # - Database queries (from other sources)
    # - Web scraping (BeautifulSoup, Scrapy, etc.)
    # - Any other data source
    
    return [
        {
            "id": 1,
            "title": "Legal Update",
            "content": "...",
            "published_date": "2024-01-15",
            "tags": ["privacy", "legislation"]  # JSON stored automatically
        },
        # ... more records
    ]

def transform_data(raw_data):
    """
    Optional: Transform/clean data before database insertion.
    """
    # Clean and transform data
    for item in raw_data:
        item['title'] = item['title'].strip().title()
        # Add computed fields, clean data, etc.
    return raw_data
```

### sqlite-utils Integration & Meta Tables

Zeeker uses Simon Willison's sqlite-utils for robust database operations:

- **Automatic table creation** with proper schema detection
- **Type inference** from data (INTEGER, TEXT, REAL, JSON)
- **Safe data insertion** without SQL injection risks
- **JSON support** for complex data structures
- **Better error handling** than raw SQL

#### Automated Meta Tables System

Every database automatically includes two meta tables:

**`_zeeker_schemas`** - Schema Version Tracking:
- Tracks schema versions, hashes, and column definitions
- Automatically detects schema changes between builds
- Provides audit trail for schema evolution

**`_zeeker_updates`** - Update Timestamps:
- Records last update time and record counts for each resource
- Tracks build performance and data freshness
- Helps identify stale data sources

#### Schema Conflict Detection

When schemas change, Zeeker provides safe resolution options:

1. **Migration Functions** - Add custom `migrate_schema()` to handle changes
2. **Force Reset** - Use `--force-schema-reset` flag to rebuild
3. **Manual Cleanup** - Delete database file and rebuild from scratch

**Example Migration:**
```python
def migrate_schema(existing_table, new_schema_info):
    """Handle adding 'age' column to users table."""
    existing_table.add_column('age', int, fk=None)
    for row_id in existing_table.pks:
        existing_table.update(row_id, {'age': 25})  # Default age
    return True
```

## 🎨 UI Customization Guide

### CSS Customization

Create scoped styles that only affect your database:

```css
/* Scope to your database to avoid conflicts */
[data-database="legal_news_project"] {
    --color-accent-primary: #e74c3c;
    --color-accent-secondary: #c0392b;
}

/* Custom header styling */
.page-database[data-database="legal_news_project"] .database-title {
    color: var(--color-accent-primary);
    text-shadow: 0 2px 4px rgba(231, 76, 60, 0.3);
}

/* Custom table styling */
.page-database[data-database="legal_news_project"] .card {
    border-left: 4px solid var(--color-accent-primary);
    transition: transform 0.2s ease;
}
```

### JavaScript Customization

Add database-specific functionality:

```javascript
// Defensive programming - ensure we're on the right database
function isDatabasePage() {
    return window.location.pathname.includes('/legal_news_project') ||
           document.body.dataset.database === 'legal_news_project';
}

document.addEventListener('DOMContentLoaded', function() {
    if (!isDatabasePage()) {
        return; // Exit if not our database
    }

    console.log('Custom JS loaded for legal_news_project database');
    
    // Add custom search suggestions
    const searchInput = document.querySelector('.hero-search-input');
    if (searchInput) {
        searchInput.placeholder = 'Search legal news, cases, legislation...';
    }
});
```

### Template Customization

Create database-specific templates using **safe naming patterns**:

#### ✅ Safe Template Names

```
database-legal_news_project.html          # Database-specific page
table-legal_news_project-articles.html    # Table-specific page
custom-legal_news_project-dashboard.html  # Custom page
_partial-header.html                       # Partial template
```

#### ❌ Banned Template Names

```
database.html     # Would break ALL database pages
table.html        # Would break ALL table pages
index.html        # Would break homepage
query.html        # Would break SQL interface
```

#### Example Database Template

```html
{% extends "default:database.html" %}

{% block extra_head %}
{{ super() }}
<meta name="description" content="Singapore legal news database">
{% endblock %}

{% block content %}
<div class="legal-news-banner">
    <h1>📰 Singapore Legal News</h1>
    <p>Latest legal developments and court decisions</p>
</div>

{{ super() }}
{% endblock %}
```

### Metadata Configuration

Provide a complete Datasette metadata structure:

```json
{
  "title": "Legal News Database",
  "description": "Singapore legal news and commentary",
  "license": "CC-BY-4.0",
  "license_url": "https://creativecommons.org/licenses/by/4.0/",
  "source_url": "https://example.com/legal-news",
  "extra_css_urls": [
    "/static/databases/legal_news_project/custom.css"
  ],
  "extra_js_urls": [
    "/static/databases/legal_news_project/custom.js"
  ],
  "databases": {
    "legal_news_project": {
      "description": "Latest Singapore legal developments",
      "title": "Legal News"
    }
  }
}
```

## 🔧 CLI Reference

### Database Project Commands

| Command | Description |
|---------|-------------|
| `zeeker init PROJECT_NAME` | Initialize new database project |
| `zeeker add RESOURCE_NAME` | Add data resource to project |
| `zeeker build` | Build SQLite database from all resources with automated meta tables |
| `zeeker build resource1 resource2` | Build database from specific resources only (selective building) |
| `zeeker build --sync-from-s3` | Build database with S3 sync (download existing DB for incremental updates) |
| `zeeker build --force-schema-reset` | Build database ignoring schema conflicts (for development) |
| `zeeker deploy` | Deploy database to S3 |

### UI Customization Commands

| Command | Description |
|---------|-------------|
| `zeeker assets generate DATABASE_NAME OUTPUT_PATH` | Generate UI customization assets |
| `zeeker assets validate ASSETS_PATH DATABASE_NAME` | Validate UI assets |
| `zeeker assets deploy LOCAL_PATH DATABASE_NAME` | Deploy UI assets to S3 |
| `zeeker assets list` | List deployed UI customizations |

### Project Commands Options

```bash
# Initialize project
zeeker init PROJECT_NAME [--path PATH]

# Add resource with Datasette options
zeeker add RESOURCE_NAME \
  --description TEXT \
  --facets FIELD \
  --sort FIELD \
  --size NUMBER \
  --fragments \
  --async \
  --fts-fields FIELD \
  --fragments-fts-fields FIELD

# Build with schema management options
zeeker build [resource1] [resource2] [--sync-from-s3] [--force-schema-reset]

# Deploy with dry run
zeeker deploy [--dry-run]
```

### UI Asset Commands Options

```bash
# Generate UI assets
zeeker assets generate DATABASE_NAME OUTPUT_PATH \
  --title TEXT \
  --description TEXT \
  --primary-color TEXT \
  --accent-color TEXT

# Deploy UI assets with options
zeeker assets deploy LOCAL_PATH DATABASE_NAME \
  --dry-run \
  --sync \
  --clean \
  --yes \
  --diff
```

## 🧪 Development

### Setup Development Environment

```bash
# Clone and setup
git clone https://github.com/houfu/zeeker.git
cd zeeker
uv sync

# Install development dependencies
uv sync --group dev

# Run tests
uv run pytest

# Format code (follows black style)
uv run black .

# Run specific test categories
uv run pytest -m unit          # Unit tests only
uv run pytest -m integration   # Integration tests only
uv run pytest -m cli          # CLI tests only
```

### Testing

The project has comprehensive test coverage:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=zeeker

# Run specific test file
uv run pytest tests/test_project.py

# Run specific test
uv run pytest tests/test_validator.py::TestTemplateValidation::test_banned_templates_rejected
```

### Project Structure

```
zeeker/
├── zeeker/
│   ├── __init__.py
│   ├── cli.py                 # Main CLI interface
│   └── core/                  # Core functionality modules
│       ├── __init__.py
│       ├── project.py         # Project management
│       ├── validator.py       # Asset validation
│       ├── generator.py       # Asset generation
│       ├── deployer.py        # S3 deployment
│       └── types.py           # Data structures
├── tests/
│   ├── conftest.py           # Test fixtures and configuration
│   ├── test_project.py       # Project management tests
│   ├── test_validator.py     # Validation tests
│   ├── test_generator.py     # Generation tests
│   └── test_deployer.py      # Deployment tests
├── database_customization_guide.md  # Detailed user guide
├── pyproject.toml            # Project configuration
└── README.md                 # This file
```

## 🔒 Safety Features

### Template Validation

The validator automatically prevents dangerous template names:

- **Banned Templates**: `database.html`, `table.html`, `index.html`, etc.
- **Safe Patterns**: `database-DBNAME.html`, `table-DBNAME-TABLE.html`, `custom-*.html`
- **Automatic Blocking**: System rejects banned templates to protect core functionality

### CSS/JS Scoping

Generated code automatically scopes to your database:

```css
/* Automatically scoped to prevent conflicts */
[data-database="your_database"] .custom-style {
    /* Your styles here */
}
```

### Database Operations

- **sqlite-utils Integration**: Automatic schema detection and type inference
- **Safe Data Insertion**: No SQL injection risks
- **JSON Support**: Complex data structures handled automatically
- **Error Handling**: Comprehensive validation and error reporting

## 🌐 Environment Variables

Required for deployment:

| Variable | Description | Required |
|----------|-------------|----------|
| `S3_BUCKET` | S3 bucket name | ✅ |
| `AWS_ACCESS_KEY_ID` | AWS access key | ✅ |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | ✅ |
| `S3_ENDPOINT_URL` | S3 endpoint URL | ⚪ Optional |

## 📖 Examples

### Complete Database Project Example

```bash
# Create project for Singapore legal data
uv run zeeker init singapore_legal

cd singapore_legal

# Add resources
uv run zeeker add court_cases \
  --description "Singapore court case summaries" \
  --facets court_level --facets case_type \
  --sort "decision_date desc"

uv run zeeker add legislation \
  --description "Singapore legislation and amendments" \
  --facets ministry --facets status \
  --sort "effective_date desc"

# Implement data fetching in resources/*.py files
# Then build and deploy
uv run zeeker build
uv run zeeker deploy
```

### UI Customization Examples

```bash
# Generate Legal Database Customization
uv run zeeker assets generate singapore_legal ./legal-customization \
  --title "Singapore Legal Database" \
  --description "Court cases and legislation for Singapore" \
  --primary-color "#2c3e50" \
  --accent-color "#e67e22"

# Generate Tech News Customization
uv run zeeker assets generate tech_news ./tech-customization \
  --title "Tech News" \
  --description "Latest technology news and trends" \
  --primary-color "#9b59b6" \
  --accent-color "#8e44ad"

# Always validate before deploying
uv run zeeker assets validate ./legal-customization singapore_legal

# Then deploy UI assets
uv run zeeker assets deploy ./legal-customization singapore_legal
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Format code: `uv run black .`
5. Run tests: `uv run pytest`
6. Submit a pull request

## 📄 License

This project is licensed under the terms specified in the project configuration.

## 🆘 Troubleshooting

### Database Project Issues

**Schema Conflict Detected**
```
❌ Schema conflict detected:
Schema conflict detected for resource 'users'.
Added columns: age
```

**Resolution Options:**
1. **Add Migration Function** (Recommended):
```python
# In resources/users.py
def migrate_schema(existing_table, new_schema_info):
    existing_table.add_column('age', int, fk=None)
    return True
```

2. **Use Force Reset Flag**:
```bash
zeeker build --force-schema-reset
```

3. **Manual Database Reset**:
```bash
rm project_name.db
zeeker build
```

**Build Fails**
- Check that all resource files have `fetch_data()` function
- Verify data is returned as list of dictionaries
- Check for syntax errors in resource files
- Ensure you're in a project directory (has `zeeker.toml`)
- Review schema conflict errors and add migration functions if needed

**Deploy Fails**
- Verify environment variables are set correctly
- Check that database file was built successfully
- Ensure S3 bucket exists and has correct permissions

### UI Customization Issues

**Templates Not Loading**
- Check template names don't use banned patterns
- Verify template follows `database-DBNAME.html` pattern
- Look at browser page source for template debug info

**Assets Not Loading**
- Verify S3 paths match `/static/databases/DATABASE_NAME/` pattern  
- Check S3 permissions and bucket configuration
- Restart Datasette container after deployment

**Validation Errors**
- Read error messages carefully - they provide specific fixes
- Use `--dry-run` flag to test deployments safely
- Check the detailed guide in `database_customization_guide.md`

For detailed troubleshooting, see the [Database Customization Guide](database_customization_guide.md).