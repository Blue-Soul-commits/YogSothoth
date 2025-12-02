from __future__ import annotations

from typing import Iterable, List, Tuple
import math

from ..core.embedding_client import EmbeddingClient
from ..core.models import CodeChunk
from .db import Database


class VectorStore:
    """Embedding-based vector store over code chunks.

    默认使用 models 配置中声明的 embedding 模型，将 CodeChunk 的
    summary + code 向量化，并和问题的向量做余弦相似度检索。
    """

    def __init__(self, db: Database, embedding_client: EmbeddingClient | None = None) -> None:
        self._db = db
        self._embedding_client = embedding_client or EmbeddingClient.from_default_config()

    # Public API ---------------------------------------------------------

    def add_chunks(self, chunks: Iterable[CodeChunk]) -> None:
        """Compute and persist embeddings for the given chunks.

        预期在重建索引（reindex）后被调用：调用方已经通过 Database
        写入了 code_chunks 表，这里只负责为对应 chunk 生成 embedding，
        并写入 chunk_embeddings 表。
        """

        chunks_list = list(chunks)
        if not chunks_list:
            return

        provider = self._embedding_client.config.get_default_provider()
        model_name = provider.models.embedding

        # 为避免超过 embedding 模型的上下文长度限制，且控制单次请求
        # 的体积，这里对每个 chunk 文本做字符级截断，并按批次调用
        # embedding 服务。
        max_chars = 8000  # 单个 chunk 最多使用的字符数
        batch_size = 32   # 每批最多处理的 chunk 数

        for i in range(0, len(chunks_list), batch_size):
            batch = chunks_list[i : i + batch_size]
            texts: list[str] = []
            for c in batch:
                full_text = (c.summary or "") + "\n" + c.code
                if len(full_text) > max_chars:
                    full_text = full_text[:max_chars]
                texts.append(full_text)

            vectors = self._embedding_client.embed_texts(texts)
            if len(vectors) != len(batch):
                raise RuntimeError(
                    "Embedding service returned unexpected number of vectors "
                    f"(expected {len(batch)}, got {len(vectors)})"
                )

            items = list(zip(batch, vectors))
            self._db.upsert_chunk_embeddings(
                provider=provider.name,
                model=model_name,
                items=items,
            )

    def search(
        self, repo_ids: List[str], query: str, top_k: int = 10
    ) -> List[Tuple[CodeChunk, float]]:
        """Return top_k code chunks with similarity scores using embeddings."""

        if not query or not repo_ids:
            return []

        provider = self._embedding_client.config.get_default_provider()
        model_name = provider.models.embedding

        # 1) 获取指定 repo_ids 下所有 chunk 的 embedding。
        chunk_embs = self._db.get_chunk_embeddings(
            repo_ids=repo_ids,
            provider=provider.name,
            model=model_name,
        )
        if not chunk_embs:
            return []

        chunks, vectors = zip(*chunk_embs)

        # 2) 为 query 生成 embedding。
        q_vecs = self._embedding_client.embed_texts([query])
        if not q_vecs:
            return []
        q_vec = q_vecs[0]

        # 3) 计算余弦相似度。
        q_norm = math.sqrt(sum(v * v for v in q_vec)) or 1.0

        scored: List[Tuple[CodeChunk, float]] = []
        for chunk, vec in zip(chunks, vectors):
            c_norm = math.sqrt(sum(v * v for v in vec))
            if c_norm == 0.0:
                score = 0.0
            else:
                dot = sum(q * c for q, c in zip(q_vec, vec))
                score = dot / (q_norm * c_norm) if dot > 0.0 else 0.0
            scored.append((chunk, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]
