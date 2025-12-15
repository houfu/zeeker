# zeeker-common

Common utilities for Zeeker data projects.

## Installation

```bash
pip install zeeker-common

# With OpenAI support
pip install zeeker-common[openai]

# With all optional dependencies
pip install zeeker-common[all]
```

## Utilities

### Hash ID Generation

```python
from zeeker_common import get_hash_id

# Generate deterministic IDs from multiple fields
user_id = get_hash_id(["user", "john.doe@example.com"])
```

### Jina Reader Integration

```python
from zeeker_common import get_jina_reader_content

# Extract clean text from web pages
content = await get_jina_reader_content("https://example.com/article")
```

Requires `JINA_API_TOKEN` environment variable.

### Retry Decorators

```python
from zeeker_common import async_retry

@async_retry
async def fetch_data():
    # Automatically retries on failure with exponential backoff
    pass
```

### OpenAI Integration (Optional)

```python
from zeeker_common.openai import get_summary

# Generate summaries using GPT-4
summary = await get_summary("Long text here...")
```

Requires `OPENAI_API_KEY` environment variable and `openai` package.

## License

MIT License - see LICENSE file for details
