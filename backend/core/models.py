from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Repo:
    """Repository metadata stored in the local system."""

    id: str
    name: str
    git_url: str
    default_branch: str = "main"
    local_path: Path = Path()
    indexed_at: Optional[datetime] = None
    summary: Optional[str] = None


@dataclass
class RepoGroup:
    """Logical group of repositories for cross-repo QA."""

    id: str
    name: str
    description: str = ""
    repo_ids: List[str] = field(default_factory=list)
    indexed_at: Optional[datetime] = None


@dataclass
class CodeChunk:
    """Small unit of code for indexing and retrieval."""

    id: str
    repo_id: str
    file_path: Path
    symbol: Optional[str] = None
    symbol_type: Optional[str] = None
    start_line: int = 1
    end_line: int = 1
    code: str = ""
    summary: Optional[str] = None
