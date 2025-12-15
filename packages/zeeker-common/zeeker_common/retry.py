"""Retry decorators for Zeeker data fetching."""

from tenacity import retry, stop_after_attempt, wait_exponential


# Async retry decorator with exponential backoff
async_retry = retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))


# Sync retry decorator with exponential backoff
sync_retry = retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
