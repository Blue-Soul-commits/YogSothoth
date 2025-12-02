import React, { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { OutlineResponse, Repo } from "../api/types";

export interface RepoOutlinePageProps {
  repo: Repo;
  onBack: () => void;
  onEnterChat: () => void;
}

function parseOwnerFromGitUrl(url: string): string {
  try {
    const u = new URL(url);
    const parts = u.pathname.replace(/^\//, "").split("/");
    return parts[0] || "unknown";
  } catch {
    return "unknown";
  }
}

export const RepoOutlinePage: React.FC<RepoOutlinePageProps> = ({
  repo,
  onBack,
  onEnterChat
}) => {
  const [outline, setOutline] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiClient.get<OutlineResponse>(
          `/repos/${encodeURIComponent(repo.id)}/outline`
        );
        setOutline(res.data.outline);
      } catch (err: any) {
        setError(
          `加载大纲失败: ${err?.message ?? String(
            err
          )}，请确认已对该仓库执行过重建索引。`
        );
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [repo.id]);

  const owner = parseOwnerFromGitUrl(repo.git_url);

  return (
    <div>
      {/* 顶部导航 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 14
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            fontSize: 12,
            borderRadius: 999,
            border: "1px solid #444",
            background: "transparent",
            color: "#e5e5e5",
            padding: "3px 12px",
            cursor: "pointer"
          }}
        >
          ← 返回仓库列表
        </button>
        <button
          type="button"
          onClick={onEnterChat}
          style={{
            fontSize: 12,
            borderRadius: 999,
            border: "1px solid #f97316",
            background: "#1f1307",
            color: "#fde68a",
            padding: "4px 12px",
            cursor: "pointer"
          }}
        >
          进入问答页面
        </button>
      </div>

      {/* 仓库信息 + 元数据 */}
      <section
        style={{
          borderRadius: 14,
          border: "1px solid #262626",
          background: "rgba(10,10,10,0.9)",
          padding: "12px 16px",
          marginBottom: 12
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
            marginBottom: 6
          }}
        >
          <div>
            <h2 style={{ marginBottom: 4, fontSize: 18 }}>
              {repo.name || repo.id}
            </h2>
            <div style={{ fontSize: 12, color: "#a3a3a3" }}>
              拥有者：{owner}
            </div>
          </div>
          <div
            style={{
              textAlign: "right",
              fontSize: 12,
              color: "#a3a3a3",
              minWidth: 180
            }}
          >
            <div>索引时间：{repo.indexed_at ?? "未索引"}</div>
            <div style={{ marginTop: 2 }}>ID：{repo.id}</div>
          </div>
        </div>
        <div
          style={{
            marginTop: 4,
            fontSize: 12,
            color: "#737373",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis"
          }}
          title={repo.git_url}
        >
          Git URL：{repo.git_url}
        </div>
      </section>

      {/* 大纲展示区域 */}
      <section
        style={{
          borderRadius: 14,
          border: "1px solid #262626",
          background: "rgba(7,7,7,0.9)",
          padding: "12px 14px",
          maxHeight: 460,
          overflowY: "auto"
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 8
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 500 }}>仓库大纲</span>
          <span style={{ fontSize: 11, color: "#737373" }}>
            由 LLM 根据当前索引生成，用于快速理解仓库结构
          </span>
        </div>

        {loading && <p style={{ fontSize: 13 }}>加载中…</p>}
        {error && (
          <p style={{ color: "red", fontSize: 13, whiteSpace: "pre-wrap" }}>
            {error}
          </p>
        )}

        {!loading && !error && outline && (
          <pre
            style={{
              marginTop: 4,
              fontSize: 13,
              lineHeight: 1.55,
              whiteSpace: "pre-wrap",
              fontFamily:
                'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
            }}
          >
            {outline}
          </pre>
        )}
      </section>
    </div>
  );
};

