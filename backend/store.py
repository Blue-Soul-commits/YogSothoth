from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


# 数据存放目录与文件
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DATA_DIR = os.path.join(_BASE_DIR, ".data")
_REPOS_DIR = os.path.join(_BASE_DIR, "repos")
_STORE_PATH = os.path.join(_DATA_DIR, "store.json")


def _ensure_dirs() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    os.makedirs(_REPOS_DIR, exist_ok=True)


@dataclass
class RepoRecord:
    id: int
    name: str
    owner: str
    url: str
    language: str
    stars: int
    description: str
    last_indexed: str  # YYYY-MM-DD
    group: str
    local_path: str


def _default_store() -> Dict[str, object]:
    return {"repos": [], "next_id": 1}


def _load_store() -> Dict[str, object]:
    _ensure_dirs()
    if not os.path.exists(_STORE_PATH):
        return _default_store()
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return _default_store()
            data.setdefault("repos", [])
            data.setdefault("next_id", 1)
            return data
    except Exception:
        return _default_store()


def _save_store(data: Dict[str, object]) -> None:
    _ensure_dirs()
    tmp = _STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _STORE_PATH)


def list_repos() -> List[Dict[str, object]]:
    data = _load_store()
    repos = data.get("repos", [])
    return list(repos)  # shallow copy


def get_repo_by_url(url: str) -> Optional[Dict[str, object]]:
    url_norm = url.strip().rstrip("/")
    for r in list_repos():
        if r.get("url", "").strip().rstrip("/") == url_norm:
            return r
    return None


def get_repo_by_id(repo_id: int) -> Optional[Dict[str, object]]:
    for r in list_repos():
        if int(r.get("id", -1)) == int(repo_id):
            return r
    return None


def _parse_repo_url(url: str) -> Tuple[str, str]:
    """
    支持 github/gitlab/gitee 等常见平台的 https 或 ssh 地址。
    返回 (owner, name)
    """
    u = url.strip()
    # SSH: git@github.com:owner/repo.git
    m = re.match(r"^git@([^:]+):([^/]+)/([^/]+?)(?:\.git)?$", u)
    if m:
        return m.group(2), m.group(3)
    # HTTPS: https://host/owner/repo(.git)?
    m = re.match(r"^https?://[^/]+/([^/]+)/([^/]+?)(?:\.git)?/?$", u)
    if m:
        return m.group(1), m.group(2)
    raise ValueError("无法解析仓库 URL，请提供类似 https://github.com/owner/repo 或 git@host:owner/repo.git 的地址")


def _detect_host(url: str) -> Optional[str]:
    u = url.strip().lower()
    if "github.com" in u:
        return "github"
    if "gitlab.com" in u:
        return "gitlab"
    if "gitee.com" in u:
        return "gitee"
    return None


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 6) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            if not data:
                return None
            return json.loads(data.decode("utf-8", "ignore"))
    except Exception:
        return None


def _fetch_stars(repo_url: str, owner: str, name: str, prev_stars: int = 0) -> int:
    """
    获取仓库 stars 数（无 Token，公共 API 配额有限）。
    Github: stargazers_count
    GitLab: star_count
    Gitee: stargazers_count（可能需要 Token，失败则回退）
    """
    host = _detect_host(repo_url or "")
    try:
        if host == "github":
            api = f"https://api.github.com/repos/{owner}/{name}"
            data = _http_get_json(
                api,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "python_frontend-indexer",
                },
            )
            if data and isinstance(data, dict):
                v = data.get("stargazers_count")
                if isinstance(v, int):
                    return v
        elif host == "gitlab":
            proj = urllib.parse.quote(f"{owner}/{name}", safe="")
            api = f"https://gitlab.com/api/v4/projects/{proj}"
            data = _http_get_json(
                api,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "python_frontend-indexer",
                },
            )
            if data and isinstance(data, dict):
                v = data.get("star_count")
                if isinstance(v, int):
                    return v
        elif host == "gitee":
            api = f"https://gitee.com/api/v5/repos/{owner}/{name}"
            data = _http_get_json(
                api,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "python_frontend-indexer",
                },
            )
            if data and isinstance(data, dict):
                # gitee 字段可能是 stargazers_count 或 stars
                v = data.get("stargazers_count") or data.get("stars")
                if isinstance(v, int):
                    return v
    except Exception:
        pass
    # 回退为之前的值，避免频繁抖动
    return int(prev_stars or 0)


def _lang_from_ext(ext: str) -> Optional[str]:
    ext = ext.lower().lstrip(".")
    mapping = {
        "py": "Python",
        "ts": "TypeScript",
        "tsx": "TypeScript",
        "js": "JavaScript",
        "jsx": "JavaScript",
        "go": "Go",
        "rs": "Rust",
        "java": "Java",
        "kt": "Kotlin",
        "kts": "Kotlin",
        "swift": "Swift",
        "c": "C",
        "h": "C",
        "cc": "C++",
        "cpp": "C++",
        "cxx": "C++",
        "hpp": "C++",
        "hh": "C++",
        "rb": "Ruby",
        "php": "PHP",
        "cs": "C#",
        "scala": "Scala",
        "m": "Objective-C",
        "mm": "Objective-C++",
        "r": "R",
        "dart": "Dart",
        "lua": "Lua",
        "sh": "Shell",
        "zsh": "Shell",
        "ps1": "PowerShell",
        "sql": "SQL",
        "html": "HTML",
        "css": "CSS",
        "scss": "CSS",
        "sass": "CSS",
        "vue": "Vue",
        "svelte": "Svelte",
        "md": "Markdown",
        "toml": "TOML",
        "yaml": "YAML",
        "yml": "YAML",
        "json": "JSON",
    }
    return mapping.get(ext)


def _detect_language(root: str, max_files: int = 4000) -> str:
    counts: Dict[str, int] = {}
    considered = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过常见大目录
        base = os.path.basename(dirpath).lower()
        if base in (".git", "node_modules", "dist", "build", "target", ".venv", "venv", "__pycache__"):
            continue
        for fn in filenames:
            if considered >= max_files:
                break
            ext = os.path.splitext(fn)[1]
            lang = _lang_from_ext(ext)
            if not lang:
                continue
            counts[lang] = counts.get(lang, 0) + 1
            considered += 1
        if considered >= max_files:
            break
    if not counts:
        return "Unknown"
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _read_description(root: str, max_len: int = 180) -> str:
    candidates = [
        "README.md",
        "README.MD",
        "README",
        "readme.md",
        "readme",
    ]
    for name in candidates:
        p = os.path.join(root, name)
        if os.path.exists(p) and os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    first = f.readline().strip()
                    if first:
                        return first[:max_len]
            except Exception:
                pass
    return "无描述"


def _dest_for_repo(owner: str, name: str) -> str:
    return os.path.join(_REPOS_DIR, owner, name)


def _git_clone(url: str, dest: str) -> None:
    # 若已存在仓库，尽量更新到最新
    if os.path.exists(dest) and os.path.isdir(os.path.join(dest, ".git")):
        try:
            subprocess.run(["git", "-C", dest, "fetch", "--all"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # 尝试优雅 reset 到远端默认分支；若失败，由异常分支处理
            subprocess.run(["git", "-C", dest, "reset", "--hard", "origin/HEAD"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return
        except subprocess.CalledProcessError:
            # fallback 为重新 clone（先删除目录）
            pass
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        # 目录存在但非 git 仓库，尝试清理
        try:
            import shutil

            shutil.rmtree(dest)
        except Exception:
            pass
    subprocess.run(
        ["git", "clone", "--single-branch", url, dest],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def index_repo(repo_url: str, group_name: str = "") -> RepoRecord:
    """
    克隆/更新仓库，检测语言/描述/Stars，写入本地 JSON 存储。
    返回入库的 RepoRecord。
    """
    if not repo_url or not isinstance(repo_url, str):
        raise ValueError("repoUrl 不能为空")
    owner, name = _parse_repo_url(repo_url)
    dest = _dest_for_repo(owner, name)

    # 执行 clone/更新
    _git_clone(repo_url, dest)

    language = _detect_language(dest)
    description = _read_description(dest)
    last_indexed = datetime.utcnow().date().isoformat()

    store = _load_store()
    repos: List[Dict[str, object]] = store.get("repos", [])
    existing = None
    for r in repos:
        if r.get("url", "").strip().rstrip("/") == repo_url.strip().rstrip("/"):
            existing = r
            break

    prev_stars = 0
    prev_group = ""
    if existing:
        try:
            prev_stars = int(existing.get("stars", 0) or 0)
        except Exception:
            prev_stars = 0
        prev_group = str(existing.get("group", "") or "")

    stars = _fetch_stars(repo_url, owner, name, prev_stars)

    if existing:
        existing.update(
            {
                "owner": owner,
                "name": name,
                "language": language,
                "description": description,
                "last_indexed": last_indexed,
                "group": group_name or prev_group,
                "local_path": dest,
                "stars": int(stars),
            }
        )
        record = existing
    else:
        new_id = int(store.get("next_id", 1))
        record = {
            "id": new_id,
            "name": name,
            "owner": owner,
            "url": repo_url,
            "language": language,
            "stars": int(stars),
            "description": description,
            "last_indexed": last_indexed,
            "group": group_name or "",
            "local_path": dest,
        }
        repos.append(record)
        store["next_id"] = new_id + 1

    store["repos"] = repos
    _save_store(store)

    return RepoRecord(**record)  # type: ignore[arg-type]


def attach_repo_to_group(repo_url: str, group_name: str) -> RepoRecord:
    """
    若仓库存在则更新 group，不存在则先索引再更新。
    """
    if not group_name:
        raise ValueError("groupName 不能为空")
    existing = get_repo_by_url(repo_url)
    if existing is None:
        return index_repo(repo_url, group_name)
    # 更新分组
    store = _load_store()
    for r in store.get("repos", []):
        if r.get("url", "").strip().rstrip("/") == repo_url.strip().rstrip("/"):
            r["group"] = group_name
            # 同时刷新索引时间（轻量更新）
            r["last_indexed"] = datetime.utcnow().date().isoformat()
            _save_store(store)
            return RepoRecord(**r)  # type: ignore[arg-type]
    # 意外情况兜底：重新索引
    return index_repo(repo_url, group_name)


def refresh_repo_by_id(repo_id: int) -> RepoRecord:
    """
    根据 ID 刷新仓库（拉取最新代码并更新元信息），保留原有分组。
    """
    existing = get_repo_by_id(int(repo_id))
    if not existing:
        raise ValueError("指定 repoId 不存在")
    return index_repo(str(existing["url"]), str(existing.get("group", "") or ""))


def refresh_repo_by_url(repo_url: str) -> RepoRecord:
    """
    根据 URL 刷新仓库，若不存在则执行新索引。
    """
    existing = get_repo_by_url(repo_url)
    group_name = str(existing.get("group", "") or "") if existing else ""
    return index_repo(repo_url, group_name)


def summarize_groups(repos: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    summary: Dict[str, Dict[str, object]] = {}
    for repo in repos:
        group = str(repo.get("group", "") or "")
        lang = str(repo.get("language", "") or "")
        last = str(repo.get("last_indexed", "") or "")
        g = summary.setdefault(group, {"group": group, "count": 0, "languages": set(), "latest_indexed": last})
        g["count"] += 1
        if lang:
            if isinstance(g["languages"], set):
                g["languages"].add(lang)
            else:
                g["languages"] = {lang}
        if last and last > str(g["latest_indexed"]):
            g["latest_indexed"] = last
    # finalize
    for item in summary.values():
        langs = item.get("languages", set())
        if isinstance(langs, set):
            item["languages"] = ", ".join(sorted(langs))
    # 排序：组名为空置后
    def _key(d: Dict[str, object]) -> Tuple[int, str]:
        name = str(d.get("group", ""))
        return (1 if name == "" else 0, name)
    return sorted(summary.values(), key=_key)