from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .models import CodeChunk, RepoGroup


@dataclass
class LLMOrchestratorConfig:
    """Configuration for LLMOrchestrator."""

    max_context_chars: int = 8000
    answer_lang: str = "zh"  # default answer language hint


class LLMOrchestrator:
    """Builds prompts/messages for LLM-based code Q&A.

    这个类只负责把「问题 + 代码片段上下文」组织成清晰的 prompt 或
    chat messages，具体调用哪个大模型、如何发送请求由上层决定。
    """

    def __init__(self, config: LLMOrchestratorConfig | None = None) -> None:
        self.config = config or LLMOrchestratorConfig()

    # ------------------------------------------------------------------
    # Public APIs
    # ------------------------------------------------------------------

    def build_prompt_for_repo(
        self,
        repo_id: str,
        question: str,
        chunks: Iterable[CodeChunk],
    ) -> str:
        """Construct an LLM prompt for a single repo."""

        scope = f"仓库 {repo_id}"
        header = self._build_system_instructions(scope=scope)
        context = self.build_context_block(chunks)
        user = self.build_user_message(question)
        return "\n\n".join([header, context, user])

    def build_prompt_for_repo_group(
        self,
        group: RepoGroup,
        question: str,
        chunks: Iterable[CodeChunk],
    ) -> str:
        """Construct an LLM prompt for a repo group."""

        scope = f"仓库组 {group.id}（包含仓库: {', '.join(group.repo_ids)}）"
        header = self._build_system_instructions(scope=scope)
        context = self.build_context_block(chunks)
        user = self.build_user_message(question)
        return "\n\n".join([header, context, user])

    def build_system_message(self, scope: str) -> str:
        """Return content to be used as a `system` message."""

        return self._build_system_instructions(scope=scope)

    def build_context_block(self, chunks: Iterable[CodeChunk]) -> str:
        """Build only the CONTEXT block, reusable across prompts."""

        return self._build_chunks_context(chunks)

    def build_user_message(self, question: str) -> str:
        """Build only the USER block, reusable across prompts."""

        return self._build_user_block(question)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_system_instructions(self, scope: str) -> str:
        """High-level system instructions for the LLM."""

        lang_hint = "中文" if self.config.answer_lang == "zh" else "English"
        return (
            "你是一名资深的代码助手，正在分析 "
            f"{scope}。\n"
            "你会基于下面提供的代码片段和文档回答用户的问题，要求：\n"
            "1. 优先结合实际代码逻辑，不要凭空幻想不存在的接口或函数。\n"
            "2. 回答时给出清晰的解释，并尽量给出具体的代码示例（保持与原仓库风格一致）。\n"
            "3. 引用代码时注明文件路径和行号，方便用户定位。\n"
            "4. 如果当前仓库/仓库组不包含相关能力，要明确说明，并给出合理的设计建议。\n"
            f"5. 回答语言优先使用 {lang_hint}。\n"
        )

    def _build_chunks_context(self, chunks: Iterable[CodeChunk]) -> str:
        """Render retrieved chunks into a context block."""

        max_chars = self.config.max_context_chars
        remaining = max_chars
        lines: List[str] = ["CONTEXT:", ""]

        for idx, chunk in enumerate(chunks, start=1):
            if remaining <= 0:
                lines.append("...（上下文已截断，后续代码未展示）")
                break

            header = (
                f"[CHUNK {idx}] repo={chunk.repo_id} "
                f"file={chunk.file_path} lines={chunk.start_line}-{chunk.end_line}"
            )
            code = chunk.code.strip()
            if len(code) > remaining:
                code = code[: remaining - 1]
            remaining -= len(code)

            lines.append(header)
            lines.append("```")
            lines.append(code)
            lines.append("```")
            lines.append("")  # blank line between chunks

        return "\n".join(lines)

    def _build_user_block(self, question: str) -> str:
        """Render the user question block."""

        return "USER:\n请基于以上上下文回答下列问题，并给出清晰、分步骤的解释：\n\n" f"{question}\n"

