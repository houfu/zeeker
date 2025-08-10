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
- `uv run zeeker add RESOURCE_NAME --fragments` - Add resource with fragments support for large documents
- `uv run zeeker build` - Build SQLite database from resources
- `uv run zeeker build --sync-from-s3` - Build database with S3 sync (download existing DB first)
- `uv run zeeker build --force-schema-reset` - Build ignoring schema conflicts
- `uv run zeeker deploy` - Deploy database to S3
- `uv run zeeker assets generate DATABASE_NAME OUTPUT_PATH` - Generate UI customization assets
- `uv run zeeker assets validate ASSETS_PATH DATABASE_NAME` - Validate UI assets
- `uv run zeeker assets deploy LOCAL_PATH DATABASE_NAME` - Deploy UI assets to S3

## Architecture Overview

### Core Structure
Zeeker is a Python CLI tool for creating and managing databases with UI customizations for Datasette:

- **zeeker/cli.py**: Main CLI interface using Click framework
- **zeeker/core/**: Core functionality modules (refactored for clean separation of concerns)
  - **project.py**: High-level project management operations
  - **database.py**: Database building with S3 sync capabilities using sqlite-utils
  - **schema.py**: Schema versioning, conflict detection, and meta table management
  - **templates.py**: Jinja2 template generation with fallback support
  - **scaffolding.py**: Project initialization and file structure creation
  - **resources.py**: Resource management and configuration
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

#### Document Fragments System
For handling large documents (legal docs, research papers, etc.), Zeeker supports automatic fragmentation:
1. **Main Table**: Document metadata (title, source, type, dates)
2. **Fragments Table**: Searchable text chunks with position tracking
3. **Smart Splitting**: Intelligent boundary detection at sentence/paragraph breaks
4. **Relationship Maintenance**: Foreign key links between documents and fragments

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
4. `build --sync-from-s3` downloads existing database from S3 before building (enables incremental updates across machines)
5. `deploy` uploads database to S3 `latest/` directory

#### S3 Database Synchronization
The `--sync-from-s3` flag enables multi-machine workflows by:
- Downloading existing database from S3 `latest/{database_name}.db` before building
- Allowing `fetch_data(existing_table)` functions to check for existing data
- Enabling incremental updates without duplicating data
- Gracefully handling missing S3 databases (continues with local build)

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

#### Fragment-Enabled Resources
Resources created with `--fragments` implement additional functions:
- `fetch_fragments_data(existing_fragments_table)` - Returns fragment records
- `transform_fragments_data()` - Optional fragment transformation
- `split_text_into_fragments()` - Helper function for intelligent text splitting

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

### Document Fragments Feature

Zeeker provides built-in support for handling large documents through automatic fragmentation. This is perfect for legal documents, research papers, contracts, or any large text content that needs to be split into searchable chunks while maintaining relationships.

#### When to Use Fragments

Use the `--fragments` flag when adding resources that contain:
- Legal documents (contracts, regulations, case law)
- Research papers and academic content
- Long-form articles or documentation
- Any text content > 1000 characters that benefits from full-text search

#### Creating Fragment-Enabled Resources

```bash
# Add resource with fragments support
zeeker add legal_docs --fragments --description "Legal documents with searchable fragments"

# This creates resources/legal_docs.py with fragment-specific template
```

#### Database Schema

Fragment-enabled resources create **two tables automatically**:

**Main Table** (`resource_name`):
- Schema is completely determined by your `fetch_data()` function
- You have full control over field names, types, and structure
- Common patterns: metadata-focused, simple content, or hybrid approaches

**Fragments Table** (`resource_name_fragments`):
- Schema is completely determined by your `fetch_fragments_data()` function  
- You choose how to link fragments to main records
- You decide fragment content structure and metadata

**Example Schemas** (not requirements):
```sql
-- Example 1: Simple approach
documents (id, title, source)
documents_fragments (parent_id, text)

-- Example 2: Legal documents
legal_docs (id, case_name, court, date, metadata)
legal_docs_fragments (doc_id, section_type, content, page_num)

-- Example 3: Research papers
papers (id, title, authors, abstract, publication_date) 
papers_fragments (paper_id, fragment_type, text, position, keywords)
```

#### Generated Template Functions

Fragment-enabled resources include these functions:

**1. `fetch_data(existing_table)`** - Main table data
```python
def fetch_data(existing_table):
    """Define your main table schema through returned data."""
    return [
        {
            # You design this schema - common patterns:
            "id": 1,
            "title": "Your Document Title", 
            "source": "document.pdf",
            "date": "2024-01-15"
            # Add whatever fields your project needs
        }
    ]
```

**2. `fetch_fragments_data(existing_fragments_table, main_data_context=None)`** - Fragment table data
```python  
def fetch_fragments_data(existing_fragments_table, main_data_context=None):
    """Define your fragments schema and splitting logic."""
    
    # ENHANCED: Use main_data_context to avoid duplicate API calls
    if main_data_context:
        # Use data already fetched in fetch_data() - no duplicate expensive calls!
        fragments = []
        for main_record in main_data_context:
            doc_content = main_record.get('content', '')
            doc_id = main_record.get('id')
            
            # Split content into fragments
            for i, chunk in enumerate(split_document(doc_content)):
                fragments.append({
                    "parent_id": doc_id,           # Link to main table
                    "fragment_num": i,             # Your ordering
                    "text": chunk,                 # Your content field
                    "char_count": len(chunk)       # Your metadata
                })
        return fragments
    
    # FALLBACK: Independent data fetch (backward compatibility)
    return [
        {
            # You design this schema - examples:
            "parent_id": 1,                    # Your choice of linking field
            "text": "Fragment content...",     # Your choice of content field  
            "section": "introduction"          # Any additional fields you need
            # Complete freedom over structure
        }
    ]
```

**Helper Functions** - You can add any functions your project needs:
- Text splitting utilities
- Document parsing functions  
- Data validation functions
- API client functions

#### Build Process with Fragments

When you run `zeeker build`:

1. **Main Table**: `fetch_data()` creates table with your chosen schema
2. **Context Passing**: Raw data from `fetch_data()` is automatically passed to `fetch_fragments_data()` as `main_data_context`
3. **Fragments Table**: `fetch_fragments_data()` creates fragments table with your chosen schema  
4. **Schema Detection**: Both tables get automatic schema inference from your data
5. **Meta Tables**: Schema tracking for both tables in `_zeeker_schemas` and `_zeeker_updates`

#### Performance Benefits of Context Passing

**New Enhanced System (Recommended):**
```python
def fetch_data(existing_table):
    expensive_documents = expensive_api_call()  # Called ONCE
    return [process_for_main_table(doc) for doc in expensive_documents]

def fetch_fragments_data(existing_fragments_table, main_data_context=None):
    if main_data_context:
        # Use already-fetched data - NO duplicate API call!
        return [create_fragments(record) for record in main_data_context]
    # Fallback for backward compatibility
```

**Benefits:**
- ✅ **Eliminate Duplicate API Calls**: Single expensive fetch instead of two
- ✅ **Faster Builds**: Especially important for large datasets or slow APIs
- ✅ **Data Consistency**: Both tables see identical data snapshot
- ✅ **Rate Limit Friendly**: Avoid hitting API rate limits
- ✅ **Backward Compatible**: Existing resources continue working unchanged

#### Best Practices for Fragments

**✅ DO:**
- Use fragments for large documents that benefit from chunking
- Design schemas that fit your specific use case
- Include some way to link fragments back to main records
- Consider what granularity makes sense for your search needs
- Use consistent data types within each table

**❌ DON'T:**
- Use fragments for simple short text content
- Feel constrained by any particular schema pattern
- Duplicate large amounts of data between tables unnecessarily  
- Make fragments too granular (single words) or too coarse (entire documents)

#### Datasette Search Integration

Fragment tables work perfectly with Datasette's full-text search:

```sql
-- Example queries (adjust field names to match your schema):

-- Search across fragments with main table context  
SELECT d.title, f.text 
FROM documents d
JOIN documents_fragments f ON d.id = f.parent_id
WHERE f.text MATCH 'search terms';

-- Search with your specific field names
SELECT * FROM your_fragments_table 
WHERE your_content_field MATCH 'search terms';
```

#### Fragment Processing Examples

**Example 1: Legal Document Chunks**
```python
def fetch_fragments_data(existing_fragments_table):
    fragments = []
    for doc_id, full_text in get_legal_documents():
        # Split by paragraphs for legal documents
        paragraphs = full_text.split('\n\n')
        for i, para in enumerate(paragraphs):
            if para.strip():
                fragments.append({
                    'case_id': doc_id,           # Your linking field
                    'paragraph_num': i,          # Your ordering field
                    'text': para.strip(),        # Your content field
                    'section_type': detect_section(para)  # Your metadata
                })
    return fragments
```

**Example 2: Research Paper Sections**  
```python
def fetch_fragments_data(existing_fragments_table):
    fragments = []
    for paper_id, sections in parse_research_papers():
        for section_name, content in sections.items():
            fragments.append({
                'paper_id': paper_id,        # Your linking approach
                'section': section_name,     # Your organization 
                'content': content,          # Your content field
                'word_count': len(content.split())  # Your metadata
            })
    return fragments
```

#### Migration from Regular Resources

To convert existing resources to use fragments:

1. **Add fragments flag**: Update `zeeker.toml`: `fragments = true`
2. **Split fetch_data()**: Move text content to `fetch_fragments_data()`
3. **Update schema**: Adjust main table to metadata-only
4. **Rebuild**: Run `zeeker build` to create fragments table

### Environment Variables
Required for S3 deployment and sync:
- `S3_BUCKET` - S3 bucket name
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key  
- `S3_ENDPOINT_URL` - Optional S3 endpoint URL

Note: The same AWS credentials used for `zeeker deploy` are used for `--sync-from-s3`

### Testing Strategy
Tests are organized by markers:
- `unit` - Individual component tests
- `integration` - Component interaction tests
- `cli` - CLI interface tests
- `slow` - Long-running tests

Test files follow pytest conventions in `tests/` directory with comprehensive fixtures in `conftest.py`.

**Fragment Testing:**
- `tests/test_fragments.py` - Comprehensive fragments feature testing
- Tests cover CLI flag, template generation, database building, and error handling
- Integration tests validate both main and fragments table creation