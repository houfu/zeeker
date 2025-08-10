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
- `uv run zeeker add RESOURCE_NAME --async` - Add resource with async/await support for concurrent data fetching
- `uv run zeeker add RESOURCE_NAME --fragments --async` - Add resource with both fragments and async support
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
1. `init` creates project structure with `pyproject.toml`, `zeeker.toml`, and automated virtual environment setup
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
├── pyproject.toml           # Project dependencies and metadata (PEP 621 compliant)
├── zeeker.toml              # Project configuration
├── resources/               # Python modules for data fetching
│   ├── __init__.py
│   └── resource_name.py     # Implements fetch_data(existing_table) function
├── .venv/                   # Isolated virtual environment (gitignored)
├── project_name.db          # Generated SQLite database (gitignored)
├── metadata.json            # Generated Datasette metadata
├── CLAUDE.md                # Project-specific development guide
└── README.md                # Auto-generated documentation
```

#### Resource Modules
Each resource must implement either sync or async functions:

**Synchronous Resources:**
- `fetch_data(existing_table)` - Returns List[Dict[str, Any]] for database insertion
  - `existing_table`: sqlite-utils Table object if table exists, None for new table
  - Use this to check existing data and avoid duplicates
- `transform_data()` - Optional data transformation function

**Asynchronous Resources:**
- `async def fetch_data(existing_table)` - Returns List[Dict[str, Any]] for database insertion
  - Same parameters and behavior as sync version
  - Use for concurrent API calls, async file I/O, or database operations
- `async def transform_data()` - Optional async data transformation function

#### Fragment-Enabled Resources
Resources created with `--fragments` implement additional functions:

**Synchronous Fragments:**
- `fetch_fragments_data(existing_fragments_table, main_data_context=None)` - Returns fragment records
- `transform_fragments_data()` - Optional fragment transformation

**Asynchronous Fragments:**
- `async def fetch_fragments_data(existing_fragments_table, main_data_context=None)` - Returns fragment records
- `async def transform_fragments_data()` - Optional async fragment transformation

### Asynchronous Resource Development

Zeeker supports both synchronous and asynchronous resource functions with automatic detection and execution.

#### When to Use Async Resources

Use async resources (`--async` flag) when your data fetching involves:
- **External API calls** - Multiple concurrent HTTP requests
- **Database connections** - Async database drivers (asyncpg, aiomysql, motor)
- **File I/O operations** - Reading many files concurrently
- **Web scraping** - Concurrent page fetching with aiohttp
- **Processing pipelines** - CPU-intensive tasks with asyncio

#### Creating Async Resources

```bash
# Standard async resource
zeeker add api_data --async --description "Concurrent API data fetching"

# Async resource with fragments
zeeker add documents --fragments --async --description "Async document processing with fragments"
```

#### Async Resource Examples

**Basic Async Resource:**
```python
import asyncio
import aiohttp
from sqlite_utils.db import Table, NotFoundError
from typing import Optional, List, Dict, Any

async def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """Async data fetching with concurrent API calls."""
    
    if existing_table:
        # Access metadata for incremental updates
        db = existing_table.db
        if "_zeeker_updates" in db.table_names():
            updates_table = db["_zeeker_updates"]
            try:
                metadata = updates_table.get(existing_table.name)
                last_updated = metadata["last_updated"]
                print(f"Last updated: {last_updated}")
            except NotFoundError:
                print("No metadata found - first run")
    
    # Concurrent API calls
    async with aiohttp.ClientSession() as session:
        urls = [
            "https://api.example.com/users",
            "https://api.example.com/posts",
            "https://api.example.com/comments"
        ]
        
        # Fetch all URLs concurrently
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        # Combine and process results
        all_data = []
        for result in results:
            all_data.extend(result)
        
        return all_data

async def fetch_url(session: aiohttp.ClientSession, url: str) -> List[Dict[str, Any]]:
    """Helper function for individual API calls."""
    async with session.get(url) as response:
        if response.status == 200:
            data = await response.json()
            return data.get('items', [])
        return []
```

**Async Fragments Resource:**
```python
import asyncio
import aiohttp
from sqlite_utils.db import Table, NotFoundError
from typing import Optional, List, Dict, Any

async def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """Async fetch documents for main table."""
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.example.com/documents") as response:
            documents = await response.json()
            return [
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "source": "api",
                    "created_date": doc.get("created", "2024-01-01"),
                }
                for doc in documents
            ]

async def fetch_fragments_data(
    existing_fragments_table: Optional[Table], 
    main_data_context: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """Async fragments processing with AI-based chunking."""
    
    if main_data_context:
        fragments = []
        
        # Process documents concurrently
        tasks = [
            process_document_async(doc) 
            for doc in main_data_context
        ]
        document_fragments = await asyncio.gather(*tasks)
        
        # Flatten results
        for doc_fragments in document_fragments:
            fragments.extend(doc_fragments)
        
        return fragments
    
    return []

async def process_document_async(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process a single document into fragments."""
    doc_id = doc.get("id")
    content = doc.get("content", "")
    
    # Simulate AI-based chunking (could be OpenAI, Anthropic, etc.)
    chunks = await ai_chunk_text(content)
    
    return [
        {
            "parent_id": doc_id,
            "fragment_num": i,
            "text": chunk,
            "char_count": len(chunk),
            "processing_time": "async"
        }
        for i, chunk in enumerate(chunks)
    ]

async def ai_chunk_text(content: str) -> List[str]:
    """Example async AI-based text chunking."""
    await asyncio.sleep(0.1)  # Simulate API call
    # Simple chunking for example - replace with actual AI service
    return [content[i:i+500] for i in range(0, len(content), 500)]
```

#### Performance Benefits

**Concurrent Processing:**
- **Sync**: Process 100 API calls sequentially = ~100 seconds
- **Async**: Process 100 API calls concurrently = ~5-10 seconds

**Resource Efficiency:**
- Single thread handling multiple I/O operations
- Better memory usage than thread-based concurrency
- Scales well for I/O-bound operations

#### Async + Fragments = Powerful Combination

Async fragments are perfect for:
- **Legal document processing** with AI-based chunking
- **Research paper analysis** with concurrent API calls for metadata
- **Web scraping** with parallel page processing
- **Large file processing** with concurrent text analysis

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

#### Accessing Metadata in Resources

You can access metadata tables within your `fetch_data()` function to implement incremental updates:

```python
from sqlite_utils.db import Table
from sqlite_utils import NotFoundError
from typing import Optional, List, Dict, Any

def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    if existing_table:
        db = existing_table.db
        
        # Access the _zeeker_updates table
        if "_zeeker_updates" in db.table_names():
            updates_table = db["_zeeker_updates"]
            
            try:
                # Get metadata for this table (returns Dict[str, Any])
                metadata = updates_table.get(existing_table.name)
                
                last_updated: str = metadata["last_updated"]    # ISO datetime string
                record_count: int = metadata["record_count"]    # Current row count
                build_id: str = metadata["build_id"]            # Build identifier
                duration_ms: int = metadata["duration_ms"]      # Last build time
                
                print(f"Last updated: {last_updated}")
                print(f"Current records: {record_count}")
                
                # Use for incremental updates
                # Example: fetch only data newer than last_updated
                
            except NotFoundError:
                print("No metadata found - first run")
        
        # Access other tables in the database
        if "other_resource" in db.table_names():
            other_table = db["other_resource"]
            # Query other tables as needed
    
    return your_data
```

**Metadata Table Schema:**
- `resource_name` (str): Table name (primary key)
- `last_updated` (str): ISO datetime string of last update
- `record_count` (int): Number of records in table
- `build_id` (str): Unique build identifier
- `duration_ms` (int): Build duration in milliseconds

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

## Common Code Recipes

### Web Content Extraction with Jina Reader

For extracting clean text content from web pages or documents, use the Jina Reader API:

```python
import os
import httpx
import click
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=1, max=10))
async def get_jina_reader_content(link: str) -> str:
    """Fetch content from the Jina reader link."""
    jina_token = os.environ.get("JINA_API_TOKEN")
    if not jina_token:
        click.echo("JINA_API_TOKEN environment variable not set", err=True)
        return ""
    jina_link = f"https://r.jina.ai/{link}"
    headers = {
        "Authorization": f"Bearer {jina_token}",
        "X-Retain-Images": "none",
        "X-Target-Selector": "article",
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.get(jina_link, headers=headers)
        return r.text
    except httpx.RequestError as e:
        click.echo(f"Error fetching content from Jina reader: {e}", err=True)
        return ""
```

**Usage in async resources:**
```python
async def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """Fetch articles using Jina Reader for clean text extraction."""
    
    urls = [
        "https://example.com/article1",
        "https://example.com/article2", 
        "https://example.com/article3"
    ]
    
    articles = []
    for url in urls:
        content = await get_jina_reader_content(url)
        if content:
            articles.append({
                "url": url,
                "title": content.split('\n')[0][:200],  # First line as title
                "content": content,
                "extracted_at": datetime.now().isoformat()
            })
    
    return articles
```

**Required dependencies:**
```bash
uv add httpx tenacity click
```

**Environment setup:**
```bash
export JINA_API_TOKEN="your_jina_api_token"
```

This recipe provides:
- **Retry logic** with exponential backoff for reliable fetching
- **Clean text extraction** without ads, navigation, or formatting
- **Article-focused content** using X-Target-Selector
- **Error handling** with user-friendly messages
- **Async/await support** for concurrent processing

### Hash ID Generation for Primary Keys

For creating deterministic, unique identifiers from multiple data elements:

```python
def get_hash_id(elements: list[str], delimiter: str = "|") -> str:
    """Generate a hash ID from a list of strings.

    Args:
        elements: List of strings to be hashed.
        delimiter: String used to join elements (default: "|").

    Returns:
        A hexadecimal MD5 hash of the joined elements.

    Examples:
        >>> get_hash_id(["2025-05-16", "Meeting Notes"])
        '1a2b3c4d5e6f7g8h9i0j'

        >>> get_hash_id(["user123", "login", "192.168.1.1"], delimiter=":")
        '7h8i9j0k1l2m3n4o5p6q'
    """
    import hashlib

    if not elements:
        raise ValueError("At least one element is required")

    joined_string = delimiter.join(str(element) for element in elements)
    return hashlib.md5(joined_string.encode()).hexdigest()
```

**Usage in resources:**
```python
def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """Fetch data with hash-based primary keys."""
    
    raw_data = [
        {"date": "2025-05-16", "title": "Meeting Notes", "content": "..."},
        {"date": "2025-05-17", "title": "Project Update", "content": "..."},
    ]
    
    records = []
    for item in raw_data:
        # Create deterministic hash ID from key fields
        hash_id = get_hash_id([item["date"], item["title"]])
        
        records.append({
            "id": hash_id,
            "date": item["date"], 
            "title": item["title"],
            "content": item["content"],
            "created_at": datetime.now().isoformat()
        })
    
    return records
```

**Use cases:**
- **Deterministic IDs** - Same input always generates same hash
- **Composite keys** - Hash multiple fields into single primary key
- **Distributed systems** - No auto-increment conflicts across machines
- **Data deduplication** - Easily detect duplicate records
- **Foreign key relationships** - Predictable IDs for linking tables

**Best practices:**
- Include all fields that make a record unique
- Use consistent field ordering for reproducible hashes
- Consider date/time precision (day vs. hour vs. minute)
- Hash stable identifiers, not volatile data like timestamps

**Example with fragments:**
```python
def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    return [{
        "id": get_hash_id(["doc1", "2025-05-16"]),
        "title": "Document 1",
        "source": "example.com"
    }]

def fetch_fragments_data(existing_fragments_table: Optional[Table], main_data_context=None) -> List[Dict[str, Any]]:
    if main_data_context:
        fragments = []
        for doc in main_data_context:
            for i, chunk in enumerate(split_text(doc["content"])):
                fragments.append({
                    "id": get_hash_id([doc["id"], str(i)]),  # Fragment hash ID
                    "parent_id": doc["id"],                   # Main table hash ID
                    "fragment_num": i,
                    "text": chunk
                })
        return fragments
```

### AI-Powered Text Summarization

For generating concise summaries of long-form content using OpenAI:

```python
import os
import click
from openai import AsyncOpenAI

SYSTEM_PROMPT_TEXT = """
As an expert in legal affairs, your task is to provide summaries of legal news articles for time-constrained attorneys in an engaging, conversational style. These summaries should highlight the critical legal aspects, relevant precedents, and implications of the issues discussed in the articles. The summary should be in 1 narrative paragraph and should not be longer than 100 words, but ensure they efficiently deliver the key legal insights, making them beneficial for quick comprehension. The end goal is to help the lawyers understand the crux of the articles without having to read them in their entirety.
"""

async def get_summary(text: str) -> str:
    """Generate a summary of the article text using OpenAI."""
    if not os.environ.get("OPENAI_API_KEY"):
        click.echo("OPENAI_API_KEY environment variable not set", err=True)
        return ""
    
    client = AsyncOpenAI(max_retries=3, timeout=60)
    try:
        response = await client.responses.create(
            model="gpt-5-mini",
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT_TEXT}]},
                {
                    "role": "user", 
                    "content": [
                        {"type": "input_text", "text": f"Here is an article to summarise:\n {text}"}
                    ],
                },
            ],
            text={"format": {"type": "text"}},
            reasoning={"effort": "low", "summary": "auto"},
            store=False,
        )
        return response.output_text
    except Exception as e:
        click.echo(f"Error generating summary from OpenAI: {e}", err=True)
        return ""
```

**Usage with web content extraction:**
```python
async def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """Fetch articles with AI-generated summaries."""
    
    urls = [
        "https://lawblog.example.com/new-precedent",
        "https://legal-news.example.com/court-decision"
    ]
    
    articles = []
    for url in urls:
        # Get clean content
        full_text = await get_jina_reader_content(url)
        if not full_text:
            continue
            
        # Generate AI summary
        summary = await get_summary(full_text)
        
        # Create record with hash ID
        article_id = get_hash_id([url, full_text[:100]])
        
        articles.append({
            "id": article_id,
            "url": url,
            "title": full_text.split('\n')[0][:200],
            "full_text": full_text,
            "ai_summary": summary,
            "extracted_at": datetime.now().isoformat(),
            "word_count": len(full_text.split())
        })
    
    return articles
```

**Customizing the system prompt:**
```python
# For different domains, adjust the SYSTEM_PROMPT_TEXT
TECH_SUMMARY_PROMPT = """
You are a technical expert summarizing technology articles for software engineers. 
Focus on technical details, implementation insights, and practical implications.
Keep summaries under 100 words in a single paragraph.
"""

BUSINESS_SUMMARY_PROMPT = """  
You are a business analyst summarizing market news for executives.
Highlight financial impact, strategic implications, and market trends.
Keep summaries under 100 words in a single paragraph.
"""

async def get_summary(text: str, domain: str = "legal") -> str:
    """Generate domain-specific summary."""
    prompts = {
        "legal": SYSTEM_PROMPT_TEXT,
        "tech": TECH_SUMMARY_PROMPT, 
        "business": BUSINESS_SUMMARY_PROMPT
    }
    
    system_prompt = prompts.get(domain, SYSTEM_PROMPT_TEXT)
    # ... rest of function with system_prompt
```

**Required dependencies:**
```bash
uv add openai click
```

**Environment setup:**
```bash
export OPENAI_API_KEY="your_openai_api_key"
```

**Features:**
- **Domain-specific summaries** - Customizable system prompts for different fields
- **Error handling** - Graceful fallback when API is unavailable
- **Retry logic** - Built-in retries for reliability  
- **Async support** - Non-blocking for concurrent processing
- **Cost control** - Uses efficient models with controlled output length

**Cost optimization tips:**
- Use `gpt-4o-mini` for cost-effective summarization
- Truncate very long texts before sending to API
- Cache summaries using hash IDs to avoid re-processing
- Consider batching multiple texts in single API calls