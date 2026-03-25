"""Tests for retry decorators."""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from zeeker_common.retry import async_retry, sync_retry
from tenacity import RetryError


class TestAsyncRetry:
    """Test suite for async_retry decorator."""

    @pytest.mark.anyio
    async def test_successful_first_attempt(self):
        """Test that successful function executes without retry."""
        call_count = 0

        @async_retry
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.anyio
    async def test_retry_on_failure_then_success(self):
        """Test retry behavior when function fails then succeeds."""
        call_count = 0

        @async_retry
        async def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = await eventually_successful()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.anyio
    async def test_gives_up_after_max_attempts(self):
        """Test that retry gives up after maximum attempts."""
        call_count = 0

        @async_retry
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent failure")

        with pytest.raises(RetryError):
            await always_fails()

        # Should attempt 3 times (stop_after_attempt(3))
        assert call_count == 3

    @pytest.mark.anyio
    async def test_preserves_return_value(self):
        """Test that decorator preserves function return value."""

        @async_retry
        async def return_complex_value():
            return {"key": "value", "list": [1, 2, 3]}

        result = await return_complex_value()
        assert result == {"key": "value", "list": [1, 2, 3]}

    @pytest.mark.anyio
    async def test_preserves_exception_info(self):
        """Test that original exception information is preserved."""

        @async_retry
        async def raises_custom_error():
            raise ValueError("Custom error message")

        with pytest.raises(RetryError) as exc_info:
            await raises_custom_error()

        # The original exception should be accessible from RetryError
        # Check that it's a ValueError with the right message
        assert exc_info.value.last_attempt.failed
        original_exc = exc_info.value.last_attempt.exception()
        assert isinstance(original_exc, ValueError)
        assert "Custom error message" in str(original_exc)

    @pytest.mark.anyio
    async def test_async_with_delay(self):
        """Test that retries include wait time (basic timing test)."""
        import time

        call_count = 0
        start_time = time.time()

        @async_retry
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Fail")
            return "success"

        await fails_twice()
        elapsed = time.time() - start_time

        # With exponential backoff (min=2, max=10), should take at least 2 seconds
        # for the second attempt (first retry waits ~2s)
        assert elapsed >= 2.0
        assert call_count == 3


class TestSyncRetry:
    """Test suite for sync_retry decorator."""

    def test_successful_first_attempt(self):
        """Test that successful function executes without retry."""
        call_count = 0

        @sync_retry
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_failure_then_success(self):
        """Test retry behavior when function fails then succeeds."""
        call_count = 0

        @sync_retry
        def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "success"

        result = eventually_successful()
        assert result == "success"
        assert call_count == 3

    def test_gives_up_after_max_attempts(self):
        """Test that retry gives up after maximum attempts."""
        call_count = 0

        @sync_retry
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent failure")

        with pytest.raises(RetryError):
            always_fails()

        # Should attempt 3 times (stop_after_attempt(3))
        assert call_count == 3

    def test_preserves_return_value(self):
        """Test that decorator preserves function return value."""

        @sync_retry
        def return_complex_value():
            return {"key": "value", "list": [1, 2, 3]}

        result = return_complex_value()
        assert result == {"key": "value", "list": [1, 2, 3]}

    def test_different_exception_types(self):
        """Test retry behavior with different exception types."""
        call_count = 0

        @sync_retry
        def raises_different_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("First error")
            elif call_count == 2:
                raise RuntimeError("Second error")
            return "success"

        result = raises_different_errors()
        assert result == "success"
        assert call_count == 3

    def test_sync_with_delay(self):
        """Test that retries include wait time."""
        import time

        call_count = 0
        start_time = time.time()

        @sync_retry
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Fail")
            return "success"

        fails_twice()
        elapsed = time.time() - start_time

        # With exponential backoff (min=2, max=10), should take at least 2 seconds
        assert elapsed >= 2.0
        assert call_count == 3


class TestRetryConfiguration:
    """Test retry decorator configuration."""

    @pytest.mark.anyio
    async def test_max_attempts_is_three(self):
        """Verify retry configuration allows exactly 3 attempts."""
        call_count = 0

        @async_retry
        async def count_attempts():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fail")

        with pytest.raises(RetryError):
            await count_attempts()

        assert call_count == 3

    def test_sync_max_attempts_is_three(self):
        """Verify sync retry configuration allows exactly 3 attempts."""
        call_count = 0

        @sync_retry
        def count_attempts():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fail")

        with pytest.raises(RetryError):
            count_attempts()

        assert call_count == 3
