from __future__ import annotations

from dataclasses import asdict
from typing import Any

from flask import Blueprint, jsonify, request

from .store import (
    list_repos as store_list_repos,
    summarize_groups as store_summarize_groups,
    index_repo as store_index_repo,
    attach_repo_to_group as store_attach_repo_to_group,
    refresh_repo_by_id as store_refresh_by_id,
    refresh_repo_by_url as store_refresh_by_url,
)

bp = Blueprint("backend_api", __name__, url_prefix="/api")


@bp.get("/repos")
def list_repos() -> Any:
    try:
        items = store_list_repos()
        q = (request.args.get("q") or "").strip().lower()
        if q:
            def norm(v: Any) -> str:
                return str(v or "").lower()
            items = [
                r for r in items
                if q in norm(r.get("name"))
                or q in norm(r.get("owner"))
                or q in norm(r.get("description"))
                or q in norm(r.get("group"))
            ]
        return jsonify({"items": items, "total": len(items)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.get("/groups")
def list_groups() -> Any:
    try:
        repos = store_list_repos()
        groups = store_summarize_groups(repos)
        q = (request.args.get("q") or "").strip().lower()
        if q:
            def norm(v: Any) -> str:
                return str(v or "").lower()
            groups = [
                g for g in groups
                if q in norm(g.get("group"))
                or q in norm(g.get("languages"))
                or q in norm(g.get("latest_indexed"))
            ]
        return jsonify({"items": groups, "total": len(groups)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/index_repo")
def index_repo() -> Any:
    """
    根据请求索引仓库：
    - 当 type == 'single' 时，强制不设置 group（即不创建仓库组）
    - 当 type == 'group' 且提供 groupName 时，写入对应分组
    """
    try:
        payload = request.get_json(silent=True) or {}
        repo_url = str(payload.get("repoUrl") or "").strip()
        repo_type = str(payload.get("type") or "single").strip().lower()
        group_name = str(payload.get("groupName") or "").strip()

        if not repo_url:
            return jsonify({"error": "repoUrl 不能为空"}), 400

        # 单仓库索引时，不创建组
        if repo_type != "group":
            group_name = ""

        rec = store_index_repo(repo_url, group_name)
        item = asdict(rec)
        return jsonify({
            "indexed": True,
            "status": "indexed",
            "type": repo_type,
            "repoId": item.get("id"),
            "repoUrl": item.get("url"),
            "item": item,
        }), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        msg = str(e)
        try:
            import subprocess
            if isinstance(e, subprocess.CalledProcessError):  # type: ignore
                stderr = e.stderr.decode("utf-8", "ignore") if e.stderr else ""
                stdout = e.stdout.decode("utf-8", "ignore") if e.stdout else ""
                msg = f"git error: {stderr or stdout or e}"
        except Exception:
            pass
        return jsonify({"error": msg}), 500


@bp.post("/groups/upsert")
def upsert_group() -> Any:
    """
    将仓库加入指定组；若仓库不存在则先索引（保留真实 stars），再入组。
    """
    try:
        payload = request.get_json(silent=True) or {}
        repo_url = str(payload.get("repoUrl") or "").strip()
        group_name = str(payload.get("groupName") or "").strip()
        if not repo_url or not group_name:
            return jsonify({"error": "repoUrl 与 groupName 均不能为空"}), 400

        rec = store_attach_repo_to_group(repo_url, group_name)
        item = asdict(rec)
        return jsonify({"ok": True, "action": "upsert_group", "item": item}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.post("/repos/<int:repo_id>/refresh")
def refresh_repo(repo_id: int) -> Any:
    """
    刷新指定 ID 仓库：拉取最新代码、更新语言/描述/Stars 与 last_indexed。
    """
    try:
        rec = store_refresh_by_id(int(repo_id))
        item = asdict(rec)
        return jsonify({"ok": True, "status": "refreshed", "item": item}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        msg = str(e)
        try:
            import subprocess
            if isinstance(e, subprocess.CalledProcessError):  # type: ignore
                stderr = e.stderr.decode("utf-8", "ignore") if e.stderr else ""
                stdout = e.stdout.decode("utf-8", "ignore") if e.stdout else ""
                msg = f"git error: {stderr or stdout or e}"
        except Exception:
            pass
        return jsonify({"error": msg}), 500


@bp.post("/repos/refresh")
def refresh_repo_by_url() -> Any:
    """
    备用接口：通过 URL 刷新仓库（若不存在则索引）。
    """
    try:
        payload = request.get_json(silent=True) or {}
        repo_url = str(payload.get("repoUrl") or "").strip()
        if not repo_url:
            return jsonify({"error": "repoUrl 不能为空"}), 400
        rec = store_refresh_by_url(repo_url)
        item = asdict(rec)
        return jsonify({"ok": True, "status": "refreshed", "item": item}), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500