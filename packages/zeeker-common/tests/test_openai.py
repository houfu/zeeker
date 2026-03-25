"""Tests for OpenAI API integration."""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from zeeker_common.openai import get_summary


@pytest.fixture
def mock_openai():
    """Create a helper for building mock OpenAI responses.

    Returns a function that, given a content string, sets up the full
    mock chain and returns (mock_openai_class, mock_client).
    """

    def _make(content="Summary"):
        mock_message = MagicMock()
        mock_message.content = content

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_openai_class = MagicMock(return_value=mock_client)
        return mock_openai_class, mock_client

    return _make


class TestGetSummary:
    """Test suite for get_summary function."""

    @pytest.mark.anyio
    async def test_missing_api_key(self):
        """Test that missing OPENAI_API_KEY raises KeyError."""
        with patch.dict(os.environ, {}, clear=True):
            mock_openai_class = MagicMock()
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                with pytest.raises(KeyError) as exc_info:
                    await get_summary("Some text")

                assert "OPENAI_API_KEY" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_successful_summary_generation(self, mock_openai):
        """Test successful summary generation."""
        mock_summary = "This is a concise summary of the input text."
        mock_openai_class, mock_client = mock_openai(mock_summary)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                result = await get_summary("Long text to summarize")

                assert result == mock_summary
                mock_openai_class.assert_called_once_with(
                    api_key="test-api-key", max_retries=3, timeout=60
                )
                mock_client.chat.completions.create.assert_called_once()
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                assert call_kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.anyio
    async def test_default_system_prompt(self, mock_openai):
        """Test that default system prompt is used when none provided."""
        mock_openai_class, mock_client = mock_openai()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                await get_summary("Text to summarize")

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                messages = call_kwargs["messages"]
                assert messages[0]["role"] == "system"
                assert messages[0]["content"] == "Summarize the following text concisely."

    @pytest.mark.anyio
    async def test_custom_system_prompt(self, mock_openai):
        """Test that custom system prompt is used when provided."""
        custom_prompt = "Create a detailed technical summary with bullet points."
        mock_openai_class, mock_client = mock_openai()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                await get_summary("Text to summarize", system_prompt=custom_prompt)

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                messages = call_kwargs["messages"]
                assert messages[0]["role"] == "system"
                assert messages[0]["content"] == custom_prompt

    @pytest.mark.anyio
    async def test_message_structure(self, mock_openai):
        """Test that messages are formatted correctly."""
        input_text = "This is the text that needs summarization."
        mock_openai_class, mock_client = mock_openai()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                await get_summary(input_text)

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                messages = call_kwargs["messages"]
                assert len(messages) == 2
                assert messages[0]["role"] == "system"
                assert messages[1]["role"] == "user"
                assert f"Summarize:\n{input_text}" in messages[1]["content"]

    @pytest.mark.anyio
    async def test_empty_api_key_raises_error(self):
        """Test that empty API key is treated as missing."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            mock_openai_class = MagicMock()
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                with pytest.raises(KeyError):
                    await get_summary("Text")

    @pytest.mark.anyio
    async def test_long_text_handling(self, mock_openai):
        """Test handling of very long input text."""
        long_text = "x" * 10000
        mock_openai_class, mock_client = mock_openai("Summary of long text")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                result = await get_summary(long_text)

                assert result == "Summary of long text"
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                messages = call_kwargs["messages"]
                assert long_text in messages[1]["content"]

    @pytest.mark.anyio
    async def test_unicode_text_handling(self, mock_openai):
        """Test handling of unicode characters in input."""
        unicode_text = "这是中文文本 with émojis 🎉 and special chars: éàü"
        mock_openai_class, mock_client = mock_openai("Unicode summary")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                result = await get_summary(unicode_text)
                assert result == "Unicode summary"

    @pytest.mark.anyio
    async def test_api_error_propagation(self):
        """Test that API errors are propagated correctly."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            mock_openai_class = MagicMock(return_value=mock_client)

            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                with pytest.raises(Exception) as exc_info:
                    await get_summary("Text")

                assert "API Error" in str(exc_info.value)
