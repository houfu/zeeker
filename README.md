# Zeeker Database Customization Tool

A Python library and CLI tool for creating, validating, and deploying database customizations for Zeeker's Datasette-based system. Zeeker uses a **three-pass asset system** that allows you to customize individual databases without breaking the overall site functionality.

## 🚀 Features

- **Safe Customizations**: Template validation prevents breaking core Datasette functionality
- **Database-Specific Styling**: CSS and JavaScript scoped to individual databases
- **Complete Asset Management**: Templates, CSS, JavaScript, and metadata in one tool
- **S3 Deployment**: Direct deployment to S3-compatible storage
- **Validation & Testing**: Comprehensive validation before deployment
- **Best Practices**: Generates code following Datasette and web development standards

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

### 1. Generate a New Database Customization

```bash
# Generate customization for a database called 'legal_news'
uv run zeeker generate legal_news ./my-customization \
  --title "Legal News Database" \
  --description "Singapore legal news and commentary" \
  --primary-color "#e74c3c" \
  --accent-color "#c0392b"
```

This creates a complete customization structure:

```
my-customization/
├── metadata.json              # Datasette metadata configuration
├── static/
│   ├── custom.css            # Database-specific CSS
│   ├── custom.js             # Database-specific JavaScript
│   └── images/               # Directory for custom images
└── templates/
    └── database-legal_news.html  # Database-specific template
```

### 2. Validate Your Customization

```bash
# Validate the customization for compliance
uv run zeeker validate ./my-customization legal_news
```

The validator checks for:
- ✅ Safe template names (prevents breaking core functionality)
- ✅ Proper metadata structure
- ✅ Best practice recommendations
- ❌ Banned template names that would break the site

### 3. Deploy to S3

```bash
# Set up environment variables
export S3_BUCKET="your-bucket-name"
export S3_ENDPOINT_URL="https://sin1.contabostorage.com"  # Optional
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# Deploy (dry run first)
uv run zeeker deploy ./my-customization legal_news --dry-run

# Deploy for real
uv run zeeker deploy ./my-customization legal_news
```

### 4. List Deployed Customizations

```bash
# See all database customizations in S3
uv run zeeker list-databases
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
│   └── legal_news.db
└── assets/
    ├── default/                     # Base assets (auto-managed)
    │   ├── templates/
    │   ├── static/
    │   └── metadata.json
    └── databases/                   # Your customizations
        └── legal_news/              # Matches your .db filename
            ├── templates/
            ├── static/
            └── metadata.json
```

## 🎨 Customization Guide

### CSS Customization

Create scoped styles that only affect your database:

```css
/* Scope to your database to avoid conflicts */
[data-database="legal_news"] {
    --color-accent-primary: #e74c3c;
    --color-accent-secondary: #c0392b;
}

/* Custom header styling */
.page-database[data-database="legal_news"] .database-title {
    color: var(--color-accent-primary);
    text-shadow: 0 2px 4px rgba(231, 76, 60, 0.3);
}

/* Custom table styling */
.page-database[data-database="legal_news"] .card {
    border-left: 4px solid var(--color-accent-primary);
    transition: transform 0.2s ease;
}
```

### JavaScript Customization

Add database-specific functionality:

```javascript
// Defensive programming - ensure we're on the right database
function isDatabasePage() {
    return window.location.pathname.includes('/legal_news') ||
           document.body.dataset.database === 'legal_news';
}

document.addEventListener('DOMContentLoaded', function() {
    if (!isDatabasePage()) {
        return; // Exit if not our database
    }

    console.log('Custom JS loaded for legal_news database');
    
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
database-legal_news.html          # Database-specific page
table-legal_news-headlines.html   # Table-specific page
custom-legal_news-dashboard.html  # Custom page
_partial-header.html              # Partial template
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
    "/static/databases/legal_news/custom.css"
  ],
  "extra_js_urls": [
    "/static/databases/legal_news/custom.js"
  ],
  "databases": {
    "legal_news": {
      "description": "Latest Singapore legal developments",
      "title": "Legal News"
    }
  }
}
```

## 🔧 CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| `generate DATABASE_NAME OUTPUT_PATH` | Generate new customization |
| `validate CUSTOMIZATION_PATH DATABASE_NAME` | Validate customization |
| `deploy LOCAL_PATH DATABASE_NAME` | Deploy to S3 |
| `list-databases` | List deployed customizations |

### Generate Options

```bash
uv run zeeker generate DATABASE_NAME OUTPUT_PATH [OPTIONS]

Options:
  --title TEXT          Database title
  --description TEXT    Database description  
  --primary-color TEXT  Primary color (default: #3498db)
  --accent-color TEXT   Accent color (default: #e74c3c)
```

### Deploy Options

```bash
uv run zeeker deploy LOCAL_PATH DATABASE_NAME [OPTIONS]

Options:
  --dry-run    Show what would be uploaded without uploading
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
uv run pytest tests/test_zeeker.py

# Run specific test
uv run pytest tests/test_zeeker.py::TestZeekerValidator::test_validate_template_name_banned_templates
```

### Project Structure

```
zeeker/
├── zeeker/
│   ├── __init__.py
│   └── cli.py                 # Main CLI and library code
├── tests/
│   ├── conftest.py           # Test fixtures and configuration
│   └── test_zeeker.py        # Comprehensive test suite
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

### Metadata Validation

- **JSON Structure**: Validates proper JSON format
- **Required Fields**: Warns about missing recommended fields
- **URL Patterns**: Validates CSS/JS URL patterns for proper loading

## 🌐 Environment Variables

Required for deployment:

| Variable | Description | Required |
|----------|-------------|----------|
| `S3_BUCKET` | S3 bucket name | ✅ |
| `AWS_ACCESS_KEY_ID` | AWS access key | ✅ |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | ✅ |
| `S3_ENDPOINT_URL` | S3 endpoint URL | ⚪ Optional |

## 📖 Examples

### Generate Legal Database Customization

```bash
uv run zeeker generate legal_cases ./legal-customization \
  --title "Legal Cases Database" \
  --description "Singapore court cases and legal precedents" \
  --primary-color "#2c3e50" \
  --accent-color "#e67e22"
```

### Generate Tech News Customization

```bash
uv run zeeker generate tech_news ./tech-customization \
  --title "Tech News" \
  --description "Latest technology news and trends" \
  --primary-color "#9b59b6" \
  --accent-color "#8e44ad"
```

### Validate Before Deploy

```bash
# Always validate first
uv run zeeker validate ./legal-customization legal_cases

# Then deploy
uv run zeeker deploy ./legal-customization legal_cases
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

### Common Issues

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