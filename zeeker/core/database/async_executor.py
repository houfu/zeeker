"""
Async execution handler for Zeeker database operations.

This module handles the execution of both synchronous and asynchronous
fetch_data and fetch_fragments_data functions with automatic detection.
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional

from sqlite_utils.db import Table


class AsyncExecutor:
    """Handles execution of both sync and async resource functions."""

    def __init__(self):
        """Initialize AsyncExecutor with fetch_data cache."""
        self._fetch_cache: Dict[str, List[Dict[str, Any]]] = {}

    def call_fetch_data(
        self, fetch_data_func: Callable, existing_table: Optional[Table], resource_name: str = None
    ) -> List[Dict[str, Any]]:
        """Call fetch_data function, handling both sync and async variants.

        Args:
            fetch_data_func: The fetch_data function from the resource module
            existing_table: sqlite-utils Table object or None
            resource_name: Name of the resource for caching (optional for backward compatibility)

        Returns:
            List[Dict[str, Any]]: The data returned by fetch_data
        """
        # Check cache if resource_name is provided
        if resource_name:
            cache_key = self._generate_cache_key(resource_name, existing_table)
            if cache_key in self._fetch_cache:
                return self._fetch_cache[cache_key]

        # Execute the function
        if inspect.iscoroutinefunction(fetch_data_func):
            # Async function - run in event loop
            result = self._run_async_function(fetch_data_func, existing_table)
        else:
            # Sync function - call directly
            result = fetch_data_func(existing_table)

        # Cache the result if resource_name is provided
        if resource_name:
            cache_key = self._generate_cache_key(resource_name, existing_table)
            self._fetch_cache[cache_key] = result

        return result

    def _generate_cache_key(self, resource_name: str, existing_table: Optional[Table]) -> str:
        """Generate cache key for fetch_data results.
        
        Args:
            resource_name: Name of the resource
            existing_table: sqlite-utils Table object or None
            
        Returns:
            Cache key string combining resource name and table state
        """
        if existing_table is None:
            return f"{resource_name}_no_table"
        
        try:
            table_count = existing_table.count
            return f"{resource_name}_table_{table_count}"
        except Exception:
            # If we can't get count, use basic key
            return f"{resource_name}_table_exists"

    def call_fetch_fragments_data(
        self,
        fetch_fragments_func: Callable,
        existing_fragments_table: Optional[Table],
        main_data_context: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Call fetch_fragments_data function, handling both sync and async variants.

        Args:
            fetch_fragments_func: The fetch_fragments_data function from the resource module
            existing_fragments_table: sqlite-utils Table object or None
            main_data_context: Raw data from fetch_data for context passing

        Returns:
            List[Dict[str, Any]]: The fragment data returned by fetch_fragments_data
        """
        if inspect.iscoroutinefunction(fetch_fragments_func):
            # Async function - run in event loop
            return self._run_async_fragments_function(
                fetch_fragments_func, existing_fragments_table, main_data_context
            )
        else:
            # Sync function - handle signature compatibility
            sig = inspect.signature(fetch_fragments_func)
            if len(sig.parameters) >= 2:
                try:
                    # Try new signature with context
                    return fetch_fragments_func(existing_fragments_table, main_data_context)
                except TypeError:
                    # Fall back to old signature
                    return fetch_fragments_func(existing_fragments_table)
            else:
                # Old signature - single parameter
                return fetch_fragments_func(existing_fragments_table)

    def _run_async_function(
        self, async_func: Callable, existing_table: Optional[Table]
    ) -> List[Dict[str, Any]]:
        """Execute an async fetch_data function."""
        try:
            # Check if we're already in an async context
            asyncio.get_running_loop()
            # If loop is already running, we need to run in a new thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, async_func(existing_table))
                return future.result()
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(async_func(existing_table))

    def _run_async_fragments_function(
        self,
        async_func: Callable,
        existing_fragments_table: Optional[Table],
        main_data_context: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute an async fetch_fragments_data function."""
        # Handle signature compatibility
        sig = inspect.signature(async_func)

        if len(sig.parameters) >= 2:
            # New signature with context
            coro = async_func(existing_fragments_table, main_data_context)
        else:
            # Old signature - single parameter
            coro = async_func(existing_fragments_table)

        try:
            # Check if we're already in an async context
            asyncio.get_running_loop()
            # If loop is already running, we need to run in a new thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(coro)
