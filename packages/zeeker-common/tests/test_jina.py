"""Tests for Jina Reader API integration."""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from zeeker_common.jina import get_jina_reader_content
from tenacity import RetryError


class TestGetJinaReaderContent:
    """Test suite for get_jina_reader_content function."""

    @pytest.mark.anyio
    async def test_missing_api_token(self):
        """Test that missing JINA_API_TOKEN raises error."""
        with patch.dict(os.environ, {}, clear=True):
            # Retry decorator wraps KeyError in RetryError
            with pytest.raises(RetryError) as exc_info:
                await get_jina_reader_content("https://example.com")

            # The original KeyError should be in the traceback
            assert "JINA_API_TOKEN" in str(exc_info.value) or "KeyError" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_successful_content_fetch(self):
        """Test successful content fetching from Jina Reader."""
        mock_content = "This is the extracted content from the webpage."

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                # Setup mock response
                mock_response = MagicMock()
                mock_response.text = mock_content
                mock_response.raise_for_status = MagicMock()

                # Setup mock client
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_client_class.return_value = mock_client

                result = await get_jina_reader_content("https://example.com/article")

                assert result == mock_content
                mock_client.get.assert_called_once()

                # Verify the correct URL and headers were used
                call_args = mock_client.get.call_args
                assert call_args[0][0] == "https://r.jina.ai/https://example.com/article"
                assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    @pytest.mark.anyio
    async def test_http_error_handling(self):
        """Test that HTTP errors are raised properly."""
        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                # Setup mock to raise HTTPError
                mock_response = MagicMock()
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "404 Not Found", request=MagicMock(), response=MagicMock()
                )

                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_client_class.return_value = mock_client

                # Should raise after 3 retry attempts
                with pytest.raises(RetryError):
                    await get_jina_reader_content("https://example.com/notfound")

                # Verify it was called 3 times due to retry
                assert mock_client.get.call_count == 3

    @pytest.mark.anyio
    async def test_timeout_configuration(self):
        """Test that client is configured with proper timeout."""
        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.text = "content"
                mock_response.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_client_class.return_value = mock_client

                await get_jina_reader_content("https://example.com")

                # Verify AsyncClient was instantiated with timeout=90
                mock_client_class.assert_called_once_with(timeout=90)

    @pytest.mark.anyio
    async def test_url_construction(self):
        """Test that URLs are correctly constructed for Jina Reader."""
        test_cases = [
            ("https://example.com", "https://r.jina.ai/https://example.com"),
            ("http://test.org/page", "https://r.jina.ai/http://test.org/page"),
            (
                "https://example.com/article?id=123",
                "https://r.jina.ai/https://example.com/article?id=123",
            ),
        ]

        for input_url, expected_jina_url in test_cases:
            with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
                with patch("httpx.AsyncClient") as mock_client_class:
                    mock_response = MagicMock()
                    mock_response.text = "content"
                    mock_response.raise_for_status = MagicMock()

                    mock_client = AsyncMock()
                    mock_client.get = AsyncMock(return_value=mock_response)
                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                    mock_client.__aexit__ = AsyncMock(return_value=None)

                    mock_client_class.return_value = mock_client

                    await get_jina_reader_content(input_url)

                    call_args = mock_client.get.call_args
                    assert call_args[0][0] == expected_jina_url

    @pytest.mark.anyio
    async def test_retry_on_network_error(self):
        """Test retry behavior on network errors."""
        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                # Setup mock to raise network error
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_client_class.return_value = mock_client

                # Should raise after 3 retry attempts
                with pytest.raises(RetryError):
                    await get_jina_reader_content("https://example.com")

                # Verify it was called 3 times due to retry
                assert mock_client.get.call_count == 3

    @pytest.mark.anyio
    async def test_retry_then_success(self):
        """Test that retry succeeds after initial failures."""
        call_count = 0

        async def mock_get_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            if call_count < 3:
                raise httpx.NetworkError("Temporary failure")

            # Third attempt succeeds
            mock_response = MagicMock()
            mock_response.text = "success content"
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=mock_get_with_retry)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_client_class.return_value = mock_client

                result = await get_jina_reader_content("https://example.com")

                assert result == "success content"
                assert call_count == 3

    @pytest.mark.anyio
    async def test_empty_token_raises_key_error(self):
        """Test that empty string token is treated as missing."""
        with patch.dict(os.environ, {"JINA_API_TOKEN": ""}):
            # Retry decorator wraps KeyError in RetryError
            with pytest.raises(RetryError):
                await get_jina_reader_content("https://example.com")

    @pytest.mark.anyio
    async def test_unicode_content_handling(self):
        """Test handling of unicode content in response."""
        unicode_content = "这是中文内容 with émojis 🎉"

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.text = unicode_content
                mock_response.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_client_class.return_value = mock_client

                result = await get_jina_reader_content("https://example.com")

                assert result == unicode_content

    @pytest.mark.anyio
    async def test_large_content_handling(self):
        """Test handling of large content responses."""
        large_content = "x" * 1000000  # 1MB of content

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = MagicMock()
                mock_response.text = large_content
                mock_response.raise_for_status = MagicMock()

                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)

                mock_client_class.return_value = mock_client

                result = await get_jina_reader_content("https://example.com")

                assert result == large_content
                assert len(result) == 1000000
