from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, List, Dict
from urllib import error, request

from ..config.models import ModelsConfig, load_models_config


@dataclass
class LLMClient:
    """Chat LLM client based on the models configuration.

    当前实现支持 \"openai-compatible\" 类型服务商，即使用
    POST {base_url}/chat/completions 接口，传入:

        {
          \"model\": \"<chat_model>\",
          \"messages\": [{\"role\": \"user\", \"content\": \"...\"}],
          \"temperature\": 0.2
        }
    """

    config: ModelsConfig

    @classmethod
    def from_default_config(cls) -> "LLMClient":
        cfg = load_models_config()
        return cls(cfg)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        """Generate a completion for a single-turn prompt."""

        messages = [{"role": "user", "content": prompt}]
        return self.generate_messages(messages, temperature=temperature)

    def generate_messages(
        self, messages: List[Dict], temperature: float = 0.2
    ) -> str:
        """Generate a completion for a list of chat messages.

        如果没有配置可用的 API key，将抛出 RuntimeError，并在消息中
        给出清晰提示，方便上层捕获和展示。
        """

        provider = self.config.get_chat_provider()
        api_key = provider.api_key
        if not api_key:
            raise RuntimeError(
                f"No API key found in environment variable {provider.api_key_env}. "
                "Please configure your model provider before using LLM-based answers."
            )

        if provider.type == "openai-compatible":
            return self._generate_openai_compatible(
                base_url=provider.base_url,
                api_key=api_key,
                model=provider.models.chat,
                messages=messages,
                temperature=temperature,
            )

        raise RuntimeError(f"Unsupported provider type for chat: {provider.type}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict],
        temperature: float,
    ) -> str:
        url = base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        req = request.Request(url, data=data, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
        except error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Chat completion request failed with HTTP {e.code}: {msg}"
            ) from e
        except error.URLError as e:
            raise RuntimeError(f"Failed to call chat endpoint: {e}") from e

        try:
            parsed = json.loads(body)
            choice = parsed["choices"][0]
            return choice["message"]["content"]
        except (KeyError, TypeError, json.JSONDecodeError, IndexError) as e:
            raise RuntimeError(
                f"Unexpected response format from chat endpoint: {body[:400]}"
            ) from e

