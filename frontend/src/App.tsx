import React, { useState } from "react";
import { RepoChatPage } from "./pages/RepoChatPage";
import { GroupChatPage } from "./pages/GroupChatPage";
import { ReposPage } from "./pages/ReposPage";
import { GroupsPage } from "./pages/GroupsPage";
import { RepoOutlinePage } from "./pages/RepoOutlinePage";
import { apiClient } from "./api/client";
import { useRouter, Link } from "./router";
import type { Repo, RepoGroup } from "./api/types";

type Section = "repos" | "groups";
type View =
  | { kind: "repos" }
  | { kind: "groups" }
  | { kind: "repoOutline"; repo: Repo }
  | { kind: "repoChat"; repo: Repo }
  | { kind: "groupChat"; group: RepoGroup };

interface IndexRepoModalProps {
  onClose: () => void;
}

interface CreateGroupModalProps {
  onClose: () => void;
}

export const App: React.FC = () => {
  const { path, navigate } = useRouter();
  const [showIndexModal, setShowIndexModal] = useState(false);
  const [showGroupModal, setShowGroupModal] = useState(false);

  return (
    <div className="page">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="brand">gitnar</div>
        </div>

        <div className="nav-group">
          <div className="sidebar-title">NAVIGATION</div>
          <Link
            to="/repos"
            className={
              "nav-button nav-button-primary" +
              (path === "/" || path.startsWith("/repos")
                ? " nav-button-active"
                : "")
            }
          >
            <span>仓库</span>
          </Link>
          <Link
            to="/groups"
            className={
              "nav-button nav-button-secondary" +
              (path.startsWith("/groups") ? " nav-button-active" : "")
            }
            style={{ marginTop: 8 }}
          >
            <span>仓库组</span>
          </Link>
        </div>

        <hr className="nav-separator" />

        <div className="nav-group">
          <div className="sidebar-title">ACTIONS</div>
          <button
            className="nav-button nav-button-secondary"
            onClick={() => setShowIndexModal(true)}
          >
            <span>索引仓库</span>
          </button>
          <button
            className="nav-button nav-button-secondary"
            onClick={() => setShowGroupModal(true)}
            style={{ marginTop: 8 }}
          >
            <span>创建仓库组</span>
          </button>
        </div>

        <hr className="nav-separator" />

        <div className="nav-group">
          <div className="sidebar-title">PROJECT</div>
          <div style={{ fontSize: 12, color: "#a3a3a3" }}>
            多仓库代码知识库 + 问答系统，面向 MCP 与 Web 前端。
          </div>
        </div>
      </aside>

      <div className="main-panel">
        <div className="panel-inner">
          <div className="panel-card">
            {(path === "/" || path === "/repos") && (
              <ReposPage
                onSelectRepo={repo =>
                  navigate(`/repos/${encodeURIComponent(repo.id)}`)
                }
              />
            )}
            {path === "/groups" && (
              <GroupsPage
                onSelectGroup={group =>
                  navigate(`/groups/${encodeURIComponent(group.id)}/chat`)
                }
              />
            )}
            {/* repo outline: /repos/:id */}
            {/^\/repos\/[^/]+$/.test(path) && (
              <RepoOutlinePage
                // 这里简单地用路径解析 repoId，实际组件内部再根据 id 拉取详情
                repo={{
                  id: decodeURIComponent(path.split("/")[2] || ""),
                  name: "",
                  git_url: "",
                  default_branch: "main",
                  local_path: null,
                  indexed_at: null,
                  summary: null
                }}
                onBack={() => navigate("/repos")}
                onEnterChat={() => navigate(`${path}/chat`)}
              />
            )}
            {/* repo chat: /repos/:id/chat */}
            {/^\/repos\/[^/]+\/chat$/.test(path) && (
              <RepoChatPage
                repo={{
                  id: decodeURIComponent(path.split("/")[2] || ""),
                  name: "",
                  git_url: "",
                  default_branch: "main",
                  local_path: null,
                  indexed_at: null,
                  summary: null
                }}
              />
            )}
            {/* group chat: /groups/:id/chat */}
            {/^\/groups\/[^/]+\/chat$/.test(path) && (
              <GroupChatPage
                group={{
                  id: decodeURIComponent(path.split("/")[2] || ""),
                  name: "",
                  description: "",
                  repo_ids: [],
                  indexed_at: null
                }}
              />
            )}
          </div>
        </div>
      </div>

      {showIndexModal && <IndexRepoModal onClose={() => setShowIndexModal(false)} />}
      {showGroupModal && <CreateGroupModal onClose={() => setShowGroupModal(false)} />}
    </div>
  );
};

// 弹窗组件：索引仓库
const IndexRepoModal: React.FC<IndexRepoModalProps> = ({ onClose }) => {
  const [gitUrl, setGitUrl] = useState("");
  const [repoId, setRepoId] = useState("");
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gitUrl.trim()) {
      setError("请填写仓库 URL");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.post<Repo>("/repos", {
        git_url: gitUrl.trim(),
        id: repoId.trim() || undefined,
        summary: summary.trim() || undefined
      });
      const createdId = res.data.id;
      await apiClient.post(`/repos/${encodeURIComponent(createdId)}/reindex`);
      onClose();
    } catch (err: any) {
      setError(`索引仓库失败: ${err?.message ?? String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="panel-card" style={{ maxWidth: 520 }}>
        <div className="panel-card-title">索引仓库</div>
        <div className="panel-card-subtitle">
          输入 Git 仓库地址，系统会自动 clone / 更新，并为其生成代码索引和大纲。
        </div>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12 }}>仓库 URL</label>
            <input
              type="text"
              value={gitUrl}
              onChange={e => setGitUrl(e.target.value)}
              placeholder="例如：https://github.com/owner/repo"
              style={{
                width: "100%",
                marginTop: 4,
                padding: "6px 8px",
                borderRadius: 8,
                border: "1px solid #3a3a3a",
                background: "rgba(5,5,5,0.9)",
                color: "#f5f5f5",
                fontSize: 13
              }}
            />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12 }}>仓库 ID（可选）</label>
            <input
              type="text"
              value={repoId}
              onChange={e => setRepoId(e.target.value)}
              placeholder="默认会从 URL 自动推导"
              style={{
                width: "100%",
                marginTop: 4,
                padding: "6px 8px",
                borderRadius: 8,
                border: "1px solid #3a3a3a",
                background: "rgba(5,5,5,0.9)",
                color: "#f5f5f5",
                fontSize: 13
              }}
            />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12 }}>简要描述（可选）</label>
            <input
              type="text"
              value={summary}
              onChange={e => setSummary(e.target.value)}
              placeholder="这个仓库是做什么的？"
              style={{
                width: "100%",
                marginTop: 4,
                padding: "6px 8px",
                borderRadius: 8,
                border: "1px solid #3a3a3a",
                background: "rgba(5,5,5,0.9)",
                color: "#f5f5f5",
                fontSize: 13
              }}
            />
          </div>
          {error && <p style={{ color: "red", marginBottom: 4 }}>{error}</p>}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                fontSize: 12,
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid #444",
                background: "transparent",
                color: "#e5e5e5",
                cursor: "pointer"
              }}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{
                fontSize: 12,
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid #f97316",
                background: "#1f1307",
                color: "#fde68a",
                cursor: "pointer",
                opacity: loading ? 0.75 : 1
              }}
            >
              {loading ? "索引中…" : "索引"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// 弹窗组件：创建仓库组
const CreateGroupModal: React.FC<CreateGroupModalProps> = ({ onClose }) => {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedRepoIds, setSelectedRepoIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  React.useEffect(() => {
    const load = async () => {
      try {
        const res = await apiClient.get<Repo[]>("/repos");
        setRepos(res.data);
      } catch (err: any) {
        setError(`加载仓库失败: ${err?.message ?? String(err)}`);
      }
    };
    void load();
  }, []);

  const toggleRepo = (id: string) => {
    setSelectedRepoIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("请填写仓库组名称");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await apiClient.post("/repo-groups", {
        name: name.trim(),
        description: description.trim() || undefined,
        repo_ids: selectedRepoIds
      });
      onClose();
    } catch (err: any) {
      setError(`创建仓库组失败: ${err?.message ?? String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="panel-card" style={{ maxWidth: 520 }}>
        <div className="panel-card-title">创建仓库组</div>
        <div className="panel-card-subtitle">
          将多个仓库组成一个仓库组，以便进行跨仓联动问答和架构分析。
        </div>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12 }}>仓库组名称</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              style={{
                width: "100%",
                marginTop: 4,
                padding: "6px 8px",
                borderRadius: 8,
                border: "1px solid #3a3a3a",
                background: "rgba(5,5,5,0.9)",
                color: "#f5f5f5",
                fontSize: 13
              }}
            />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12 }}>描述（可选）</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              style={{
                width: "100%",
                marginTop: 4,
                padding: "6px 8px",
                borderRadius: 8,
                border: "1px solid #3a3a3a",
                background: "rgba(5,5,5,0.9)",
                color: "#f5f5f5",
                fontSize: 13
              }}
            />
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12, display: "block", marginBottom: 4 }}>
              选择要加入的仓库（可多选）
            </label>
            <div className="select-multi">
              {repos.map(repo => {
                const selected = selectedRepoIds.includes(repo.id);
                return (
                  <div
                    key={repo.id}
                    onClick={() => toggleRepo(repo.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "4px 6px",
                      marginBottom: 2,
                      borderRadius: 6,
                      background: selected ? "#1f1307" : "transparent",
                      border: selected
                        ? "1px solid #f97316"
                        : "1px solid transparent",
                      cursor: "pointer",
                      fontSize: 12
                    }}
                  >
                    <span>{repo.id}</span>
                    {selected && (
                      <span
                        style={{
                          fontSize: 11,
                          color: "#fde68a"
                        }}
                      >
                        已选择
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          {error && <p style={{ color: "red", marginBottom: 4 }}>{error}</p>}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                fontSize: 12,
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid #444",
                background: "transparent",
                color: "#e5e5e5",
                cursor: "pointer"
              }}
            >
              取消
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{
                fontSize: 12,
                padding: "4px 10px",
                borderRadius: 999,
                border: "1px solid #f97316",
                background: "#1f1307",
                color: "#fde68a",
                cursor: "pointer",
                opacity: loading ? 0.75 : 1
              }}
            >
              {loading ? "创建中…" : "创建"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
