from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from ..core.models import CodeChunk, Repo, RepoGroup


def _dt_to_str(value: Optional[datetime]) -> Optional[str]:
    """Serialize datetime to ISO string for SQLite."""

    return value.isoformat() if value is not None else None


def _dt_from_str(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string from SQLite."""

    if not value:
        return None
    return datetime.fromisoformat(value)


class Database:
    """Thin wrapper around SQLite for core metadata and code chunks.

    This wrapper focuses on simple, explicit SQL so it remains easy
    to debug and reason about. It can be swapped for a more fully
    fledged ORM later if needed.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False so the connection can be shared if needed.
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.ensure_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def ensure_schema(self) -> None:
        """Create tables if they do not exist yet."""

        cur = self._conn.cursor()

        # Repository metadata
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS repos (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                git_url TEXT NOT NULL,
                default_branch TEXT,
                local_path TEXT,
                indexed_at TEXT,
                summary TEXT
            )
            """
        )

        # Repository groups. repo_ids is stored as JSON for now.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS repo_groups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                repo_ids_json TEXT NOT NULL,
                indexed_at TEXT
            )
            """
        )

        # Code chunks for retrieval.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS code_chunks (
                id TEXT PRIMARY KEY,
                repo_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                symbol TEXT,
                symbol_type TEXT,
                start_line INTEGER,
                end_line INTEGER,
                code TEXT,
                summary TEXT
            )
            """
        )

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_code_chunks_repo_id ON code_chunks(repo_id)"
        )

        # Embeddings for code chunks. We keep provider/model so multiple
        # backends can coexist if needed.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_embeddings (
                chunk_id TEXT NOT NULL,
                repo_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                PRIMARY KEY (chunk_id, provider, model)
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_repo
            ON chunk_embeddings(repo_id, provider, model)
            """
        )

        # Conversations for multi-turn QA.
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,       -- 'repo' or 'group'
                target_id TEXT NOT NULL,   -- repo_id or group_id
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,        -- 'user' or 'assistant'
                content TEXT NOT NULL,
                created_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_messages_conv
            ON conversation_messages(conversation_id, id)
            """
        )

        self._conn.commit()

    # ------------------------------------------------------------------
    # Repo helpers
    # ------------------------------------------------------------------

    def upsert_repo(self, repo: Repo) -> None:
        """Insert or update a repository record."""

        self._conn.execute(
            """
            INSERT INTO repos (id, name, git_url, default_branch, local_path, indexed_at, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                git_url=excluded.git_url,
                default_branch=excluded.default_branch,
                local_path=excluded.local_path,
                indexed_at=excluded.indexed_at,
                summary=excluded.summary
            """,
            (
                repo.id,
                repo.name,
                repo.git_url,
                repo.default_branch,
                str(repo.local_path) if repo.local_path else None,
                _dt_to_str(repo.indexed_at),
                repo.summary,
            ),
        )
        self._conn.commit()

    def get_repo(self, repo_id: str) -> Optional[Repo]:
        """Return a single repository by id, or None if missing."""

        cur = self._conn.execute("SELECT * FROM repos WHERE id = ?", (repo_id,))
        row = cur.fetchone()
        if row is None:
            return None

        return Repo(
            id=row["id"],
            name=row["name"],
            git_url=row["git_url"],
            default_branch=row["default_branch"] or "main",
            local_path=Path(row["local_path"]) if row["local_path"] else Path(),
            indexed_at=_dt_from_str(row["indexed_at"]),
            summary=row["summary"],
        )

    def list_repos(self) -> List[Repo]:
        """Return all repositories ordered by id."""

        cur = self._conn.execute("SELECT * FROM repos ORDER BY id")
        rows = cur.fetchall()
        return [
            Repo(
                id=row["id"],
                name=row["name"],
                git_url=row["git_url"],
                default_branch=row["default_branch"] or "main",
                local_path=Path(row["local_path"]) if row["local_path"] else Path(),
                indexed_at=_dt_from_str(row["indexed_at"]),
                summary=row["summary"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # RepoGroup helpers
    # ------------------------------------------------------------------

    def upsert_repo_group(self, group: RepoGroup) -> None:
        """Insert or update a repository group record."""

        repo_ids_json = json.dumps(group.repo_ids)
        self._conn.execute(
            """
            INSERT INTO repo_groups (id, name, description, repo_ids_json, indexed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                repo_ids_json=excluded.repo_ids_json,
                indexed_at=excluded.indexed_at
            """,
            (
                group.id,
                group.name,
                group.description,
                repo_ids_json,
                _dt_to_str(group.indexed_at),
            ),
        )
        self._conn.commit()

    def get_repo_group(self, group_id: str) -> Optional[RepoGroup]:
        """Return a single repository group by id, or None if missing."""

        cur = self._conn.execute(
            "SELECT * FROM repo_groups WHERE id = ?", (group_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None

        repo_ids = json.loads(row["repo_ids_json"]) if row["repo_ids_json"] else []
        return RepoGroup(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            repo_ids=repo_ids,
            indexed_at=_dt_from_str(row["indexed_at"]),
        )

    def list_repo_groups(self) -> List[RepoGroup]:
        """Return all repository groups ordered by id."""

        cur = self._conn.execute("SELECT * FROM repo_groups ORDER BY id")
        rows = cur.fetchall()
        groups: List[RepoGroup] = []
        for row in rows:
            repo_ids = json.loads(row["repo_ids_json"]) if row["repo_ids_json"] else []
            groups.append(
                RepoGroup(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"] or "",
                    repo_ids=repo_ids,
                    indexed_at=_dt_from_str(row["indexed_at"]),
                )
            )
        return groups

    # ------------------------------------------------------------------
    # CodeChunk helpers (minimal for now)
    # ------------------------------------------------------------------

    def replace_chunks_for_repo(self, repo_id: str, chunks: Iterable[CodeChunk]) -> None:
        """Replace all code chunks for a repo with the given iterable."""

        cur = self._conn.cursor()
        cur.execute("DELETE FROM code_chunks WHERE repo_id = ?", (repo_id,))

        rows = [
            (
                chunk.id,
                chunk.repo_id,
                str(chunk.file_path),
                chunk.symbol,
                chunk.symbol_type,
                int(chunk.start_line),
                int(chunk.end_line),
                chunk.code,
                chunk.summary,
            )
            for chunk in chunks
        ]
        if rows:
            cur.executemany(
                """
                INSERT INTO code_chunks (
                    id,
                    repo_id,
                    file_path,
                    symbol,
                    symbol_type,
                    start_line,
                    end_line,
                    code,
                    summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

        self._conn.commit()

    def list_chunks_for_repo(self, repo_id: str) -> List[CodeChunk]:
        """Return all code chunks for a given repo."""

        cur = self._conn.execute(
            "SELECT * FROM code_chunks WHERE repo_id = ? ORDER BY file_path, start_line",
            (repo_id,),
        )
        rows = cur.fetchall()
        return [
            CodeChunk(
                id=row["id"],
                repo_id=row["repo_id"],
                file_path=Path(row["file_path"]),
                symbol=row["symbol"],
                symbol_type=row["symbol_type"],
                start_line=int(row["start_line"] or 1),
                end_line=int(row["end_line"] or 1),
                code=row["code"] or "",
                summary=row["summary"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    def upsert_chunk_embeddings(
        self,
        provider: str,
        model: str,
        items: Iterable[tuple[CodeChunk, list[float]]],
    ) -> None:
        """Insert or update embeddings for the given chunks."""

        rows = [
            (
                chunk.id,
                chunk.repo_id,
                provider,
                model,
                json.dumps(vector),
            )
            for chunk, vector in items
        ]
        if not rows:
            return

        self._conn.executemany(
            """
            INSERT INTO chunk_embeddings (
                chunk_id,
                repo_id,
                provider,
                model,
                embedding_json
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chunk_id, provider, model) DO UPDATE SET
                repo_id=excluded.repo_id,
                embedding_json=excluded.embedding_json
            """,
            rows,
        )
        self._conn.commit()

    def get_chunk_embeddings(
        self,
        repo_ids: list[str],
        provider: str,
        model: str,
    ) -> list[tuple[CodeChunk, list[float]]]:
        """Return (CodeChunk, embedding) pairs for the given repos."""

        if not repo_ids:
            return []

        placeholders = ",".join("?" for _ in repo_ids)
        sql = f"""
            SELECT
                ce.chunk_id,
                ce.embedding_json,
                cc.repo_id,
                cc.file_path,
                cc.symbol,
                cc.symbol_type,
                cc.start_line,
                cc.end_line,
                cc.code,
                cc.summary
            FROM chunk_embeddings AS ce
            JOIN code_chunks AS cc ON cc.id = ce.chunk_id
            WHERE ce.provider = ?
              AND ce.model = ?
              AND ce.repo_id IN ({placeholders})
        """
        cur = self._conn.execute(sql, (provider, model, *repo_ids))
        rows = cur.fetchall()

        results: list[tuple[CodeChunk, list[float]]] = []
        for row in rows:
            chunk = CodeChunk(
                id=row["chunk_id"],
                repo_id=row["repo_id"],
                file_path=Path(row["file_path"]),
                symbol=row["symbol"],
                symbol_type=row["symbol_type"],
                start_line=int(row["start_line"] or 1),
                end_line=int(row["end_line"] or 1),
                code=row["code"] or "",
                summary=row["summary"],
            )
            vector = json.loads(row["embedding_json"])
            results.append((chunk, vector))
        return results

    # ------------------------------------------------------------------
    # Conversation helpers (multi-turn QA)
    # ------------------------------------------------------------------

    def ensure_conversation(
        self, conv_id: str, scope: str, target_id: str
    ) -> None:
        """Create a conversation record if it does not exist."""

        now = _dt_to_str(datetime.utcnow())
        self._conn.execute(
            """
            INSERT INTO conversations (id, scope, target_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                scope=excluded.scope,
                target_id=excluded.target_id,
                updated_at=excluded.updated_at
            """,
            (conv_id, scope, target_id, now, now),
        )
        self._conn.commit()

    def add_conversation_message(
        self, conv_id: str, role: str, content: str
    ) -> None:
        """Append a message to a conversation."""

        now = _dt_to_str(datetime.utcnow())
        self._conn.execute(
            """
            INSERT INTO conversation_messages (
                conversation_id,
                role,
                content,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (conv_id, role, content, now),
        )
        self._conn.commit()

    def get_conversation_messages(
        self,
        conv_id: str,
        limit: int = 20,
    ) -> list[dict[str, str]]:
        """Return messages for a given conversation ordered by insertion."""

        cur = self._conn.execute(
            """
            SELECT role, content
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (conv_id, limit),
        )
        rows = cur.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
