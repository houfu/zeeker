"""Jina Reader API integration for web content extraction."""

import os
import httpx
from tenacity import retry, stop_after_attempt


@retry(stop=stop_after_attempt(3))
async def get_jina_reader_content(link: str) -> str:
    """Fetch web content using Jina Reader API with retries.

    Jina Reader extracts clean text content from web pages, removing
    ads, navigation, and other clutter.

    Args:
        link: URL to fetch content from

    Returns:
        Extracted text content from the page

    Raises:
        httpx.HTTPError: If the request fails after retries
        KeyError: If JINA_API_TOKEN environment variable is not set

    Example:
        >>> content = await get_jina_reader_content("https://example.com/article")
        >>> print(content[:100])
    """
    api_token = os.environ.get("JINA_API_TOKEN")
    if not api_token:
        raise KeyError("JINA_API_TOKEN environment variable is required")

    headers = {"Authorization": f"Bearer {api_token}"}

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.get(f"https://r.jina.ai/{link}", headers=headers)
        response.raise_for_status()
        return response.text
