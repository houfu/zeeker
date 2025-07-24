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
3. `build` executes `fetch_data()` functions and builds SQLite database
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
│   └── resource_name.py     # Implements fetch_data() function
├── project_name.db          # Generated SQLite database (gitignored)
├── metadata.json            # Generated Datasette metadata
└── README.md                # Auto-generated documentation
```

#### Resource Modules
Each resource must implement:
- `fetch_data()` - Returns List[Dict[str, Any]] for database insertion
- `transform_data()` - Optional data transformation function

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