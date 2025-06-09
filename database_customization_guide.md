# Database Customization Guide

## Overview

Zeeker uses a **three-pass asset system** that lets you customize individual databases without breaking the overall site. Here's how to add your own templates, CSS, JavaScript, and metadata.

## How It Works

When the container starts, it runs three passes:

1. **Pass 1**: Download database files (`.db` files)
2. **Pass 2**: Set up base assets (shared templates, CSS, etc.)
3. **Pass 3**: Apply your database-specific customizations

Your customizations **overlay** the base assets, so you only need to provide files you want to change.

## S3 Structure

```
s3://your-bucket/
├── latest/                          # Your .db files go here
│   └── your_database.db
└── assets/
    ├── default/                     # Base assets (auto-managed)
    │   ├── templates/
    │   ├── static/
    │   ├── plugins/
    │   └── metadata.json
    └── databases/                   # Your customizations go here
        └── your_database/           # Folder matches your .db filename
            ├── templates/           # Custom templates (optional)
            ├── static/              # Custom CSS/JS (optional)
            └── metadata.json        # Custom metadata (optional)
```

## Quick Start

### 1. Find Your Database Name

Your customization folder name must match your database filename (without `.db`):

- Database file: `legal_news.db` → Folder: `databases/legal_news/`
- Database file: `court_cases.db` → Folder: `databases/court_cases/`

### 2. Create Your Customization Folder

Upload to S3 at: `s3://your-bucket/assets/databases/your_database/`

### 3. Add What You Need

You only need to upload files you want to customize. Everything else uses the base assets.

## Customization Options

### Custom Metadata (`metadata.json`)

**Important**: You must provide a complete Datasette metadata.json structure, not just database-specific parts. The system performs a full merge.

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

This follows standard Datasette metadata.json format - you can't provide fragments.

**Merging Rules (from the code):**
- `extra_css_urls` and `extra_js_urls` are **appended** to base URLs (never replaced)
- `databases.your_database` settings are **added** (won't override global `*` settings)  
- Other root-level fields like `title`, `description` **replace** base values
- Nested objects are deep-merged where possible

### Custom CSS (`static/custom.css`)

Override styles for your database:

```css
/* Custom colors for this database */
:root {
    --color-accent-primary: #e74c3c;  /* Red theme */
    --color-accent-cyan: #e67e22;     /* Orange accents */
}

/* Database-specific header styling */
.database-title {
    color: var(--color-accent-primary);
    text-shadow: 0 2px 4px rgba(231, 76, 60, 0.3);
}

/* Custom table styling */
.page-database .card {
    border-left: 4px solid var(--color-accent-primary);
}
```

### Custom JavaScript (`static/custom.js`)

Add database-specific functionality:

```javascript
// Custom behavior for this database
document.addEventListener('DOMContentLoaded', function() {
    console.log('Custom JS loaded for legal news database');
    
    // Add custom search suggestions
    const searchInput = document.querySelector('.hero-search-input');
    if (searchInput) {
        searchInput.placeholder = 'Search legal news, cases, legislation...';
    }
    
    // Custom table enhancements
    enhanceLegalNewsTables();
});

function enhanceLegalNewsTables() {
    // Your custom table functionality
    const tables = document.querySelectorAll('.table-wrapper table');
    tables.forEach(table => {
        // Add click handlers, formatting, etc.
    });
}
```

### Custom Templates (`templates/`)

🛡️ **SAFETY FIRST**: General template names like `database.html` are **banned** in database customizations to prevent breaking core functionality.

**❌ BANNED Template Names:**
- `database.html` - would break all database pages
- `table.html` - would break all table pages  
- `index.html` - would break homepage
- `query.html` - would break SQL interface
- `row.html` - would break record pages
- `error.html` - would break error handling

**✅ ALLOWED Template Names:**
- `database-YOURDB.html` - Database-specific pages
- `table-YOURDB-TABLENAME.html` - Table-specific pages
- `custom-YOURDB-dashboard.html` - Custom pages
- `_partial-header.html` - Partial templates
- Any name that doesn't conflict with core templates

**Database-Specific Template Examples:**

**`templates/database-legal_news.html`** - Only affects your database
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

**`templates/table-legal_news-headlines.html`** - Only affects specific table
```html
{% extends "default:table.html" %}

{% block content %}
<div class="headlines-header">
    <h1>📋 Legal Headlines Archive</h1>
    <p>Searchable archive of Singapore legal news</p>
</div>

{{ super() }}
{% endblock %}
```

**Why This Is Safer:**
- ✅ No risk of breaking core Datasette functionality
- ✅ Templates only affect your specific database/tables
- ✅ Other databases remain unaffected
- ✅ System remains functional even if your templates have issues
- ✅ Clear separation between base templates and customizations

### Debugging Template Names

Datasette has specific template naming rules. To see which templates it looks for:

1. **View page source** in your browser
2. **Scroll to bottom** and look for a comment like:
   ```html
   <!-- Templates considered: *database-mydb.html, database.html -->
   ```
3. **The `*` shows which template was used**

**For database-specific templates:**
- Database page looks for: `database-YOURDB.html`, then `database.html`
- Table page looks for: `table-YOURDB-TABLENAME.html`, then `table-YOURDB.html`, then `table.html`

**Template Name Sanitization:**
If your database/table names have spaces or special characters, Datasette sanitizes them:
- Database: `Legal News` → `Legal-News-a1b2c3` (with MD5 hash)
- Check page source to see exact names considered

## File Locations After Deployment

Your files get deployed to specific locations:

- **CSS/JS**: `/static/databases/your_database/filename.css`
- **Templates**: Processed by Jinja2 template engine (not directly accessible)
- **Metadata**: Merged into main Datasette configuration

**Static Asset URLs:**
The Zeeker system configures Datasette with `--static static:/app/static`, so your files are accessible at:
- `https://data.zeeker.sg/static/databases/your_database/custom.css`
- `https://data.zeeker.sg/static/databases/your_database/custom.js`

## Testing Your Customizations

### 1. Local Testing with uv

```bash
# Install dependencies
uv sync

# Test the merge locally
uv run scripts/manage.py check-assets --verbose

# See what gets loaded
uv run scripts/manage.py status
```

### 2. Deploy and Check

```bash
# Validate templates before deploying (future feature)
uv run scripts/manage.py validate-templates legal_news

# Upload your customizations to S3
aws s3 sync ./my-customizations/ s3://bucket/assets/databases/my_database/

# Restart the container to apply changes
docker compose restart zeeker-datasette

# Check logs for any template validation messages
docker compose logs -f zeeker-datasette | grep -i template
```

### 3. Verify in Browser

1. Visit your database page: `/your_database`
2. Check browser dev tools for your CSS/JS loading
3. View page source to confirm metadata changes

## Best Practices

### CSS Guidelines

```css
/* ✅ Good: Scope to your database */
.page-database .custom-header { }
.database-card[data-database="your_db"] { }

/* ❌ Avoid: Global changes that affect other databases */
.card { color: red; }  /* This affects ALL databases */
```

### JavaScript Guidelines

```javascript
// ✅ Good: Check if you're on the right database
if (window.location.pathname.includes('/your_database')) {
    // Your custom code
}

// ✅ Good: Defensive programming
const element = document.querySelector('.specific-element');
if (element) {
    // Safe to use element
}

// ❌ Avoid: Assuming elements exist
document.querySelector('.might-not-exist').addEventListener(...);  // Could crash
```

### File Organization

```
assets/databases/your_database/
├── static/
│   ├── custom.css              # Main stylesheet
│   ├── database-specific.js    # Main JavaScript
│   └── images/                 # Database-specific images
│       └── banner.png
├── templates/
│   ├── database-your_database.html    # Safe: database-specific
│   ├── table-your_database-TABLE.html # Safe: table-specific  
│   └── custom-dashboard.html          # Safe: custom name
└── metadata.json               # Database configuration
```

**Template Naming Rules:**
- ✅ `database-DBNAME.html` - Database-specific pages
- ✅ `table-DBNAME-TABLENAME.html` - Table-specific pages
- ✅ `custom-anything.html` - Custom pages
- ❌ `database.html` - BANNED (would break core functionality)
- ❌ `table.html` - BANNED (would break core functionality)

## Troubleshooting

### Assets Not Loading?

```bash
# Check if files exist in S3
aws s3 ls s3://bucket/assets/databases/your_database/ --recursive

# Check container logs
docker compose logs zeeker-datasette | grep "your_database"

# Verify merge process
uv run scripts/manage.py list-databases --verbose
```

### Templates Being Rejected?

**Symptoms:**
- Logs show "BANNED TEMPLATE" errors
- Templates not applying
- Container starts but customizations missing

**Cause:** You used banned general template names

**Fix:**
1. **Rename your templates** to database-specific names:
   ```bash
   # Instead of:
   database.html ❌
   
   # Use:
   database-legal_news.html ✅
   table-legal_news-headlines.html ✅
   custom-legal_news-dashboard.html ✅
   ```

2. **Re-upload to S3** with correct names
3. **Restart container**: `docker compose restart zeeker-datasette`

**Template Validation:**
The system automatically blocks dangerous template names to protect core functionality. This prevents accidentally breaking the entire site.

### Metadata Not Merging?

1. **Validate JSON syntax**: `cat metadata.json | python -m json.tool`
2. **Use complete structure**: Must be a valid Datasette metadata.json, not fragments
3. **Check container logs** for merge errors: `docker compose logs zeeker-datasette | grep metadata`
4. **Verify paths match**: Database folder name must match .db filename exactly

## Advanced Tips

### Datasette-Specific Features

**CSS Body Classes:**
Datasette automatically adds CSS classes to the `<body>` tag:
```css
/* Target specific databases */
body.db-your_database .card { }

/* Target specific tables */  
body.table-your_database-your_table .row { }

/* Target specific columns */
.col-column_name { }
```

**Template Variables:**
All Datasette templates have access to standard variables:
- `{{ database }}` - Current database name
- `{{ table }}` - Current table name  
- `{{ row }}` - Current row data
- `{{ request }}` - Request object
- `{{ datasette }}` - Datasette instance

To see which templates Datasette considered for any page:

1. View page source in your browser
2. Scroll to the bottom and look for a comment like:
   ```html
   <!-- Templates considered: *database-mydb.html, database.html -->
   ```
3. The `*` shows which template was actually used

This is invaluable for debugging template naming issues.

### Conditional Styling

```css
/* Different styles based on database */
[data-database="legal_news"] .card {
    border-color: #e74c3c;
}

[data-database="court_cases"] .card {
    border-color: #3498db;
}
```

### Template Inheritance

```html
<!-- Extend base but customize specific sections -->
{% extends "default:database.html" %}

{% block nav %}
{% include "_header.html" %}
<div class="custom-nav">
    <!-- Your database-specific navigation -->
</div>
{% endblock %}
```

### JavaScript Modules

```javascript
// static/modules/legal-search.js
export function enhanceLegalSearch() {
    // Reusable search enhancements
}

// static/database-main.js
import { enhanceLegalSearch } from './modules/legal-search.js';

document.addEventListener('DOMContentLoaded', () => {
    enhanceLegalSearch();
});
```

## Need Help?

1. **Check the code**: Look at existing base templates in `templates/`
2. **Test locally**: Use `uv run scripts/manage.py` commands
3. **Ask for help**: Email with your specific use case

The system is designed to be forgiving - if your customizations have errors, the base assets will still work.