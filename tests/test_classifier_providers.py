"""Tests for LLM provider implementations."""

from unittest.mock import Mock, patch

import httpx
import pytest

from dod_scan.classifier_providers import (
    AnthropicProvider,
    OpenRouterProvider,
    create_provider,
)
from dod_scan.classifier_prompt import SYSTEM_PROMPT


class TestAnthropicProvider:
    def test_model_name_property(self) -> None:
        with patch("anthropic.Anthropic"):
            provider = AnthropicProvider(api_key="test-key", model="claude-3-opus-20240229")
            assert provider.model_name == "claude-3-opus-20240229"

    def test_classify_calls_anthropic_api(self) -> None:
        mock_response = Mock()
        mock_response.content = [Mock(text="test response")]

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            provider = AnthropicProvider(api_key="test-key", model="claude-3-opus")
            result = provider.classify("user prompt")

            mock_client.messages.create.assert_called_once()
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["model"] == "claude-3-opus"
            assert call_kwargs["max_tokens"] == 512
            assert call_kwargs["system"] == SYSTEM_PROMPT
            assert call_kwargs["temperature"] == 0.0
            assert call_kwargs["messages"] == [{"role": "user", "content": "user prompt"}]
            assert result == "test response"

    def test_classify_extracts_text_from_response(self) -> None:
        mock_response = Mock()
        mock_response.content = [Mock(text="extracted text")]

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            provider = AnthropicProvider(api_key="test-key", model="claude-3-opus")
            result = provider.classify("test")

            assert result == "extracted text"

    def test_classify_raises_on_api_error(self) -> None:
        from anthropic import APIError

        with patch("anthropic.Anthropic") as mock_anthropic_class:
            mock_client = Mock()
            mock_anthropic_class.return_value = mock_client
            mock_client.messages.create.side_effect = APIError("API error", request=Mock(), body={})

            provider = AnthropicProvider(api_key="test-key", model="claude-3-opus")
            with pytest.raises(APIError):
                provider.classify("test")


class TestOpenRouterProvider:
    def test_model_name_property(self) -> None:
        provider = OpenRouterProvider(api_key="test-key", model="openai/gpt-4")
        assert provider.model_name == "openai/gpt-4"

    def test_classify_sends_correct_request(self) -> None:
        with patch("dod_scan.classifier_providers.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "test response"}}]
            }
            mock_post.return_value = mock_response

            provider = OpenRouterProvider(api_key="test-key", model="openai/gpt-4")
            result = provider.classify("user prompt")

            mock_post.assert_called_once()
            call_args = mock_post.call_args

            assert call_args[0][0] == "https://openrouter.ai/api/v1/chat/completions"
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"
            assert call_args[1]["headers"]["Content-Type"] == "application/json"

            payload = call_args[1]["json"]
            assert payload["model"] == "openai/gpt-4"
            assert payload["max_tokens"] == 512
            assert payload["temperature"] == 0.0
            assert payload["messages"] == [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "user prompt"},
            ]

            assert result == "test response"

    def test_classify_extracts_content_from_response(self) -> None:
        with patch("dod_scan.classifier_providers.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "extracted content"}}]
            }
            mock_post.return_value = mock_response

            provider = OpenRouterProvider(api_key="test-key", model="openai/gpt-4")
            result = provider.classify("test")

            assert result == "extracted content"

    def test_classify_raises_on_http_error(self) -> None:
        with patch("dod_scan.classifier_providers.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
                "HTTP error", request=Mock(), response=Mock()
            )

            provider = OpenRouterProvider(api_key="test-key", model="openai/gpt-4")
            with pytest.raises(httpx.HTTPStatusError):
                provider.classify("test")

    def test_timeout_setting(self) -> None:
        with patch("dod_scan.classifier_providers.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "test"}}]
            }
            mock_post.return_value = mock_response

            provider = OpenRouterProvider(api_key="test-key", model="openai/gpt-4")
            provider.classify("test")

            call_kwargs = mock_post.call_args[1]
            assert call_kwargs["timeout"] == 60.0


class TestCreateProvider:
    def test_create_anthropic_provider(self) -> None:
        with patch("anthropic.Anthropic"):
            provider = create_provider("anthropic", "test-key", "claude-3-opus")
            assert isinstance(provider, AnthropicProvider)
            assert provider.model_name == "claude-3-opus"

    def test_create_openrouter_provider(self) -> None:
        provider = create_provider("openrouter", "test-key", "openai/gpt-4")
        assert isinstance(provider, OpenRouterProvider)
        assert provider.model_name == "openai/gpt-4"

    def test_create_unknown_provider_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider("unknown", "test-key", "model")

    def test_create_provider_is_case_sensitive(self) -> None:
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_provider("Anthropic", "test-key", "model")
