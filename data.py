from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class IndexedRepository:
    """索引仓库实体，包含基本展示字段。"""

    id: int
    name: str
    owner: str
    language: str
    stars: int
    description: str
    last_indexed: str  # ISO 日期字符串
    group: str


def load_mock_repositories() -> List[IndexedRepository]:
    """提供虚拟索引仓库数据，后续可替换为真实 MCP 接口。"""
    mock_data: Iterable[IndexedRepository] = (
        IndexedRepository(
            id=idx,
            name=f"deep-project-{idx}",
            owner=f"owner-{idx % 7}",
            language=["Python", "TypeScript", "Go", "Rust"][idx % 4],
            stars=1200 - idx * 3,
            description="探索 RAG 与多模型协同的实验项目，展示代码索引结果。",
            last_indexed=f"2025-10-{(idx % 28) + 1:02d}",
            group=["core-services", "experiments", "community"][idx % 3],
        )
        for idx in range(1, 51)
    )
    return list(mock_data)