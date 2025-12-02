from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path

from ..config.settings import get_settings
from ..core.qa_service import QAService
from ..storage.db import Database


# NOTE: This module contains logical handlers for the MCP tools.
# Integration with a concrete MCP framework (tool registration,
# server startup, etc.) will be added in a later iteration. The
# functions below are written in a framework-agnostic way so they
# can be reused from whatever MCP glue code we add later.


_settings = get_settings()


def _db_path_from_url(db_url: str) -> Path:
    """Convert a SQLite-style URL into a filesystem path.

    We accept either a raw path or ``sqlite:///...`` URL.
    """

    if db_url.startswith("sqlite:///"):
        return Path(db_url.replace("sqlite:///", "", 1)).resolve()
    return Path(db_url).resolve()


_db = Database(_db_path_from_url(_settings.db_url))
_qa_service = QAService(_db)


def _dt_to_iso(dt: Optional["datetime.datetime"]) -> Optional[str]:  # type: ignore[name-defined]
    """Helper to safely format datetimes as ISO strings for JSON.

    We keep this local to avoid adding a hard dependency on timezone-
    aware datetime handling at this layer. ``None`` is preserved.
    """

    return dt.isoformat() if dt is not None else None


def list_repos() -> List[Dict[str, Any]]:
    """Logical implementation for the ``list_repos`` MCP tool.

    Returns a list of dictionaries describing each repository. The
    exact shape can be adapted by the MCP integration layer, but the
    keys used here are intended to be stable and human-readable.
    """

    repos = _db.list_repos()
    result: List[Dict[str, Any]] = []
    for repo in repos:
        result.append(
            {
                "id": repo.id,
                "name": repo.name,
                "git_url": repo.git_url,
                "default_branch": repo.default_branch,
                "local_path": str(repo.local_path) if repo.local_path else None,
                "indexed_at": _dt_to_iso(repo.indexed_at),
                "summary": repo.summary,
            }
        )
    return result


def list_repo_groups() -> List[Dict[str, Any]]:
    """Logical implementation for the ``list_repo_groups`` MCP tool."""

    groups = _db.list_repo_groups()
    result: List[Dict[str, Any]] = []
    for group in groups:
        result.append(
            {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "repo_ids": list(group.repo_ids),
                "indexed_at": _dt_to_iso(group.indexed_at),
            }
        )
    return result


def ask_repo(
    repo_id: str,
    question: str,
    top_k: int = 10,
    session_id: Optional[str] = None,
    link_history: bool = True,
) -> Dict[str, Any]:
    """Logical implementation for the ``ask_repo`` MCP tool.

    The return value is a dictionary with the following keys:

    - ``repo_id``: the repository id the question was asked against.
    - ``question``: the original question.
    - ``answer_text``: human-readable answer text.
    - ``references``: list of reference dictionaries.

    ``session_id`` and ``link_history`` can be used to enable multi-turn
    conversations. If ``link_history`` is true and ``session_id`` is provided,
    the underlying QA service will load + append conversation history for
    that session. If ``link_history`` is false, the question is treated as
    single-turn even if a ``session_id`` is present.
    """

    effective_session_id = session_id if (link_history and session_id) else None
    answer = _qa_service.ask_repo_llm(
        repo_id=repo_id,
        question=question,
        top_k=top_k,
        session_id=effective_session_id,
    )
    return {
        "repo_id": repo_id,
        "question": question,
        "answer_text": answer.answer_text,
        "references": answer.references,
        "session_id": session_id,
        "link_history": link_history,
    }


def ask_repo_group(
    group_id: str,
    question: str,
    top_k_per_repo: int = 5,
    session_id: Optional[str] = None,
    link_history: bool = True,
) -> Dict[str, Any]:
    """Logical implementation for the ``ask_repo_group`` MCP tool.

    The return value mirrors :func:`ask_repo` but includes ``group_id``
    instead of ``repo_id``. Multi-turn behaviour is controlled by the same
    ``session_id`` / ``link_history`` parameters.
    """

    effective_session_id = session_id if (link_history and session_id) else None
    answer = _qa_service.ask_repo_group_llm(
        group_id=group_id,
        question=question,
        top_k_per_repo=top_k_per_repo,
        session_id=effective_session_id,
    )
    return {
        "group_id": group_id,
        "question": question,
        "answer_text": answer.answer_text,
        "references": answer.references,
        "session_id": session_id,
        "link_history": link_history,
    }
