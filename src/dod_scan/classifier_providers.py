# pattern: Imperative Shell
"""LLM provider implementations for contract classification."""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from dod_scan.classifier_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    def classify(self, user_prompt: str) -> str:
        """Send classification prompt and return raw response text."""
        ...

    @property
    def model_name(self) -> str: ...


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    def classify(self, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.0,
        )
        return response.content[0].text


class OpenRouterProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._url = "https://openrouter.ai/api/v1/chat/completions"

    @property
    def model_name(self) -> str:
        return self._model

    def classify(self, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 512,
            "temperature": 0.0,
        }
        resp = httpx.post(
            self._url, json=payload, headers=headers, timeout=60.0
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def create_provider(provider: str, api_key: str, model: str) -> LLMProvider:
    if provider == "anthropic":
        return AnthropicProvider(api_key, model)
    if provider == "openrouter":
        return OpenRouterProvider(api_key, model)
    raise ValueError(f"Unknown LLM provider: {provider}")
