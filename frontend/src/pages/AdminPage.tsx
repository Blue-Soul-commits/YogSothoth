import React, { useState } from "react";
import { setAdminToken, getAdminToken } from "../api/client";
import { ReposPage } from "./ReposPage";
import type { Repo } from "../api/types";

export const AdminPage: React.FC = () => {
  const [input, setInput] = useState("");
  const [authed, setAuthed] = useState<boolean>(!!getAdminToken());
  const [error, setError] = useState<string | null>(null);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) {
      setError("请输入管理员密钥");
      return;
    }
    setAdminToken(input.trim());
    setAuthed(true);
    setError(null);
  };

  const handleSelectRepo = (_repo: Repo) => {
    // 管理页面暂时不需要跳转到大纲 / 问答，保留接口以复用 ReposPage。
  };

  return (
    <div className="page">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="brand">gitnar · Admin</div>
        </div>
        <div className="nav-group">
          <div className="sidebar-title">ADMIN</div>
          <div style={{ fontSize: 12, color: "#a3a3a3" }}>
            仅用于索引仓库、管理仓库组等敏感操作，请勿泄露管理员密钥。
          </div>
        </div>
      </aside>

      <div className="main-panel">
        <div className="panel-inner">
          <div className="panel-card" style={{ maxWidth: 640 }}>
            {!authed ? (
              <section>
                <div className="panel-card-title">管理员登录</div>
                <div className="panel-card-subtitle">
                  请输入后端配置的管理员密钥，以执行索引和仓库组管理等操作。
                </div>
                <form onSubmit={handleLogin}>
                  <div style={{ marginBottom: 8 }}>
                    <label
                      style={{
                        fontSize: 12,
                        marginBottom: 4,
                        display: "block"
                      }}
                    >
                      管理员密钥
                    </label>
                    <input
                      type="password"
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      placeholder="输入 GITNAR_ADMIN_TOKEN"
                      style={{
                        width: "100%",
                        padding: "6px 8px",
                        borderRadius: 8,
                        border: "1px solid #3a3a3a",
                        background: "rgba(5,5,5,0.9)",
                        color: "#f5f5f5",
                        fontSize: 13
                      }}
                    />
                  </div>
                  {error && (
                    <p style={{ color: "red", marginBottom: 6, fontSize: 12 }}>
                      {error}
                    </p>
                  )}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "flex-end",
                      gap: 8
                    }}
                  >
                    <button
                      type="submit"
                      style={{
                        fontSize: 13,
                        padding: "4px 12px",
                        borderRadius: 999,
                        border: "1px solid #f97316",
                        background: "#1f1307",
                        color: "#fde68a",
                        cursor: "pointer"
                      }}
                    >
                      登录
                    </button>
                  </div>
                </form>
              </section>
            ) : (
              <section>
                <div className="panel-card-title">仓库管理（管理员）</div>
                <div className="panel-card-subtitle">
                  已为当前会话配置 <code>X-Admin-Token</code>，可以在主界面执行「索引仓库」、
                  「重新索引」和创建仓库组等操作。
                </div>
                <ReposPage onSelectRepo={handleSelectRepo} />
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

