# CLAUDE.md - Test_Fts_Project Project Development Guide

This file provides Claude Code with project-specific context and guidance for developing this project.

## Project Overview

**Project Name:** test_fts_project
**Database:** test_fts_project.db
**Purpose:** Database project for test_fts_project data management

## Development Environment

This project uses **uv** for dependency management with an isolated virtual environment:

- `pyproject.toml` - Project dependencies and metadata
- `.venv/` - Isolated virtual environment (auto-created)
- All commands should be run with `uv run` prefix

### Dependency Management
- **Add dependencies:** `uv add package_name` (e.g., `uv add requests pandas`)
- **Install dependencies:** `uv sync` (automatically creates .venv if needed)
- **Common packages:** requests, beautifulsoup4, pandas, lxml, pdfplumber, openpyxl

### Environment Variables
Zeeker automatically loads `.env` files when running build, deploy, and asset commands:

- **Create `.env` file:** Store sensitive credentials and configuration
- **Auto-loaded:** Environment variables are available in your resources during `zeeker build`
- **S3 deployment:** Required for `zeeker deploy` and `zeeker assets deploy`

**Example `.env` file:**
```
# S3 deployment credentials
S3_BUCKET=my-datasette-bucket
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_ENDPOINT_URL=https://s3.amazonaws.com

# API keys for data resources
JINA_API_TOKEN=your_jina_token
OPENAI_API_KEY=your_openai_key
```

**Usage in resources:**
```python
import os

def fetch_data(existing_table):
    api_key = os.getenv("MY_API_KEY")  # Loaded from .env automatically
    # ... rest of your code
```

## Development Commands

### Quick Commands
- `uv run zeeker add RESOURCE_NAME` - Add new resource to this project
- `uv run zeeker add RESOURCE_NAME --fragments` - Add resource with document fragments support
- `uv run zeeker build` - Build database from all resources in this project
- `uv run zeeker deploy` - Deploy this project's database to S3

### Code Formatting
- `uv run black .` - Format code with black
- `uv run ruff check .` - Lint code with ruff
- `uv run ruff check --fix .` - Auto-fix ruff issues

### Testing This Project
- `uv run pytest` - Run tests (if added to project)
- Check generated `test_fts_project.db` after build
- Verify metadata.json structure

### Working with Dependencies
When implementing resources that need external libraries:
1. **First add the dependency:** `uv add library_name`
2. **Then use in your resource:** `import library_name` in `resources/resource_name.py`
3. **Build works automatically:** `uv run zeeker build` uses the isolated environment

## Resources in This Project

### `searchable_docs` Resource
- **Description:** Searchable documents
- **File:** `resources/searchable_docs.py`
- **Type:** Fragment-enabled (creates two tables: `searchable_docs` and `searchable_docs_fragments`)
- **Schema:** Check `resources/searchable_docs.py` both fetch_data() and fetch_fragments_data() functions

### `documents` Resource
- **Description:** Documents with auto-searchable fragments
- **File:** `resources/documents.py`
- **Type:** Fragment-enabled (creates two tables: `documents` and `documents_fragments`)
- **Schema:** Check `resources/documents.py` both fetch_data() and fetch_fragments_data() functions


## Schema Notes for This Project

### Important Schema Decisions
- Document any project-specific schema choices here
- Note field types that are critical for this project's data
- Record any special data handling requirements

### Common Schema Issues to Watch
- **Dates:** Use ISO format strings like "2024-01-15"
- **Numbers:** Use float for prices/scores that might have decimals
- **IDs:** Use int for primary keys, str for external system IDs
- **JSON data:** Use dict/list types for complex data structures

### Fragment Resources
If using fragment-enabled resources (created with `--fragments`):
- **Two Tables:** Each fragment resource creates a main table and a `_fragments` table
- **Schema Freedom:** You design both table schemas through your `fetch_data()` and `fetch_fragments_data()` functions
- **Linking:** Include some way to link fragments back to main records (your choice of field names)
- **Use Cases:** Large documents, legal texts, research papers, or any content that benefits from searchable chunks

## Project-Specific Notes

### Data Sources
- Document where this project's data comes from
- Note any API endpoints, file formats, or data constraints
- Record update frequencies and data refresh patterns

### Business Logic
- Document any special business rules for this project
- Note relationships between resources
- Record any data validation requirements

### Deployment Notes
- Any special S3 configuration for this project
- Environment variables specific to this project
- Deployment schedules or constraints

## Team Notes

*Use this section for team-specific development notes, decisions, or reminders*

---

This file is automatically created by Zeeker and can be customized for your project's needs.
The main Zeeker development guide is in the repository root CLAUDE.md file.
