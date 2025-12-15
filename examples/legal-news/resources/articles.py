"""
Legal news articles resource demonstrating best practices with zeeker-common.

This is an example implementation showing:
- Using zeeker-common utilities (get_hash_id, get_jina_reader_content)
- Proper duplicate handling with existing_table
- Async data fetching
- Schema design best practices
"""
from sqlite_utils.db import Table
from typing import Optional, List, Dict, Any

# Using zeeker-common utilities for hash IDs and web extraction
from zeeker_common import get_hash_id, get_jina_reader_content


async def fetch_data(existing_table: Optional[Table]) -> List[Dict[str, Any]]:
    """
    Fetch legal news articles using Jina Reader for content extraction.

    This demonstrates:
    - Async fetching with zeeker-common utilities
    - Deterministic ID generation with get_hash_id
    - Proper duplicate handling
    - Clean web content extraction with Jina Reader

    Args:
        existing_table: sqlite-utils Table object or None

    Returns:
        List of article dictionaries
    """
    # Example article URLs (in production, these would come from an RSS feed or API)
    article_urls = [
        "https://example.com/legal-news/article1",
        "https://example.com/legal-news/article2",
        "https://example.com/legal-news/article3",
    ]

    # Get existing IDs to avoid duplicates
    existing_ids = set()
    if existing_table:
        existing_ids = {row["id"] for row in existing_table.rows}
        print(f"Found {len(existing_ids)} existing articles")

    # Fetch new articles
    articles = []
    for url in article_urls:
        # Generate deterministic ID from URL
        article_id = get_hash_id([url])

        # Skip if already in database
        if article_id in existing_ids:
            continue

        try:
            # Extract content using Jina Reader (requires JINA_API_TOKEN in .env)
            # content = await get_jina_reader_content(url)

            # For this example, we'll use mock data
            content = f"Mock article content for {url}"

            articles.append({
                "id": article_id,
                "url": url,
                "title": f"Example Legal News Article",
                "content": content,
                "category": "legislation",
                "jurisdiction": "US",
                "published_date": "2024-01-15",
            })
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            continue

    print(f"Adding {len(articles)} new articles")
    return articles
