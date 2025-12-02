from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass
class Settings:
    """Application settings with simple env overrides.

    This keeps configuration minimal for now. A YAML or .env-based
    loader can be added later without breaking callers.
    """

    db_url: str = os.getenv("MCP_DB_URL", "sqlite:///./data/app.db")
    repos_root: Path = Path(os.getenv("MCP_REPOS_ROOT", "./data/repos")).resolve()
    outlines_root: Path = Path(os.getenv("MCP_OUTLINES_ROOT", "./data/outlines")).resolve()
    # 简单管理员密钥，用于保护后台管理接口。
    admin_token: str = os.getenv("GITNAR_ADMIN_TOKEN", "gitnar-admin-demo")


def get_settings() -> Settings:
    """Return a Settings instance.

    Separated into a function so it can be wired into dependency
    injection frameworks if needed.
    """

    return Settings()
