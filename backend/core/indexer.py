from __future__ import annotations

from pathlib import Path
from typing import Iterable, List
import ast

from .models import CodeChunk
from ..storage.vector_store import VectorStore


class Indexer:
    """Builds and updates indexable code chunks for repositories."""

    def index_repo(self, repo_id: str, repo_root: Path) -> List[CodeChunk]:
        """Scan files and return chunks for the given repository.

        For code files we attempt to split into smaller, symbol-level
        blocks (functions/classes) when possible, and fall back to
        slicing large files into fixed-size line ranges. For other
        languages and docs we use a generic line-based splitter so that
        all content can participate in retrieval.
        """

        chunks: List[CodeChunk] = []
        if not repo_root.exists():
            return chunks

        # Common source file extensions plus some documentation types so
        # that README/Markdown content is also indexed.
        exts = {
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".go",
            ".rs",
            ".java",
            ".cs",
            ".md",
            ".txt",
        }

        for path in repo_root.rglob("*"):
            if not path.is_file():
                continue

            suffix = path.suffix.lower()
            name_upper = path.name.upper()

            # Allow extension-less but common docs like README, LICENSE.
            if suffix not in exts:
                if suffix == "" and (
                    name_upper.startswith("README")
                    or name_upper in {"LICENSE", "LICENCE", "COPYING"}
                ):
                    pass
                else:
                    continue

            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Skip files we cannot decode as UTF-8.
                continue

            rel_path = path.relative_to(repo_root)

            if suffix == ".py":
                chunks.extend(self._chunk_python_file(repo_id, rel_path, text))
            else:
                chunks.extend(self._chunk_generic_file(repo_id, rel_path, text))

        return chunks

    def index_chunks(self, chunks: Iterable[CodeChunk]) -> None:
        """Populate embeddings for the given chunks using the VectorStore."""

        # Delayed import to avoid circular dependency during package init.
        from ..storage.db import Database  # type: ignore

        # In a real application you would likely inject these
        # dependencies instead of constructing them here, but for now
        # this keeps wiring simple.
        db = Database(Path("data/app.db"))
        try:
            vs = VectorStore(db)
            vs.add_chunks(chunks)
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _chunk_python_file(self, repo_id: str, rel_path: Path, text: str) -> List[CodeChunk]:
        """Split a Python file into chunks per top-level class/function.

        If parsing fails, we fall back to generic chunking.
        """

        lines = text.splitlines()
        chunks: List[CodeChunk] = []

        try:
            tree = ast.parse(text)
        except SyntaxError:
            return self._chunk_generic_file(repo_id, rel_path, text)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", None)
                if end is None:
                    end = len(lines)
                start = max(start, 1)
                end = min(end, len(lines))

                code_block = "\n".join(lines[start - 1 : end])
                symbol_name = getattr(node, "name", None)
                symbol_type = "class" if isinstance(node, ast.ClassDef) else "function"

                first_lines = code_block.strip().splitlines()[:5]
                short_summary = " ".join(first_lines)[:200] if first_lines else None

                chunk_id = f"{repo_id}:{rel_path}:L{start}-{end}"
                chunks.append(
                    CodeChunk(
                        id=str(chunk_id),
                        repo_id=repo_id,
                        file_path=rel_path,
                        symbol=symbol_name,
                        symbol_type=symbol_type,
                        start_line=start,
                        end_line=end,
                        code=code_block,
                        summary=short_summary,
                    )
                )

        # If we did not manage to create any chunks (e.g. file only has
        # imports), fall back to a generic chunk.
        if not chunks:
            return self._chunk_generic_file(repo_id, rel_path, text)

        return chunks

    def _chunk_generic_file(
        self, repo_id: str, rel_path: Path, text: str, max_lines: int = 200  # max_lines kept for signature compatibility
    ) -> List[CodeChunk]:
        """Create a single chunk for a non-Python file.

        为了避免「按固定行数切块」带来的割裂，这里对非 Python 文件
        采用整文件一个 CodeChunk 的策略（同时保留精简摘要）。
        这样对所有语言都适用，只是粒度相对粗一些。
        """

        lines = text.splitlines()
        total = len(lines)
        if total == 0:
            return []

        first_lines = text.strip().splitlines()[:5]
        short_summary = " ".join(first_lines)[:200] if first_lines else None

        chunk_id = f"{repo_id}:{rel_path}:L1-{total}"
        chunk = CodeChunk(
            id=str(chunk_id),
            repo_id=repo_id,
            file_path=rel_path,
            symbol=None,
            symbol_type=None,
            start_line=1,
            end_line=total,
            code=text,
            summary=short_summary,
        )

        return [chunk]
