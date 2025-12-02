from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import re
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..config.settings import get_settings
from ..core.indexer import Indexer
from ..core.models import Repo, RepoGroup
from ..core.outline_generator import OutlineGenerator
from ..core.qa_service import QAService
from ..core.repo_manager import RepoManager
from ..storage.db import Database


app = FastAPI(title="gitnar Admin API")

# Enable CORS so that the React frontend (Vite dev server) can call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Infrastructure wiring
# ---------------------------------------------------------------------------


_settings = get_settings()


def _db_path_from_url(db_url: str) -> Path:
    """Very small helper to turn a SQLite URL into a path.

    We accept either a raw filesystem path or a URL of the form
    ``sqlite:///relative/or/absolute/path``.
    """

    if db_url.startswith("sqlite:///"):
        return Path(db_url.replace("sqlite:///", "", 1)).resolve()
    return Path(db_url).resolve()


_db = Database(_db_path_from_url(_settings.db_url))
_repo_manager = RepoManager(_settings.repos_root)
_indexer = Indexer()
_outline_generator = OutlineGenerator()
_qa_service = QAService(_db)


def _derive_repo_id(git_url: str) -> str:
    """Derive a simple repo id from a git URL when the client doesn't provide one."""

    path = urlparse(git_url).path or git_url
    name_part = path.rstrip("/").split("/")[-1]
    if name_part.endswith(".git"):
        name_part = name_part[: -len(".git")]
    # Replace anything that is not alphanumeric or dash with dash.
    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", name_part).strip("-").lower()
    return slug or "repo"


def _slugify(value: str) -> str:
    """Generate a simple slug suitable for ids from an arbitrary string."""

    slug = re.sub(r"[^a-zA-Z0-9-]+", "-", value).strip("-").lower()
    return slug or "group"


class RepoCreateRequest(BaseModel):
    git_url: str
    id: Optional[str] = None
    name: Optional[str] = None
    default_branch: Optional[str] = None
    branch: Optional[str] = None  # optional checkout/clone branch
    summary: Optional[str] = None


class RepoResponse(BaseModel):
    id: str
    name: str
    git_url: str
    default_branch: str
    local_path: Optional[str] = None
    indexed_at: Optional[datetime] = None
    summary: Optional[str] = None


class RepoGroupResponse(BaseModel):
    id: str
    name: str
    description: str
    repo_ids: List[str]
    indexed_at: Optional[datetime] = None


class ReindexResponse(BaseModel):
    repo: RepoResponse
    chunks_indexed: int
    outline_path: Optional[str] = None


class RepoQARequest(BaseModel):
    repo_id: str
    question: str
    top_k: int = 10
    session_id: Optional[str] = None


class GroupQARequest(BaseModel):
    group_id: str
    question: str
    top_k_per_repo: int = 5
    session_id: Optional[str] = None


class QAResponse(BaseModel):
    answer_text: str
    references: List[Dict[str, Any]]


class OutlineResponse(BaseModel):
    repo_id: str
    outline: str


class RepoGroupCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    repo_ids: List[str] = []


class RepoGroupUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    repo_ids: Optional[List[str]] = None


def _repo_to_response(repo: Repo) -> RepoResponse:
    return RepoResponse(
        id=repo.id,
        name=repo.name,
        git_url=repo.git_url,
        default_branch=repo.default_branch,
        local_path=str(repo.local_path) if repo.local_path else None,
        indexed_at=repo.indexed_at,
        summary=repo.summary,
    )


def _group_to_response(group: RepoGroup) -> RepoGroupResponse:
    return RepoGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        repo_ids=group.repo_ids,
        indexed_at=group.indexed_at,
    )


def _run_full_reindex(repo_id: str) -> None:
    """Heavy reindex job: run in the background so HTTP requests return quickly."""

    repo = _db.get_repo(repo_id)
    if repo is None or not repo.local_path:
        return

    repo_root = Path(repo.local_path)
    chunks = _indexer.index_repo(repo_id=repo.id, repo_root=repo_root)

    # Persist chunks in the DB.
    _db.replace_chunks_for_repo(repo.id, chunks)

    # Compute and persist embeddings for the new chunks.
    _indexer.index_chunks(chunks)

    # Generate and save outline markdown.
    outline_md = _outline_generator.generate_outline(repo.id, chunks)
    _outline_generator.save_outline(
        repo.id, _settings.outlines_root, outline_md
    )

    # Update metadata.
    repo.indexed_at = datetime.utcnow()
    _db.upsert_repo(repo)


@app.post("/qa/repo", response_model=QAResponse)
async def qa_repo(payload: RepoQARequest) -> QAResponse:
    """QA endpoint for a single repository using embedding + LLM pipeline."""

    answer = _qa_service.ask_repo_llm(
        repo_id=payload.repo_id,
        question=payload.question,
        top_k=payload.top_k,
        session_id=payload.session_id,
    )
    return QAResponse(answer_text=answer.answer_text, references=answer.references)


@app.post("/qa/repo-group", response_model=QAResponse)
async def qa_repo_group(payload: GroupQARequest) -> QAResponse:
    """QA endpoint for a repository group using embedding + LLM pipeline."""

    answer = _qa_service.ask_repo_group_llm(
        group_id=payload.group_id,
        question=payload.question,
        top_k_per_repo=payload.top_k_per_repo,
        session_id=payload.session_id,
    )
    return QAResponse(answer_text=answer.answer_text, references=answer.references)


@app.get("/repos/{repo_id}/outline", response_model=OutlineResponse)
async def get_outline(repo_id: str) -> OutlineResponse:
    """Return LLM-generated outline markdown for a repo.

    如果尚未生成大纲（大纲文件不存在），提示用户先执行重建索引。
    """

    path = _settings.outlines_root / f"{repo_id}.md"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Outline not found. Please reindex this repository first.",
        )

    outline_md = path.read_text(encoding="utf-8")
    return OutlineResponse(repo_id=repo_id, outline=outline_md)


@app.post("/repos/{repo_id}/reindex", response_model=ReindexResponse)
async def reindex_repo(repo_id: str, background_tasks: BackgroundTasks) -> ReindexResponse:
    """Schedule a rebuild of code chunks and outline for the given repo.

    The heavy work is delegated to a background task so this endpoint
    can return quickly even for大型仓库. 返回值中 chunks_indexed / outline_path
    仅表示「任务已接收」，具体值会在任务完成后写入 DB 和大纲文件。
    """

    repo = _db.get_repo(repo_id)
    if repo is None or not repo.local_path:
        raise HTTPException(status_code=404, detail=f"Unknown or uninitialized repo: {repo_id}")

    # 将完整重建任务挂到后台，当前请求快速返回。
    background_tasks.add_task(_run_full_reindex, repo.id)

    return ReindexResponse(
        repo=_repo_to_response(repo),
        chunks_indexed=0,
        outline_path=None,
    )


@app.get("/health")
async def health() -> Dict[str, str]:
    """Simple health check endpoint."""

    return {"status": "ok"}


@app.post("/repos", response_model=RepoResponse)
async def create_repo(payload: RepoCreateRequest) -> RepoResponse:
    """Create or update a repo record and clone/update the local git repo.

    This is the main entrypoint the frontend will use when a user adds a
    new GitHub repository. The heavy lifting is done by ``RepoManager``
    and the result is persisted via ``Database``.
    """

    repo_id = payload.id or _derive_repo_id(payload.git_url)
    name = payload.name or repo_id
    default_branch = payload.default_branch or "main"

    repo = Repo(
        id=repo_id,
        name=name,
        git_url=payload.git_url,
        default_branch=default_branch,
    )
    if payload.summary:
        repo.summary = payload.summary

    # Clone or update the local git repository.
    local_path = _repo_manager.clone_or_update(repo, branch=payload.branch)
    repo.local_path = local_path

    # Persist metadata.
    _db.upsert_repo(repo)

    return _repo_to_response(repo)


@app.get("/repos", response_model=List[RepoResponse])
async def list_repos() -> List[RepoResponse]:
    """List repositories known to the system."""

    repos = _db.list_repos()
    return [_repo_to_response(r) for r in repos]


@app.get("/repo-groups", response_model=List[RepoGroupResponse])
async def list_repo_groups() -> List[RepoGroupResponse]:
    """List repository groups configured in the system."""

    groups = _db.list_repo_groups()
    return [_group_to_response(g) for g in groups]


@app.post("/repo-groups", response_model=RepoGroupResponse)
async def create_repo_group(payload: RepoGroupCreateRequest) -> RepoGroupResponse:
    """Create a new repository group."""

    group_id = payload.id or _slugify(payload.name)
    description = payload.description or ""

    group = RepoGroup(
        id=group_id,
        name=payload.name,
        description=description,
        repo_ids=list(payload.repo_ids),
    )

    _db.upsert_repo_group(group)
    return _group_to_response(group)


@app.patch("/repo-groups/{group_id}", response_model=RepoGroupResponse)
async def update_repo_group(
    group_id: str, payload: RepoGroupUpdateRequest
) -> RepoGroupResponse:
    """Update an existing repository group."""

    existing = _db.get_repo_group(group_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Repository group not found")

    if payload.name is not None:
        existing.name = payload.name
    if payload.description is not None:
        existing.description = payload.description
    if payload.repo_ids is not None:
        existing.repo_ids = list(payload.repo_ids)

    _db.upsert_repo_group(existing)
    return _group_to_response(existing)
