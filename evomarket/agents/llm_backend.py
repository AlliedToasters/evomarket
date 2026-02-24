"""LLM backend — OpenAI-compatible chat completions client."""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class LLMBackend:
    """Client for any OpenAI-compatible chat completions API.

    Works with Ollama, vLLM, LM Studio, OpenRouter, and any other
    endpoint implementing the OpenAI chat completions format.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "",
        temperature: float = 0.7,
        max_tokens: int = 256,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate(self, prompt: str) -> str:
        """Send prompt to the chat completions endpoint and return response text.

        Returns empty string on any network or API error.
        """
        url = f"{self.base_url}/chat/completions"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.RequestException as exc:
            logger.warning("LLMBackend.generate failed: %s", exc)
            return ""
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("LLMBackend.generate: unexpected response format: %s", exc)
            return ""
