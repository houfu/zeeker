# Zeeker Database Management Tool

[![PyPI version](https://badge.fury.io/py/zeeker.svg)](https://badge.fury.io/py/zeeker)
[![Test Status](https://github.com/houfu/zeeker/workflows/Test/badge.svg)](https://github.com/houfu/zeeker/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A Python library and CLI tool for creating, managing, and deploying databases and customizations for Zeeker's Datasette-based system. Zeeker uses a **three-pass asset system** that allows you to manage complete database projects and customize individual databases without breaking overall site functionality.

## 🚀 Features

- **Complete Database Projects**: Create, build, and deploy entire databases with data resources
- **Safe UI Customizations**: Template validation prevents breaking core Datasette functionality  
- **Database-Specific Styling**: CSS and JavaScript scoped to individual databases
- **S3 Deployment**: Direct deployment to S3-compatible storage for both databases and assets
- **sqlite-utils Integration**: Robust database operations with automatic schema detection
- **Validation & Testing**: Comprehensive validation before deployment
- **Best Practices**: Generates code following Datasette and web development standards

## 🛠 Two Workflows

Zeeker supports two complementary workflows:

### 📊 **Database Projects** (Primary Workflow)
Create and manage complete databases with data resources:
- Initialize projects with `zeeker init`
- Add data resources with `zeeker add`
- Build SQLite databases with `zeeker build`
- Deploy databases with `zeeker deploy`

### 🎨 **UI Customizations** (Secondary Workflow)  
Customize the appearance of individual databases:
- Generate UI assets with `zeeker assets generate`
- Validate customizations with `zeeker assets validate`
- Deploy UI assets with `zeeker assets deploy`

## 📦 Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd zeeker

# Install dependencies with uv
uv sync

# Install in development mode
uv pip install -e .
```

### Using pip

```bash
pip install zeeker
```

## 🛠 Quick Start

### Database Project Workflow

#### 1. Create a New Database Project

```bash
# Initialize a new project
uv run zeeker init legal_news_project

# Navigate to project directory
cd legal_news_project
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
```

#### 3. Implement Data Fetching

Edit `resources/articles.py`:
```python
def fetch_data():
    """Fetch legal news articles."""
    # Your data fetching logic here
    # Could be API calls, file reading, web scraping, etc.
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
uv run zeeker build

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
export S3_ENDPOINT_URL="https://sin1.contabostorage.com"  # Optional
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
├── zeeker.toml              # Project configuration
├── resources/               # Python modules for data fetching
│   ├── __init__.py
│   ├── articles.py          # Resource: articles table
│   └── court_cases.py       # Resource: court_cases table
├── my-project.db            # Generated SQLite database (gitignored)
├── metadata.json            # Generated Datasette metadata
├── .gitignore               # Git ignore rules
└── README.md                # Project documentation
```

### Resource Development

Each resource is a Python module that implements `fetch_data()`:

```python
"""
Articles resource for legal news data.
"""

def fetch_data():
    """
    Fetch data for the articles table.
    
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

### sqlite-utils Integration

Zeeker uses Simon Willison's sqlite-utils for robust database operations:

- **Automatic table creation** with proper schema detection
- **Type inference** from data (INTEGER, TEXT, REAL, JSON)
- **Safe data insertion** without SQL injection risks
- **JSON support** for complex data structures
- **Better error handling** than raw SQL

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
| `zeeker build` | Build SQLite database from resources |
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
  --size NUMBER

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
git clone <repository-url>
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

**Build Fails**
- Check that all resource files have `fetch_data()` function
- Verify data is returned as list of dictionaries
- Check for syntax errors in resource files
- Ensure you're in a project directory (has `zeeker.toml`)

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