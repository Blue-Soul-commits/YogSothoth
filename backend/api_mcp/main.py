from __future__ import annotations

"""
FastMCP entrypoint for the multi-repo assistant.

This file wires the logical MCP handlers from ``backend.api_mcp.server``
into an actual MCP server using the official ``mcp`` Python SDK.

Usage (after installing ``mcp`` in your environment, e.g. ``pip install "mcp[cli]"``):

    # stdio transport (good for local desktop integrations)
    python -m backend.api_mcp.main

    # or, with the mcp CLI:
    #   mcp dev backend/api_mcp/main.py
    #   mcp run backend/api_mcp/main.py
"""

from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from . import server as logic


mcp = FastMCP("multi-repo-assistant")


@mcp.tool(name="list_repos")
def list_repos_tool() -> List[Dict[str, Any]]:
    """List repositories known to the system."""

    return logic.list_repos()


@mcp.tool(name="list_repo_groups")
def list_repo_groups_tool() -> List[Dict[str, Any]]:
    """List repository groups configured in the system."""

    return logic.list_repo_groups()


@mcp.tool(name="ask_repo")
def ask_repo_tool(
    repo_id: str,
    question: str,
    top_k: int = 10,
    session_id: str | None = None,
    link_history: bool = True,
) -> Dict[str, Any]:
    """Ask a question against a single repository.

    ``session_id`` can be used to associate multiple calls into a single
    logical conversation. If ``link_history`` is false, the call is treated
    as single-turn even if a ``session_id`` is provided.
    """

    return logic.ask_repo(
        repo_id=repo_id,
        question=question,
        top_k=top_k,
        session_id=session_id,
        link_history=link_history,
    )


@mcp.tool(name="ask_repo_group")
def ask_repo_group_tool(
    group_id: str,
    question: str,
    top_k_per_repo: int = 5,
    session_id: str | None = None,
    link_history: bool = True,
) -> Dict[str, Any]:
    """Ask a question across all repositories in a group.

    Multi-turn behaviour mirrors ``ask_repo``; use ``session_id`` to identify
    the conversation and ``link_history`` to toggle whether history should be
    replayed.
    """

    return logic.ask_repo_group(
        group_id=group_id,
        question=question,
        top_k_per_repo=top_k_per_repo,
        session_id=session_id,
        link_history=link_history,
    )


def main() -> None:
    """Run the FastMCP server using stdio transport by default."""

    # Default transport is stdio; you can override with e.g.
    #   mcp.run(transport="streamable-http")
    # if you prefer HTTP for tools like MCP Inspector.
    mcp.run()


if __name__ == "__main__":
    main()
