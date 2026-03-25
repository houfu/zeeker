"""Tests for OpenAI API integration."""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from zeeker_common.openai import get_summary


class TestGetSummary:
    """Test suite for get_summary function."""

    @pytest.mark.anyio
    async def test_import_error_when_openai_not_installed(self):
        """Test that ImportError is raised when openai package is not installed."""
        # Mock the AsyncOpenAI to be None (simulating missing package)
        with patch("zeeker_common.openai.AsyncOpenAI", None):
            with pytest.raises(ImportError) as exc_info:
                await get_summary("Some text to summarize")

            assert "openai" in str(exc_info.value).lower()
            assert "pip install zeeker-common[openai]" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_missing_api_key(self):
        """Test that missing OPENAI_API_KEY raises KeyError."""
        with patch.dict(os.environ, {}, clear=True):
            # Mock AsyncOpenAI to exist (package installed)
            mock_openai_class = MagicMock()
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                with pytest.raises(KeyError) as exc_info:
                    await get_summary("Some text")

                assert "OPENAI_API_KEY" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_successful_summary_generation(self):
        """Test successful summary generation."""
        mock_summary = "This is a concise summary of the input text."

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            # Mock the OpenAI client and response
            mock_message = MagicMock()
            mock_message.content = mock_summary

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_openai_class = MagicMock(return_value=mock_client)

            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                result = await get_summary("Long text to summarize")

                assert result == mock_summary

                # Verify client was created with correct parameters
                mock_openai_class.assert_called_once_with(
                    api_key="test-api-key", max_retries=3, timeout=60
                )

                # Verify chat completion was called
                mock_client.chat.completions.create.assert_called_once()
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                assert call_kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.anyio
    async def test_default_system_prompt(self):
        """Test that default system prompt is used when none provided."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            mock_message = MagicMock()
            mock_message.content = "Summary"

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_openai_class = MagicMock(return_value=mock_client)

            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                await get_summary("Text to summarize")

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                messages = call_kwargs["messages"]

                # Check that default system prompt is used
                assert messages[0]["role"] == "system"
                assert messages[0]["content"] == "Summarize the following text concisely."

    @pytest.mark.anyio
    async def test_custom_system_prompt(self):
        """Test that custom system prompt is used when provided."""
        custom_prompt = "Create a detailed technical summary with bullet points."

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            mock_message = MagicMock()
            mock_message.content = "Summary"

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_openai_class = MagicMock(return_value=mock_client)

            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                await get_summary("Text to summarize", system_prompt=custom_prompt)

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                messages = call_kwargs["messages"]

                assert messages[0]["role"] == "system"
                assert messages[0]["content"] == custom_prompt

    @pytest.mark.anyio
    async def test_message_structure(self):
        """Test that messages are formatted correctly."""
        input_text = "This is the text that needs summarization."

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            mock_message = MagicMock()
            mock_message.content = "Summary"

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_openai_class = MagicMock(return_value=mock_client)

            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                await get_summary(input_text)

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                messages = call_kwargs["messages"]

                # Should have system and user messages
                assert len(messages) == 2
                assert messages[0]["role"] == "system"
                assert messages[1]["role"] == "user"
                assert f"Summarize:\n{input_text}" in messages[1]["content"]

    @pytest.mark.anyio
    async def test_model_configuration(self):
        """Test that correct model is used."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            mock_message = MagicMock()
            mock_message.content = "Summary"

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_openai_class = MagicMock(return_value=mock_client)

            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                await get_summary("Text")

                call_kwargs = mock_client.chat.completions.create.call_args[1]
                assert call_kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.anyio
    async def test_client_retry_configuration(self):
        """Test that client is configured with max_retries."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            mock_message = MagicMock()
            mock_message.content = "Summary"

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_openai_class = MagicMock(return_value=mock_client)

            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                await get_summary("Text")

                # Verify AsyncOpenAI was created with max_retries=3
                call_kwargs = mock_openai_class.call_args[1]
                assert call_kwargs["max_retries"] == 3
                assert call_kwargs["timeout"] == 60

    @pytest.mark.anyio
    async def test_empty_api_key_raises_error(self):
        """Test that empty API key is treated as missing."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            mock_openai_class = MagicMock()
            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                with pytest.raises(KeyError):
                    await get_summary("Text")

    @pytest.mark.anyio
    async def test_long_text_handling(self):
        """Test handling of very long input text."""
        long_text = "x" * 10000

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            mock_message = MagicMock()
            mock_message.content = "Summary of long text"

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_openai_class = MagicMock(return_value=mock_client)

            with patch("zeeker_common.openai.AsyncOpenAI", mock_openai_class):
                result = await get_summary(long_text)

                assert result == "Summary of long text"

                # Verify the long text was passed correctly
                call_kwargs = mock_client.chat.completions.create.call_args[1]
                messages = call_kwargs["messages"]
                assert long_text in messages[1]["content"]

    @pytest.mark.anyio
    async def test_unicode_text_handling(self):
        """Test handling of unicode characters in input."""
        unicode_text = "这是中文文本 with émojis 🎉 and special chars: éàü"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            mock_message = MagicMock()
            mock_message.content = "Unicode summary"

            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            mock_openai_class = MagicMock(return_value=mock_client)

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
