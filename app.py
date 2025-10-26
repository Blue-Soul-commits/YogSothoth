from __future__ import annotations

import os
import sys
from math import ceil
from typing import Any, Dict, List

from flask import Flask, render_template, request, url_for

# 兼容从子目录直接运行（python app.py）与包方式（python -m python_frontend.app）
_CURR_DIR = os.path.dirname(__file__)
_PARENT_DIR = os.path.abspath(os.path.join(_CURR_DIR, os.pardir))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from python_frontend.backend import bp as backend_bp
from python_frontend.backend.store import (
    list_repos as store_list_repos,
    summarize_groups as store_summarize_groups,
)

PAGE_SIZE = 20  # 4 列 × 5 行


def paginate(items: List[Dict[str, Any]], page: int, page_size: int) -> Dict[str, Any]:
    total_items = len(items)
    total_pages = max(1, ceil(total_items / page_size))
    current_page = max(1, min(page, total_pages))

    start = (current_page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total_pages": total_pages,
        "current_page": current_page,
        "has_prev": current_page > 1,
        "has_next": current_page < total_pages,
    }


def create_app() -> Flask:
    app = Flask(__name__, template_folder="frontend/templates", static_folder="frontend/static")

    # 注册后端 API 蓝图（索引/分组等）
    app.register_blueprint(backend_bp)

    @app.route("/", methods=["GET"])
    def index():
        view_mode = request.args.get("view", "repos")
        search_query = (request.args.get("q") or "").strip().lower()
        page = request.args.get("page", "1")

        try:
            page_number = int(page)
        except ValueError:
            page_number = 1

        # 使用真实存储的数据，而非虚拟数据
        all_repos: List[Dict[str, Any]] = store_list_repos()

        filtered_repos = all_repos
        if search_query:
            def norm(v: Any) -> str:
                return str(v or "").lower()
            filtered_repos = [
                r for r in all_repos
                if search_query in norm(r.get("name"))
                or search_query in norm(r.get("owner"))
                or search_query in norm(r.get("description"))
                or search_query in norm(r.get("group"))
            ]

        pagination = paginate(filtered_repos, page_number, PAGE_SIZE)

        groups_summary = store_summarize_groups(filtered_repos)
        # 提供初始数据给前端（现在是“真实”数据），稍后前端会完全依赖 /api* 拉取
        all_groups_payload = store_summarize_groups(all_repos)

        return render_template(
            "index.html",
            view_mode=view_mode,
            search_query=search_query,
            repos=pagination["items"],
            pagination=pagination,
            groups_summary=groups_summary,
            all_repos=all_repos,
            all_groups=all_groups_payload,
        )

    @app.template_global()
    def page_url(page: int, view_mode: str, search_query: str) -> str:
        return url_for("index", page=page, view=view_mode, q=search_query)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)