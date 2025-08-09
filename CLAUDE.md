# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
- `uv run pytest` - Run all tests
- `uv run pytest -m unit` - Run unit tests only  
- `uv run pytest -m integration` - Run integration tests only
- `uv run pytest -m cli` - Run CLI tests only
- `uv run pytest --cov=zeeker` - Run tests with coverage
- `uv run pytest tests/test_project.py` - Run specific test file
- `uv run pytest tests/test_validator.py::TestTemplateValidation::test_banned_templates_rejected` - Run specific test

### Code Formatting
- `uv run black .` - Format code following black style (line length: 100)

### Development Setup
- `uv sync` - Install dependencies
- `uv sync --group dev` - Install with development dependencies
- `uv pip install -e .` - Install in development mode

### Project Commands (for testing/development)
- `uv run zeeker init PROJECT_NAME` - Initialize new database project
- `uv run zeeker add RESOURCE_NAME` - Add data resource to project
- `uv run zeeker build` - Build SQLite database from resources
- `uv run zeeker deploy` - Deploy database to S3
- `uv run zeeker assets generate DATABASE_NAME OUTPUT_PATH` - Generate UI customization assets
- `uv run zeeker assets validate ASSETS_PATH DATABASE_NAME` - Validate UI assets
- `uv run zeeker assets deploy LOCAL_PATH DATABASE_NAME` - Deploy UI assets to S3

## Architecture Overview

### Core Structure
Zeeker is a Python CLI tool for creating and managing databases with UI customizations for Datasette:

- **zeeker/cli.py**: Main CLI interface using Click framework
- **zeeker/core/**: Core functionality modules
  - **project.py**: Project management and database building using sqlite-utils
  - **validator.py**: Asset validation against safety rules
  - **generator.py**: UI asset generation (templates, CSS, JS)
  - **deployer.py**: S3 deployment functionality
  - **types.py**: Data structures and validation results

### Key Design Patterns

#### Two-Workflow System
1. **Database Projects**: Complete database management (init → add → build → deploy)
2. **UI Customizations**: Asset generation and deployment for database-specific styling

#### Three-Pass Asset System
S3 deployment follows a three-pass structure:
1. Pass 1: Database files (`latest/*.db`)
2. Pass 2: Base assets (`assets/default/`)
3. Pass 3: Database-specific customizations (`assets/databases/{db_name}/`)

#### sqlite-utils Integration
Uses Simon Willison's sqlite-utils for robust database operations:
- Automatic table creation with schema detection
- Type inference from data (INTEGER, TEXT, REAL, JSON)
- Safe data insertion without SQL injection risks
- JSON support for complex data structures

### Safety Features

#### Template Validation
The validator prevents dangerous template names that would break core Datasette functionality:
- **Banned**: `database.html`, `table.html`, `index.html`, `query.html`
- **Safe patterns**: `database-{DBNAME}.html`, `table-{DBNAME}-{TABLE}.html`, `custom-*.html`

#### CSS/JS Scoping
Generated assets are automatically scoped to prevent conflicts:
```css
[data-database="database_name"] .custom-style { /* styles */ }
```

### Data Flow

#### Database Project Flow
1. `init` creates project structure with `zeeker.toml`
2. `add` creates resource Python modules in `resources/`
3. `build` executes `fetch_data(existing_table)` functions and builds SQLite database
4. `deploy` uploads database to S3 `latest/` directory

#### UI Customization Flow
1. `assets generate` creates templates, CSS, JS with safe naming
2. `assets validate` checks against banned patterns and structure
3. `assets deploy` uploads to S3 `assets/databases/{db_name}/` directory

### Project Structure Conventions

#### Database Projects
```
project/
├── zeeker.toml              # Project configuration
├── resources/               # Python modules for data fetching
│   ├── __init__.py
│   └── resource_name.py     # Implements fetch_data(existing_table) function
├── project_name.db          # Generated SQLite database (gitignored)
├── metadata.json            # Generated Datasette metadata
└── README.md                # Auto-generated documentation
```

#### Resource Modules
Each resource must implement:
- `fetch_data(existing_table)` - Returns List[Dict[str, Any]] for database insertion
  - `existing_table`: sqlite-utils Table object if table exists, None for new table
  - Use this to check existing data and avoid duplicates
- `transform_data()` - Optional data transformation function

### Database Schema Management

#### Automated Meta Tables System
Zeeker automatically creates and maintains two meta tables for every project:

**`_zeeker_schemas` - Schema Version Tracking:**
- Tracks schema versions, hashes, and column definitions for each resource
- Automatically detects when schemas change between builds
- Provides audit trail for schema evolution

**`_zeeker_updates` - Update Timestamps:**
- Records last update time for each resource table
- Tracks record counts and build performance metrics  
- Helps identify stale data and monitor data freshness

These tables are created automatically during `zeeker build` with zero configuration required.

#### Schema Conflict Detection & Migration
Zeeker now automatically detects schema changes and provides safe migration options:

**Automatic Detection:**
- Compares schema hashes to detect changes
- Fails safe by default to prevent data corruption
- Provides clear error messages with resolution options

**Schema Conflicts - Three Resolution Options:**

1. **Add Migration Function (Recommended):**
```python
# In your resource file (e.g., resources/users.py)
def fetch_data(existing_table):
    return [{"id": 1, "name": "Alice", "age": 25}]  # Added 'age' field

def migrate_schema(existing_table, new_schema_info):
    """Handle schema changes safely."""
    # Add the new column with default values
    existing_table.add_column('age', int, fk=None)
    
    # Update existing records with default age
    for row_id in existing_table.pks:
        existing_table.update(row_id, {'age': 25})
    
    return True  # Migration successful
```

2. **Force Schema Reset:**
```bash
# Ignore conflicts and rebuild (development use)
zeeker build --force-schema-reset
```

3. **Manual Cleanup:**
```bash
# Delete database and rebuild from scratch
rm project_name.db
zeeker build
```

#### Important: Schema Lock-In Behavior
**Your first `fetch_data()` call permanently determines column types.** Once a table is created, column types cannot be changed, only new columns can be added.

#### How Type Inference Works
- sqlite-utils examines the first ~100 records from your data
- Python types are mapped to SQLite column types automatically
- Schema is locked after first table creation
- Schema version increments when structure changes

#### Python Type → SQLite Type Mapping
```python
# Type mapping examples:
{
    "id": 1,                    # int → INTEGER
    "price": 19.99,             # float → REAL  
    "name": "Product",          # str → TEXT
    "active": True,             # bool → INTEGER (0/1)
    "tags": ["red", "sale"],    # list → TEXT (JSON)
    "meta": {"size": "large"}   # dict → TEXT (JSON)  
}
```

#### Schema Best Practices

**✅ DO:**
- Use correct Python types in your first data batch
- Use `float` for any numeric data that might have decimals later
- Provide consistent data types across all records
- Use ISO date strings for dates: `"2024-01-15"`
- Test your first batch carefully before deployment
- Add `migrate_schema()` functions when changing schemas

**❌ DON'T:**
- Mix types in the same field (e.g., sometimes int, sometimes string)
- Use `None` values in key columns on first run (causes inference issues)
- Assume you can change column types later
- Use integers for data that might become floats (prices, scores, etc.)
- Ignore schema conflict errors (they prevent data corruption)

#### Common Schema Issues

**Problem: Price stored as INTEGER instead of REAL**
```python
# BAD - First batch uses integers
[{"price": 20}, {"price": 15}]  # price → INTEGER

# Later batches with decimals get truncated:
[{"price": 19.99}]  # Stored as 19 (loses decimal!)
```

**Solution: Use floats from the start**
```python
# GOOD - First batch uses floats
[{"price": 20.0}, {"price": 15.0}]  # price → REAL
```

**Problem: Mixed data types**
```python
# BAD - Inconsistent types
[{"id": 1}, {"id": "abc"}]  # Causes type confusion
```

**Solution: Consistent types**
```python  
# GOOD - All IDs are integers
[{"id": 1}, {"id": 2}]  # id → INTEGER
```

#### Schema Debugging with Meta Tables
1. **Check Schema Versions:** Query `_zeeker_schemas` table to see schema evolution
2. **Monitor Data Freshness:** Query `_zeeker_updates` table for last update times
3. **Compare Environments:** Use schema hashes to detect differences between deployments
4. **Track Performance:** Review build duration and record counts over time
5. **Debug Schema Conflicts:** Error messages show exactly what changed

### Environment Variables
Required for S3 deployment:
- `S3_BUCKET` - S3 bucket name
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key  
- `S3_ENDPOINT_URL` - Optional S3 endpoint URL

### Testing Strategy
Tests are organized by markers:
- `unit` - Individual component tests
- `integration` - Component interaction tests
- `cli` - CLI interface tests
- `slow` - Long-running tests

Test files follow pytest conventions in `tests/` directory with comprehensive fixtures in `conftest.py`.
- update documentation after this commit