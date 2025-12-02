import React, { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { Repo } from "../api/types";

export interface ReposPageProps {
  onSelectRepo: (repo: Repo) => void;
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

export const ReposPage: React.FC<ReposPageProps> = ({ onSelectRepo }) => {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const loadRepos = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const res = await apiClient.get<Repo[]>("/repos");
      setRepos(res.data);
    } catch (err: any) {
      setMessage(`加载仓库列表失败: ${err?.message ?? String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRepos();
  }, []);

  const handleReindex = async (repoId: string) => {
    setLoading(true);
    setMessage(null);
    try {
      await apiClient.post(`/repos/${encodeURIComponent(repoId)}/reindex`);
      await loadRepos();
      setMessage(`已触发重建索引: ${repoId}`);
    } catch (err: any) {
      setMessage(`重建索引失败: ${err?.message ?? String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 style={{ marginBottom: "0.5rem" }}>仓库</h2>
      <p style={{ fontSize: 13, color: "#a3a3a3", marginBottom: "0.75rem" }}>
        以下为已注册的仓库，点击卡片可查看大纲并进入问答页面。
      </p>
      {message && <p style={{ color: "red", marginBottom: "0.5rem" }}>{message}</p>}
      {loading && <p>加载中...</p>}
      {!loading && repos.length === 0 && <p>当前尚无仓库，请先索引一个仓库。</p>}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
          gap: "12px"
        }}
      >
        {repos.map(repo => {
          const owner = parseOwnerFromGitUrl(repo.git_url);
          return (
            <div
              key={repo.id}
              className="panel-card"
              style={{
                cursor: "pointer",
                borderRadius: 14,
                padding: "12px 14px"
              }}
              onClick={() => onSelectRepo(repo)}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 6
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: 14,
                      fontWeight: 500
                    }}
                  >
                    {repo.name || repo.id}
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: "#a3a3a3"
                    }}
                  >
                    拥有者：{owner}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={e => {
                    e.stopPropagation();
                    void handleReindex(repo.id);
                  }}
                  disabled={loading}
                  style={{
                    fontSize: 12,
                    padding: "4px 8px",
                    borderRadius: 999,
                    border: "1px solid #f97316",
                    background: "#1f1307",
                    color: "#fde68a",
                    cursor: "pointer"
                  }}
                >
                  重新索引
                </button>
              </div>
              <div style={{ fontSize: 12, color: "#a3a3a3" }}>
                索引时间：{repo.indexed_at ?? "未索引"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

