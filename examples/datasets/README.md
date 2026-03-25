# Simple Datasets Example

A minimal Zeeker project demonstrating basic usage with static data.

## Purpose

This example shows the simplest possible Zeeker project:
- No external dependencies beyond zeeker
- Static data (no API calls)
- Basic duplicate handling
- Simple schema

## Setup

```bash
# Install dependencies
uv sync

# Build the database
uv run zeeker build
```

## Structure

- `resources/sample_data.py` - Simple static data resource
- `zeeker.toml` - Basic project configuration
- `datasets.db` - Generated SQLite database (after build)

## Learning Points

This example demonstrates:

1. **Basic resource structure** - Minimal `fetch_data()` implementation
2. **Static data** - No external APIs or files needed
3. **Type inference** - How sqlite-utils infers types from Python data
4. **Duplicate handling** - Simple ID-based deduplication

## Usage

```bash
# Build the database
uv run zeeker build

# View the data (if you have datasette installed)
datasette datasets.db
```

## Next Steps

After understanding this example, check out:
- `examples/legal-news/` - More advanced example with async fetching and zeeker-common utilities
- Main Zeeker documentation for full feature set
