import React, { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { Repo, RepoGroup, QAResponse } from "../api/types";

interface Message {
  role: "user" | "assistant";
  content: string;
  refs?: QAResponse["references"];
}

interface GroupChatPageProps {
  group: RepoGroup;
}

export const GroupChatPage: React.FC<GroupChatPageProps> = ({ group }) => {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 为了展示成员仓库名，需要拉一遍 repos 列表
  const [repos, setRepos] = useState<Repo[]>([]);

  // 多轮对话：sessionId + 是否联动历史
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [linkHistory, setLinkHistory] = useState<boolean>(true);

  // 从 URL 读取 / 生成 sessionId，并写回 URL（?sessionId=...）
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const url = new URL(window.location.href);
      let sid = url.searchParams.get("sessionId");
      if (!sid) {
        if (window.crypto && "randomUUID" in window.crypto) {
          sid = window.crypto.randomUUID();
        } else {
          sid = `${Date.now().toString(36)}-${Math.random()
            .toString(36)
            .slice(2, 10)}`;
        }
        url.searchParams.set("sessionId", sid);
        window.history.replaceState(null, "", url.toString());
      }
      setSessionId(sid);
    } catch {
      const sid = `${Date.now().toString(36)}-${Math.random()
        .toString(36)
        .slice(2, 10)}`;
      setSessionId(sid);
    }
  }, []);

  useEffect(() => {
    const loadRepos = async () => {
      try {
        const res = await apiClient.get<Repo[]>("/repos");
        setRepos(res.data);
      } catch (err: any) {
        // 展示错误但不中断问答功能
        setError(`加载仓库列表失败: ${err?.message ?? String(err)}`);
      }
    };
    void loadRepos();
  }, []);

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setError(null);
    setLoading(true);

    const q = question.trim();
    setQuestion("");
    setMessages(prev => [...prev, { role: "user", content: q }]);

    try {
      const payload: {
        group_id: string;
        question: string;
        top_k_per_repo: number;
        session_id?: string;
      } = {
        group_id: group.id,
        question: q,
        top_k_per_repo: 5
      };
      if (linkHistory && sessionId) {
        payload.session_id = sessionId;
      }
      const res = await apiClient.post<QAResponse>("/qa/repo-group", payload);
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: res.data.answer_text,
          refs: res.data.references
        }
      ]);
    } catch (err: any) {
      setError(`提问失败: ${err?.message ?? String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCopyLink = async () => {
    if (typeof window === "undefined") return;
    try {
      await navigator.clipboard.writeText(window.location.href);
    } catch (err: any) {
      setError(`复制链接失败: ${err?.message ?? String(err)}`);
    }
  };

  const memberRepos = repos.filter(r => group.repo_ids.includes(r.id));

  return (
    <div>
      {/* 顶部区域：标题 + 会话信息 */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 16,
          gap: 20
        }}
      >
        <div>
          <h2 style={{ marginBottom: 6, fontSize: 18 }}>仓库组问答</h2>
          <p style={{ fontSize: 13, color: "#a3a3a3", maxWidth: 520 }}>
            针对多个仓库组合的整体行为、协作方式和迁移方案进行联动分析与设计讨论。
          </p>
        </div>
        <div
          style={{
            fontSize: 11,
            color: "#a3a3a3",
            textAlign: "right",
            minWidth: 200
          }}
        >
          <div style={{ marginBottom: 4 }}>
            会话 ID：
            <code style={{ fontSize: 11 }}>
              {sessionId ? `${sessionId.slice(0, 8)}…` : "生成中…"}
            </code>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                cursor: "pointer"
              }}
            >
              <input
                type="checkbox"
                checked={linkHistory}
                onChange={e => setLinkHistory(e.target.checked)}
                style={{ width: 12, height: 12 }}
              />
              <span>联动对话记录</span>
            </label>
            <button
              type="button"
              onClick={handleCopyLink}
              style={{
                fontSize: 11,
                padding: "3px 9px",
                borderRadius: 999,
                border: "1px solid #444",
                background: "transparent",
                color: "#e5e5e5",
                cursor: "pointer"
              }}
            >
              复制链接
            </button>
          </div>
        </div>
      </header>

      {/* 仓库组信息卡片 */}
      <section
        style={{
          borderRadius: 12,
          border: "1px solid #262626",
          background: "rgba(10,10,10,0.9)",
          padding: "10px 14px",
          marginBottom: 12,
          fontSize: 12
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
            marginBottom: 4
          }}
        >
          <div>
            <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 2 }}>
              {group.name}
            </div>
            <div style={{ color: "#a3a3a3" }}>ID：{group.id}</div>
          </div>
          <div style={{ textAlign: "right", color: "#a3a3a3" }}>
            成员仓库：{group.repo_ids.length}
          </div>
        </div>
        {group.description && (
          <div style={{ color: "#a3a3a3", marginBottom: 4 }}>
            {group.description}
          </div>
        )}
        {memberRepos.length > 0 && (
          <div
            style={{
              marginTop: 4,
              color: "#a3a3a3",
              display: "flex",
              flexWrap: "wrap",
              gap: 6
            }}
          >
            {memberRepos.map(r => (
              <span
                key={r.id}
                style={{
                  padding: "2px 8px",
                  borderRadius: 999,
                  border: "1px solid #333",
                  background: "#111111",
                  fontSize: 11
                }}
              >
                {r.name || r.id}
              </span>
            ))}
          </div>
        )}
      </section>

      {error && (
        <p style={{ color: "red", marginBottom: 8, fontSize: 12 }}>{error}</p>
      )}

      {/* 对话内容区域 */}
      <section
        style={{
          borderRadius: 14,
          border: "1px solid #262626",
          background: "rgba(7,7,7,0.9)",
          padding: "12px 14px",
          marginBottom: 10,
          maxHeight: 420,
          minHeight: 220,
          display: "flex",
          flexDirection: "column"
        }}
      >
        <div
          style={{
            marginBottom: 8,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center"
          }}
        >
          <span style={{ fontSize: 13, fontWeight: 500 }}>对话</span>
          <span style={{ fontSize: 11, color: "#737373" }}>
            历史上下文由后端 conversations / conversation_messages 管理
          </span>
        </div>

        {messages.length === 0 && (
          <p style={{ fontSize: 13, color: "#a3a3a3" }}>
            还没有消息，先问一个问题试试吧，例如「这个仓库组中各仓库之间的调用关系是怎样的？」。
          </p>
        )}

        <div
          className="chat-scroll"
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "0.6rem",
            overflowY: "auto",
            paddingRight: 4
          }}
        >
          {messages.map((m, idx) => {
            const isUser = m.role === "user";
            return (
              <div
                key={idx}
                style={{
                  display: "flex",
                  justifyContent: isUser ? "flex-end" : "flex-start"
                }}
              >
                <div
                  style={{
                    maxWidth: "82%",
                    borderRadius: 12,
                    padding: "0.55rem 0.85rem",
                    background: isUser ? "#111111" : "#181818",
                    border: "1px solid #262626",
                    boxShadow: "0 4px 10px rgba(0,0,0,0.35)"
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      marginBottom: 3,
                      color: "#d4d4d4"
                    }}
                  >
                    {isUser ? "你" : "助手"}
                  </div>
                  <pre
                    style={{
                      whiteSpace: "pre-wrap",
                      margin: 0,
                      fontFamily: "inherit",
                      fontSize: 13
                    }}
                  >
                    {m.content}
                  </pre>
                  {m.refs && m.refs.length > 0 && (
                    <details
                      className="ref-card"
                      style={{
                        marginTop: "0.5rem",
                        fontSize: 12
                      }}
                    >
                      <summary>
                        引用的代码位置（共 {m.refs.length} 处）
                      </summary>
                      <ul>
                        {m.refs.map((ref, i) => (
                          <li key={i}>
                            <span className="ref-badge">
                              仓库 {ref.repo_id}
                            </span>
                            <code>{ref.file_path}</code> · 行{" "}
                            {ref.start_line}-{ref.end_line}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 提问输入区 */}
      <form onSubmit={handleAsk}>
        <textarea
          rows={3}
          style={{
            width: "100%",
            borderRadius: 12,
            border: "1px solid #3a3a3a",
            background: "rgba(5,5,5,0.9)",
            color: "#f5f5f5",
            padding: 10,
            fontSize: 13,
            resize: "vertical"
          }}
          placeholder="输入你的问题，例如：这个仓库组整体的初始化链路、边界划分或迁移策略？"
          value={question}
          onChange={e => setQuestion(e.target.value)}
        />
        <div
          style={{
            marginTop: 8,
            display: "flex",
            justifyContent: "flex-end"
          }}
        >
          <button
            type="submit"
            disabled={loading}
            style={{
              fontSize: 13,
              borderRadius: 999,
              border: "1px solid #f97316",
              background: "#1f1307",
              color: "#fde68a",
              padding: "5px 14px",
              cursor: "pointer",
              opacity: loading ? 0.75 : 1
            }}
          >
            {loading ? "提问中…" : "提问"}
          </button>
        </div>
      </form>
    </div>
  );
};

