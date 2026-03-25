"""OpenAI API integration for text processing."""

import os
from typing import Optional

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


async def get_summary(text: str, system_prompt: Optional[str] = None) -> str:
    """Generate a summary using OpenAI's API.

    Requires the 'openai' optional dependency:
        pip install zeeker-common[openai]

    Args:
        text: Text to summarize
        system_prompt: Optional system prompt to guide summarization

    Returns:
        Generated summary text

    Raises:
        ImportError: If openai package is not installed
        KeyError: If OPENAI_API_KEY environment variable is not set

    Example:
        >>> summary = await get_summary("Long article text here...")
        >>> print(summary)
    """
    if AsyncOpenAI is None:
        raise ImportError(
            "OpenAI support requires the 'openai' package. "
            "Install with: pip install zeeker-common[openai]"
        )

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise KeyError("OPENAI_API_KEY environment variable is required")

    if system_prompt is None:
        system_prompt = "Summarize the following text concisely."

    client = AsyncOpenAI(api_key=api_key, max_retries=3, timeout=60)

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Summarize:\n{text}"},
        ],
    )

    return response.choices[0].message.content
