"""Tests for Jina Reader API integration."""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from zeeker_common.jina import get_jina_reader_content
from tenacity import RetryError


@pytest.fixture
def mock_httpx():
    """Create a helper for building mock httpx async clients.

    Returns a function that, given optional response text and an optional
    side_effect, sets up the full mock chain and returns
    (mock_client_class, mock_client).
    """

    def _make(text="content", side_effect=None):
        mock_response = MagicMock()
        mock_response.text = text
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        if side_effect:
            mock_client.get = AsyncMock(side_effect=side_effect)
        else:
            mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_client_class = MagicMock(return_value=mock_client)
        return mock_client_class, mock_client

    return _make


class TestGetJinaReaderContent:
    """Test suite for get_jina_reader_content function."""

    @pytest.mark.anyio
    async def test_missing_api_token(self):
        """Test that missing JINA_API_TOKEN raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RetryError) as exc_info:
                await get_jina_reader_content("https://example.com")

            assert "JINA_API_TOKEN" in str(exc_info.value) or "KeyError" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_successful_content_fetch(self, mock_httpx):
        """Test successful content fetching from Jina Reader."""
        mock_content = "This is the extracted content from the webpage."
        mock_client_class, mock_client = mock_httpx(text=mock_content)

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient", mock_client_class):
                result = await get_jina_reader_content("https://example.com/article")

                assert result == mock_content
                mock_client.get.assert_called_once()

                call_args = mock_client.get.call_args
                assert call_args[0][0] == "https://r.jina.ai/https://example.com/article"
                assert call_args[1]["headers"]["Authorization"] == "Bearer test-token"

    @pytest.mark.anyio
    async def test_http_error_handling(self, mock_httpx):
        """Test that HTTP errors are raised properly."""
        error = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=MagicMock())
        # Need a response that raises on raise_for_status
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = error

        mock_client_class, mock_client = mock_httpx()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient", mock_client_class):
                with pytest.raises(RetryError):
                    await get_jina_reader_content("https://example.com/notfound")

                assert mock_client.get.call_count == 3

    @pytest.mark.anyio
    async def test_url_construction(self, mock_httpx):
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
            mock_client_class, mock_client = mock_httpx()

            with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
                with patch("httpx.AsyncClient", mock_client_class):
                    await get_jina_reader_content(input_url)

                    call_args = mock_client.get.call_args
                    assert call_args[0][0] == expected_jina_url

    @pytest.mark.anyio
    async def test_retry_on_network_error(self, mock_httpx):
        """Test retry behavior on network errors."""
        mock_client_class, mock_client = mock_httpx(
            side_effect=httpx.NetworkError("Connection failed")
        )

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient", mock_client_class):
                with pytest.raises(RetryError):
                    await get_jina_reader_content("https://example.com")

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
            with pytest.raises(RetryError):
                await get_jina_reader_content("https://example.com")

    @pytest.mark.anyio
    async def test_unicode_content_handling(self, mock_httpx):
        """Test handling of unicode content in response."""
        unicode_content = "这是中文内容 with émojis 🎉"
        mock_client_class, mock_client = mock_httpx(text=unicode_content)

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient", mock_client_class):
                result = await get_jina_reader_content("https://example.com")
                assert result == unicode_content

    @pytest.mark.anyio
    async def test_large_content_handling(self, mock_httpx):
        """Test handling of large content responses."""
        large_content = "x" * 1000000
        mock_client_class, mock_client = mock_httpx(text=large_content)

        with patch.dict(os.environ, {"JINA_API_TOKEN": "test-token"}):
            with patch("httpx.AsyncClient", mock_client_class):
                result = await get_jina_reader_content("https://example.com")
                assert result == large_content
                assert len(result) == 1000000
