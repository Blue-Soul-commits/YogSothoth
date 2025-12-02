from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List
from urllib import request, error

from ..config.models import ModelsConfig, load_models_config


@dataclass
class EmbeddingClient:
    """Simple embedding client based on the models configuration.

    当前实现支持 "openai-compatible" 类型的服务商：使用
    POST {base_url}/embeddings 接口，传入:
        {"model": "<embedding>", "input": [text1, text2, ...]}
    并从返回的 JSON 结构中解析 embedding。
    """

    config: ModelsConfig

    @classmethod
    def from_default_config(cls) -> "EmbeddingClient":
        cfg = load_models_config()
        return cls(cfg)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return embedding vectors for the given texts.

        如果没有配置可用的 API key，将抛出 RuntimeError，并在消息中给出
        清晰提示（方便你在调用层统一处理）。
        """

        if not texts:
            return []

        provider = self.config.get_embedding_provider()
        api_key = provider.api_key
        if not api_key:
            raise RuntimeError(
                f"No API key found in environment variable {provider.api_key_env}. "
                "Please configure your model provider before using embedding search."
            )

        if provider.type == "openai-compatible":
            return self._embed_openai_compatible(
                base_url=provider.base_url,
                api_key=api_key,
                model=provider.models.embedding,
                texts=texts,
            )

        raise RuntimeError(f"Unsupported provider type: {provider.type}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _embed_openai_compatible(
        self,
        base_url: str,
        api_key: str,
        model: str,
        texts: List[str],
    ) -> List[List[float]]:
        url = base_url.rstrip("/") + "/embeddings"
        payload = {"model": model, "input": texts}
        data = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        req = request.Request(url, data=data, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=300) as resp:
                body = resp.read().decode("utf-8")
        except error.HTTPError as e:
            msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Embedding request failed with HTTP {e.code}: {msg}"
            ) from e
        except error.URLError as e:
            raise RuntimeError(f"Failed to call embedding endpoint: {e}") from e

        try:
            parsed = json.loads(body)
            data_list = parsed["data"]
            return [item["embedding"] for item in data_list]
        except (KeyError, TypeError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"Unexpected response format from embedding endpoint: {body[:400]}"
            ) from e
