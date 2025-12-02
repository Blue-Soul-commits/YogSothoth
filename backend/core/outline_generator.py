from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from .models import CodeChunk
from .llm_client import LLMClient


class OutlineGenerator:
    """Generates markdown outlines for a repository."""

    def generate_outline(self, repo_id: str, chunks: Iterable[CodeChunk]) -> str:
        """Return markdown outline text for the given repo using LLM.

        为了控制上下文长度，我们只向大模型提供每个 CodeChunk 的
        路径 / 符号名 / 摘要，而不是完整代码。
        """

        items: List[str] = []
        for chunk in chunks:
            symbol = f" :: {chunk.symbol}" if chunk.symbol else ""
            summary = (chunk.summary or "").strip()
            # 每条最多 300 字符，避免 prompt 过长
            if len(summary) > 300:
                summary = summary[:297] + "..."
            items.append(
                f"- file: {chunk.file_path}{symbol}\n  summary: {summary or '（无摘要）'}"
            )

        outline_source = "\n".join(items)

        prompt = (
            "你是一名资深架构师，请根据下面的代码片段摘要，为该仓库生成一份结构清晰的 "
            "Markdown 大纲（不要写多余解释，只输出 Markdown）：\n\n"
            f"仓库 ID: {repo_id}\n\n"
            "以下是各个文件/符号的摘要信息：\n\n"
            f"{outline_source}\n\n"
            "请输出的 Markdown 至少包含：\n"
            "1. 顶部的一级标题（项目名或仓库 ID）；\n"
            "2. 项目简介；\n"
            "3. 主要模块/目录结构；\n"
            "4. 关键类 / 函数 / 接口的列表；\n"
            "5. 如果能推断出来，可以简要描述典型使用流程或调用链。\n"
        )

        client = LLMClient.from_default_config()
        try:
            outline_md = client.generate(prompt, temperature=0.2)
        except Exception as exc:  # 回退到简单列表模式
            lines = [f"# {repo_id} outline (fallback)", "", f"> LLM 生成失败: {exc}", ""]
            for chunk in chunks:
                symbol = f" :: {chunk.symbol}" if chunk.symbol else ""
                lines.append(f"- {chunk.file_path}{symbol}")
            outline_md = "\n".join(lines)

        return outline_md

    def save_outline(self, repo_id: str, outline_root: Path, outline_md: str) -> Path:
        """Save outline markdown to disk and return its path."""

        outline_root.mkdir(parents=True, exist_ok=True)
        path = outline_root / f"{repo_id}.md"
        path.write_text(outline_md, encoding="utf-8")
        return path
