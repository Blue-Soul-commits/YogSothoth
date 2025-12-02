from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from .models import CodeChunk, RepoGroup
from .llm_client import LLMClient
from .llm_orchestrator import LLMOrchestrator
from ..storage.db import Database
from ..storage.vector_store import VectorStore


@dataclass
class QAAnswer:
    """Answer returned by QAService.

    ``references`` is a list of opaque dictionaries that describe
    which code chunks or files were used when generating the answer.
    The exact shape can evolve over time without breaking callers.
    """

    answer_text: str
    references: List[Dict[str, Any]]


class QAService:
    """High-level entrypoint for repo and repo-group QA."""

    def __init__(
        self,
        db: Database,
        vector_store: VectorStore | None = None,
        llm_orchestrator: LLMOrchestrator | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._db = db
        self._vector_store = vector_store or VectorStore(db)
        self._llm_orchestrator = llm_orchestrator or LLMOrchestrator()
        self._llm_client = llm_client  # 延迟初始化，真正需要时再构造

    # ------------------------------------------------------------------
    # Public APIs（非 LLM 结构化回答，主要用于兼容）
    # ------------------------------------------------------------------

    def ask_repo(self, repo_id: str, question: str, top_k: int = 10) -> QAAnswer:
        """Answer a question within a single repository using structured answer."""

        chunks = self._search_chunks([repo_id], question, top_k_per_repo=top_k)
        return self._build_answer(chunks, group=None)

    def ask_repo_group(
        self, group_id: str, question: str, top_k_per_repo: int = 5
    ) -> QAAnswer:
        """Answer a question across all repositories in a group using structured answer."""

        group: RepoGroup | None = self._db.get_repo_group(group_id)
        if group is None:
            return QAAnswer(
                answer_text=f"No repository group found with id '{group_id}'.",
                references=[],
            )

        chunks = self._search_chunks(group.repo_ids, question, top_k_per_repo)
        return self._build_answer(chunks, group=group)

    # ------------------------------------------------------------------
    # Prompt 构造（供外层自行调用 LLM 时使用）
    # ------------------------------------------------------------------

    def build_prompt_for_repo(
        self, repo_id: str, question: str, top_k: int = 10
    ) -> str:
        chunks = self._search_chunks([repo_id], question, top_k_per_repo=top_k)
        plain_chunks = [c for c, _ in chunks]
        return self._llm_orchestrator.build_prompt_for_repo(
            repo_id=repo_id, question=question, chunks=plain_chunks
        )

    def build_prompt_for_repo_group(
        self, group_id: str, question: str, top_k_per_repo: int = 5
    ) -> str:
        group = self._db.get_repo_group(group_id)
        if group is None:
            raise ValueError(f"Unknown repository group: {group_id}")

        chunks = self._search_chunks(group.repo_ids, question, top_k_per_repo)
        plain_chunks = [c for c, _ in chunks]
        return self._llm_orchestrator.build_prompt_for_repo_group(
            group=group, question=question, chunks=plain_chunks
        )

    # ------------------------------------------------------------------
    # LLM 回答（单轮 / 多轮均通过此入口）
    # ------------------------------------------------------------------

    def ask_repo_llm(
        self,
        repo_id: str,
        question: str,
        top_k: int = 10,
        session_id: str | None = None,
    ) -> QAAnswer:
        """使用 embedding 检索 + LLM 生成自然语言回答（单仓库，多轮对话可选）。"""

        chunks = self._search_chunks([repo_id], question, top_k_per_repo=top_k)

        if not chunks:
            return self._no_chunks_answer(scope=f"repository '{repo_id}'")

        plain_chunks = [c for c, _ in chunks]
        scope = f"仓库 {repo_id}"
        system_msg = self._llm_orchestrator.build_system_message(scope=scope)
        context_block = self._llm_orchestrator.build_context_block(plain_chunks)
        user_block = self._llm_orchestrator.build_user_message(question)
        current_user_content = f"{context_block}\n\n{user_block}"

        messages: List[Dict[str, str]] = []
        messages.append({"role": "system", "content": system_msg})

        # 读取历史消息（如果提供了 session_id）。
        if session_id:
            self._db.ensure_conversation(session_id, scope="repo", target_id=repo_id)
            history = self._db.get_conversation_messages(session_id, limit=20)
            for m in history:
                messages.append({"role": m["role"], "content": m["content"]})

        messages.append({"role": "user", "content": current_user_content})

        llm = self._llm_client or LLMClient.from_default_config()
        answer_text = llm.generate_messages(messages)

        # 记录本轮对话。
        if session_id:
            self._db.add_conversation_message(
                session_id, role="user", content=current_user_content
            )
            self._db.add_conversation_message(
                session_id, role="assistant", content=answer_text
            )

        references = self._build_references(chunks)
        return QAAnswer(answer_text=answer_text, references=references)

    def ask_repo_group_llm(
        self,
        group_id: str,
        question: str,
        top_k_per_repo: int = 5,
        session_id: str | None = None,
    ) -> QAAnswer:
        """使用 embedding 检索 + LLM 生成自然语言回答（仓库组，多轮对话可选）。"""

        group = self._db.get_repo_group(group_id)
        if group is None:
            return QAAnswer(
                answer_text=f"No repository group found with id '{group_id}'.",
                references=[],
            )

        chunks = self._search_chunks(group.repo_ids, question, top_k_per_repo)
        if not chunks:
            return self._no_chunks_answer(scope=f"repository group '{group.id}'")

        plain_chunks = [c for c, _ in chunks]
        scope = f"仓库组 {group.id}（包含仓库: {', '.join(group.repo_ids)}）"
        system_msg = self._llm_orchestrator.build_system_message(scope=scope)
        context_block = self._llm_orchestrator.build_context_block(plain_chunks)
        user_block = self._llm_orchestrator.build_user_message(question)
        current_user_content = f"{context_block}\n\n{user_block}"

        messages: List[Dict[str, str]] = []
        messages.append({"role": "system", "content": system_msg})

        if session_id:
            self._db.ensure_conversation(session_id, scope="group", target_id=group_id)
            history = self._db.get_conversation_messages(session_id, limit=20)
            for m in history:
                messages.append({"role": m["role"], "content": m["content"]})

        messages.append({"role": "user", "content": current_user_content})

        llm = self._llm_client or LLMClient.from_default_config()
        answer_text = llm.generate_messages(messages)

        if session_id:
            self._db.add_conversation_message(
                session_id, role="user", content=current_user_content
            )
            self._db.add_conversation_message(
                session_id, role="assistant", content=answer_text
            )

        references = self._build_references(chunks)
        return QAAnswer(answer_text=answer_text, references=references)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_chunks(
        self, repo_ids: Iterable[str], question: str, top_k_per_repo: int
    ) -> List[Tuple[CodeChunk, float]]:
        """Vector-store backed search over code chunks."""

        results: List[Tuple[CodeChunk, float]] = []
        for repo_id in repo_ids:
            per_repo = self._vector_store.search(
                [repo_id], question, top_k=top_k_per_repo
            )
            results.extend(per_repo)
        return results

    def _build_answer(
        self,
        chunks: List[Tuple[CodeChunk, float]],
        group: RepoGroup | None = None,
    ) -> QAAnswer:
        """旧的结构化回答：返回引用列表，answer_text 简要说明。"""

        if not chunks:
            scope = (
                f"repository group '{group.id}'"
                if group is not None
                else "repository"
            )
            return self._no_chunks_answer(scope=scope)

        if group is not None:
            header = (
                f"Showing code locations across group '{group.id}' "
                "related to your question:"
            )
        else:
            header = "Showing code locations related to your question:"

        references = self._build_references(chunks)
        return QAAnswer(answer_text=header, references=references)

    def _no_chunks_answer(self, scope: str) -> QAAnswer:
        return QAAnswer(
            answer_text=(
                f"No indexed code chunks found for the {scope}. "
                "You may need to run a reindex operation first."
            ),
            references=[],
        )

    def _build_references(
        self,
        chunks: List[Tuple[CodeChunk, float]],
    ) -> List[Dict[str, Any]]:
        """构造 references 列表。"""

        references: List[Dict[str, Any]] = []
        for chunk, score in chunks:
            references.append(
                {
                    "repo_id": chunk.repo_id,
                    "file_path": str(chunk.file_path),
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "score": score,
                }
            )
        return references

