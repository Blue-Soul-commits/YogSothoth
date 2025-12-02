from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ProviderModels:
    chat: str
    embedding: str


@dataclass
class ProviderConfig:
    """Configuration for a single LLM/Embedding provider."""

    name: str
    type: str  # e.g. "openai-compatible", "custom-http"
    base_url: str
    api_key_env: str
    models: ProviderModels

    @property
    def api_key(self) -> Optional[str]:
        """Read API key from the configured environment variable.

        调用方可以选择是否直接使用这里的 key，或者在更高一层
        通过 Secrets 管理系统注入。
        """

        return os.getenv(self.api_key_env)


@dataclass
class ModelsConfig:
    default_provider: str
    default_chat_provider: Optional[str]
    default_embedding_provider: Optional[str]
    providers: Dict[str, ProviderConfig]

    def get_default_provider(self) -> ProviderConfig:
        return self.providers[self.default_provider]

    def get_chat_provider(self) -> ProviderConfig:
        """Return provider for chat LLM.

        如果 default_chat_provider 未配置，则回退到 default_provider。
        """

        name = self.default_chat_provider or self.default_provider
        return self.providers[name]

    def get_embedding_provider(self) -> ProviderConfig:
        """Return provider for embeddings.

        如果 default_embedding_provider 未配置，则回退到 default_provider。
        """

        name = self.default_embedding_provider or self.default_provider
        return self.providers[name]


def _load_raw_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_models_config(
    root: Path | None = None, filename: str = "models.json"
) -> ModelsConfig:
    """Load model/provider configuration.

    - If ``backend/config/models.json`` 存在，则优先使用；
    - 否则回退到 ``models.example.json`` 中的默认配置。
    """

    if root is None:
        root = Path(__file__).parent

    config_path = root / filename
    if not config_path.exists():
        # Fallback to example file.
        config_path = root / "models.example.json"

    raw = _load_raw_config(config_path)
    default_provider_name = raw.get("default_provider", "default")
    default_chat_provider = raw.get("default_chat_provider")
    default_embedding_provider = raw.get("default_embedding_provider")
    providers_raw = raw.get("providers", {})

    providers: Dict[str, ProviderConfig] = {}
    for name, p in providers_raw.items():
        models_raw = p.get("models", {})
        providers[name] = ProviderConfig(
            name=name,
            type=p.get("type", "openai-compatible"),
            base_url=p.get("base_url", ""),
            api_key_env=p.get("api_key_env", "OPENAI_API_KEY"),
            models=ProviderModels(
                chat=models_raw.get("chat", ""),
                embedding=models_raw.get("embedding", ""),
            ),
        )

    return ModelsConfig(
        default_provider=default_provider_name,
        default_chat_provider=default_chat_provider,
        default_embedding_provider=default_embedding_provider,
        providers=providers,
    )
