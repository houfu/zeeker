# Legal News Example Project

An example Zeeker project demonstrating best practices for building a legal news database.

## Features

- Uses `zeeker-common` for shared utilities
- Demonstrates async data fetching
- Shows proper duplicate handling
- Implements hash-based ID generation
- Includes Jina Reader integration for web content extraction

## Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. (Optional) Create `.env` file with API keys:
   ```bash
   JINA_API_TOKEN=your_token_here
   ```

3. Build the database:
   ```bash
   uv run zeeker build
   ```

## Structure

- `resources/articles.py` - Example resource showing zeeker-common utilities
- `zeeker.toml` - Project configuration with Datasette metadata
- `legal_news.db` - Generated SQLite database (after build)

## Learning Points

This example demonstrates:

1. **Async data fetching** - Using `async def fetch_data()` for concurrent operations
2. **zeeker-common utilities** - Hash IDs, Jina Reader, retry decorators
3. **Duplicate prevention** - Checking `existing_table` before inserting
4. **Schema design** - Proper types, facets, and column metadata
5. **Error handling** - Graceful handling of fetch failures

## Usage

```bash
# Build the database
uv run zeeker build

# Generate metadata
uv run zeeker metadata generate

# Deploy to S3 (requires S3 credentials)
uv run zeeker deploy
```
